#!/usr/bin/env python3
"""Exercise Mesa's actual image-binding and attachment-snapshot code with mock BOs."""
from pathlib import Path
import argparse
import subprocess
import tempfile


def function(source, name, prefix):
    start = source.index('\n' + name + '(') + 1
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return prefix + '\n' + source[start:end] + '\n'

p = argparse.ArgumentParser()
p.add_argument('mesa', type=Path)
root = p.parse_args().mesa
image = (root/'src/asahi/vulkan/hk_image.c').read_text()
commands = (root/'src/asahi/vulkan/hk_cmd_buffer.c').read_text()
code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#define MIN2(a,b) ((a)<(b)?(a):(b))
#define UNREACHABLE(x) abort()
#define VK_IMAGE_ASPECT_COLOR_BIT 1
#define VK_IMAGE_ASPECT_DEPTH_BIT 2
#define VK_IMAGE_ASPECT_STENCIL_BIT 4
#define HK_MAX_RTS 4
#define HK_DRM_MAX_FRAGMENT_ATTACHMENTS (2*HK_MAX_RTS+4)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define static_assert _Static_assert
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
typedef uint32_t VkImageAspectFlags; typedef uint32_t VkImageCreateFlags;
typedef struct VkAllocationCallbacks {int unused;} VkAllocationCallbacks;
struct agx_va {uint64_t addr;};
struct agx_bo {struct agx_va *va; uint64_t size; int refs; char data[32768];};
struct agx_device {int unused;}; struct hk_device {struct agx_device dev;};
struct hk_image_plane {struct {uint64_t size_B;} layout; uint64_t offset_B,addr; struct agx_va *va; struct agx_bo *bound_bo, *sparse_map; void *map; uint64_t rem;};
struct hk_image {struct {int unused;} vk; uint8_t plane_count; struct hk_image_plane planes[3];};
struct hk_image_view {struct {void *image;} vk; struct {uint8_t image_plane;} planes[1];};
struct att {struct hk_image_view *iview, *resolve_iview;};
struct hk_rendering_state {bool g17p_direct_color_resolve; unsigned color_att_count; struct att color_att[HK_MAX_RTS],depth_att,stencil_att;};
struct hk_cs {struct {bool complete; unsigned count;} fragment_attachments;};
struct hk_cmd_buffer {struct {bool error;} vk; struct hk_device *dev; struct agx_bo *retained[16]; unsigned count; bool fail;};
struct mem_vk {uint64_t size;}; struct hk_device_memory {struct mem_vk vk; struct agx_bo *bo;};
static void agx_bo_reference(struct agx_bo *b){assert(b && b->refs>0);b->refs++;}
static void agx_bo_unreference(struct agx_device *d, struct agx_bo *b){(void)d;if(b){assert(b->refs>0);b->refs--;}}
static void agx_va_free(struct agx_device *d, struct agx_va *v, bool unbind){(void)d;(void)v;(void)unbind;}
static void *agx_bo_map(struct agx_bo *b){return b->data;}
static bool hk_image_plane_binding(uint64_t base,uint64_t size,uint64_t memoff,uint64_t off,uint64_t length,uint64_t *addr,uint64_t *booff){if(memoff>size || off>size-memoff || length>size-memoff-off)return false;*booff=memoff+off;*addr=base+*booff;return true;}
static struct hk_device *hk_cmd_buffer_device(struct hk_cmd_buffer *c){return c->dev;}
static bool agx_native_graphics(const struct agx_device *d){(void)d;return true;}
static uint8_t hk_image_aspects_to_plane(struct hk_image *i, VkImageAspectFlags a){(void)i;return a==VK_IMAGE_ASPECT_STENCIL_BIT ? 1:0;}
static void hk_cmd_buffer_retain_bo(struct hk_cmd_buffer *c, struct agx_bo *b){if(!b)return;for(unsigned i=0;i<c->count;i++)if(c->retained[i]==b)return;if(c->fail){c->vk.error=true;return;} agx_bo_reference(b);c->retained[c->count++]=b;}
static bool vk_command_buffer_has_error(void *p){return *(bool*)p;}
static void hk_drm_attachment_set_add(void *p,uint64_t addr,uint64_t size){(void)addr;(void)size;((struct hk_cs*)p)->fragment_attachments.count++;}
'''
code += function(image, 'hk_image_plane_bind', 'static bool')
code += function(image, 'hk_image_plane_finish', 'static void')
code += function(commands, 'hk_cs_capture_fragment_attachments', 'static void')
code += r'''
int main(void) {
 struct hk_device dev={0}; struct agx_va va={.addr=0x100000}; struct agx_bo bo={.va=&va,.size=16384,.refs=1};
 struct hk_device_memory mem={.vk={.size=16384},.bo=&bo}; struct hk_image image={.plane_count=1}; image.planes[0].layout.size_B=4096;
 struct hk_image_view view={.vk={.image=&image.vk}}; struct hk_rendering_state render={.color_att_count=2}; render.color_att[0].iview=&view; render.color_att[1].iview=&view;
 struct hk_cmd_buffer cmd={.dev=&dev}; struct hk_cs cs={0};
 assert(!hk_image_plane_bind(&dev,&image.planes[0],&mem,16000)); assert(bo.refs==1);
 assert(hk_image_plane_bind(&dev,&image.planes[0],&mem,0)); assert(bo.refs==2);
 hk_cs_capture_fragment_attachments(&cmd,&render,&cs); assert(!cmd.vk.error && cmd.count==1 && bo.refs==3 && cs.fragment_attachments.count==2);
 agx_bo_unreference(&dev.dev,&bo); hk_image_plane_finish(&dev,&image.planes[0],0,NULL); assert(bo.refs==1);
 agx_bo_unreference(&dev.dev,cmd.retained[0]); assert(bo.refs==0);
 struct agx_bo b2={.va=&va,.size=16384,.refs=1}; mem.bo=&b2; image.planes[0].bound_bo=NULL; assert(hk_image_plane_bind(&dev,&image.planes[0],&mem,0));
 struct hk_cmd_buffer failed={.dev=&dev,.fail=true}; struct hk_cs bad={0}; hk_cs_capture_fragment_attachments(&failed,&render,&bad); assert(failed.vk.error && bad.fragment_attachments.count==0 && b2.refs==2);
 hk_image_plane_finish(&dev,&image.planes[0],0,NULL); agx_bo_unreference(&dev.dev,&b2); assert(b2.refs==0);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    d = Path(directory)
    (d/'test.c').write_text(code)
    subprocess.run(['cc','-std=gnu11','-Wall','-Werror','-Wno-unused-parameter',str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
print('PASS: image binding, shared BO deduplication, release ordering, invalid bounds and retain failure')
