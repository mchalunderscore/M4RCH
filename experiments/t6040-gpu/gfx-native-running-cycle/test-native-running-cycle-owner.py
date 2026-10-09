#!/usr/bin/env python3
"""Actual native-ordered owner headers, stage-specific known6d gates and bounded logs; no hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;typedef uint32_t u32;typedef uint8_t u8;
#define GFX_NATIVE_RUNNING_CYCLE_TRIAL 1
#define GFX_NATIVE_POWERGATE_DRAIN_TRIAL 1
#define GFX_NATIVE_STATUS_ZERO_TRIAL 1
#define GFX_RESET_SCOPE_PAGES 174U
#define GFX_POWER_OFF_STATE_MASK 0x90001cffU
#define GFX_POWER_OFF_POLL_SAMPLES 101U
#define GFX_POWER_OFF_POLL_DELAY_US 1000U
#define BIT(n) (1U<<(n))
#define START BIT(4)
#define EMPTY BIT(17)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof(*(a)))
#define READ_ONCE(v) (v)
#define __iomem
#define RECOVERY_STATUS 0x100000U
#define RECOVERY_REQUEST 0x200000U
#define RECOVERY_CONTROL 0x300000U
#define RECOVERY_CONTROL_INITIAL 32U
#define RECOVERY_CONTROL_LAST 128U
#define RECEIVE_CAPACITY 65536U
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
struct page { u64 pa; };
struct fake_power { int usage_count,runtime_status,runtime_error; };
struct fake_device { struct fake_power power; bool enabled,active,suspended; };
struct platform_device { struct fake_device dev; } consumer_storage;
struct apple_pmgr_gfx_reset_observation { u32 before,valid; bool domain_on; };
static struct platform_device *consumer=&consumer_storage;
static char asc_storage[0x1000],mbox_storage[0x1000];
static void *asc=asc_storage,*mbox=mbox_storage;
static struct page page_storage[175],*owned[174];
static u64 root_storage[1],*bootstrap=root_storage,*borrowed_l1;
static u64 *target_page=root_storage,*target_slot=root_storage;
static bool installed,root_sent,root_detached,device_context_retained;
static bool held,recovery_resident,resident_session,asc_region,mbox_region;
static bool recovery_session_failed,recovery_work_submitted,receive_enabled,receive_crashed;
static struct { unsigned int used,status,doorbells; } receive_journal;
static bool gfx_reset_scope_owner_pinned,gfx_reset_scope_sealed,gfx_reset_scope_host_stopped;
static bool gfx_poweroff_gate_consumed,gfx_poweroff_pm_attempted;
static bool gfx_poweroff_provider_off_observed,gfx_poweroff_accounting_ok;
static bool gfx_poweroff_start_clear_attempted;
static int gfx_poweroff_pm_result,gfx_poweroff_snapshot_result;
static bool started;
static unsigned int recovery_completed_total,recovery_operation;
static int graph_io_lock,recovery_receive_work;
static unsigned long jiffies;
static const char *fault;
static unsigned int pmgets,pmputs,starts,cpuwrites,requests,hellos,mapacks,hostons;
static unsigned int hwreads,reads_after_put,diagcalls,firstcalls,cancels;
static u32 control44,status48;
static u64 messages[20],metadata[20];static unsigned int count,pos;
static unsigned int coordinate_on_calls,coordinate_off_calls;
static u64 ptd_request;static u32 votes[3];
static unsigned int stage,snapshot_calls;
static bool get_done,put_done;
static bool gfx_retained_cycle_intent;
struct work_struct { int unused; };
static unsigned int worker_reads,worker_schedules;
static bool recovery_messages(void){worker_reads++;return true;}
static void schedule_delayed_work(int *work,unsigned long delay)
{assert(work==&recovery_receive_work&&delay==10);worker_schedules++;}
static unsigned int control_after10_reads;
static void inject_after_on(void);
static void inject_after_intent(void);
static void inject_on_phase(const char *row);
static char logs[524288];static size_t log_used;static unsigned int maximum_log_row;
static unsigned int log_group_position;
static bool is(const char *s){return !strcmp(fault,s);}
static void pr_info(const char *fmt,...)
{va_list ap;va_start(ap,fmt);int n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);assert(n>=0&&(size_t)n<sizeof(logs)-log_used);if(strstr(fmt,"m4rch gfx-native-running-cycle")==fmt){const char *prefixes[]={"m4rch gfx-native-running-cycle: ","m4rch gfx-native-running-cycle-state: ","m4rch gfx-native-running-cycle-transport: ","m4rch gfx-native-running-cycle-management: ","m4rch gfx-native-running-cycle-off: ","m4rch gfx-native-running-cycle-on: "};bool grouped=false;for(unsigned int k=0;k<6;k++)if(strstr(fmt,prefixes[k])==fmt){assert(k==log_group_position);log_group_position=(k+1)%6;grouped=true;}if(!grouped)assert(strstr(fmt,"m4rch gfx-native-running-cycle-rx:")==fmt||strstr(fmt,"m4rch gfx-native-running-cycle-tx:")==fmt);assert(n<512&&logs[log_used+n-1]=='\n');if((unsigned int)n>maximum_log_row)maximum_log_row=n;}if(strstr(fmt,"m4rch gfx-retained-cycle-coordinate: epoch=2")==fmt&&strstr(logs+log_used,"enabled=1 result=0"))inject_after_on();if(strstr(fmt,"m4rch gfx-native-running-cycle:")==fmt&&strstr(logs+log_used,"phase=second-start-intent"))inject_after_intent();if(strstr(fmt,"m4rch gfx-native-running-cycle:")==fmt)inject_on_phase(logs+log_used);log_used+=(size_t)n;}
static int atomic_read(const int *v){return *v;}
static bool sysfs_streq(const char *a,const char *b){return !strcmp(a,b);}
static void lockdep_assert_held(const int *p){assert(p==&graph_io_lock&&*p==1);}
static void mutex_lock(int *p){assert(*p==0);*p=1;}
static void mutex_unlock(int *p){assert(*p==1);*p=0;}
static void cancel_delayed_work(int *p){assert(p==&recovery_receive_work&&gfx_retained_cycle_intent);cancels++;}
static void gfx_coord_owner_pin(void){}
static bool pm_runtime_enabled(struct fake_device *d){return d->enabled;}
static bool pm_runtime_active(struct fake_device *d){return d->active;}
static bool pm_runtime_suspended(struct fake_device *d){return d->suspended;}
static u64 page_to_phys(struct page *p){assert(p);return p->pa;}
static void recovery_invalidate(void *p,size_t n){assert(p&&n==8);}
static bool gfx_poweroff_retained(void)
{
 if(!gfx_reset_scope_owner_pinned||!recovery_resident||!resident_session||!consumer||
    !asc||!mbox||!asc_region||!mbox_region||!root_sent||!installed||root_detached||
    !device_context_retained)return false;
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++)if(!owned[i])return false;
 return true;
}
static bool gfx_reset_scope_backing(void){return gfx_poweroff_retained()&&held&&pm_runtime_active(&consumer->dev);}
static bool recovery_idle(void){return !is("work-not-idle");}
static u32 recovery_read32(unsigned int o)
{
 if(o==RECOVERY_STATUS+0x4900)return 2;
 if(o==RECOVERY_STATUS+0x4910||o==RECOVERY_REQUEST+4)return 1;
 if(o==RECOVERY_REQUEST)return 0;
 if(o==RECOVERY_CONTROL||o==RECOVERY_CONTROL+8||o==RECOVERY_CONTROL+16)return 32;
 assert(false);return 0;
}
static u64 recovery_read64(unsigned int o){assert(o==RECOVERY_STATUS+0x48f0);return 1;}
static unsigned long msecs_to_jiffies(unsigned int ms){return ms;}
static bool time_before(unsigned long a,unsigned long b){return (long)(a-b)<0;}
static void usleep_range(unsigned int lo,unsigned int hi){assert(lo==1000&&hi==1100);if(!is("clock-stalled")&&!is("boot-clock-stalled")&&!is("host-clock-stalled"))jiffies++;}
static void wmb(void){}
static u32 readl(void *p);
static u64 readq(void *p);
static void writeq(u64 v,void *p);
static void writel(u32 v,void *p);
static bool receive_mailbox(u64 m,u64 meta){(void)m;(void)meta;assert(false);return false;}
static int gfx_reset_scope_result(const char *cmd,int ret){(void)cmd;recovery_operation++;return ret;}
static int gfx_poweroff_sample(void){diagcalls++;return 0;}
static int gfx_reset_scope_snapshot(void){diagcalls++;return 0;}
static int gfx_poweroff_attempt(void){assert(false);return -EIO;}
static int gfx_poweroff_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o);
static int pm_runtime_resume_and_get(struct fake_device *d);
static int pm_runtime_put_sync_suspend(struct fake_device *d);
#include "gfx-native-running-cycle.h"

static struct gfx_coord_session gfx_coord_owner_session;
static bool gfx_coord_owner_module_pinned,gfx_coord_owner_startup_retained;
static bool gfx_coord_owner_pmp_region,gfx_coord_owner_pmc_region;
static void *gfx_coord_owner_pmp,*gfx_coord_owner_pmc;
static int gfx_coord_owner_alias_check(void){return is(get_done&&stage==1?"coord-on-alias":"coord-off-alias")?-EBUSY:0;}
static int read_ptd(void *ctx,unsigned int entry,u64 *payload,u64 *raw)
{(void)ctx;assert(get_done&&!put_done);*raw=0;*payload=entry==GFX_COORD_REQUEST_ENTRY?ptd_request:0;return 0;}
static int write_ptd(void *ctx,unsigned int entry,u64 value)
{
 (void)ctx;assert(entry==GFX_COORD_REQUEST_ENTRY&&get_done&&!put_done);
 if(value&GFX_COORD_REQUEST_BIT){coordinate_on_calls++;if(is("coord-on-write"))return -EIO;}
 else {coordinate_off_calls++;if(is("coord-off-write"))return -EIO;}
 ptd_request=value;return 0;
}
static int read_vote(void *ctx,unsigned int rail,u32 *value)
{(void)ctx;assert(rail<3&&get_done&&!put_done);*value=votes[rail];return 0;}
static int write_vote(void *ctx,unsigned int rail,u32 value)
{(void)ctx;assert(rail<3&&get_done&&!put_done);if(is((value&4)?"coord-on-vote":"coord-off-vote"))return -EIO;votes[rail]=value;return 0;}
static u64 now_ns(void *ctx){(void)ctx;return jiffies*1000000ULL;}
static void delay(void *ctx){(void)ctx;jiffies++;}
static void event(void *ctx,const char *s,unsigned int i,u64 v,u64 st,int r)
{(void)ctx;(void)s;(void)i;(void)v;(void)st;(void)r;}
static const struct gfx_coord_ops gfx_coord_owner_ops={NULL,read_ptd,write_ptd,read_vote,write_vote,now_ns,delay,event};
#include "gfx-retained-power-cycle-coordinate.h"
/* ACTUAL_RECEIVE_WORKER */

/* Faults occur at the actual successful coordinator-return log and the actual
 * START-intent log, before the corresponding fresh admission reads. */
static void inject_after_on(void)
{
 if(is("after-on-status6d")||is("native-observed-6c-to-6d")||strstr(fault,"sixd-post-on-")==fault)
  status48=0x6d;
 if(is("sixd-post-on-start-set"))control44=START;
}
static void inject_after_intent(void)
{
 if(is("post-intent-status6d"))status48=0x6d;
 if(is("post-intent-pm-error"))consumer->dev.power.runtime_error=-EIO;
}

static void inject_on_phase(const char *row)
{
 bool boot=strstr(row,"phase=boot-running-observed")!=NULL;
 bool intent=strstr(row,"phase=host-on-intent")!=NULL;
 bool reply=strstr(row,"phase=host-on-reply-observed")!=NULL;
 if(boot) {
  if(is("host-queued-b20")){messages[count]=GFX_RETAINED_CYCLE_HOST_ON;metadata[count]=0;count++;}
  if(is("host-missing-running"))gfx_retained_cycle_boot_running_observed=false;
  if(is("host-missing-map"))gfx_retained_cycle_endpoint_map=false;
  if(is("host-missing-hello"))gfx_retained_cycle_hello_replied=false;
  if(is("host-intent-used"))gfx_retained_cycle_host_on_attempted=true;
  if(is("host-capacity-one"))gfx_retained_cycle_records=15;
  if(is("host-capacity-zero"))gfx_retained_cycle_records=16;
  if(is("host-capacity-two"))gfx_retained_cycle_records=14;
  if(is("host-first-cached"))gfx_retained_cycle_first_off_preserved=false;
  if(is("host-first-current"))gfx_native_powergate_ack_observed=false;
  if(is("host-identity"))*target_slot^=0x4000;
  if(is("host-on-complete"))gfx_retained_cycle_coord_session.on_complete=false;
  if(is("host-on-attempt"))gfx_retained_cycle_coord_session.on_attempted=false;
  if(is("host-ref"))gfx_retained_cycle_second_ref_held=false;
  if(is("host-enabled"))consumer->dev.enabled=false;
  if(is("host-active"))consumer->dev.active=false;
  if(is("host-suspended"))consumer->dev.suspended=true;
  if(is("host-usage"))consumer->dev.power.usage_count=2;
  if(is("host-error"))consumer->dev.power.runtime_error=-EIO;
  if(is("host-start-clear"))control44=0;
 }
 if(intent) {
  if(is("host-intent-first"))gfx_native_powergate_ack_observed=false;
  if(is("host-intent-identity"))*target_slot^=0x4000;
  if(is("host-intent-pm-error"))consumer->dev.power.runtime_error=-EIO;
  if(is("host-intent-start-clear"))control44=0;
 }
 if(reply) {
  if(is("host-reply-first"))gfx_native_powergate_ack_observed=false;
  if(is("host-reply-identity"))*target_slot^=0x4000;
  if(is("host-reply-pm-error"))consumer->dev.power.runtime_error=-EIO;
  if(is("host-reply-start-clear"))control44=0;
  if(is("pre202-missing-running"))gfx_retained_cycle_boot_running_observed=false;
  if(is("pre202-missing-host-write"))gfx_retained_cycle_host_on_write_attempted=false;
  if(is("pre202-missing-host-reply"))gfx_retained_cycle_host_on_reply_observed=false;
 }
}

static int gfx_poweroff_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o)
{
 (void)index;snapshot_calls++;
 assert(gfx_retained_cycle_intent&&graph_io_lock==1);
 memset(o,0,sizeof(*o));o->valid=1;
 if(!strcmp(phase,"retained-cycle-before-get")) {
  assert(!held&&!get_done&&!pmgets);o->before=is("fresh-off-busy")?0x0f000b00:0x0f000300;o->domain_on=is("fresh-off-domain-on");
  return is("fresh-off-error")?-EIO:0;
 }
 assert(get_done);
 if(!strcmp(phase,"retained-cycle-after-get")||!strcmp(phase,"retained-cycle-before-second-off")) {
  assert(held&&!put_done);o->domain_on=!is("active-domain-off");o->before=is("active-busy")?0x1f000bff:0x1f0003ff;
  return is("active-snapshot-error")?-EIO:0;
 }
 assert(!strcmp(phase,"retained-cycle-after-second-off")&&put_done&&!held);
 o->before=is("second-off-busy")?0x0f000b00:0x0f000300;o->domain_on=is("second-off-domain-on");
 return is("second-off-error")?-EIO:0;
}
static int pm_runtime_resume_and_get(struct fake_device *d)
{
 assert(graph_io_lock==1&&gfx_retained_cycle_intent&&gfx_retained_cycle_pm_get_attempted);
 assert(!held&&!pmgets&&!d->power.usage_count);pmgets++;
 if(is("pm-get-negative"))return -EIO;
 d->power.usage_count=1;d->active=true;d->suspended=false;d->power.runtime_status=0;get_done=true;stage=1;
 control44=0;status48=0x6a;
 if(is("pm-get-usage"))d->power.usage_count=2;
 if(is("pm-get-error"))d->power.runtime_error=-EIO;
 if(is("pm-get-suspended")){d->suspended=true;d->active=false;}
 if(is("after-get-pa"))owned[7]->pa+=0x4000;
 if(is("after-get-root"))*target_slot^=0x4000;
 if(is("cold-status6e"))status48=0x6e;
 if(is("cold-status6c"))status48=0x6c;
 if(is("native-observed-6c-to-6d"))status48=0x6c;
 if(is("cold-status48"))status48=0x48;
 if(is("cold-status6d"))status48=0x6d;
 if(is("cold-status0"))status48=0;
 if(is("cold-start-set"))control44=START;
 return 0;
}
static int pm_runtime_put_sync_suspend(struct fake_device *d)
{
 assert(graph_io_lock==1&&gfx_retained_cycle_pm_put_attempted&&!held);
 assert(gfx_retained_cycle_cpu_stopped&&gfx_retained_cycle_coord_session.off_complete);
 assert(d->power.usage_count==1&&!pmputs);pmputs++;put_done=true;
 d->power.usage_count=0;d->active=false;d->suspended=true;d->power.runtime_status=2;
 if(is("pm-put-error")){d->power.runtime_error=-EIO;return -EIO;}
 if(is("pm-put-accounting"))d->power.usage_count=1;
 return 0;
}
static u32 readl(void *p)
{
 assert(graph_io_lock==1&&held&&get_done&&!put_done);hwreads++;
 if(put_done)reads_after_put++;
 if(p==(char*)asc+0x44) {
  if(is("control-invalid"))return ~0U;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("boundary-returned-start"))return START;
  if(gfx_retained_cycle_clear10_attempted&&!gfx_retained_cycle_clear20_attempted) {
   control_after10_reads++;
   if(control_after10_reads==2&&is("start-reasserted"))control44|=START;
   if(control_after10_reads==2&&is("fresh-rmw-mutated"))control44|=0x400;
  }
  if(gfx_retained_cycle_start_attempted&&!starts&&is("start-invalid"))return ~0U;
  if(gfx_retained_cycle_start_attempted&&!starts&&is("start-reasserted-before-write"))return START;
  if(gfx_retained_cycle_cpu_stopped&&is("off-control-invalid"))return ~0U;
  if(gfx_retained_cycle_endpoint_map&&!requests&&is("pre202-start-clear"))return control44&~START;
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-control-invalid"))return ~0U;
  return control44;
 }
 if(p==(char*)asc+0x48) {
  if(is("status-invalid"))return ~0U;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("boundary-returned-status"))return 0x6e;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("after-on-status6c"))return 0x6c;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("after-on-status48"))return 0x48;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("after-on-status-invalid"))return ~0U;
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-status6e"))return 0x6e;
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-status48"))return 0x48;
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-status-invalid"))return ~0U;
  if(gfx_retained_cycle_endpoint_map&&!requests&&is("pre202-status-invalid"))return ~0U;
  if(gfx_retained_cycle_ack_observed&&is("idle-timeout"))return 0x6c;
  if(gfx_retained_cycle_clear20_attempted&&is("post-stop-idle-lost"))return 0x6c;
  if(gfx_retained_cycle_cpu_stopped&&is("off-status-invalid"))return ~0U;
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-status-invalid"))return ~0U;
  return status48;
 }
 if(p==(char*)mbox+0x110) {
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("sixd-post-on-tx-full"))return BIT(16);
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-tx-full"))return BIT(16);
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-tx-invalid"))return ~0U;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("boundary-returned-tx"))return BIT(16);
  if(is("tx-invalid"))return ~0U;
  if(is("tx-full"))return BIT(16);
  if(gfx_retained_cycle_endpoint_map&&!requests&&is("pre202-tx-full"))return BIT(16);
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-tx-invalid"))return ~0U;
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-tx-full"))return BIT(16);
  if(gfx_retained_cycle_host_on_attempted&&!hostons&&is("host-intent-tx-full"))return BIT(16);
  if(gfx_retained_cycle_host_on_reply_observed&&is("host-reply-tx-full"))return BIT(16);
  return 0;
 }
 if(p==(char*)mbox+0x114) {
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("sixd-post-on-rx-pending"))return 0;
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-rx-pending"))return 0;
  if(!starts&&gfx_retained_cycle_start_attempted&&is("immediate-rx-invalid"))return ~0U;
  if(is("rx-invalid"))return ~0U;
  if(!starts&&is("cold-rx-pending"))return 0;
  if(!starts&&gfx_retained_cycle_coord_session.on_complete&&is("boundary-returned-rx"))return 0;
  if(gfx_retained_cycle_endpoint_map&&!requests&&is("pre202-rx-pending"))return 0;
  if(gfx_retained_cycle_ack_observed&&is("post-ack-rx-pending"))return 0;
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-rx-invalid"))return ~0U;
  if(gfx_retained_cycle_boot_running_observed&&!hostons&&is("host-rx-pending"))return 0;
  if(gfx_retained_cycle_host_on_attempted&&!hostons&&is("host-intent-rx-pending"))return 0;
  if(gfx_retained_cycle_host_on_reply_observed&&is("host-reply-rx-pending"))return 0;
  if(hostons&&!gfx_retained_cycle_host_on_reply_observed&&is("host-wait-rx-invalid"))return ~0U;
  return pos<count?0:EMPTY;
 }
 assert(false);return 0;
}
static u64 readq(void *p)
{
 assert(graph_io_lock==1&&held&&starts&&pos<count&&!put_done);
 if(p==(char*)mbox+0x830)return messages[pos];
 assert(p==(char*)mbox+0x838);u64 value=metadata[pos++];
 if(is("late-hello"))jiffies=4000;
 if(requests&&is("late-ack"))jiffies+=2000;
 if(hostons&&!requests&&is("host-reply-late"))jiffies+=2000;
 if(pos==4&&is("boot-late"))jiffies=4000;
 return value;
}
static void writeq(u64 value,void *p)
{
 assert(graph_io_lock==1&&held&&gfx_retained_cycle_intent&&starts&&!put_done);
 if(p==(char*)mbox+0x808){assert(value==0);return;}
 assert(p==(char*)mbox+0x800);
 if(value==GFX_RETAINED_CYCLE_HOST_ON) {
  assert(gfx_retained_cycle_boot_running_observed&&gfx_retained_cycle_host_on_attempted&&gfx_retained_cycle_host_on_write_attempted);
  assert(hellos==1&&mapacks==2&&pos==count&&!hostons&&!requests);hostons++;
  if(is("host-no-reply")||is("host-clock-stalled"))return;
  messages[count]=is("host-reply-invalid")?~0ULL:is("host-reply-boot20")?GFX_RETAINED_CYCLE_BOOT_RUNNING:
   is("host-reply-shutdown")?0x0070000000000201ULL:is("host-reply-upperbits")?0x01b0000000000020ULL:
   is("host-reply-state")?0x00b0000000000021ULL:GFX_RETAINED_CYCLE_HOST_ON;
  metadata[count]=is("host-reply-endpoint")?1:is("host-reply-metadata-invalid")?~0ULL:0;count++;return;
 }
 if(value==GFX_NATIVE_POWERGATE_REQUEST) {
  assert(gfx_retained_cycle_request_attempted&&hellos==1&&mapacks==2&&pos==count);
  assert(gfx_retained_cycle_endpoint_map&&requests==0&&hostons==1&&gfx_retained_cycle_host_on_reply_observed);requests++;stage=3;
  if(is("no-ack")||is("clock-stalled"))return;
  messages[count]=is("ack-boot20")?GFX_RETAINED_CYCLE_BOOT_RUNNING:is("ack-host20")?GFX_RETAINED_CYCLE_HOST_ON:is("ack-invalid")?~0ULL:is("ack-wrong")?0x0070000000000220ULL:
   is("ack-one")?0x0070000000000201ULL:0x0070000000000202ULL;
  metadata[count]=is("ack-endpoint")?32:0;count++;return;
 }
 if(((value>>52)&0xf)==2) {
  assert(value==0x00200000000c000cULL&&gfx_retained_cycle_hello_reply_attempts==1&&hellos==0);hellos++;
 } else {
  assert(((value>>52)&0xf)==8&&mapacks<2);mapacks++;
  if(mapacks==2&&is("pre202-pm-error"))consumer->dev.power.runtime_error=-EIO;
  if(mapacks==2&&is("journal-no-ack-slot"))gfx_retained_cycle_records=16;
 }
}
static void writel(u32 value,void *p)
{
 assert(graph_io_lock==1&&held&&p==(char*)asc+0x44&&!put_done);
 if(value&START) {
  assert(gfx_retained_cycle_start_attempted&&gfx_retained_cycle_boundary_qualified&&!starts);
  starts++;stage=2;
  if(!is("start-dropped"))control44=value;
  status48=0x6d;
  if(is("no-hello")||is("clock-stalled"))return;
  messages[0]=is("hello-version")?0x00100000000b000bULL:0x00100000000c000cULL;
  metadata[0]=is("hello-endpoint")?32:0;
  messages[1]=is("map-before-hello")?0x00100000000c000cULL:0x0080000000000003ULL;
  metadata[1]=0;
  messages[2]=is("map-base-alias")?0x0088000900000003ULL:
   is("map-order")?0x0088000000000003ULL:
   is("map-bitmap")?0x0088000100000001ULL:0x0088000100000003ULL;
  metadata[2]=0;count=4;
  messages[3]=is("boot-invalid")?~0ULL:is("boot-upperbits")?0x0170000000000020ULL:
   is("boot-host20")?GFX_RETAINED_CYCLE_HOST_ON:is("boot-shutdown")?0x0070000000000201ULL:GFX_RETAINED_CYCLE_BOOT_RUNNING;
  metadata[3]=is("boot-endpoint")?1:is("boot-metadata-invalid")?~0ULL:0;
  if(is("boot-before-map"))messages[2]=GFX_RETAINED_CYCLE_BOOT_RUNNING;
  if(is("boot-missing")||is("boot-clock-stalled"))count=3;
  if(is("hello-invalid"))messages[0]=~0ULL;
  if(is("map-type"))messages[2]=0x0070000000000002ULL;
  return;
 }
 assert(gfx_retained_cycle_ack_observed&&requests==1);cpuwrites++;
 if(cpuwrites==1&&is("clear10-dropped"))return;
 if(cpuwrites==2&&is("clear20-dropped")) {control44=value|0x20;return;}
 control44=value;
}
static void reset(const char *selected)
{
 fault=selected;graph_io_lock=1;held=false;recovery_resident=resident_session=true;
 asc_region=mbox_region=installed=root_sent=device_context_retained=true;
 root_detached=false;gfx_reset_scope_owner_pinned=gfx_reset_scope_sealed=gfx_reset_scope_host_stopped=true;
 recovery_session_failed=true;recovery_work_submitted=false;receive_enabled=true;
 receive_journal.used=51176;receive_journal.status=0;receive_journal.doorbells=0;
 consumer->dev=(struct fake_device){.power={0,2,0},.enabled=true,.active=false,.suspended=true};
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++){page_storage[i].pa=0x400000ULL+i*0x4000;owned[i]=&page_storage[i];}
 *target_slot=page_to_phys(owned[0])|3;
 gfx_native_powergate_intent=gfx_native_powergate_request_attempted=true;
 gfx_native_powergate_ack_observed=gfx_native_powergate_cpu_stopped=true;
 gfx_native_powergate_clear10_attempted=gfx_native_powergate_clear20_attempted=true;
 gfx_native_powergate_off_delegated=true;gfx_poweroff_gate_consumed=gfx_poweroff_pm_attempted=true;
 gfx_poweroff_provider_off_observed=gfx_poweroff_accounting_ok=true;
 gfx_poweroff_pm_result=gfx_poweroff_snapshot_result=0;
 gfx_poweroff_start_clear_attempted=true;started=true;
 gfx_coord_owner_session=(struct gfx_coord_session){true,true,true,true};
 gfx_coord_owner_module_pinned=gfx_coord_owner_startup_retained=true;
 gfx_coord_owner_pmp_region=gfx_coord_owner_pmc_region=true;
 gfx_coord_owner_pmp=&ptd_request;gfx_coord_owner_pmc=votes;
 assert(gfx_retained_cycle_identity(true));
}
int main(int argc,char **argv)
{
 assert(argc==2);reset(argv[1]);
 if(strstr(fault,"stage-guard-")==fault) {
  gfx_retained_cycle_intent=gfx_retained_cycle_pm_get_attempted=true;
  assert(pm_runtime_resume_and_get(&consumer->dev)==0);
  held=gfx_retained_cycle_second_ref_held=gfx_retained_cycle_first_off_preserved=true;
  gfx_retained_cycle_coord_session.on_attempted=gfx_retained_cycle_coord_session.on_complete=true;
  status48=0x6d;
  enum gfx_retained_cycle_start_stage admission=GFX_RETAINED_CYCLE_POST_ON;
  if(is("stage-guard-invalid"))admission=(enum gfx_retained_cycle_start_stage)99;
  if(is("stage-guard-pre6d"))admission=GFX_RETAINED_CYCLE_PRE_ON;
  if(is("stage-guard-on-intent"))gfx_retained_cycle_coord_session.on_attempted=false;
  if(is("stage-guard-on-complete"))gfx_retained_cycle_coord_session.on_complete=false;
  if(is("stage-guard-ref"))gfx_retained_cycle_second_ref_held=false;
  if(is("stage-guard-held"))held=false;
  if(is("stage-guard-enabled"))consumer->dev.enabled=false;
  if(is("stage-guard-active"))consumer->dev.active=false;
  if(is("stage-guard-suspended"))consumer->dev.suspended=true;
  if(is("stage-guard-usage"))consumer->dev.power.usage_count=2;
  if(is("stage-guard-error"))consumer->dev.power.runtime_error=-EIO;
  if(is("stage-guard-first-cached"))gfx_retained_cycle_first_off_preserved=false;
  if(is("stage-guard-first-current"))gfx_native_powergate_ack_observed=false;
  int boundary=gfx_retained_cycle_cold_boundary(admission,false);
  assert(boundary<0&&!starts&&!requests&&!pmputs);
  if(!is("stage-guard-pre6d"))assert(hwreads==0);
  if(is("stage-guard-first-current"))assert(!gfx_native_powergate_ack_observed);
  printf("PASS %s ret=%d get=%u start=%u request=%u put=%u records=%u maximum_new_log_row=%u\n",fault,boundary,pmgets,starts,requests,pmputs,gfx_retained_cycle_records,maximum_log_row);
  return 0;
 }
 if(is("log-row-bound")) {
  gfx_retained_cycle_pm_get_result=gfx_retained_cycle_pm_put_result=gfx_retained_cycle_off_snapshot_result=INT32_MIN;
  consumer->dev.power.usage_count=consumer->dev.power.runtime_error=consumer->dev.power.runtime_status=INT32_MIN;
  gfx_retained_cycle_control=gfx_retained_cycle_status=gfx_retained_cycle_rx=gfx_retained_cycle_tx=UINT32_MAX;
  gfx_retained_cycle_hello_reply_attempts=gfx_retained_cycle_map_reply_attempts=UINT32_MAX;
  gfx_retained_cycle_appmap=UINT32_MAX;gfx_retained_cycle_map_seen=UINT8_MAX;
  gfx_retained_cycle_records=gfx_retained_cycle_polls=gfx_retained_cycle_ack_polls=UINT32_MAX;
  gfx_retained_cycle_idle_polls=gfx_retained_cycle_off_samples=UINT32_MAX;
  gfx_retained_cycle_ack_message=gfx_retained_cycle_ack_metadata=UINT64_MAX;
  gfx_retained_cycle_boot_running_message=gfx_retained_cycle_boot_running_metadata=UINT64_MAX;
  gfx_retained_cycle_host_on_reply_message=gfx_retained_cycle_host_on_reply_metadata=UINT64_MAX;
  gfx_retained_cycle_host_on_polls=UINT32_MAX;
  gfx_retained_cycle_refusal="retained-evidence-changed-after-protocol";
  gfx_retained_cycle_log("second-coordinate-off-intent",INT32_MIN);
  assert(maximum_log_row<512&&!log_group_position);
  printf("PASS log-row-bound maximum_new_log_row=%u\n",maximum_log_row);return 0;
 }
 if(is("first-intent"))gfx_native_powergate_intent=false;
 if(is("first-request"))gfx_native_powergate_request_attempted=false;
 if(is("first-ack"))gfx_native_powergate_ack_observed=false;
 if(is("first-cpu"))gfx_native_powergate_cpu_stopped=false;
 if(is("first-clear10"))gfx_native_powergate_clear10_attempted=false;
 if(is("first-clear20"))gfx_native_powergate_clear20_attempted=false;
 if(is("first-off-delegated"))gfx_native_powergate_off_delegated=false;
 if(is("first-off-gate"))gfx_poweroff_gate_consumed=false;
 if(is("first-pm-attempt"))gfx_poweroff_pm_attempted=false;
 if(is("first-pm-result"))gfx_poweroff_pm_result=-EIO;
 if(is("first-provider"))gfx_poweroff_provider_off_observed=false;
 if(is("first-snapshot"))gfx_poweroff_snapshot_result=-EIO;
 if(is("first-accounting"))gfx_poweroff_accounting_ok=false;
 if(is("first-host-stopped"))gfx_reset_scope_host_stopped=false;
 if(is("first-sealed"))gfx_reset_scope_sealed=false;
 if(is("first-recovery-failed"))recovery_session_failed=false;
 if(is("first-coordinate"))gfx_coord_owner_session.off_complete=false;
 if(is("first-work"))recovery_work_submitted=true;
 if(is("identity-page"))owned[7]=&page_storage[174];
 if(is("identity-pa"))owned[7]->pa+=0x4000;
 if(is("identity-root"))*target_slot^=0x4000;
 if(is("identity-context"))device_context_retained=false;
 if(is("first-usage"))consumer->dev.power.usage_count=1;
 if(is("first-runtime-error"))consumer->dev.power.runtime_error=-EIO;
 if(is("first-active")){consumer->dev.active=true;consumer->dev.suspended=false;}
 if(is("first-held"))held=true;
 if(is("startup-unknown"))gfx_native_powergate_startup_unknown=true;
 bool before_diag=is("diagnostic-before");
 if(before_diag){assert(gfx_retained_cycle_command("sample")==0);assert(!gfx_retained_cycle_intent&&pmgets==0);}
 int ret=gfx_retained_cycle_command("gfx-native-running-cycle");
 if(is("post-intent-pm-error"))assert(gfx_retained_cycle_start_attempted&&!strcmp(gfx_retained_cycle_refusal,"post-on-stage-unqualified"));
 bool success=is("success")||is("ack-one")||is("fresh-rmw-mutated")||is("cold-status6c")||is("after-on-status6c")||is("after-on-status6d")||is("native-observed-6c-to-6d")||is("post-intent-status6d")||is("host-capacity-two")||before_diag;
 if(success) {
  assert(ret==0&&gfx_retained_cycle_complete&&pmgets==1&&pmputs==1);
  assert(starts==1&&hostons==1&&requests==1&&hellos==1&&mapacks==2&&cpuwrites==2);
  assert(coordinate_on_calls==1&&coordinate_off_calls==1);
  assert(!held&&!gfx_retained_cycle_second_ref_held&&gfx_retained_cycle_provider_off_observed);
  assert(gfx_retained_cycle_records==(is("host-capacity-two")?16:6)&&gfx_retained_cycle_first_off_preserved&&gfx_retained_cycle_identities_preserved);
  assert(gfx_retained_cycle_journal[0].message==0x00100000000c000cULL);
  assert(gfx_retained_cycle_boot_running_observed&&gfx_retained_cycle_host_on_reply_observed);
  assert(gfx_retained_cycle_journal[3].message==GFX_RETAINED_CYCLE_BOOT_RUNNING);
  assert(gfx_retained_cycle_journal[is("host-capacity-two")?14:4].message==GFX_RETAINED_CYCLE_HOST_ON);
 } else assert(ret<0&&!gfx_retained_cycle_complete);
 assert(pmgets<=1&&pmputs<=1&&starts<=1&&hostons<=1&&requests<=1&&cpuwrites<=2);
 assert(!reads_after_put&&receive_journal.used==51176&&receive_journal.status==0);
 assert(gfx_coord_owner_session.on_complete&&(!is("first-coordinate")||!gfx_coord_owner_session.off_complete));
 if(gfx_retained_cycle_intent) {
  unsigned int oldgets=pmgets,oldputs=pmputs,oldstarts=starts,oldreq=requests,oldreads=hwreads;
  assert(gfx_retained_cycle_command("gfx-native-running-cycle")==-EALREADY);
  assert(gfx_retained_cycle_command("gfx-powergate")==-EPERM);
  assert(gfx_retained_cycle_command("reset")==-EPERM);
  assert(pmgets==oldgets&&pmputs==oldputs&&starts==oldstarts&&requests==oldreq&&hwreads==oldreads);
  assert(gfx_retained_cycle_command("gfx-snapshot")==0);
  assert(pmgets==oldgets&&pmputs==oldputs&&starts==oldstarts&&requests==oldreq&&hwreads==oldreads);
  graph_io_lock=0;
  struct work_struct queued={0};recovery_receive_worker(&queued);
  assert(!worker_reads&&!worker_schedules&&graph_io_lock==0);
  graph_io_lock=1;
 }
 if(is("pm-get-negative"))assert(!held&&!gfx_retained_cycle_second_ref_held&&pmputs==0);
 if(pmgets&&get_done&&!pmputs)assert(held&&(gfx_retained_cycle_second_ref_held||is("host-ref")));
 if(is("cold-status6e")||is("cold-status48")||is("cold-status6d")||is("cold-status0"))
  assert(!starts&&!requests&&!coordinate_on_calls&&!pmputs);
 if(strstr(fault,"immediate-")==fault||is("after-on-status48")||is("after-on-status-invalid")||
    is("boundary-returned-status")||is("boundary-returned-rx")||is("boundary-returned-tx"))
  assert(!starts&&!requests&&!pmputs&&coordinate_on_calls==1);
 if(is("tx-full")||is("tx-invalid")||is("boundary-returned-tx"))assert(!starts&&!requests&&!pmputs);
 if(is("map-base-alias")||is("map-order")||is("map-bitmap")||is("map-type"))
  assert(!requests&&!pmputs&&mapacks==1&&gfx_retained_cycle_records==3);
 if(is("start-invalid")||is("start-reasserted-before-write"))assert(!starts&&!requests&&!pmputs);
 if(is("journal-no-ack-slot"))assert(!requests&&!pmputs&&gfx_retained_cycle_records==16);
 if(is("off-control-invalid")||is("off-status-invalid"))assert(!coordinate_off_calls&&!pmputs&&cpuwrites==2);
 if(is("second-off-busy"))assert(pmputs==1&&gfx_retained_cycle_off_samples==101);
 if(is("fresh-rmw-mutated"))assert(control44==0x400);
 if(strstr(fault,"sixd-post-on-")==fault||is("post-intent-pm-error"))
  assert(!starts&&!requests&&!pmputs&&coordinate_on_calls==1&&held&&gfx_retained_cycle_second_ref_held);
 if(is("first-sealed"))assert(!gfx_reset_scope_sealed&&!pmgets);
 if(is("first-recovery-failed"))assert(!recovery_session_failed&&!pmgets);
 if(strstr(fault,"boot-")==fault)assert(!hostons&&!requests&&!pmputs);
 if(strstr(fault,"host-")==fault&&!is("host-capacity-two"))assert(!requests&&!pmputs);
 if(strstr(fault,"host-intent-")==fault&&!is("host-intent-used"))assert(gfx_retained_cycle_host_on_attempted&&!hostons);
 if(strstr(fault,"host-reply-")==fault)assert(hostons==1);
 if(is("ack-boot20")||is("ack-host20"))assert(hostons==1&&requests==1&&!gfx_retained_cycle_ack_observed&&!cpuwrites&&!pmputs);
 if(strstr(fault,"pre202-missing-")==fault)assert(hostons==1&&!requests&&!pmputs);
 assert(!log_group_position);
 if(is("host-queued-b20"))assert(!hostons&&pos==4&&count==5&&!requests&&!pmputs);
 assert(diagcalls<=2&&snapshot_calls<=104&&cancels<=1&&recovery_operation==0);
 printf("PASS %s ret=%d get=%u start=%u request=%u put=%u records=%u maximum_new_log_row=%u\n",fault,ret,pmgets,starts,requests,pmputs,gfx_retained_cycle_records,maximum_log_row);
 return 0;
}
'''

CASES = [
    'success','ack-one','fresh-rmw-mutated','diagnostic-before','startup-unknown','log-row-bound',
    'first-intent','first-request','first-ack','first-cpu','first-clear10','first-clear20',
    'first-off-delegated','first-off-gate','first-pm-attempt','first-pm-result','first-provider',
    'first-snapshot','first-accounting','first-host-stopped','first-sealed','first-recovery-failed','first-coordinate','first-work',
    'identity-page','identity-pa','identity-root','identity-context','first-usage',
    'first-runtime-error','first-active','first-held','fresh-off-busy','fresh-off-domain-on','fresh-off-error',
    'pm-get-negative','pm-get-usage','pm-get-error','pm-get-suspended','after-get-pa','after-get-root',
    'active-domain-off','active-busy','active-snapshot-error','cold-status6e','cold-status6c','cold-status48','cold-status6d','cold-status0',
    'cold-start-set','cold-rx-pending','control-invalid','status-invalid','rx-invalid',
    'coord-on-alias','coord-on-write','coord-on-vote','boundary-returned-start','boundary-returned-status',
    'after-on-status6c','after-on-status48','after-on-status-invalid','immediate-status6e','immediate-status48','immediate-status-invalid','immediate-rx-pending','immediate-rx-invalid','immediate-tx-full','immediate-tx-invalid','boundary-returned-rx','boundary-returned-tx','start-dropped','start-invalid','start-reasserted-before-write','no-hello','hello-version','hello-endpoint','hello-invalid',
    'map-before-hello','map-base-alias','map-order','map-bitmap','map-type','tx-full','tx-invalid',
    'late-hello','pre202-start-clear','pre202-status-invalid','pre202-rx-pending','pre202-tx-full',
    'pre202-pm-error','journal-no-ack-slot','no-ack','clock-stalled','late-ack','ack-invalid','ack-wrong','ack-endpoint',
    'post-ack-rx-pending','idle-timeout','clear10-dropped','start-reasserted','clear20-dropped',
    'post-stop-idle-lost','off-control-invalid','off-status-invalid','work-not-idle','coord-off-alias','coord-off-write','coord-off-vote',
    'pm-put-error','pm-put-accounting','second-off-busy','second-off-domain-on','second-off-error',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CASES += ['after-on-status6d', 'native-observed-6c-to-6d', 'post-intent-status6d',
          'sixd-post-on-start-set', 'sixd-post-on-rx-pending', 'sixd-post-on-tx-full',
          'post-intent-pm-error', 'stage-guard-invalid', 'stage-guard-pre6d',
          'stage-guard-on-intent', 'stage-guard-on-complete', 'stage-guard-ref',
          'stage-guard-held', 'stage-guard-enabled', 'stage-guard-active',
          'stage-guard-suspended', 'stage-guard-usage', 'stage-guard-error',
          'stage-guard-first-cached', 'stage-guard-first-current']


CASES += ['boot-missing','boot-clock-stalled','boot-before-map','boot-invalid','boot-metadata-invalid','boot-upperbits','boot-host20','boot-shutdown','boot-endpoint','boot-late',
 'host-queued-b20','host-missing-running','host-missing-map','host-missing-hello','host-intent-used','host-capacity-one','host-capacity-zero','host-capacity-two',
 'host-first-cached','host-first-current','host-identity','host-on-complete','host-on-attempt','host-ref','host-enabled','host-active','host-suspended','host-usage','host-error','host-start-clear',
 'host-control-invalid','host-status-invalid','host-rx-invalid','host-rx-pending','host-tx-invalid','host-tx-full',
 'host-intent-first','host-intent-identity','host-intent-pm-error','host-intent-start-clear','host-intent-tx-full','host-intent-rx-pending',
 'host-no-reply','host-clock-stalled','host-wait-rx-invalid','host-reply-invalid','host-reply-boot20','host-reply-shutdown','host-reply-upperbits','host-reply-state','host-reply-endpoint','host-reply-metadata-invalid','host-reply-late',
 'host-reply-first','host-reply-identity','host-reply-pm-error','host-reply-start-clear','host-reply-tx-full','host-reply-rx-pending',
 'pre202-missing-running','pre202-missing-host-write','pre202-missing-host-reply','ack-boot20','ack-host20']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    receipt_path = source / 'native-running-cycle-owner-source-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['profile']['version'] == 10
    assert receipt['profile']['pre_on_known_statuses'] == ['0x6a', '0x6c']
    assert receipt['profile']['post_on_known_statuses'] == ['0x6a', '0x6c', '0x6d']
    assert receipt['profile']['status6d_requires_second_on_complete_and_second_ref'] is True
    assert 'known_native_reentry_statuses' not in receipt['profile']
    for row in receipt['output_source_pins']:
        assert sha(source / row['name']) == row['sha256'], row['name']
    for name in ['gfx-native-running-cycle.h','gfx-retained-power-cycle-coordinate.h']:
        assert (source / name).read_bytes() == (HERE / name).read_bytes()
    assert receipt['source_preparer']['sha256'] == sha(HERE / 'prepare-native-running-cycle-owner.py')
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    results=[]
    with tempfile.TemporaryDirectory(prefix='gfx-retained-cycle-q-') as directory:
        path = Path(directory)
        unit = path / 'actual-owner.c'
        owner_source = (source / 'recovery-cycle.h').read_text()
        marker = 'static void recovery_receive_worker(struct work_struct *work)\n{'
        begin = owner_source.index(marker)
        end = begin + len(marker)
        nesting = 1
        while nesting:
            nesting += (owner_source[end] == '{') - (owner_source[end] == '}')
            end += 1
        actual_worker = owner_source[begin:end]
        assert '&& !gfx_retained_cycle_intent' in actual_worker
        unit.write_text(HARNESS.replace('/* ACTUAL_RECEIVE_WORKER */', actual_worker))
        binary = path / 'actual-owner'
        compile_command = ['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror',
                           '-Wno-unused-function','-Wno-unused-variable',
                           '-Wno-unused-parameter',
                           '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                           '-I',str(source),str(unit),'-o',str(binary)]
        compiled = subprocess.run(compile_command,capture_output=True,text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+'\n'+compiled.stderr)
        for case in CASES:
            result = subprocess.run([str(binary),case],env=environment,capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError(case+'\n'+result.stdout+'\n'+result.stderr)
            results.append({'case':case,'returncode':result.returncode,'stdout':result.stdout.strip()})
    pins = [{'path':str(HERE / name),'sha256':sha(HERE / name)} for name in
            ['gfx-native-running-cycle.h','gfx-retained-power-cycle-coordinate.h',
             'prepare-native-running-cycle-owner.py','test-native-running-cycle-owner.py']]
    pins += [{'path':str(receipt_path),'sha256':sha(receipt_path)}]
    pins += [{'path':str(source / row['name']),'sha256':row['sha256']} for row in receipt['output_source_pins']]
    value = {'schema':'m4rch.gfx-native-running-cycle-c-qualification.v1','passed':True,
             'hardware_access':False,'ASan_UBSan':True,'case_count':len(results),
             'actual_headers':True,'actual_second_coordinate_core':True,
             'actual_receive_worker':True,'actual_running_host_on_before_202_replay':True,'observed_boot_power20_sequence_simulated':True,'actual_complete_six_row_groups':True,'second_log_row_count':6,'new_log_rows_bounded':True,'maximum_new_log_row_bytes':max(int(x['stdout'].split('maximum_new_log_row=')[-1]) for x in results),
             'stage_specific_start_guards_exercised':True,
             'actual_observed_6c_to_paired_on_to_6d_sequence_simulated':True,
             'first_success_evidence_simulated':True,'first_drain_logic_not_requalified':True,
             'source_path':str(source),'source_receipt_sha256':sha(receipt_path),
             'inputs':pins,'cases':results,
             'limitations':['PM runtime/provider/CPU/mailbox/retained DRAM and MMIO adapters use RAM callbacks.',
                            'The frozen first85C and paired coordinate qualifications compose separately.',
                            'These cases do not establish actual reentry, secondACK, physicalOFF, apprejoin, rendering or DMA retirement.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'passed':True,'case_count':len(results),'output':str(args.output),
                      'sha256':sha(args.output),'hardware_access':False}))


if __name__ == '__main__':
    main()
