import json,hashlib,subprocess
from pathlib import Path
root=Path('/home/alice/Desktop/m4rch');base=root/'out/gfx-native-full-power-trial-v24/prepared-owner-v6';out=root/'out/gfx-native-full-power-root-release-v6-qualification';out.mkdir(exist_ok=False)
x=(base/'graph-map.h').read_text();fn=x[x.index('static void root_release(void)'):x.index('static int gfx_full_power_graph_prepare(void);')]
raw=(base/'full-power-timestamp-map.h').read_text();raw=raw[:raw.index('static void gfx_full_power_timestamp_invalidate(void)')]
(out/'timestamp.h').write_text(raw);(out/'full-power-timestamp-contract.h').write_bytes((base/'full-power-timestamp-contract.h').read_bytes());(out/'root-release.h').write_text(fn)
s=r'''#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
typedef uint64_t u64;typedef uint8_t u8;
#define PAGE_SIZE 0x4000UL
#define ROOT_VA 0xfffffc2000100000ULL
#define PA_MASK ((((1ULL<<42)-1))&~(PAGE_SIZE-1))
#define FW_GRAPH_RW ((1ULL<<55)|(1ULL<<54)|(1ULL<<10)|(1ULL<<6)|8ULL|3ULL)
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define EFFECTIVE_MAPPED_PAGES 123
#define pr_info(...) ((void)0)
struct page {u64 pa;u64 words[2048];};static struct page pages[176];static struct page *owned[176];
static u64 *bootstrap,*borrowed_l1,*target_page,*target_slot;
static bool installed,root_sent,root_detached,device_context_retained;
static unsigned int freed,unmapped,cleaned,invalidated;
static void *page_address(struct page*p){return p->words;}
static u64 page_to_phys(struct page*p){return p->pa;}
static u64 get_unaligned_le64(void*p){u64 x;memcpy(&x,p,8);return x;}
static void put_unaligned_le64(u64 x,void*p){memcpy(p,&x,8);}
static void *pool_graph_cpu(u64 *l2,u64 va,unsigned int size){(void)l2;(void)va;(void)size;return pages[4].words;}
#include "timestamp.h"
static void clean_page(void*p){(void)p;cleaned++;}
static void invalidate_root_va(void){invalidated++;}
static void memunmap(void*p){(void)p;unmapped++;}
static void __free_pages(struct page*p,unsigned int n){(void)p;(void)n;freed++;}
#include "root-release.h"
static u64 parent[2048],boot[2048],snapshot[2048];
static void reset(bool borrowed){
 memset(pages,0,sizeof(pages));for(unsigned int i=0;i<176;i++){pages[i].pa=0x100000000ULL+i*PAGE_SIZE;owned[i]=&pages[i];}
 for(unsigned int i=0;i<2048;i++)parent[i]=0xface000000000000ULL+i*PAGE_SIZE;
 memset(boot,0,sizeof(boot));bootstrap=boot;borrowed_l1=borrowed?parent:NULL;
 target_page=borrowed?parent:boot;target_slot=target_page+(borrowed?0:2);*target_slot=pages[borrowed?1:0].pa|3;
 installed=true;root_sent=false;root_detached=false;device_context_retained=false;freed=unmapped=cleaned=invalidated=0;
 gfx_full_power_timestamp_borrowed=borrowed?parent:NULL;gfx_full_power_timestamp_published=borrowed;if(borrowed)parent[192]=pages[174].pa|3;
 memcpy(snapshot,parent,sizeof(parent));
}
static void retained(void){assert(freed==0&&unmapped==0&&cleaned==0&&invalidated==0);for(unsigned int i=0;i<176;i++)assert(owned[i]==&pages[i]);assert(memcmp(parent,snapshot,sizeof(parent))==0);}
int main(void){
 for(unsigned int n=0;n<2;n++){
  reset(n);root_release();assert(freed==176);assert(unmapped==(n?2U:1U));assert(cleaned==1&&invalidated==1);assert(!installed);for(unsigned int i=0;i<176;i++)assert(!owned[i]);for(unsigned int i=0;i<2048;i++)if(!n||(i!=0&&i!=192))assert(parent[i]==snapshot[i]);if(n)assert(parent[0]==0&&parent[192]==0);else assert(boot[2]==0);
  reset(n);*target_slot^=0x4000;memcpy(snapshot,parent,sizeof(parent));u64 old=*target_slot;root_release();retained();assert(*target_slot==old);assert(installed);
  reset(n);target_slot=NULL;root_release();retained();
  reset(n);target_page=NULL;root_release();retained();
  reset(n);root_sent=true;root_release();retained();
  reset(n);device_context_retained=true;root_release();retained();
 }
 reset(true);parent[192]^=0x4000;memcpy(snapshot,parent,sizeof(parent));root_release();retained();assert(gfx_full_power_timestamp_published);
 reset(true);borrowed_l1=NULL;root_release();retained();
 /* Keep unrelated helpers referenced without repeating their qualification. */
 (void)gfx_full_power_timestamp_prepare;(void)gfx_full_power_timestamp_publish_borrowed;
 puts("2 valid release modes and 12 pre-mutation retention paths passed");return 0;
}
'''
(out/'test.c').write_text(s)
r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(out/'test.c'),'-o',str(out/'test')],capture_output=True,text=True);(out/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
r=subprocess.run([str(out/'test')],capture_output=True,text=True);(out/'run.stdout').write_text(r.stdout);assert r.returncode==0,r.stderr
pin=lambda p:dict(path=str(p.resolve()),bytes=len(p.read_bytes()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
report=dict(schema='m4rch.v24-root-release-qualification.v6',inputs=[pin(base/p) for p in ['graph-map.h','full-power-timestamp-map.h','full-power-timestamp-contract.h']]+[pin(Path(__file__))],actual_root_release_extracted=True,compile_result=0,run_result=0,valid_release_modes=2,retention_before_any_clear_free_unmap_paths=12,all_owned_pages=176,unrelated_borrowed_slots_preserved=True,previous_v5_blocker_closed=True,standalone_timestamp_qualification_repeated=False,hardware_actions=[],trial_ready=False)
(out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');(root/'docs/evidence/2026-10-11-v24-root-release-qualification-v6.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
