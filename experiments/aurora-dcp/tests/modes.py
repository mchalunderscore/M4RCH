#!/usr/bin/env python3
"""Exercise the production catalog and modeset function with host transport shims."""
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from timing import encode, mode

p=argparse.ArgumentParser();p.add_argument('kernel',type=Path);p.add_argument('work',type=Path);a=p.parse_args()
a.work.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(Path(__file__).with_name('timing.py')),str(a.kernel),str(a.work)],check=True)
for name,values in [('catalog',[mode(120,19),mode(60,42),mode(48,91)]),('duplicate',[mode(60,42),mode(120,42)]),('only120',[mode(120,19)])]:
 (a.work/(name+'.bin')).write_bytes(encode(values))
(a.work/'catalog.c').write_text(r'''
#include <stdio.h>
#include <assert.h>
#include "dcp-m4-timing.h"
static unsigned char data[65536];
int main(int argc,char **argv) {
 struct dcp_m4_timing modes[32], one; unsigned int count;
 for(int arg=1;arg<argc;arg++) {
  FILE *f=fopen(argv[arg],"rb"); assert(f); size_t n=fread(data,1,sizeof(data),f);fclose(f);
  int ret=j614s_timing_catalog(data,n,modes,32,&count);
  if(arg==2) { assert(ret<0 && count==0);continue; }
  assert(!ret); assert(count==(arg==1?3:1));
  assert(modes[0].id==19 && modes[0].color_id==93 && modes[0].refresh_16_16==120U*65536);
  assert(modes[0].clock_khz==744000);
  assert(!dcp_m4_parse_timing(data,n,&one)); assert(one.id==(arg==1?42:19));
  if(arg==1) { assert(modes[1].id==42 && modes[2].id==91); assert(j614s_timing_catalog(data,n,modes,1,&count)<0 && count==0); }
  for(size_t cut=0;cut<n;cut++) assert(j614s_timing_catalog(data,cut,modes,32,&count)<0);
 }
 puts("Catalog PASS: all physical 48/60/120 modes, actual IDs/color/clock, duplicate-ID refusal, capacity, every truncated prefix");
}
''')
flags=['clang','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(a.work/'include'),'-I'+str(a.kernel/'drivers/gpu/drm/apple')]
subprocess.run(flags+[str(a.work/'catalog.c'),'-o',str(a.work/'catalog')],check=True)
subprocess.run([str(a.work/'catalog'),*[str(a.work/(n+'.bin')) for n in ['catalog','duplicate','only120']]],check=True)
source=(a.kernel/'drivers/gpu/drm/apple/iomfb_m4.c').read_text();start=source.index('int iomfb_m4_modeset(');end=source.index('\nint iomfb_m4_error(',start)
# Test the actual compiled function with deterministic mode matching and RPC shims.
preamble=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint32_t u32;
#define EINVAL 22
#define EIO 5
#define READ_ONCE(x) (x)
#define dev_info(...) ((void)0)
#define msecs_to_jiffies(x) (x)
#define jiffies 100
#define put_unaligned_le32(v,p) do { u32 _v=(v);memcpy(p,&_v,4); } while(0)
static u32 get_unaligned_le32(const void *p) { u32 v;memcpy(&v,p,4);return v; }
struct timing {u32 id,color_id,refresh_16_16;};
struct drm_display_mode {int index;};
struct dcp_m4_runtime {struct timing modes[3],timing;unsigned mode_count;bool mode_programmed;u32 modeset_status;unsigned long deadline;};
struct iomfb_m4 {struct dcp_m4_runtime *runtime;int error,lock;void *dev;};
struct apple_dcp {struct iomfb_m4 *v26_6;};
static int held,calls,wire_error,health_error;static u32 reply;static u8 wire[8];
static void mutex_lock(int *m) { assert(!held);held=1; }
static void mutex_unlock(int *m) { assert(held);held=0; }
static bool iomfb_m4_has_mode(struct apple_dcp *d,const struct drm_display_mode *m) {return m->index>=0 && m->index<(d->v26_6->runtime->mode_count?:1);}
static int iomfb_m4_get_mode_at(struct apple_dcp *d,unsigned i,struct drm_display_mode *m) {m->index=i;return 0;}
static bool drm_mode_equal(const struct drm_display_mode *a,const struct drm_display_mode *b) {return a->index==b->index;}
static int dcp_m4_runtime_call(struct dcp_m4_runtime *r,unsigned method,bool remote,const void *in,u32 ni,void *out,u32 no) {
 assert(held && method==413 && !remote && ni==8 && no==4 && r->deadline==8600);calls++;memcpy(wire,in,8);memcpy(out,&reply,4);return wire_error;
}
static int dcp_m4_runtime_health(struct dcp_m4_runtime *r) {assert(held);return health_error;}
static void dcp_m4_failed(struct iomfb_m4 *d,int ret) {assert(held && ret);d->error=ret;}
'''
test=r'''
int main(void) {
 struct dcp_m4_runtime r={.mode_count=2,.modes={{19,93,120U*65536},{42,93,60U*65536}}};
 struct iomfb_m4 d={.runtime=&r};struct apple_dcp o={.v26_6=&d};
 struct drm_display_mode high={0},low={1},bad={2};
 assert(iomfb_m4_modeset(&o,&bad)==-EINVAL && !calls);
 assert(!iomfb_m4_modeset(&o,&high) && calls==1 && r.mode_programmed && r.timing.id==19);
 assert(get_unaligned_le32(wire)==93 && get_unaligned_le32(wire+4)==19 && !r.deadline);
 assert(!iomfb_m4_modeset(&o,&high) && calls==1);
 assert(!iomfb_m4_modeset(&o,&low) && calls==2 && r.timing.id==42);
 reply=0x8000000b;assert(iomfb_m4_modeset(&o,&high)==-EIO && d.error==-EIO && r.timing.id==42);
 assert(iomfb_m4_modeset(&o,&high)==-EIO && calls==3);
 d.error=0;reply=0;wire_error=-110;assert(iomfb_m4_modeset(&o,&high)==-110 && d.error==-110 && r.timing.id==42 && !r.deadline);
 d.error=0;wire_error=0;health_error=-71;assert(iomfb_m4_modeset(&o,&high)==-71 && d.error==-71 && r.timing.id==42);
 d.error=0;health_error=0;r.mode_count=0;int before=calls;assert(!iomfb_m4_modeset(&o,&high) && calls==before);
 assert(!held);puts("Modeset PASS: actual function, wire IDs/order/length/deadline, 120->60, unchanged-mode no-op, rejected/timeout/unhealthy failures retain prior state, opt-out no RPC");
}
'''
(a.work/'modeset.c').write_text(preamble+source[start:end]+test)
subprocess.run(flags+[str(a.work/'modeset.c'),'-o',str(a.work/'modeset')],check=True)
subprocess.run([str(a.work/'modeset')],check=True)
