#!/usr/bin/env python3
"""Compile the actual read-only runtime helper with ASan/UBSan CPU operands."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL 1
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
static bool gfx_native_fender_enable_complete,gfx_native_fender_enable_unknown;
static bool gfx_native_fender_enable_attempted;
static unsigned int maxrow,rows;
static bool silent;
static void row(const char *fmt,...){char b[1024];va_list ap;va_start(ap,fmt);
 int n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);assert(n>0&&(size_t)n<sizeof b);
 assert(n<512);if((unsigned int)n>maxrow)maxrow=n;rows++;
 if(!silent)fputs(b,stdout);}
#define pr_info row
'''

SUFFIX = r'''
static unsigned int checks;
static void check(u32 word,bool complete,bool expected){
 assert(gfx_runtime_active_word(word,complete)==expected);checks++;
}
static void wrapper(u32 word,u32 valid,bool domain,bool expected){
 unsigned int before=rows;
 assert(gfx_native_runtime_active("cold-guard",valid,domain,word)==expected);
 assert(rows==before+1);checks++;
}
int main(int argc,char **argv){
 assert(argc==2);
 if(strcmp(argv[1],"matrix")){
  gfx_native_fender_enable_complete=strcmp(argv[1],"strict-ff")!=0;
  gfx_native_fender_enable_attempted=gfx_native_fender_enable_complete;
  u32 word=0;
  if(!strcmp(argv[1],"strict-ff"))word=0x1f0003ffU;
  else if(!strcmp(argv[1],"dynamic-auto-0"))word=0x1000030fU;
  else if(!strcmp(argv[1],"dynamic-auto-4"))word=0x1400034fU;
  else if(!strcmp(argv[1],"dynamic-auto-f"))word=0x1f0003ffU;
  else assert(!"unknown fixture");
  wrapper(word,1,true,true);
  assert(rows==1);fprintf(stderr,"PASS %s checks=%u maxrow=%u\n",argv[1],checks,maxrow);return 0;
 }
 silent=true;
 /* Before enable, the exact inherited static-FF mask remains authoritative. */
 check(0x1f0003ffU,false,true);check(0x0f0000ffU,false,true);
 check(0x1400034fU,false,false);check(0x1000030fU,false,false);
 for(unsigned int bit=0;bit<32;bit++)if((0x80001cffU>>bit)&1U)
  check(0x1f0003ffU^(1U<<bit),false,false);
 /* Independent categorical matrix: the only legal actual states are0/4/f;
  * gated0/4 require AUTO, TARGETf and all four blocked controls clear. */
 for(unsigned int actual=0;actual<16;actual++)
  for(unsigned int target=0;target<16;target++)
   for(unsigned int automatic=0;automatic<2;automatic++){
    u32 word=0x04000300U|(actual<<4)|target|(automatic<<28);
    bool expected=target==15 && (actual==15 || (automatic&&(actual==0||actual==4)));
    check(word,true,expected);
   }
 unsigned int states[]={0,4,15},blocked[]={10,11,12,31};
 for(unsigned int s=0;s<3;s++)for(unsigned int b=0;b<4;b++)
  check(0x1000030fU|(states[s]<<4)|(1U<<blocked[b]),true,false);
 /* PS_AUTO and MIN are observations, not a fabricated coupling predicate. */
 for(unsigned int a=0;a<16;a++)for(unsigned int m=0;m<16;m++)
  check(0x1000034fU|(a<<24)|(m<<16),true,true);
 check(UINT32_MAX,false,false);check(UINT32_MAX,true,false);
 gfx_native_fender_enable_complete=false;gfx_native_fender_enable_attempted=false;
 wrapper(0x1f0003ffU,1,true,true);wrapper(0x1400034fU,1,true,false);
 wrapper(0x1f0003ffU,0,true,false);wrapper(0x1f0003ffU,1,false,false);
 gfx_native_fender_enable_attempted=true;
 wrapper(0x1f0003ffU,1,true,false);
 gfx_native_fender_enable_complete=true;
 wrapper(0x1400034fU,1,true,true);wrapper(0x1000030fU,1,true,true);
 wrapper(0x1f0003ffU,1,true,true);wrapper(0x0f0003ffU,1,true,true);
 wrapper(0x0400034fU,1,true,false);wrapper(0x14000b4fU,1,true,false);
 gfx_native_fender_enable_unknown=true;
 wrapper(0x1f0003ffU,1,true,false);wrapper(0x1400034fU,1,true,false);
 gfx_native_fender_enable_complete=false;
 wrapper(0x1f0003ffU,1,true,false);
 /* Every original application/control/idle/live operand remains required. */
 for(unsigned int failure=0;failure<13;failure++){
  u64 counter=0;u32 phase=0,host=0,state=0,flag=0,c[3]={33,33,33},trace=3;
  bool idle_required=true,idle=true,live=true;
  if(failure==1)counter=UINT64_MAX;if(failure==2)phase=1;
  if(failure==3)host=1;if(failure==4)state=1;if(failure==5)flag=1;
  if(failure>=6&&failure<=8)c[failure-6]=34;if(failure==9)trace=4;
  if(failure==10)idle=false;if(failure==11)live=false;
  if(failure==12){idle=false;idle_required=false;}
  unsigned int before=rows;
  bool good=failure==0||failure==12;
  assert(gfx_runtime_application_guard(33,3,idle_required,idle,live,counter,phase,host,state,flag,c,trace)==good);
  assert(rows==before+(good?0:1));checks++;
 }
 assert(maxrow<512);
 fprintf(stdout,"PASS matrix checks=%u rows=%u maxrow=%u\n",checks,rows,maxrow);return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--helper', type=Path, default=HERE/'gfx-native-runtime-state.h')
    ap.add_argument('--output', type=Path, default=ROOT/'out/gfx-native-fender-runtime-cycle/runtime-qualification-v1.json')
    args = ap.parse_args()
    helper, output = args.helper.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    actual, tester = output.with_suffix('.actual-helper.c'), output.with_suffix('.tester.py')
    actual.write_text(PREFIX+helper.read_text()+SUFFIX)
    tester.write_bytes(Path(__file__).read_bytes())
    fixtures = {}
    invocations = []
    with tempfile.TemporaryDirectory(prefix='m4rch-fender-runtime-') as tmp:
        binary = Path(tmp)/'actual-helper'
        argv = ['cc', '-std=gnu11', '-O1', '-g', '-fsanitize=address,undefined',
                '-fno-omit-frame-pointer', str(actual), '-o', str(binary)]
        build = subprocess.run(argv, capture_output=True, text=True)
        if build.returncode:
            output.with_suffix('.build-failed.log').write_text(build.stderr)
            raise RuntimeError(build.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        for name in ('matrix', 'strict-ff', 'dynamic-auto-0', 'dynamic-auto-4', 'dynamic-auto-f'):
            result = subprocess.run([str(binary), name], env=env, capture_output=True, text=True)
            if result.returncode:
                output.with_suffix('.'+name+'.failed.log').write_text(result.stdout+result.stderr)
                raise RuntimeError(result.stderr)
            invocations.append(dict(name=name, returncode=result.returncode,
                                    stdout=result.stdout, stderr=result.stderr))
            if name != 'matrix':
                fixture = output.with_suffix('.'+name+'.log')
                fixture.write_text(result.stdout)
                fixtures[name] = dict(path=str(fixture), sha256=sha(fixture))
        matrix = invocations[0]['stdout']
        checks = int(matrix.split('checks=')[1].split()[0])+4
    pins = [dict(path=str(p), sha256=sha(p)) for p in (helper, tester, actual)]
    receipt = dict(schema='m4rch.gfx-native-fender-runtime-state.actual-c-qualification.v1',
                   passed=True, cases_passed=checks, case_count=checks,
                   helper_sha256=sha(helper), input_pins=pins,
                   compile_argv=argv, compiler_returncode=build.returncode,
                   sanitizer='address,undefined', invocations=invocations,
                   success_log_fixtures=fixtures, hardware_actions=[],
                   qualification='Actual read-only C helper CPU matrix; not MMIO, runtime hardware timing, GPU execution, power completion or retirement proof.')
    with output.open('x') as f:
        f.write(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), sha256=sha(output), cases_passed=checks,
                          helper_sha256=sha(helper), fixtures=fixtures)))


if __name__ == '__main__':
    main()
