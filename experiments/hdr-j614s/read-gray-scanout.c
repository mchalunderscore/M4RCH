/* Read only eight small regions from the active linear scanout framebuffer. */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <linux/dma-buf.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>
int main(void) {
 int fd=open("/dev/dri/card1",O_RDWR|O_CLOEXEC), prime=-1; if(fd<0){perror("open drm");return 1;}
 drmModeRes *r=drmModeGetResources(fd);if(!r||r->count_crtcs!=1){fprintf(stderr,"unexpected CRTCs\n");return 1;}
 drmModeCrtc *c=drmModeGetCrtc(fd,r->crtcs[0]);if(!c||!c->buffer_id){fprintf(stderr,"no active framebuffer\n");return 1;}
 drmModeFB2 *b=drmModeGetFB2(fd,c->buffer_id);if(!b||!b->handles[0]||b->modifier||b->pixel_format!=DRM_FORMAT_ARGB2101010||b->width!=3024||b->height!=1964){fprintf(stderr,"unexpected framebuffer\n");return 1;}
 if(drmPrimeHandleToFD(fd,b->handles[0],DRM_CLOEXEC,&prime)){perror("prime");return 1;}
 size_t len=(size_t)b->pitches[0]*b->height;uint8_t *m=mmap(NULL,len,PROT_READ,MAP_SHARED,prime,0);if(m==MAP_FAILED){perror("mmap");return 1;}
 struct dma_buf_sync sync={.flags=DMA_BUF_SYNC_READ|DMA_BUF_SYNC_START};if(ioctl(prime,DMA_BUF_IOCTL_SYNC,&sync)){perror("dma start");return 1;}
 printf("framebuffer %u %ux%u AR30; mean RGB10 of 32x32 central samples:\n",b->fb_id,b->width,b->height);
 for(int i=0;i<8;i++){uint64_t rgb[3]={0};unsigned x=(2*i+1)*b->width/16,y=b->height/2;
  for(unsigned j=y-16;j<y+16;j++)for(unsigned k=x-16;k<x+16;k++){uint32_t v=*(uint32_t *)(m+b->offsets[0]+j*b->pitches[0]+4*k);rgb[0]+=(v>>20)&1023;rgb[1]+=(v>>10)&1023;rgb[2]+=v&1023;}
  printf("%d %.2f %.2f %.2f\n",i,rgb[0]/1024.0,rgb[1]/1024.0,rgb[2]/1024.0);
 }
 sync.flags=DMA_BUF_SYNC_READ|DMA_BUF_SYNC_END;if(ioctl(prime,DMA_BUF_IOCTL_SYNC,&sync)){perror("dma end");return 1;}munmap(m,len);close(prime);drmModeFreeFB2(b);drmModeFreeCrtc(c);drmModeFreeResources(r);close(fd);return 0;
}
