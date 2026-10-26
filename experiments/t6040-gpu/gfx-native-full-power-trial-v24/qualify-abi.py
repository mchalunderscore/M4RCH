#!/usr/bin/env python3
"""Run the actual standalone AArch64 C/Rust ABI against full native RAM outputs."""
import argparse,json,subprocess
from pathlib import Path
from prepare import pin

def qualify(source,evidence,output):
 source=Path(source).resolve();evidence=Path(evidence).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
 receipt=json.loads((evidence/'qualification.json').read_text());tests=[]
 for case in receipt['cases']:
  index=case['index'];owners=case['owners'];maps=[owners[k] for k in ['primary_map','secondary_map']]
  words=[[values[2*i]|(values[2*i+1]<<16) for i in range(8)] for values in maps]
  tests.append('{ uint32_t pm[8]={'+','.join(str(v)+'u' for v in words[0])+'}, sm[8]={'+','.join(str(v)+'u' for v in words[1])+'};\n')
  tests.append(f'memset(p,0,sizeof(p));memset(h,0,sizeof(h));memset(r,0,sizeof(r));memset(a,0,sizeof(a)); memset(p+64+0x6530,{index+1},8);for(unsigned i=0;i<48;i++)p[64+0x2888+i]=(uint8_t)({index}+i);\n')
  tests.append('assert(m4rch_native_power_validate(pm,sm)==0);assert(m4rch_native_power_write(pm,sm,24,p+64,h+64,r+64,a+64,0xfffffc200014f000ULL,0xfffffc200012c000ULL,0xfffffc200014f100ULL)==0);\n')
  for name,var,size in [('power','p',0x6578),('hardware','h',0x2718),('region-c','r',0xe58),('aonptd','a',0xe4)]:
   tests.append(f'compare({json.dumps(str(evidence/f"case-{index}"/(name+"-native.bin")))},{var}+64,{size}); guard({var},{size});\n')
  tests.append('}\n')
 code='''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
extern int m4rch_native_power_validate(const uint32_t*,const uint32_t*);
extern int m4rch_native_power_write(const uint32_t*,const uint32_t*,uint64_t,uint8_t*,uint8_t*,uint8_t*,uint8_t*,uint64_t,uint64_t,uint64_t);
__attribute__((noreturn)) void m4rch_full_power_panic(void){abort();}
static uint8_t p[0x6578+128],h[0x2718+128],r[0xe58+128],a[0xe4+128];
static void compare(const char *path,uint8_t *actual,size_t n){FILE*f=fopen(path,"rb");assert(f);uint8_t*expected=malloc(n);assert(fread(expected,1,n,f)==n);fclose(f);for(size_t i=0;i<n;i++)if(actual[i]!=expected[i]){fprintf(stderr,"%s mismatch offset%zx %x %x\\n",path,i,actual[i],expected[i]);abort();}free(expected);}
static void guard(uint8_t*b,size_t n){for(unsigned i=0;i<64;i++)assert(b[i]==0 && b[n+64+i]==0);}
int main(void){
'''+''.join(tests)+'''
 uint32_t zero[8]={0};memset(p,0x77,sizeof(p));memset(h,0x77,sizeof(h));memset(r,0x77,sizeof(r));memset(a,0x77,sizeof(a));
 assert(m4rch_native_power_validate(zero,zero)==-22);
 assert(m4rch_native_power_validate(NULL,zero)==-22);
 assert(m4rch_native_power_write(zero,zero,24,p+64,h+64,r+64,a+64,0xfffffc200014f000ULL,0xfffffc200012c000ULL,0xfffffc200014f100ULL)==-22);
 for(unsigned i=0;i<sizeof(p);i++)assert(p[i]==0x77);
 for(unsigned i=0;i<sizeof(h);i++)assert(h[i]==0x77);
 for(unsigned i=0;i<sizeof(r);i++)assert(r[i]==0x77);
 for(unsigned i=0;i<sizeof(a);i++)assert(a[i]==0x77);
 assert(m4rch_native_power_write(NULL,zero,24,p,h,r,a,0,0,0)==-22);
 return 0;}
'''
 c=output/'abi-tests.c';c.write_text(code)
 cmd=['clang','-O2','-Wall','-Wextra','-Werror',str(c),str(source/'native-power-rust.o'),str(source/'rust-panic-shims.S'),'-o',str(output/'abi-tests')]
 compile=subprocess.run(cmd,capture_output=True,text=True);(output/'compile.log').write_text(compile.stdout+compile.stderr);assert compile.returncode==0,compile.stderr
 run=subprocess.run([str(output/'abi-tests')],capture_output=True,text=True);(output/'run.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
 dis=subprocess.check_output(['llvm-objdump','-d',str(source/'native-power-rust.o')],text=True)
 import re
 fp=[line for line in dis.splitlines() if '\t' in line and re.search(r'\b(?:q|s|d|v)[0-9]+\b',line.split('\t')[-1])]
 assert not fp,fp[:10]
 report=dict(schema='m4rch.native-power-c-rust-abi.v24',inputs=[pin(__file__),pin(c),pin(source/'native-power-rust.o'),pin(source/'rust-panic-shims.S'),pin(evidence/'qualification.json')],
             whole_native_components_agree=True,native_cases=len(receipt['cases']),guard_cases=2,rust_object_contains_fp_or_simd=False,
             compile_returncode=compile.returncode,run_returncode=run.returncode,hardware_actions=[],kernel_module_build=False)
 (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--evidence',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(qualify(a.source,a.evidence,a.output)))
