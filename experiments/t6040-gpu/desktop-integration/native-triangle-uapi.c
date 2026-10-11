/* SPDX-License-Identifier: MIT
 * One fixed, preallocated render submission. No Mesa compute/readback path.
 * Build against the UAPI in the same kernel bundle as the loaded driver.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/sync_file.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <xf86drm.h>
#include "asahi_drm.h"

static int submitted;
static void fail(const char *what)
{
   fprintf(stderr, "FAIL: %s: %s\n", what, strerror(errno));
   /* Once submitted, preserve the file/VM/GEM owners for the combined runner
    * to collect the kernel's completion/recovery transcript before stopping us.
    * There is no work replay, unbind, queue destruction, or module operation. */
   if (submitted) { fflush(NULL); for (;;) pause(); }
   exit(1);
}
static void call(int fd, unsigned long op, void *arg, const char *what)
{ if (ioctl(fd, op, arg)) fail(what); }
static void output(int dir, const char *name, const void *bytes, size_t size)
{
   int fd = openat(dir, name, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0600);
   if (fd < 0) fail(name);
   const char *p = bytes;
   while (size) { ssize_t n=write(fd,p,size); if(n<0&&errno==EINTR)continue;
      if(n<=0)fail(name);
      p+=n;size-=n; }
   if(fsync(fd)||close(fd))fail(name);
}
static void *object(int fd, int inputs, const char *name, uint64_t size,
                    uint64_t address, uint32_t vm, uint32_t access)
{
   /* WC CPU mappings avoid retaining a writeback cache alias of GPU-written
    * pages. GET_PARAMS and the bundled driver bind the VM, not a raw sampler. */
   struct drm_asahi_gem_create create={.size=size};
   call(fd,DRM_IOCTL_ASAHI_GEM_CREATE,&create,"GEM_CREATE");
   struct drm_asahi_gem_mmap_offset offset={.handle=create.handle};
   call(fd,DRM_IOCTL_ASAHI_GEM_MMAP_OFFSET,&offset,"GEM_MMAP_OFFSET");
   void *map=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,offset.offset);
   if(map==MAP_FAILED)fail("GEM mmap");
   int input=openat(inputs,name,O_RDONLY|O_NOFOLLOW);
   struct stat st;
   if(input<0||fstat(input,&st)||!S_ISREG(st.st_mode)||(uint64_t)st.st_size!=size)
      fail("input size");
   uint64_t done=0;
   while(done<size){ssize_t n=read(input,(char*)map+done,size-done);
      if(n<0&&errno==EINTR)continue;
      if(n<=0)fail("input read");
      done+=n;}
   close(input);
   __sync_synchronize();
   struct drm_asahi_gem_bind_op op={.handle=create.handle,.range=size,
      .addr=address,.flags=access};
   struct drm_asahi_vm_bind bind={.vm_id=vm,.num_binds=1,
      .stride=sizeof(op),.userptr=(uintptr_t)&op};
   call(fd,DRM_IOCTL_ASAHI_VM_BIND,&bind,"VM_BIND");
   return map;
}
int main(int argc,char **argv)
{
   if(argc!=4){fprintf(stderr,"usage: %s RENDER_NODE CHECKED_INPUT_DIR EMPTY_OUTPUT_DIR\n",argv[0]);return 2;}
   int inputs=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
   int out=open(argv[3],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
   int fd=open(argv[1],O_RDWR|O_CLOEXEC|O_NOFOLLOW);
   struct stat st;
   if(inputs<0||out<0||fd<0||fstat(fd,&st)||!S_ISCHR(st.st_mode)
      ||drmGetNodeTypeFromFd(fd)!=DRM_NODE_RENDER)fail("explicit render node/directories");
   drmVersionPtr v=drmGetVersion(fd);
   if(!v||!v->name||strcmp(v->name,"asahi"))fail("Asahi driver identity");
   drmFreeVersion(v);
   struct drm_asahi_params_global p={0};
   struct drm_asahi_get_params params={.pointer=(uintptr_t)&p,.size=sizeof(p)};
   call(fd,DRM_IOCTL_ASAHI_GET_PARAMS,&params,"GET_PARAMS");
   if(params.size<sizeof(p)||p.chip_id!=0x6040||p.gpu_generation!=16||p.gpu_variant!='S'
      ||p.gpu_revision!=0x11||p.num_dies!=1||p.num_clusters_total!=2
      ||p.num_cores_per_cluster!=10||p.core_masks[0]!=0x3db||p.core_masks[1]!=0x3db)
      fail("captured J614s topology");
   /* The shader/pipeline bundle contains these VAs. Kernel-private allocator
    * range begins beyond the draw-state page and cannot overlap these binds. */
   struct drm_asahi_vm_create vm={.kernel_start=0x1001000000ULL,.kernel_end=0x1100000000ULL};
   call(fd,DRM_IOCTL_ASAHI_VM_CREATE,&vm,"VM_CREATE");
   object(fd,inputs,"usc.bin",0x50000,1ULL<<40,vm.vm_id,DRM_ASAHI_BIND_READ);
   object(fd,inputs,"state.bin",0x4000,0x1000000000ULL,vm.vm_id,DRM_ASAHI_BIND_READ);
   void *target=object(fd,inputs,"target.bin",0x4000,0x2000010000ULL,vm.vm_id,
      DRM_ASAHI_BIND_READ|DRM_ASAHI_BIND_WRITE);
   struct drm_asahi_queue_create queue={.vm_id=vm.vm_id,.priority=DRM_ASAHI_PRIORITY_MEDIUM,
      .usc_exec_base=1ULL<<40};
   call(fd,DRM_IOCTL_ASAHI_QUEUE_CREATE,&queue,"QUEUE_CREATE");
   struct drm_syncobj_create sync={0};
   call(fd,DRM_IOCTL_SYNCOBJ_CREATE,&sync,"SYNCOBJ_CREATE");
   struct {struct drm_asahi_cmd_header attachments_header;
      struct drm_asahi_attachment target_attachment;
      struct drm_asahi_cmd_header render_header;
      struct drm_asahi_cmd_render render;} commands={0};
   commands.attachments_header=(struct drm_asahi_cmd_header){DRM_ASAHI_SET_FRAGMENT_ATTACHMENTS,
      sizeof(commands.target_attachment),DRM_ASAHI_BARRIER_NONE,DRM_ASAHI_BARRIER_NONE};
   commands.target_attachment=(struct drm_asahi_attachment){.pointer=0x2000010000ULL,.size=0x4000};
   commands.render_header=(struct drm_asahi_cmd_header){DRM_ASAHI_CMD_RENDER,
      sizeof(commands.render),DRM_ASAHI_BARRIER_NONE,DRM_ASAHI_BARRIER_NONE};
   commands.render=(struct drm_asahi_cmd_render){
      .flags=DRM_ASAHI_RENDER_PROCESS_EMPTY_TILES,.vdm_ctrl_stream_base=0x1000000000ULL,
      .isp_scissor_base=0x1000002000ULL,.isp_dbias_base=0x1000002040ULL,
      .ppp_ctrl=0x202,.width_px=64,.height_px=64,.layers=1,
      .utile_width_px=32,.utile_height_px=32,.samples=1,.sample_size_B=4,
      /* Reciprocal merge threshold used by this kernel's G16 serializer. */
      .isp_merge_upper_x=0x3cddb3d9,.isp_merge_upper_y=0x3cddb3d9,
      .bg={.usc=0x30c00},.eot={.usc=0x30800},
      .partial_bg={.usc=0x30c00},.partial_eot={.usc=0x30800}};
   struct drm_asahi_sync signal={.sync_type=DRM_ASAHI_SYNC_SYNCOBJ,.handle=sync.handle};
   struct drm_asahi_submit submit={.syncs=(uintptr_t)&signal,.cmdbuf=(uintptr_t)&commands,
      .queue_id=queue.queue_id,.out_sync_count=1,.cmdbuf_size=sizeof(commands)};
   output(out,"submit-intent.bin",&commands,sizeof(commands));
   submitted=1;
   call(fd,DRM_IOCTL_ASAHI_SUBMIT,&submit,"SUBMIT");
   struct drm_syncobj_handle export={.handle=sync.handle,
      .flags=DRM_SYNCOBJ_HANDLE_TO_FD_FLAGS_EXPORT_SYNC_FILE};
   call(fd,DRM_IOCTL_SYNCOBJ_HANDLE_TO_FD,&export,"export completion fence");
   struct pollfd wait={.fd=export.fd,.events=POLLIN};
   int ready;do{ready=poll(&wait,1,60000);}while(ready<0&&errno==EINTR);
   struct sync_file_info info={0};
   call(export.fd,SYNC_IOC_FILE_INFO,&info,"completion fence status");
   char report[256];int n=snprintf(report,sizeof(report),
      "{\"poll_result\":%d,\"poll_events\":%d,\"fence_status\":%d,\"compute_commands\":0,\"submissions\":1}\n",
      ready,wait.revents,info.status);
   output(out,"completion.json",report,n);
   if(ready<=0||info.status!=1){errno=EIO;fail("render failed or incomplete; owners retained");}
   __sync_synchronize();
   output(out,"triangle.rgba",target,0x4000);
   puts("Render fence succeeded; linear target captured. Pixel validation is separate from fence success.");
   return 0;
}
