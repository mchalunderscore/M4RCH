#!/usr/bin/env python3
"""Exercise the actual Fender OFF leaf with RAM MMIO and frozen runtime policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def pin(path):
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL 1
#define GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL 1
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
static const char *which;
static bool is(const char *s){return !strcmp(which,s);}
static unsigned char fender[16384],other[16384],control[16384];
static void *gfx_gravity_preasc_io[2]={control,fender};
static bool gfx_gravity_preasc_region[2]={true,true};
static bool gfx_gravity_preasc_complete=true,gfx_gravity_preasc_unknown=false;
static u32 gfx_gravity_preasc_gpu_id=0x0a031100U;
static int consumer_instance,asc_instance,mbox_instance;
static void *consumer=&consumer_instance,*asc=&asc_instance,*mbox=&mbox_instance;
static void *gfx_gravity_preasc_consumer=&consumer_instance;
static void *gfx_gravity_preasc_asc=&asc_instance,*gfx_gravity_preasc_mbox=&mbox_instance;
static bool gfx_postdraw_cycle_intent=true,gfx_postdraw_unknown=false;
static bool gfx_postdraw_off_attempted=false,gfx_postdraw_pm_put_attempted=false;
static bool gfx_postdraw_control_sealed=false,held=true,active_ok=true;
static bool gfx_native_powergate_idle_observed=true,gfx_native_powergate_cpu_stopped=true;
static bool gfx_native_powergate_clear10_attempted=true,gfx_native_powergate_clear20_attempted=true;
static u32 gfx_native_powergate_control_after20=0,gfx_native_powergate_idle_status=0x6e;
static bool gfx_native_fender_enable_intent=true,gfx_native_fender_enable_attempted=true;
static bool gfx_native_fender_enable_complete=true,gfx_native_fender_enable_unknown=false;
static void *gfx_native_fender_enable_map=fender;
static u32 gfx_native_fender_enable_gpu_id=0x0a031100U;
static int graph_io_lock=1;
static unsigned int reads,writes,snapshots,barriers,maxrow;
static bool second_call;
static u32 gpu_id=0x0a031100U,gate=0;
struct apple_pmgr_gfx_reset_observation {u32 valid;bool domain_on;u32 before;};
static struct apple_pmgr_gfx_reset_observation snapshot={1,true,0x1400034f};
static bool gfx_postdraw_active(void){return held&&active_ok;}
static void assert_lock(int *l){assert(l==&graph_io_lock&&*l==1);}
#define lockdep_assert_held assert_lock
static void row(const char *fmt,...){char b[1024];va_list ap;va_start(ap,fmt);
 int n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);assert(n>0&&(size_t)n<sizeof b);
 assert(n<512);if((unsigned int)n>maxrow)maxrow=n;fputs(b,second_call?stderr:stdout);}
#define pr_info row
static int gfx_cold_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o){
 assert(!strcmp(phase,"fender-off-before")&&index==0&&graph_io_lock==1);
 assert(gfx_postdraw_active()&&!writes&&!reads&&!snapshots);snapshots++;*o=snapshot;
 if(is("snapshot-ownership"))active_ok=false;
 if(is("snapshot-error"))return -EIO;if(is("snapshot-positive"))return 1;
 return 0;
}
static u32 readl(void *p){assert(graph_io_lock==1);reads++;
 assert(p==fender||p==fender+0x2030);
 if(p==fender){assert(reads==1&&!writes);if(is("gpu-ownership"))active_ok=false;
  if(is("map-changed"))gfx_gravity_preasc_io[1]=other;return gpu_id;}
 if(!writes){assert(reads==2);if(is("prewrite-ownership"))active_ok=false;
  if(is("baseline-invalid"))return UINT32_MAX;return gate;}
 assert(writes==1&&reads==3);
 if(is("readback-invalid"))return UINT32_MAX;
 if(is("postwrite-ownership"))active_ok=false;
 return gate;
}
static void writel(u32 value,void *p){assert(p==fender+0x2030&&reads==2&&!writes);
 assert(graph_io_lock==1&&held&&active_ok&&snapshots==1);assert(value==(gate|4U));writes++;
 if(!is("readback-drop"))gate=value;
}
static void full_barrier(void){assert(reads==3&&writes==1&&!barriers);barriers++;}
'''

SUFFIX = r'''
int main(int argc,char **argv){assert(argc==2);which=argv[1];
 if(is("no-cycle"))gfx_postdraw_cycle_intent=false;if(is("cycle-unknown"))gfx_postdraw_unknown=true;
 if(is("off-attempted"))gfx_postdraw_off_attempted=true;if(is("put-attempted"))gfx_postdraw_pm_put_attempted=true;
 if(is("sealed"))gfx_postdraw_control_sealed=true;if(is("held"))held=false;
 if(is("inactive"))active_ok=false;if(is("idle-not-observed"))gfx_native_powergate_idle_observed=false;
 if(is("cpu-not-stopped"))gfx_native_powergate_cpu_stopped=false;
 if(is("clear10-not-attempted"))gfx_native_powergate_clear10_attempted=false;
 if(is("clear20-not-attempted"))gfx_native_powergate_clear20_attempted=false;
 if(is("control-invalid"))gfx_native_powergate_control_after20=UINT32_MAX;
 if(is("control10-set"))gfx_native_powergate_control_after20=0x10;
 if(is("control20-set"))gfx_native_powergate_control_after20=0x20;
 if(is("idle-invalid"))gfx_native_powergate_idle_status=UINT32_MAX;
 if(is("idle-not-set"))gfx_native_powergate_idle_status=0x6c;
 if(is("enable-no-intent"))gfx_native_fender_enable_intent=false;
 if(is("enable-no-attempt"))gfx_native_fender_enable_attempted=false;
 if(is("enable-incomplete"))gfx_native_fender_enable_complete=false;
 if(is("enable-unknown"))gfx_native_fender_enable_unknown=true;
 if(is("enable-map"))gfx_native_fender_enable_map=other;
 if(is("preasc-incomplete"))gfx_gravity_preasc_complete=false;if(is("preasc-unknown"))gfx_gravity_preasc_unknown=true;
 if(is("region0"))gfx_gravity_preasc_region[0]=false;if(is("region1"))gfx_gravity_preasc_region[1]=false;
 if(is("mapping0"))gfx_gravity_preasc_io[0]=NULL;if(is("mapping1"))gfx_gravity_preasc_io[1]=NULL;
 if(is("consumer"))consumer=NULL;if(is("asc"))asc=NULL;if(is("mbox"))mbox=NULL;
 if(is("gpu-zero"))gpu_id=0;if(is("gpu-ones"))gpu_id=UINT32_MAX;if(is("gpu-changed"))gpu_id^=0x100;
 if(is("preasc-id-match"))gfx_gravity_preasc_gpu_id^=0x100;
 if(is("enable-id-match"))gfx_native_fender_enable_gpu_id^=0x100;
 if(is("physical-invalid"))snapshot.valid=0;if(is("physical-domain-off"))snapshot.domain_on=false;
 if(is("physical-ones"))snapshot.before=UINT32_MAX;if(is("physical-target"))snapshot.before=0x14000340;
 if(is("physical-busy"))snapshot.before|=0x800;
 if(is("physical-reset"))snapshot.before|=0x80000000;
 if(is("physical-ps-reset"))snapshot.before|=0x1000;if(is("physical-disable"))snapshot.before|=0x400;
 if(is("physical-actual8"))snapshot.before=0x1400038f;
 if(is("physical-no-auto"))snapshot.before=0x0400034f;
 if(is("dynamic-zero"))snapshot.before=0x1000030f;
 if(is("dynamic-f"))snapshot.before=0x1f0003ff;
 if(is("dynamic-f-no-auto"))snapshot.before=0x0f0003ff;
 if(is("preserve"))gate=0xabcdeff2;if(is("already-disabled"))gate=0xa0000124;
 if(is("high-valid"))gate=0xfffffffe;if(is("fresh-baseline"))gate=0x8000000b;
 if(is("all-ones-result"))gate=0xfffffffb;
 u32 before=gate;int ret=gfx_native_fender_disable();
 bool success=is("success")||is("duplicate")||is("preserve")||is("already-disabled")||
  is("high-valid")||is("fresh-baseline")||is("dynamic-zero")||is("dynamic-f")||is("dynamic-f-no-auto");
 if(success){assert(!ret&&gfx_native_fender_disable_complete&&!gfx_native_fender_disable_unknown);
  assert(reads==3&&writes==1&&snapshots==1&&barriers==1);assert(gate==(before|4U));
  assert((gate&~4U)==(before&~4U));
 }else{assert(ret<0&&!gfx_native_fender_disable_complete);assert(gfx_native_fender_disable_unknown==(writes>0));
  bool after_write=is("readback-drop")||is("readback-invalid")||is("postwrite-ownership")||is("all-ones-result");
  assert(writes==(after_write?1U:0U));assert(barriers==(is("postwrite-ownership")?1U:0U));
  if(is("snapshot-positive"))assert(ret==-EIO);
 }
 unsigned int r=reads,w=writes,s=snapshots,b=barriers;second_call=true;
 assert(gfx_native_fender_disable()==-EALREADY);assert(reads==r&&writes==w&&snapshots==s&&barriers==b);
 assert(gfx_native_fender_disable_intent&&graph_io_lock==1&&maxrow<512);
 fprintf(stderr,"PASS %s result=%d reads=%u writes=%u snapshots=%u barrier=%u maxrow=%u\n",which,ret,reads,writes,snapshots,barriers,maxrow);return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, default=HERE/'gfx-native-fender-disable.h')
    parser.add_argument('--output', type=Path,
                        default=ROOT/'out/gfx-native-fender-off-cycle/fender-off-qualification-v1.json')
    args = parser.parse_args()
    helper = args.helper.resolve()
    runtime = ROOT/'experiments/t6040-gpu/gfx-native-fender-runtime-cycle/gfx-native-runtime-state.h'
    if pin(runtime)['sha256'] != '4e25f120981774cef205020ea8d59683c42d549477ce174af427b7b3c61d8497':
        raise ValueError('Frozen v19 runtime policy required')
    body = helper.read_text()
    barrier = 'asm volatile("dsb sy" ::: "memory");'
    if body.count(barrier) != 1:
        raise ValueError('Expected exactly one full ARM64 barrier')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    actual = output.with_suffix('.actual-helper.c')
    tester = output.with_suffix('.tester.py')
    actual.write_text(PREFIX + runtime.read_text() + body.replace(barrier, 'full_barrier();') + SUFFIX)
    tester.write_bytes(Path(__file__).read_bytes())
    cases = ['success','duplicate','preserve','already-disabled','high-valid','fresh-baseline',
             'dynamic-zero','dynamic-f','dynamic-f-no-auto','all-ones-result',
             'no-cycle','cycle-unknown','off-attempted','put-attempted','sealed','held','inactive',
             'idle-not-observed','cpu-not-stopped','clear10-not-attempted','clear20-not-attempted',
             'control-invalid','control10-set','control20-set','idle-invalid','idle-not-set',
             'enable-no-intent','enable-no-attempt','enable-incomplete','enable-unknown','enable-map',
             'preasc-incomplete','preasc-unknown','region0','region1','mapping0','mapping1',
             'consumer','asc','mbox','gpu-zero','gpu-ones','gpu-changed','preasc-id-match','enable-id-match',
             'snapshot-error','snapshot-positive','snapshot-ownership','physical-invalid','physical-domain-off',
             'physical-ones','physical-target','physical-busy','physical-reset','physical-ps-reset',
             'physical-disable','physical-actual8','physical-no-auto','gpu-ownership','map-changed',
             'baseline-invalid','prewrite-ownership','readback-drop','readback-invalid','postwrite-ownership']
    results = []
    with tempfile.TemporaryDirectory(prefix='m4rch-fender-disable-') as tmp:
        binary = Path(tmp)/'actual-helper'
        command = ['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined',
                   '-fno-omit-frame-pointer',str(actual),'-o',str(binary)]
        build = subprocess.run(command, capture_output=True, text=True)
        if build.returncode:
            output.with_suffix('.build-failed.log').write_text(build.stderr)
            raise RuntimeError(build.stderr)
        for case in cases:
            result = subprocess.run([str(binary), case], capture_output=True, text=True,
                                    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
            fixture = output.with_suffix(f'.{case}.log')
            fixture.write_text(result.stdout)
            if result.returncode:
                output.with_suffix(f'.{case}.failed.log').write_text(result.stderr)
                raise RuntimeError(f'{case}: {result.stderr}\n{result.stdout}')
            results.append({'case':case,'returncode':result.returncode,
                            'result':result.stderr.strip(),'fixture':pin(fixture)})
    sources = [helper,Path(__file__).resolve(),runtime,actual,tester,
               ROOT/'docs/evidence/2026-10-10-gfx-native-fender-enable.json',
               ROOT/'out/gfx-native-fender-runtime-cycle/runtime-qualification-v1.json']
    report = {'schema':'m4rch.gfx-native-fender-disable.actual-C-qualification.v1',
              'passed':True,'case_count':len(cases),'cases':results,
              'compiler':{'command':command,'returncode':build.returncode},
              'helper_sha256':pin(helper)['sha256'],'input_pins':[pin(p) for p in sources],
              'success_log_fixture':results[0]['fixture'],'maximum_mmio_writes':1,
              'hardware_access':False,'hardware_actions':[],'kernel_build':False,
              'caller_order_verified':False,
              'qualification':'Actual production OFF leaf and unchanged frozen runtime predicate, RAM MMIO, ASan/UBSan. One ARM64 full barrier is replaced with an asserted fixture barrier. Each case also asserts refused second invocation makes no further hardware service calls. Caller insertion and real MMIO/firmware/PM ordering remain separate root checks.',
              'experimental_transfer':{'operation':'fresh old | 4 at SGX+d06030; exact readback/full barrier',
                'location':'after idle and CPU stop, before off-intent/seal/paired coordinate OFF',
                'native_full_poweroff_reproduced':False,'pmgr_writes':0,'ack_cleanup':False,
                'new_mappings':False,'backing_release':False,'same_boot_retry':False}}
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_count':len(cases),'report':pin(output),
                      'helper':pin(helper),'success_log_fixture':report['success_log_fixture']}))


if __name__ == '__main__':
    main()
