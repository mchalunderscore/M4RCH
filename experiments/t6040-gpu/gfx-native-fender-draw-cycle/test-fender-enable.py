#!/usr/bin/env python3
"""Exercise the actual pre-draw Fender enable helper with RAM MMIO services."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define __iomem
#define GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL 1
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
static bool gfx_cold_running=true,gfx_cold_sealed=false,gfx_cold_complete=false;
static bool gfx_cold_control_ready=true,gfx_cold_draw_intent=false;
static bool gfx_cold_draw_notify_attempted=false,gfx_cold_draw_notify_sent=false;
static bool gfx_cold_record_attempted[2]={false,false};
static bool gfx_cold_producer_attempted[2]={false,false};
static bool recovery_work_submitted=false,held=true,live_ok=true;
static int graph_io_lock=1;
static unsigned int reads,writes,guard_calls,barriers,maxrow;
static u32 gpu_id=0x0a031100U,gate=6;
static bool gfx_cold_live(void){return held&&live_ok;}
static void assert_lock(int *l){assert(l==&graph_io_lock&&*l==1);}
#define lockdep_assert_held assert_lock
static bool gfx_cold_guard(unsigned int count,bool idle,unsigned int trace){
 assert(graph_io_lock==1&&count==33&&idle&&trace==3);guard_calls++;
 if(is("guard-ownership"))live_ok=false;
 return !is("physical-off")&&!is("physical-invalid")&&!is("control-mismatch")&&
        !is("work-not-idle")&&!is("trace-mismatch")&&!is("guard-error");
}
static void row(const char *fmt,...){char b[1024];va_list ap;va_start(ap,fmt);
 int n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);assert(n>0&&(size_t)n<sizeof b);
 assert(n<512);if((unsigned int)n>maxrow)maxrow=n;fputs(b,stdout);}
#define pr_info row
static u32 readl(void *p){assert(graph_io_lock==1);reads++;
 assert(p==fender||p==fender+0x2030);
 if(p==fender){assert(reads==1&&!writes);if(is("map-changed"))gfx_gravity_preasc_io[1]=other;return gpu_id;}
 if(!writes){assert(reads==2);if(is("prewrite-ownership"))live_ok=false;
  if(is("baseline-invalid"))return UINT32_MAX;return gate;}
 assert(writes==1&&reads==3);
 if(is("readback-invalid"))return UINT32_MAX;
 if(is("postwrite-ownership"))live_ok=false;
 return gate;
}
static void writel(u32 value,void *p){assert(p==fender+0x2030&&reads==2&&!writes);
 assert(graph_io_lock==1&&held&&live_ok);assert(value==(gate&~6U));writes++;
 if(!is("readback-drop"))gate=value;
}
static void full_barrier(void){assert(reads==3&&writes==1&&!barriers);barriers++;}
'''

SUFFIX = r'''
int main(int argc,char **argv){assert(argc==2);which=argv[1];
 if(is("not-running"))gfx_cold_running=false;if(is("sealed"))gfx_cold_sealed=true;
 if(is("cold-complete"))gfx_cold_complete=true;if(is("control-not-ready"))gfx_cold_control_ready=false;
 if(is("draw-intent"))gfx_cold_draw_intent=true;if(is("work-submitted"))recovery_work_submitted=true;
 if(is("notify-attempted"))gfx_cold_draw_notify_attempted=true;if(is("notify-sent"))gfx_cold_draw_notify_sent=true;
 if(is("record0"))gfx_cold_record_attempted[0]=true;if(is("record1"))gfx_cold_record_attempted[1]=true;
 if(is("producer0"))gfx_cold_producer_attempted[0]=true;if(is("producer1"))gfx_cold_producer_attempted[1]=true;
 if(is("preasc-incomplete"))gfx_gravity_preasc_complete=false;if(is("preasc-unknown"))gfx_gravity_preasc_unknown=true;
 if(is("region0"))gfx_gravity_preasc_region[0]=false;if(is("region1"))gfx_gravity_preasc_region[1]=false;
 if(is("mapping0"))gfx_gravity_preasc_io[0]=NULL;if(is("mapping1"))gfx_gravity_preasc_io[1]=NULL;
 if(is("consumer"))consumer=NULL;if(is("asc"))asc=NULL;if(is("mbox"))mbox=NULL;
 if(is("held"))held=false;if(is("identity"))live_ok=false;
 if(is("gpu-zero"))gpu_id=0;if(is("gpu-ones"))gpu_id=UINT32_MAX;if(is("gpu-changed"))gpu_id^=0x100;
 if(is("preserve"))gate=0xabcdeff6;if(is("already-enabled"))gate=0xa0000121;
 if(is("high-valid"))gate=0xfffffffe;if(is("fresh-baseline"))gate=0x8000000b;
 u32 before=gate;int ret=gfx_native_fender_enable();
 bool success=is("success")||is("duplicate")||is("preserve")||is("already-enabled")||is("high-valid")||is("fresh-baseline");
 if(success){assert(!ret&&gfx_native_fender_enable_complete&&!gfx_native_fender_enable_unknown);
  assert(reads==3&&writes==1&&guard_calls==1&&barriers==1);assert(gate==(before&~6U));
  assert((gate&~6U)==(before&~6U));
 }else{assert(ret<0&&!gfx_native_fender_enable_complete);assert(gfx_native_fender_enable_unknown==(writes>0));
  bool after_write=is("readback-drop")||is("readback-invalid")||is("postwrite-ownership");
  assert(writes==(after_write?1U:0U));assert(barriers==(is("postwrite-ownership")?1U:0U));
 }
 unsigned int r=reads,w=writes,g=guard_calls,b=barriers;
 assert(gfx_native_fender_enable()==-EALREADY);assert(reads==r&&writes==w&&guard_calls==g&&barriers==b);
 assert(gfx_native_fender_enable_intent&&graph_io_lock==1&&maxrow<512);
 fprintf(stderr,"PASS %s result=%d reads=%u writes=%u guard=%u barrier=%u maxrow=%u\n",which,ret,reads,writes,guard_calls,barriers,maxrow);return 0;
}
'''

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--helper', type=Path, default=HERE/'gfx-native-fender-enable.h')
    ap.add_argument('--output', type=Path, default=ROOT/'out/gfx-native-fender-draw-cycle/fender-qualification-v1.json')
    args = ap.parse_args()
    helper = args.helper.resolve()
    body = helper.read_text()
    barrier = 'asm volatile("dsb sy" ::: "memory");'
    if body.count(barrier) != 1:
        raise ValueError('Expected exactly one full ARM64 barrier')
    body = body.replace(barrier, 'full_barrier();')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    actual = output.with_suffix('.actual-helper.c')
    tester = output.with_suffix('.tester.py')
    actual.write_text(PREFIX+body+SUFFIX)
    tester.write_bytes(Path(__file__).read_bytes())
    cases = ['success','duplicate','preserve','already-enabled','high-valid','fresh-baseline',
             'not-running','sealed','cold-complete','control-not-ready','draw-intent','work-submitted',
             'notify-attempted','notify-sent','record0','record1','producer0','producer1',
             'preasc-incomplete','preasc-unknown','region0','region1','mapping0','mapping1',
             'consumer','asc','mbox','held','identity','physical-off','physical-invalid',
             'control-mismatch','work-not-idle','trace-mismatch','guard-error','guard-ownership',
             'gpu-zero','gpu-ones','gpu-changed','map-changed','baseline-invalid',
             'prewrite-ownership','readback-drop','readback-invalid','postwrite-ownership']
    results = []
    with tempfile.TemporaryDirectory(prefix='m4rch-fender-enable-') as tmp:
        binary = Path(tmp)/'actual-helper'
        argv = ['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined',
                '-fno-omit-frame-pointer',str(actual),'-o',str(binary)]
        build = subprocess.run(argv,capture_output=True,text=True)
        if build.returncode:
            output.with_suffix('.build-failed.log').write_text(build.stderr)
            raise RuntimeError(build.stderr)
        for case in cases:
            result = subprocess.run([str(binary),case],capture_output=True,text=True,
                                    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
            fixture = output.with_suffix(f'.{case}.log')
            fixture.write_text(result.stdout)
            if result.returncode:
                output.with_suffix(f'.{case}.failed.log').write_text(result.stderr)
                raise RuntimeError(f'{case}: {result.stderr}\n{result.stdout}')
            results.append({'case':case,'returncode':result.returncode,'result':result.stderr.strip(),
                            'fixture':{'path':str(fixture),'bytes':fixture.stat().st_size,'sha256':sha(fixture)}})
    sources = [helper,Path(__file__).resolve(),actual,tester,
               ROOT/'docs/evidence/2026-10-08-private-kick-fender.json',
               ROOT/'docs/evidence/2026-10-08-private-kick-initialization.json']
    report = {'schema':'m4rch.gfx-native-fender-enable.actual-C-qualification.v1',
              'passed':True,'case_count':len(cases),'cases':results,
              'helper_sha256':sha(helper),'input_pins':[{'path':str(p),'sha256':sha(p)} for p in sources],
              'success_log_fixture':results[0]['fixture'],'maximum_mmio_writes':1,
              'hardware_access':False,'kernel_build':False,'caller_order_verified':False,
              'qualification':'Actual production helper with RAM MMIO and bounded existing-owner guard stubs, ASan/UBSan. One ARM64 full barrier is replaced with an asserted fixture barrier. Includes preserved bits, unchanged enabled value, every admission refusal, identity transitions, invalid reads, dropped write, and refused second invocation. Does not prove real PM/MMIO/cache/firmware ordering or GPU execution. Root must qualify actual owner caller insertion separately.',
              'experimental_transfer':{'operation':'fresh old & ~6 at SGX+d06030; ordered write/readback/full barrier',
                'location':'after fresh firmware control33, before first draw intent/publication',
                'native_enclosure':'addKicks uses disable(old|4), direct SGX+4090/+4098 kick, enable(old&~6)',
                'native_complete_addkicks_reproduced':False,'ep33_is_native_addkicks':False,
                'direct_kick_written':False,'scheduler_ack_written':False,'teardown_clear':False,
                'restart_replay':False,'backing_release':False}}
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_count':len(cases),'path':str(output),'sha256':sha(output),
                      'helper_sha256':sha(helper),'success_log_fixture':report['success_log_fixture']}))

if __name__ == '__main__':
    main()
