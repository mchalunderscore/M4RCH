#!/usr/bin/env python3
"""Qualify actual cold C admission/control/publication/stop using RAM services.

Hardware/cache primitives are intercepted. Unchanged allocation/context/RX/native
coordinator history is composed from frozen v12 qualifications, not rerun.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FROZEN_Q=ROOT/'out/gfx-native-ap-repeat-cycle/owner-qualification-v8.json'
FROZEN_Q_SHA='68f5f2de51794d7c93cd6c4b077a4e023605b9266266db8b114290769ff99776'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def extract(text,marker):
 a=text.index(marker);b=text.index('{',a);i=b+1;depth=1
 while depth:
  depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[a:i]
def cache_intercept(text):return re.sub(r'asm volatile\([\s\S]*?\);','mock_cache();',text)

PREFIX=r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define BIT_ULL(n) (1ULL<<(n))
#define GENMASK_ULL(h,l) ((~0ULL<<(l))&(~0ULL>>(63-(h))))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof(*(x)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define PAGE_SIZE 16384U
#define __iomem
#define GFX_COLD_RENDER_TRIAL 1
#define GFX_NATIVE_STATUS_ZERO_TRIAL 1
#define GRAPH_JOINED_INIT_EXPERIMENT 1
#define GRAPH_RECOVERY_EXPERIMENT 1
#define EMPTY BIT(17)
#define START BIT(4)
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
#undef static_assert
#define static_assert(x) _Static_assert(x,#x)
#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))
#include "graph-contract.h"
#include "job-data.h"
#include "render-data.h"
#include "recovery-contract.h"
/* ACTUAL_PAGE_MACROS */
struct page {u64 pa;u8 data[PAGE_SIZE];};
struct fake_power {int usage_count,runtime_status,runtime_error;};
struct fake_dev {struct fake_power power;bool enabled,active,suspended;};
struct platform_device {struct fake_dev dev;};
struct apple_pmgr_gfx_reset_observation {u32 before,valid;bool domain_on;int operation_error,cleanup_error;};
static struct page page_storage[174],*owned[174];
static struct platform_device consumer_storage,*consumer=&consumer_storage;
static char asc_memory[4096],mbox_memory[4096];
static void *asc=asc_memory,*mbox=mbox_memory;
static u64 root_word,*target_slot=&root_word,*target_page=&root_word,*bootstrap=&root_word,*borrowed_l1;
static bool held,asc_region,mbox_region,started,installed,root_sent,root_detached,device_context_retained;
static bool resident_session,recovery_resident,recovery_work_submitted;
static int graph_io_lock;
static unsigned long jiffies;
static unsigned int gfx_cold_sample_index,gfx_cold_elapsed_ms;
static unsigned long gfx_cold_sample_jiffies;
static bool gfx_cold_fault_valid;
static u64 gfx_cold_fault_info,gfx_cold_fault_addr;
static const unsigned int gfx_cold_current_epoch=1;
static const char *fault;
static unsigned int messages_sent,control_notifies,draw_notifies,root_notifies,endpoint_starts;
static unsigned int firmware_step,cache_calls,clean_records,physical_calls,diag_hw_reads;
static bool cold_phase,mailbox_pending,control_pending,draw_pending;
static u64 mailbox_message,mailbox_metadata,tx_message;
static bool is(const char *s){return !strcmp(fault,s);}
static char logs[2097152];static size_t log_used;static unsigned int maximum_log_row;
static void inject(const char *row);
static void pr_info(const char *fmt,...)
{
 va_list ap;va_start(ap,fmt);int n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);
 assert(n>0&&(size_t)n<sizeof(logs)-log_used&&logs[log_used+n-1]=='\n');
 assert(n<=511);if((unsigned int)n>maximum_log_row)maximum_log_row=n;
 char saved[512];memcpy(saved,logs+log_used,(size_t)n);saved[n]=0;
 printf("[ %10.6f] %s",(double)jiffies/1000.0,saved);
 log_used+=(size_t)n;inject(saved);
}
#define pr_err pr_info
#define pr_warn pr_info
static void mock_cache(void){cache_calls++;}
static void *page_address(struct page *p){assert(p);return p->data;}
static u64 page_to_phys(struct page *p){assert(p);return p->pa;}
static void recovery_invalidate(void *p,size_t n){assert(p&&n);cache_calls++;}
static void recovery_clean(void *p,size_t n);
static int atomic_read(int *p){return *p;}
static bool pm_runtime_enabled(struct fake_dev *d){return d->enabled;}
static bool pm_runtime_active(struct fake_dev *d){return d->active;}
static bool pm_runtime_suspended(struct fake_dev *d){return d->suspended;}
static unsigned long msecs_to_jiffies(unsigned int m){return m;}
static unsigned int jiffies_to_msecs(unsigned long j){return (unsigned int)j;}
static bool time_before(unsigned long a,unsigned long b){return (long)(a-b)<0;}
static bool time_after_eq(unsigned long a,unsigned long b){return !time_before(a,b);}
static void lockdep_assert_held(int *p){assert(p==&graph_io_lock&&*p==1);}
static void mutex_lock(int *p){assert(*p==0);*p=1;}
static void mutex_unlock(int *p){assert(*p==1);*p=0;}
static bool sysfs_streq(const char *a,const char *b){return !strcmp(a,b);}
static u32 get_unaligned_le32(const void *p){u32 v;memcpy(&v,p,4);return v;}
static u16 get_unaligned_le16(const void *p){u16 v;memcpy(&v,p,2);return v;}
static void wmb(void){mock_cache();}
static void mock_progress(void);
static void usleep_range(unsigned int a,unsigned int b)
{assert(a==1000&&b>=a);if(!is("observe-clock-stalled")||!draw_pending)jiffies++;mock_progress();}
static u32 readl(void *p);
static u64 readq(void *p);
static void writeq(u64 v,void *p);
static unsigned char ksm_memory[0x4000],identity_memory[0x4000],primary_memory[0x4000];
static unsigned char fault_memory[0x4000],prc_memory[0x4000],engine_memory[0x4000];
static void *ioremap(u64 base,size_t size)
{
 (void)size;diag_hw_reads++;
 if(base==0x288020000ULL)return draw_pending&&jiffies>=100&&is("post-ksm-map-missing")?NULL:ksm_memory;
 if(base==0x288d04000ULL)return identity_memory;
 if(base==0x288004000ULL)return primary_memory;
 if(base==0x288d4c000ULL)return prc_memory;
 if(base==0x288d44000ULL)return engine_memory;
 if(base==0x28800c000ULL)return is("fault-map-missing")||(draw_pending&&jiffies>=100&&is("post-fault-map-missing"))?NULL:fault_memory;
 assert(false);return NULL;
}
static void iounmap(void *p){assert(p);}
static bool gfx_coord_owner_module_pinned,gfx_coord_owner_startup_retained;
static bool gfx_coord_owner_pmp_region,gfx_coord_owner_pmc_region;
static void *gfx_coord_owner_pmp,*gfx_coord_owner_pmc;
static void gfx_coord_owner_pin(void){gfx_coord_owner_module_pinned=true;}
static bool gfx_coord_owner_retained(void){return gfx_coord_owner_startup_retained;}
static int gfx_coord_owner_prepare(void)
{
 if(is("coord-resource"))return -EBUSY;
 gfx_coord_owner_pmp_region=gfx_coord_owner_pmc_region=true;
 gfx_coord_owner_pmp=primary_memory;gfx_coord_owner_pmc=engine_memory;return 0;
}
static int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o)
{
 physical_calls++;o->valid=APPLE_PMGR_GFX_VALID_BEFORE;o->domain_on=true;o->before=0x1f0003ff;
 if(is("physical-missing"))o->valid=0;
 if(is("physical-busy"))o->before|=BIT(11);
 if(is("physical-error"))o->operation_error=-EIO;
 return 0;
}
'''

MOCK=r'''
static u64 ptd;static u32 votes[3];
static int mock_ptd_read(void *ctx,unsigned int index,u64 *payload,u64 *status)
{
 (void)ctx;*payload=index==GFX_COORD_REQUEST_ENTRY?ptd:0;*status=0;return 0;
}
static int mock_ptd_write(void *ctx,unsigned int index,u64 value)
{(void)ctx;assert(index==GFX_COORD_REQUEST_ENTRY);if(is("coord-request-error"))return -EIO;ptd=value;return 0;}
static int mock_vote_read(void *ctx,unsigned int index,u32 *value)
{(void)ctx;assert(index<3);*value=votes[index];return 0;}
static int mock_vote_write(void *ctx,unsigned int index,u32 value)
{(void)ctx;assert(index<3);if(!is("coord-vote-readback"))votes[index]=value;return 0;}
static u64 mock_now(void *ctx){(void)ctx;return jiffies*1000000ULL;}
static void mock_delay(void *ctx){(void)ctx;usleep_range(1000,1100);}
static const struct gfx_coord_ops gfx_coord_owner_ops={
 .read_ptd=mock_ptd_read,.write_ptd=mock_ptd_write,.read_vote=mock_vote_read,
 .write_vote=mock_vote_write,.now_ns=mock_now,.delay=mock_delay,.event=gfx_coord_owner_event};
static u32 mem32(unsigned int o){u32 v;memcpy(&v,recovery_ptr(o),4);return v;}
static void fw32(unsigned int o,u32 v){memcpy(recovery_ptr(o),&v,4);}
static void recovery_clean(void *p,size_t n)
{
 cache_calls++;
 if(n==24 && (p==recovery_ptr(recovery_work_rings[0]) || p==recovery_ptr(recovery_work_rings[1]))) {
  unsigned int i=p==recovery_ptr(recovery_work_rings[1]);
  assert(gfx_cold_draw_intent&&gfx_cold_record_attempted[i]);
  assert(!memcmp(p,recovery_work_records[i],24));clean_records++;
 }
 if(p==recovery_ptr(RECOVERY_CONTROL+16)) {
  assert(gfx_cold_control_intent&&gfx_cold_control_producer_attempted&&mem32(RECOVERY_TRACE_MASK)==0);
  if(is("control-producer-drop"))fw32(RECOVERY_CONTROL+16,32);
 }
 for(unsigned int i=0;i<2;i++) if(p==recovery_ptr(recovery_work_cursors[i]+16)) {
  assert(gfx_cold_draw_intent&&gfx_cold_record_cleaned[i]&&gfx_cold_producer_attempted[i]);
  if((i==0&&is("producer0-drop"))||(i==1&&is("producer1-drop")))fw32(recovery_work_cursors[i]+16,0);
 }
 if(p==recovery_ptr(RECOVERY_TRACE_MASK)&&is("trace-drop"))fw32(RECOVERY_TRACE_MASK,3);
}
static u32 readl(void *p)
{
 if(p==(char*)mbox+0x110) {
  if((cold_phase&&is("cold-tx-full")) ||
     (gfx_cold_control_intent&&!gfx_cold_draw_intent&&is("control-tx-full")) ||
     (gfx_cold_draw_intent&&is("draw-tx-full")))return BIT(16);
  return 0;
 }
 if(p==(char*)mbox+0x114)return mailbox_pending?0:EMPTY;
 u32 value;memcpy(&value,p,4);return value;
}
static u64 readq(void *p)
{
 if(p==(char*)mbox+0x830){assert(mailbox_pending);return mailbox_message;}
 if(p==(char*)mbox+0x838){assert(mailbox_pending);mailbox_pending=false;return mailbox_metadata;}
 u64 value;memcpy(&value,p,8);return value;
}
static void writeq(u64 v,void *p)
{
 if(p==(char*)mbox+0x800){tx_message=v;return;}
 assert(p==(char*)mbox+0x808);messages_sent++;
 if(cold_phase) {
  assert(v==0&&tx_message==GFX_COLD_AP_ON&&gfx_ap_cold_request_write_attempted);
  mailbox_message=is("cold-reply-word")?GFX_COLD_AP_ON^0x10000:GFX_COLD_AP_ON;
  mailbox_metadata=is("cold-reply-meta")?1:0;mailbox_pending=true;return;
 }
 if((tx_message>>52)==5) {assert((v==0)&&endpoint_starts<2);endpoint_starts++;return;}
 if(v==32){assert(tx_message==0x00810c2000100000ULL&&endpoint_starts==2);root_notifies++;return;}
 assert(v==33);
 if(tx_message==0x0084000000000000ULL) {
  assert(gfx_cold_control_notify_attempted&&gfx_cold_control_producer_attempted);
  assert(mem32(RECOVERY_CONTROL+16)==33&&mem32(RECOVERY_TRACE_MASK)==0);
  control_notifies++;assert(control_notifies==1);control_pending=true;
 } else {
  assert(tx_message==0x0083000000000000ULL&&gfx_cold_draw_notify_attempted);
  assert(clean_records==2&&gfx_cold_producer_verified[0]&&gfx_cold_producer_verified[1]);
  draw_notifies++;assert(draw_notifies==1);draw_pending=true;
 }
}
static void mock_progress(void)
{
 firmware_step++;
 if(!gfx_cold_control_intent&&!is("initial-control-timeout")) {
  fw32(RECOVERY_CONTROL,32);fw32(RECOVERY_CONTROL+8,32);
 }
 if(control_pending&&!is("control-timeout")&&!is("control-stale32")&&
    (!is("control-late33")||jiffies>=GFX_COLD_CONTROL_TIMEOUT_MS)) {
  fw32(RECOVERY_CONTROL,33);fw32(RECOVERY_CONTROL+8,is("control-prefetch-stale")?32:33);
  if(is("control-cursor-ahead"))fw32(RECOVERY_CONTROL,34);
  control_pending=false;
 }
 if(draw_pending&&is("post-device-fault")) {
  u64 info=7,address=0x850000000ULL;memcpy(fault_memory+0x18c0,&info,8);memcpy(fault_memory+0x18c8,&address,8);
 }
 if(draw_pending&&is("post-rx-crash")){mailbox_pending=true;mailbox_message=0xdead;mailbox_metadata=1;}
}
static void inject(const char *row)
{
 if(strstr(row,"m4rch gfx-cold-render: phase=control-intent ")) {
  if(is("intent-identity"))owned[2]->pa^=0x4000;
  if(is("intent-request"))fw32(RECOVERY_REQUEST+4,1);
 }
 if(strstr(row,"m4rch gfx-cold-render: phase=control-ready ")) {
  if(is("ready-identity"))root_word^=0x4000;
  if(is("ready-request"))fw32(RECOVERY_REQUEST,2);
  if(is("ready-target"))owned[RENDER_FIRST_PAGE+20]->data[0]^=1;
 }
 if(strstr(row,"m4rch gfx-cold-render: phase=draw-intent ")) {
  if(is("draw-intent-identity"))owned[3]->pa^=0x4000;
  if(is("draw-intent-target"))owned[RENDER_FIRST_PAGE+20]->data[0]^=1;
 }
 if(strstr(row,"m4rch gfx-cold-render-record: phase=record-cleaned index=0 ")&&is("record0-ownership"))consumer->dev.power.runtime_error=-EIO;
 if(strstr(row,"m4rch gfx-cold-render-record: phase=producer-published index=0 ")&&is("producer0-ownership"))held=false;
 if(strstr(row,"m4rch gfx-cold-render: phase=draw-published ")) {
  if(is("post-journal-full")) {
   receive_journal.used=RECEIVE_CAPACITY;
   fw32(receive_rings[0].state+0x20,1);
  }
  if(is("post-unsupported-event")) {
   fw32(receive_rings[0].ring,2);fw32(receive_rings[0].state+0x20,1);
  }
 }
}
static bool crashlog_boot(void){cold_phase=true;return true;}
static int root_prepare(bool install){assert(install);cold_phase=false;installed=true;return 0;}
static int graph_snapshot_create(void){return 0;}
static int joined_context_attach(void){device_context_retained=true;return 0;}
'''

MAIN=r'''
static void setup(void)
{
 for(unsigned int i=0;i<174;i++){owned[i]=&page_storage[i];owned[i]->pa=0x100000000ULL+i*PAGE_SIZE;}
 for(unsigned int i=0;i<69;i++)memcpy(owned[2+i]->data,graph_bytes+i*PAGE_SIZE,PAGE_SIZE);
 for(unsigned int i=0;i<POOL_PAGES;i++) {
  unsigned int offset=i*PAGE_SIZE,n=sizeof(job_bytes)>offset?sizeof(job_bytes)-offset:0;
  if(n>PAGE_SIZE)n=PAGE_SIZE;if(n)memcpy(owned[POOL_FIRST_PAGE+i]->data,(u8*)job_bytes+offset,n);
 }
 for(unsigned int i=0;i<RENDER_BACKING_PAGES;i++)memcpy(owned[RENDER_FIRST_PAGE+i]->data,render_bytes+i*PAGE_SIZE,PAGE_SIZE);
 consumer_storage.dev=(struct fake_dev){.power={.usage_count=1},.enabled=true,.active=true};
 held=asc_region=mbox_region=resident_session=true;
 root_word=owned[0]->pa|3;
 fw32(RECOVERY_CONTROL,32);fw32(RECOVERY_CONTROL+8,32);
 if(is("initial-control-timeout")||is("initial-control-delayed")){fw32(RECOVERY_CONTROL,0);fw32(RECOVERY_CONTROL+8,0);}
 if(is("baseline-work"))fw32(recovery_work_cursors[3]+16,1);
 if(is("baseline-active-ta"))fw32(RECOVERY_STATUS+0x40b8,9);
 if(is("baseline-phase"))fw32(RECOVERY_STATUS+0x4900,2);
 if(is("baseline-host-stop"))fw32(RECOVERY_STATUS+0x4910,1);
 if(is("baseline-request"))fw32(RECOVERY_REQUEST+4,1);
 if(is("baseline-counter")){u64 v=1;memcpy(recovery_ptr(RECOVERY_STATUS+0x48f0),&v,8);}
 if(is("baseline-control-record"))((u8*)recovery_ptr(GFX_COLD_CONTROL_RECORD))[1]=1;
 if(is("baseline-target"))owned[RENDER_FIRST_PAGE+20]->data[0]^=1;
 if(is("baseline-job"))owned[POOL_FIRST_PAGE]->data[0]^=1;
 if(is("baseline-trace"))fw32(RECOVERY_TRACE_MASK,1);
 if(is("baseline-usage"))consumer->dev.power.usage_count=2;
 if(is("baseline-pm-error"))consumer->dev.power.runtime_error=-EIO;
 if(is("power38-zero"))fw32(RECOVERY_POWER+0x38,0);
 if(is("power38-one"))fw32(RECOVERY_POWER+0x38,1);
 if(is("raw-registers-nonzero")){memset(primary_memory,0xff,sizeof(primary_memory));memset(prc_memory,0xff,sizeof(prc_memory));memset(engine_memory,0xff,sizeof(engine_memory));}
}
int main(int argc,char **argv)
{
 setvbuf(stdout,NULL,_IONBF,0);
 assert(argc==2);fault=argv[1];setup();
 assert(gfx_cold_startup_admission(1,false,false,false,false)==0);
 assert(gfx_cold_startup_admission(2,true,false,false,false)==0);
 assert(gfx_cold_startup_admission(2,true,true,false,false)==-EINVAL);
 int ret=gfx_coord_owner_begin_on();
 if(!ret){started=true;ret=actual_automatic_entry();}
 if(!strcmp(fault,"success")||!strcmp(fault,"initial-control-delayed")||is("power38-zero")||is("power38-one")||is("raw-registers-nonzero")||is("row-bound")) {
  assert(!ret&&gfx_cold_complete&&gfx_cold_draw_notify_sent&&control_notifies==1&&draw_notifies==1);
  assert(gfx_cold_observation_samples==6&&gfx_cold_software_stopped&&gfx_cold_sealed&&!receive_enabled);
  assert(held&&consumer->dev.power.usage_count==1&&gfx_cold_identities_preserved);
  assert(gfx_cold_counter==0&&gfx_cold_phase==0&&gfx_cold_host_stop==0);
  assert(gfx_cold_ready_control[0]==33&&gfx_cold_ready_control[1]==33&&gfx_cold_ready_control[2]==33);
 } else {
  assert(ret || !gfx_cold_complete);
  assert(!gfx_cold_complete);
  if(gfx_cold_pipeline_intent)assert(gfx_cold_software_stopped&&gfx_cold_sealed&&!receive_enabled);
 }
 if(strstr(fault,"control-")||strstr(fault,"baseline-")||strstr(fault,"intent-")||strstr(fault,"ready-")||strstr(fault,"cold-")||strstr(fault,"coord-")||strstr(fault,"physical-")) {
  if(strcmp(fault,"initial-control-delayed")&&strcmp(fault,"draw-intent-identity")&&strcmp(fault,"draw-intent-target"))assert(!draw_notifies);
 }
 if(gfx_cold_pipeline_intent) {
  unsigned int before=messages_sent,used=receive_journal.used;
  int outcome=gfx_cold_terminal_result;const char *refusal=gfx_cold_refusal;
  mutex_lock(&graph_io_lock);assert(gfx_cold_run()==-EALREADY);
  assert(gfx_cold_diagnostic("submit")==-EPERM);assert(gfx_cold_diagnostic("recover")==-EPERM);
  assert(gfx_cold_diagnostic("gfx-powergate")==-EPERM);assert(gfx_cold_diagnostic("sample")==0);
  mutex_unlock(&graph_io_lock);
  assert(messages_sent==before&&receive_journal.used==used&&gfx_cold_terminal_result==outcome&&gfx_cold_refusal==refusal);
 }
 assert(control_notifies<=1&&draw_notifies<=1&&root_notifies<=1);
 if(root_notifies)assert(cache_calls>0);
 if(is("row-bound")) {
  gfx_cold_counter=UINT64_MAX;gfx_cold_phase=gfx_cold_host_stop=gfx_cold_request_state=gfx_cold_request_flag=UINT32_MAX;
  for(unsigned int i=0;i<3;i++)gfx_cold_control[i]=gfx_cold_baseline_control[i]=gfx_cold_ready_control[i]=UINT32_MAX;
  gfx_cold_trace_before=gfx_cold_trace_after=gfx_cold_control_polls=gfx_cold_observe_polls=gfx_cold_observation_samples=UINT32_MAX;
  gfx_cold_sample_index=gfx_cold_elapsed_ms=UINT32_MAX;gfx_cold_sample_jiffies=~0UL;
  gfx_cold_terminal_result=INT32_MIN;gfx_cold_log("diagnostic-cached",INT32_MIN);
 }
 printf("PASS %s control=%u draw=%u samples=%u retained=%u maxrow=%u\n",fault,control_notifies,draw_notifies,gfx_cold_observation_samples,gfx_cold_retained_pages(),maximum_log_row);
 return 0;
}
'''

CASES=['success','initial-control-delayed','power38-zero','power38-one','raw-registers-nonzero','row-bound','initial-control-timeout','baseline-work','baseline-active-ta','baseline-phase','baseline-host-stop','baseline-request','baseline-counter','baseline-control-record','baseline-target','baseline-job','baseline-trace','baseline-usage','baseline-pm-error','physical-missing','physical-busy','physical-error','coord-resource','coord-request-error','coord-vote-readback','cold-tx-full','cold-reply-word','cold-reply-meta','control-timeout','control-stale32','control-prefetch-stale','control-cursor-ahead','control-late33','control-tx-full','control-producer-drop','trace-drop','intent-identity','intent-request','ready-identity','ready-request','ready-target','draw-intent-identity','draw-intent-target','record0-ownership','producer0-ownership','producer0-drop','producer1-drop','draw-tx-full','post-device-fault','post-rx-crash','post-journal-full','post-unsupported-event','fault-map-missing','post-ksm-map-missing','post-fault-map-missing','observe-clock-stalled']

def make_harness(source):
 primitives=(source/'recovery-cycle.h').read_text();owner=(source/'asc-graph-init.c').read_text();coord=(source/'gfx-coordinate-owner.h').read_text()
 macros='\n'.join(x for x in (source/'command-pool-map.h').read_text().splitlines() if x.startswith('#define '))
 macros+='\n'+'\n'.join(x for x in (source/'render-backing-map.h').read_text().splitlines() if x.startswith('#define '))
 out=PREFIX.replace('/* ACTUAL_PAGE_MACROS */',macros)
 out+='\n'+(source/'gfx-cold-startup.h').read_text()
 out+='\n'+(source/'gfx-cold-ap.h').read_text()
 out+='\n'+(source/'gfx-cold-runtime.h').read_text().replace('#include <linux/soc/apple/pmgr-gfx-reset.h>','')
 for marker in ['static void *recovery_ptr(','static u32 recovery_read32(','static u64 recovery_read64(','static void recovery_write32(']:out+='\n'+extract(primitives,marker)
 out+='\n'+(source/'receive-service.h').read_text().split('static ssize_t receive_read(')[0]
 out+='\n'+extract(primitives,'static bool recovery_messages(')+'\n'+extract(primitives,'static bool recovery_idle(')
 out+='\n'+(source/'gfx-coordinate-core.h').read_text()
 out+='\nstatic struct gfx_coord_session gfx_coord_owner_session;\nstatic struct gfx_coord_observation gfx_coord_owner_on,gfx_coord_owner_off;\nstatic unsigned int gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events;\n'
 out+='\n'+extract(coord,'static void gfx_coord_owner_event(')+'\n'+MOCK
 out+='\n'+extract(coord,'static int gfx_coord_owner_transition(')+'\n'+extract(coord,'static void gfx_coord_owner_log(')+'\n'+extract(coord,'static int gfx_coord_owner_begin_on(')
 # Mocks depend on actual fixed cold state fields, so provide forward declarations.
 fields=(source/'gfx-cold-render.h').read_text().split('static unsigned int gfx_cold_retained_pages(')[0]
 fields='\n'.join(x for x in fields.splitlines() if (not x.startswith('#') or x.startswith('#define ')) and not x.startswith('/*') and not x.startswith(' *') and not x.startswith(' */'))
 out=out.replace('\n'+MOCK,'\n'+fields+'\n'+MOCK)
 out+='\n'+cache_intercept(extract(owner,'static void ksm_status_sample('))
 out+='\n'+cache_intercept(extract(owner,'static void __maybe_unused joined_output_sample(')).replace('__maybe_unused ','')
 header=(source/'gfx-cold-render.h').read_text();out+='\n'+header[header.index('static unsigned int gfx_cold_retained_pages('):]
 out+='\n'+extract(owner,'static bool power_ack(unsigned int request, unsigned int reply, u16 state)')
 a=owner.index(' if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)');b=owner.index('\nfail:',a)
 entry=owner[a:b]
 out+='\nstatic int actual_automatic_entry(void){int ret=0;bool epmap=true;u32 appmap=3;u8 apps_started=0;if(false)goto stop_firmware;\n'+entry+'\n}\n'
 out+='\n'+MAIN
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
 if output.exists() or output.with_suffix('.actual-owner.c').exists():raise ValueError('Qualification output must be new')
 receipt_path=source/'cold-render-owner-source-receipt.json';r=json.loads(receipt_path.read_text())
 assert r['profile']['version']==13
 for pin in r['output_source_pins']:assert sha(source/pin['name'])==pin['sha256'],pin['name']
 assert sha(FROZEN_Q)==FROZEN_Q_SHA;frozen=json.loads(FROZEN_Q.read_text());assert frozen['passed']
 output.parent.mkdir(parents=True,exist_ok=True)
 harness_path=output.with_suffix('.actual-owner.c');harness_path.write_text(make_harness(source))
 snapshot=output.with_suffix('.tester.py');snapshot.write_bytes(Path(__file__).read_bytes())
 results=[];fixtures=[];maxrow=0
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 with tempfile.TemporaryDirectory(prefix='cold-render-c-q-') as td:
  binary=Path(td)/'owner'
  command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-unused-but-set-global','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(harness_path),'-o',str(binary)]
  c=subprocess.run(command,text=True,capture_output=True)
  if c.returncode:raise RuntimeError(c.stdout+'\n'+c.stderr)
  for case in CASES:
   x=subprocess.run([str(binary),case],text=True,capture_output=True,env=env)
   if x.returncode:raise RuntimeError(case+'\n'+x.stdout+'\n'+x.stderr)
   raw='\n'.join(row for row in x.stdout.splitlines() if 'm4rch ' in row)+'\n'
   path=output.with_suffix('.'+case+'.log');path.write_text(raw)
   fixtures.append(dict(case=case,path=str(path),sha256=sha(path),bytes=path.stat().st_size))
   last=x.stdout.splitlines()[-1];maxrow=max(maxrow,int(last.split('maxrow=')[1]))
   results.append(dict(case=case,returncode=x.returncode,stdout=last))
 pins=[dict(path=str(p),sha256=sha(p)) for p in [receipt_path,FROZEN_Q,harness_path,snapshot,Path(__file__).resolve()]]
 pins += [dict(path=str(source/pin['name']),sha256=pin['sha256']) for pin in r['output_source_pins']]
 report=dict(schema='m4rch.gfx-cold-render.actual-C-qualification.v1',passed=True,hardware_access=False,kernel_build=False,
  source_path=str(source),source_receipt_sha256=sha(receipt_path),case_count=len(results),cases=results,
  compiler=command,sanitizers=['address','undefined'],maximum_new_log_row_bytes=maxrow,
  actual_cold_power_ack=True,actual_cold_root_and_automatic_pipeline=True,actual_native_on_core_and_admission=True,
  actual_cache_invalidation_call_sites=True,cache_instructions_intercepted=True,actual_receive_transport=True,
  once_control33_and_two_record_draw=True,unknown_partial_submission_retains_resources=True,
  stopped_receive_journal_and_no_delayed_worker=True,terminal_outcome_immutable_on_duplicate=True,
  frozen_unchanged_composition=dict(path=str(FROZEN_Q),sha256=FROZEN_Q_SHA,case_count=frozen['case_count'],rerun=False,
   scope='Unchanged allocation/context/native coordination/RX/draw history; retained E2/E3 management is preserved, not part of cold render.'),
  success_log_fixture=fixtures[0],actual_log_fixtures=fixtures,input_pins=pins,
  qualification='Actual production cold C functions with RAM page/MMIO/physical/PM/cache services. Allocation/context/OF/resource services remain mocked and composed. No firmware/device execution, actual cache instruction behavior, rendered pixels, retirement or hardware timing proved.')
 with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(path=str(output),sha256=sha(output),case_count=len(results),maxrow=maxrow,success_fixture=fixtures[0])))

if __name__=='__main__':main()
