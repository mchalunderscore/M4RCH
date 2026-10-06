#!/usr/bin/env python3
"""Test extracted kernel row/wrapper code with RAM shims, not MMIO hardware."""
from pathlib import Path
import argparse,subprocess


def function(text,name):
    end=text.index('{',text.index(name+'('));start=text.rfind('\n',0,text.rfind('\n',0,end))+1
    # Signatures can span several lines; locate preceding static declaration.
    start=text.rfind('static ',0,end)
    depth=1;pos=end+1
    while depth:
        depth+=(text[pos]=='{')-(text[pos]=='}');pos+=1
    return text[start:pos]+'\n'


HEADER=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64; typedef uint32_t __le32;
#define __iomem
#define __always_inline inline __attribute__((always_inline))
#define CONFIG_64BIT 1
#define IS_ENABLED(x) (x)
#define GFP_KERNEL 0
#define ARCH_KMALLOC_MINALIGN 64
#define round_up(x,a) (((x)+(a)-1)&~((a)-1))
#define cpu_to_le32(x) (x)
#define le32_to_cpup(p) (*(p))
struct drm_rect { int x1,y1,x2,y2; };
struct drm_format_info { unsigned cpp[1]; };
struct drm_framebuffer { unsigned pitches[1]; const struct drm_format_info *format; };
struct drm_format_conv_state { unsigned char data[512]; };
static int drm_rect_width(const struct drm_rect *r) { return r->x2-r->x1; }
static int drm_rect_height(const struct drm_rect *r) { return r->y2-r->y1; }
static void *drm_format_conv_state_reserve(struct drm_format_conv_state *s, size_t size, int flags) { (void)flags;return size<=sizeof(s->data)?s->data:NULL; }
static void memcpy_toio(void *d,const void *s,size_t n) { memcpy(d,s,n); }
static u64 get_unaligned_le64(const void *s) { u64 p; memcpy(&p,s,8);return p; }
static void put_unaligned_le64(u64 p,void *d) { memcpy(d,&p,8); }
'''
TEST=r'''
static u32 expected(u32 p) { u32 r=(p>>16)&255,g=(p>>8)&255,b=p&255;return ((r<<2)|(r>>6))<<20|((g<<2)|(g>>6))<<10|(b<<2)|(b>>6); }
int main(void) {
 unsigned char src[4096] __attribute__((aligned(64))),dst[4096] __attribute__((aligned(64))),want[4096];
 struct drm_format_info format={{4}};struct drm_framebuffer fb={{92},&format}; unsigned count=0;
 for(unsigned i=0;i<sizeof(src);i++)src[i]=(i*71+37)&255;
 for(unsigned io=0;io<2;io++)for(unsigned cached=0;cached<2;cached++)for(unsigned pitched=0;pitched<2;pitched++)
 for(unsigned x=0;x<6;x++)for(unsigned y=0;y<4;y++)for(unsigned w=0;w<14;w++)for(unsigned h=0;h<6;h++) {
  struct drm_rect clip={x,y,x+w,y+h};struct drm_format_conv_state state;
  unsigned pitch=pitched?w*4+20:0,effective=pitch?pitch:w*4;
  memset(dst,0xa5,sizeof(dst));memcpy(want,dst,sizeof(dst));
  for(unsigned row=0;row<h;row++)for(unsigned col=0;col<w;col++) {u32 pixel;memcpy(&pixel,src+(row+y)*92+(col+x)*4,4);pixel=expected(pixel);memcpy(want+4+row*effective+col*4,&pixel,4);}
  int ret=io?__drm_fb_xfrm_toio(dst+4,pitch,4,src,&fb,&clip,cached,&state,drm_fb_xrgb8888_to_xrgb2101010_line):__drm_fb_xfrm(dst+4,pitch,4,src,&fb,&clip,cached,&state,drm_fb_xrgb8888_to_xrgb2101010_line);
  if(ret||memcmp(dst,want,sizeof(dst))) {fprintf(stderr,"FAIL io=%u cached=%u pitch=%u x=%u y=%u w=%u h=%u\n",io,cached,pitch,x,y,w,h);return 1;}count++;
 }
 printf("PASS %u extracted-wrapper cases: RAM/io-copy shim, cached/uncached, padded/default pitches, clipping, zero/odd widths and sentinels\n",count);return 0;
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('header',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    source=a.source.read_text();header=a.header.read_text()
    text=HEADER+function(source,'clip_offset')+function(source,'__drm_fb_xfrm')+function(source,'__drm_fb_xfrm_toio')+function(source,'drm_fb_xfrm_line_32to32')+function(header,'drm_pixel_xrgb8888_to_xrgb2101010')+function(source,'drm_fb_xrgb8888_to_xrgb2101010_line')+TEST
    c=a.out/'wrapper-test.c';c.write_text(text);exe=a.out/'wrapper-test'
    subprocess.run(['cc','-O2','-fno-strict-aliasing','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

if __name__=='__main__':main()
