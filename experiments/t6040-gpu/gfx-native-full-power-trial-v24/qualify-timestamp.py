#!/usr/bin/env python3
"""Compile the actual timestamp PTE helpers with RAM-only host service shims."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[2]
def pin(p):
 p=Path(p).resolve();x=p.read_bytes();return dict(path=str(p),bytes=len(x),sha256=hashlib.sha256(x).hexdigest())
def qualify(out):
 out.mkdir(parents=True,exist_ok=False)
 raw=(KIT/'full-power-timestamp-map.h').read_text();pos=raw.index('static void gfx_full_power_timestamp_invalidate(void)')
 # No host execution of TLBI: only this architecture-specific leaf is replaced.
 (out/'full-power-timestamp-map.h').write_text(raw[:pos]+'static void gfx_full_power_timestamp_invalidate(void) {}\n')
 (out/'full-power-timestamp-contract.h').write_bytes((KIT/'full-power-timestamp-contract.h').read_bytes())
 code=r'''#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <assert.h>
typedef uint64_t u64;typedef uint8_t u8;
#define PAGE_SIZE 0x4000UL
#define ROOT_VA 0xfffffc2000100000ULL
#define PA_MASK ((((1ULL<<42)-1))&~(PAGE_SIZE-1))
#define FW_GRAPH_RW ((1ULL<<55)|(1ULL<<54)|(1ULL<<10)|(1ULL<<6)|8ULL|3ULL)
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define pr_info(...) ((void)0)
struct page {u64 pa;u64 words[2048];};
static struct page pages[176];static struct page *owned[176];
static void *page_address(struct page *p){return p->words;}
static u64 page_to_phys(struct page *p){return p->pa;}
static u64 get_unaligned_le64(void *p){u64 x;memcpy(&x,p,8);return x;}
static void put_unaligned_le64(u64 x,void *p){memcpy(p,&x,8);}
static void *pool_graph_cpu(u64 *l2,u64 va,unsigned int size){
 if(va!=ROOT_VA+0x8000||size!=0x30||l2[(va>>14)&2047]!=(pages[4].pa|FW_GRAPH_RW))return NULL;
 return page_address(owned[4]);
}
#include "full-power-timestamp-map.h"
static u64 *l1;static u64 l0[64],l2[2048],borrowed[2048],saved_borrowed[2048];
static void reset(unsigned int n){
 memset(pages,0,sizeof(pages));l1=pages[0].words;memset(l0,0,sizeof(l0));memset(l2,0,sizeof(l2));
 gfx_full_power_timestamp_borrowed=NULL;gfx_full_power_timestamp_published=false;
 for(unsigned int i=0;i<176;i++){pages[i].pa=0x100000000ULL+((u64)n<<24)+i*PAGE_SIZE;owned[i]=&pages[i];}
 l2[((ROOT_VA+0x8000)>>14)&2047]=pages[4].pa|FW_GRAPH_RW;
 l1[0]=pages[1].pa|3;l0[(ROOT_VA>>36)&63]=pages[0].pa|3;
 for(unsigned int i=0;i<2048;i++)borrowed[i]=0xdead000000000000ULL+i*4096;
 borrowed[192]=0;memcpy(saved_borrowed,borrowed,sizeof(borrowed));
}
int main(void){
 for(unsigned int n=0;n<64;n++){
  reset(n);assert(gfx_full_power_timestamp_prepare(l1,l2));
  assert(l1[0]==(pages[1].pa|3));assert(l1[192]==(pages[174].pa|3));
  u64 root_entry=l0[(FULL_POWER_TIMESTAMP_VA>>36)&63];assert((root_entry&PA_MASK)==pages[0].pa);
  u64 child_entry=pages[0].words[(FULL_POWER_TIMESTAMP_VA>>25)&2047];assert((child_entry&PA_MASK)==pages[174].pa);
  u64 leaf_entry=pages[174].words[(FULL_POWER_TIMESTAMP_VA>>14)&2047];assert((leaf_entry&PA_MASK)==pages[175].pa);
  assert(pages[174].words[((FULL_POWER_TIMESTAMP_VA+PAGE_SIZE)>>14)&2047]==0);
  assert(pages[174].words[1280]==(pages[175].pa|FW_GRAPH_RW));
  for(unsigned int i=0;i<2048;i++){assert(pages[175].words[i]==0);if(i!=1280)assert(pages[174].words[i]==0);if(i!=0&&i!=192)assert(l1[i]==0);}
  assert(get_unaligned_le64((u8*)pages[4].words+0x28)==FULL_POWER_TIMESTAMP_VA);
  assert(gfx_full_power_timestamp_borrowed_available(borrowed));assert(gfx_full_power_timestamp_publish_borrowed(borrowed));
  assert(!gfx_full_power_timestamp_publish_borrowed(borrowed));assert(gfx_full_power_timestamp_can_detach());
  for(unsigned int i=0;i<2048;i++)if(i!=192)assert(borrowed[i]==saved_borrowed[i]);
  assert(gfx_full_power_timestamp_remove_borrowed());assert(memcmp(borrowed,saved_borrowed,sizeof(borrowed))==0);
  assert(gfx_full_power_timestamp_remove_borrowed());gfx_full_power_timestamp_invalidate();
 }
 for(unsigned int n=0;n<7;n++){
  reset(n);if(n==0)l1[192]=3;if(n==1)pages[174].words[0]=1;if(n==2)pages[175].words[0]=1;
  if(n==3){pages[175].pa=pages[174].pa;}if(n==4){pages[175].pa|=1;}
  if(n==5){pages[4].words[5]=1;}if(n==6){l2[((ROOT_VA+0x8000)>>14)&2047]=0;}
  u64 oldhw=pages[4].words[5],oldl1=l1[192],oldtab=pages[174].words[1280];
  assert(!gfx_full_power_timestamp_prepare(l1,l2));assert(pages[4].words[5]==oldhw);assert(l1[192]==oldl1);assert(pages[174].words[1280]==oldtab);
 }
 reset(99);assert(gfx_full_power_timestamp_prepare(l1,l2));borrowed[192]=5;
 assert(!gfx_full_power_timestamp_borrowed_available(borrowed));assert(!gfx_full_power_timestamp_publish_borrowed(borrowed));assert(borrowed[192]==5);
 borrowed[192]=0;assert(gfx_full_power_timestamp_publish_borrowed(borrowed));borrowed[192]^=0x4000;
 u64 unexpected=borrowed[192];assert(!gfx_full_power_timestamp_can_detach());assert(!gfx_full_power_timestamp_remove_borrowed());assert(borrowed[192]==unexpected);assert(gfx_full_power_timestamp_published);
 puts("64 full PTE walks/publication/removal; 9 refusal/asymmetric-owner checks passed");return 0;
}
'''
 (out/'test.c').write_text(code)
 r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(out/'test.c'),'-o',str(out/'test')],capture_output=True,text=True);(out/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(out/'test')],capture_output=True,text=True);(out/'run.stdout').write_text(r.stdout);assert r.returncode==0,r.stderr
 native=ROOT/'docs/evidence/2026-10-11-gravity-native-queue-bindings-v7.json'
 if not native.exists():native=ROOT/'experiments/t6040-gpu/desktop-integration/t6040-native-boot/recover_queue_bindings_v7.py'
 report=dict(schema='m4rch.native-timestamp-ptes.v24',inputs=[pin(__file__),pin(KIT/'full-power-timestamp-contract.h'),pin(KIT/'full-power-timestamp-map.h'),pin(native),pin(ROOT/'out/gpu-gravity-normal-boot-v8/source/linux/drivers/gpu/drm/asahi/g16_fw.rs'),pin(ROOT/'out/gpu-gravity-normal-boot-v8/source/linux/drivers/gpu/drm/asahi/g16_runtime.rs'),pin(ROOT/'out/gpu-gravity-normal-boot-v8/source/linux/drivers/gpu/drm/asahi/pgtable.rs')],compile_result=0,run_result=0,full_pte_walk_cases=64,refusal_cases=9,borrowed_unrelated_entries_preserved=2047,owned_extra_pages=2,timestamp_backing_bytes=16384,virtual='0xfffffc2181400000',l0_index=2,l1_index=192,l2_index=1280,hardware_field='hardware+0x28',leaf_protection='same FW_SHARED_RW asnormalGravitymap_timestamp; uncached firmwareRW',native_binding=dict(store_pc='0x89aa404',selected_conversion='identity',conversion_entry='0x89c8ff8'),architecture_leaf='TLBI is omitted fromhost test; generatedARM64kernelowner mustcompile actualleaf andcall beforeDSB',scope='Actual C helpers and actualPTEcodec run inhostRAM; nohardware/firmware acceptance, cachevisibility orretirement proved',hardware_actions=[],trial_ready=False)
 (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);qualify(p.parse_args().output.resolve())
