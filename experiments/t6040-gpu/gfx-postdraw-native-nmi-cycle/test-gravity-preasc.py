#!/usr/bin/env python3
"""Compile and exercise the actual preASC helper with bounded RAM services.

This fixture is an isolated helper invocation; real startup caller order is
bound separately by the owner preparer. No kernel or hardware access occurs.
"""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HELPER = HERE / 'gfx-gravity-preasc.h'
GRAVITY = ROOT / 'out/gfx-native-reset-kernel/linux/drivers/gpu/drm/asahi'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdlib.h>
#include <errno.h>
typedef uint32_t u32; typedef uint64_t u64;
#define __iomem
#define GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL 1
#define START 16U
#define EMPTY (1U<<17)
#define READ_ONCE(x) (x)
#define IORESOURCE_MEM 0x200U
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
struct fake_dev { struct {int usage_count; int runtime_error;} power;
 bool active,suspended,enabled; };
struct platform_device {struct fake_dev dev;};
struct device_node {int id;};
struct resource {u64 start,end;unsigned long flags;};
struct apple_pmgr_gfx_reset_observation {u32 valid,before;bool domain_on;};
static struct platform_device device={{{1,0},true,false,true}};
static struct platform_device *consumer=&device;
static unsigned char asc_bytes[4096],mbox_bytes[4096],control_bytes[16384],fender_bytes[16384];
static void *asc=asc_bytes,*mbox=mbox_bytes;
static bool held=true,started=false,asc_region=true,mbox_region=true;
static bool gfx_coord_owner_module_pinned=true,retained=true;
static struct {bool on_complete;} gfx_coord_owner_session={true};
static int graph_io_lock;
static const char *which;
static unsigned int mmio_reads,sgx_reads,writes,requests,maps,physical_reads,maxrow;
static unsigned int operand_reads[3],operand_writes[3];
static bool region_claimed[2],mapped[2],board_ok=true;
static u32 control_word=0,status_word=0x6a,rx_word=EMPTY,gpu_word=0x0a031100;
static u32 regs[3]={0x100,0x80000002,0xabcde040};
static struct device_node alias_node={1};
static bool is(const char *s){return !strcmp(which,s);}
static bool indexed(const char *s,unsigned int i){char b[80];snprintf(b,sizeof b,"%s-%u",s,i);return is(b);}
static int atomic_read(const int *x){return *x;}
static bool pm_runtime_enabled(struct fake_dev *d){return d->enabled;}
static bool pm_runtime_active(struct fake_dev *d){return d->active;}
static bool pm_runtime_suspended(struct fake_dev *d){return d->suspended;}
static bool gfx_coord_owner_retained(void){return retained;}
static void mutex_lock(int *m){assert(*m==0);*m=1;}
static void mutex_unlock(int *m){assert(*m==1);*m=0;}
static void logrow(const char *fmt,...){char b[1024];va_list ap;va_start(ap,fmt);int n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);assert(n>0&&(size_t)n<sizeof b);if((unsigned int)n>maxrow)maxrow=n;assert(n<512);fputs(b,stdout);}
#define pr_info logrow
#define pr_err logrow
static bool of_machine_is_compatible(const char *s){assert(graph_io_lock==1);assert(!strcmp(s,"apple,j614s")||!strcmp(s,"apple,t6040"));return board_ok;}
static struct device_node *of_find_all_nodes(struct device_node *n){assert(graph_io_lock==1);return is("alias")&&!n?&alias_node:NULL;}
static bool of_device_is_available(struct device_node *n){assert(n==&alias_node);return true;}
static int of_address_to_resource(struct device_node *n,unsigned int i,struct resource *r){assert(n==&alias_node);if(i)return -EINVAL;r->start=0x288d04000ULL;r->end=0x288d07fffULL;r->flags=IORESOURCE_MEM;return 0;}
static void of_node_put(struct device_node *n){assert(n==&alias_node);}
static void *request_mem_region(u64 base,unsigned int bytes,const char *name){unsigned int i=base==0x289000000ULL?0:1;assert(graph_io_lock==1&&held&&!started);assert(base==(i?0x288d04000ULL:0x289000000ULL));assert(bytes==0x4000);assert(!region_claimed[i]&&!sgx_reads&&!writes);assert(!strcmp(name,i?"m4rch-gravity-preasc-fender":"m4rch-gravity-preasc-control"));requests++;if(indexed("busy",i))return NULL;region_claimed[i]=true;return &region_claimed[i];}
static void *ioremap(u64 base,unsigned int bytes){unsigned int i=base==0x289000000ULL?0:1;assert(graph_io_lock==1&&region_claimed[0]&&region_claimed[1]);assert(bytes==0x4000);assert(base==(i?0x288d04000ULL:0x289000000ULL));maps++;if(indexed("map",i))return NULL;mapped[i]=true;return i?fender_bytes:control_bytes;}
static int gfx_cold_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o){assert(graph_io_lock==1&&held&&!started);assert(!strcmp(phase,"gravity-preasc")&&!index);physical_reads++;o->valid=is("physical-invalid")?0:1;o->domain_on=!is("physical-off");o->before=is("physical-off")?0:0x1f0003ff;if(is("physical-error"))return -EIO;return 0;}
static int operand(void *p){if(p==control_bytes+0x104)return 0;if(p==control_bytes+0x108)return 1;if(p==fender_bytes+0x2030)return 2;return -1;}
static u32 readl(void *p){int i;assert(graph_io_lock==1&&held&&!started);mmio_reads++;
 if(p==asc_bytes+0x44)return control_word;if(p==asc_bytes+0x48)return status_word;if(p==mbox_bytes+0x114)return rx_word;
 assert(region_claimed[0]&&region_claimed[1]&&mapped[0]&&mapped[1]);sgx_reads++;
 if(p==fender_bytes)return gpu_word;
 i=operand(p);assert(i>=0);operand_reads[i]++;
 if(indexed("baseline-invalid",i)&&operand_reads[i]==1)return UINT32_MAX;
 if(indexed("prewrite-invalid",i)&&operand_reads[i]==2)return UINT32_MAX;
 if(is("fresh-rmw")&&i==0&&operand_reads[i]==2)regs[0]=0xa0000120;
 if(is("prewrite-pm")&&i==2&&operand_reads[i]==1)device.dev.power.usage_count=2;
 if(indexed("readback-invalid",i)&&operand_writes[i])return UINT32_MAX;
 return regs[i];}
static void writel(u32 value,void *p){int i=operand(p);assert(i>=0&&graph_io_lock==1&&held&&!started);assert(region_claimed[0]&&region_claimed[1]&&mapped[0]&&mapped[1]);assert(operand_reads[0]>=1&&operand_reads[1]>=1&&operand_reads[2]>=1);assert(operand_reads[i]==2&&operand_writes[i]==0);assert((unsigned int)i==writes);assert(value==(i<2?(regs[i]|1):6));operand_writes[i]++;writes++;if(!indexed("readback-drop",i))regs[i]=value;}
'''

SUFFIX = r'''
int main(int argc,char **argv){assert(argc==2);which=argv[1];
 if(is("board"))board_ok=false;if(is("no-consumer"))consumer=NULL;
 if(is("held"))held=false;if(is("usage"))device.dev.power.usage_count=2;
 if(is("runtime-error"))device.dev.power.runtime_error=-EIO;
 if(is("inactive")){device.dev.active=false;device.dev.suspended=true;}
 if(is("disabled"))device.dev.enabled=false;
 if(is("started"))started=true;if(is("coordinate"))gfx_coord_owner_session.on_complete=false;
 if(is("start-bit"))control_word=START;if(is("status"))status_word=0x6d;if(is("fifo"))rx_word=0;
 if(is("gpu-zero"))gpu_word=0;if(is("gpu-ones"))gpu_word=UINT32_MAX;
 if(is("preserve")){regs[0]=0xfffffffc;regs[1]=0x80008002;regs[2]=0xdeadbeef;}
 int ret=gfx_gravity_preasc();assert(graph_io_lock==0);bool success=is("success")||is("duplicate")||is("preserve")||is("fresh-rmw");
 if(success){assert(ret==0&&gfx_gravity_preasc_complete&&!gfx_gravity_preasc_unknown);assert(writes==3&&requests==2&&maps==2&&physical_reads==1);assert(regs[2]==6);assert((regs[0]&1)&&(regs[1]&1));
  if(is("preserve")){assert(regs[0]==0xfffffffd&&regs[1]==0x80008003);}
  if(is("fresh-rmw"))assert(regs[0]==0xa0000121);
 }else {assert(ret<0&&!gfx_gravity_preasc_complete);assert(gfx_gravity_preasc_unknown==(writes>0));}
 if(is("duplicate")){unsigned int r=mmio_reads,q=requests,m=maps,w=writes;assert(gfx_gravity_preasc()==-EALREADY);assert(mmio_reads==r&&requests==q&&maps==m&&writes==w);}
 if(!success){for(unsigned int i=0;i<3;i++){if(indexed("readback-drop",i)||indexed("readback-invalid",i))assert(writes==i+1);if(indexed("prewrite-invalid",i))assert(writes==i);}if(strncmp(which,"readback-",9)&&strncmp(which,"prewrite-invalid-",17))assert(!writes);}
 assert(maxrow<512);fprintf(stderr,"PASS %s writes=%u claims=%u maps=%u reads=%u maxrow=%u\n",which,writes,requests,maps,mmio_reads,maxrow);return 0;}
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=ROOT/'out/gfx-postdraw-native-nmi-cycle/preasc-qualification-v1.json')
    ap.add_argument('--helper', type=Path, default=HELPER)
    args = ap.parse_args()
    helper = args.helper.resolve()
    text = helper.read_text()
    if 'release_mem_region' in text or 'iounmap(' in text:
        raise ValueError('PreASC resources must remain retained')
    body = text.replace('#include <linux/of_address.h>', '')
    # User-mode fixture executes the actual production helper. Replace only
    # its ARM64 memory barrier with a compiler fence for portable RAM services.
    barrier = 'asm volatile("dsb sy" ::: "memory");'
    if body.count(barrier) != 1:
        raise ValueError('Exact source memory barrier changed')
    body = body.replace(barrier, 'asm volatile("" ::: "memory");')
    cases = ['success','duplicate','preserve','fresh-rmw','board','no-consumer',
             'held','usage','runtime-error','inactive','disabled','started',
             'coordinate','physical-error','physical-invalid','physical-off',
             'start-bit','status','fifo','alias','busy-0','busy-1','map-0','map-1',
             'gpu-zero','gpu-ones','prewrite-pm']
    for family in ('baseline-invalid','prewrite-invalid','readback-drop','readback-invalid'):
        cases.extend(f'{family}-{i}' for i in range(3))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    actual = output.with_suffix('.actual-helper.c')
    tester = output.with_suffix('.tester.py')
    actual.write_text(PREFIX + body + SUFFIX)
    tester.write_bytes(Path(__file__).read_bytes())
    results = []
    with tempfile.TemporaryDirectory(prefix='m4rch-preasc-') as tmp:
        binary = Path(tmp)/'actual-preasc'
        build = subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined',
                                '-fno-omit-frame-pointer',str(actual),'-o',str(binary)],
                               capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(build.stderr)
        for case in cases:
            result = subprocess.run([str(binary),case],capture_output=True,text=True,
                                    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
            if result.returncode:
                raise RuntimeError(f'{case}: {result.stderr}\n{result.stdout}')
            fixture = output.with_suffix(f'.{case}.log')
            fixture.write_text(result.stdout)
            results.append({'case':case,'returncode':result.returncode,'stdout':result.stderr.strip(),
                            'fixture':{'path':str(fixture),'bytes':fixture.stat().st_size,'sha256':sha(fixture)}})
    pins = [{'path':str(p),'sha256':sha(p)} for p in [helper,Path(__file__).resolve(),actual,tester,
             GRAVITY/'g16.rs',GRAVITY/'asahi_m4.rs',GRAVITY/'g16_profile.rs',
             ROOT/'docs/evidence/2026-10-08-private-kick-fender.json']]
    report = {'schema':'m4rch.gfx-gravity-preasc.actual-C-qualification.v1','passed':True,
              'hardware_access':False,'kernel_build':False,'case_count':len(cases),'cases':results,
              'prepared_helper_sha256':sha(helper),'input_pins':pins,
              'success_log_fixture':results[0]['fixture'],
              'actual_log_fixtures':[{'case':r['case'],**r['fixture']} for r in results],
              'qualification':'Actual isolated production helper with RAM PM/MMIO/resource/OF services and ASan/UBSan. Caller insertion/order is qualified separately. One ARM64 barrier is replaced with a compiler fence. No real firmware/hardware/rendering/teardown proof.',
              'maximum_source_writes':3,'full_16k_page_reservations':True,
              'all_baselines_precede_first_write':True,'first_two_preserve_other_bits':True,
              'fender_literal_six_policy':True,'no_release_or_restore':True,
              'management_rejoin_prefix_replay':False,'source_t6040_normal_startup':False}
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_count':len(cases),'path':str(output),'sha256':sha(output),
                      'helper_sha256':sha(helper),'success_log_fixture':report['success_log_fixture']}))

if __name__ == '__main__':
    main()
