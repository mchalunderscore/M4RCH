/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM replay includes the actual owner header, idle checks, worker and typed
 * command handler. Driver API and MMIO/cache/transport effects are recorders.
 */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>

typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define START (1U<<4)
#define GFX_RESET_SCOPE_TRIAL 1
#include "recovery-contract.h"
#include <linux/soc/apple/pmgr-gfx-reset.h>
struct kobject { int unused; };
struct kobj_attribute { int unused; };
struct work_struct { int unused; };
struct test_device { bool active; };
struct platform_device { struct test_device dev; };
struct page { int unused; };
static struct platform_device test_consumer, *consumer;
static struct page pages[174], *owned[174];
static u8 ram[2*1024*1024],asc_bytes[256],mbox_bytes[4096];
static void *asc,*mbox;
static bool held,asc_region,mbox_region,root_sent,installed,root_detached;
static bool device_context_retained,resident_session,recovery_resident,recovery_work_submitted;
static bool recovery_session_failed,recovery_trace_disabled;
static unsigned int recovery_operation,graph_io_lock;
static struct { unsigned int used,status,doorbells; } receive_journal;
static struct work_struct recovery_receive_work;
static unsigned int mutex_depth,cancel_calls,schedule_calls,receive_calls,ack_calls;
static unsigned int pulse_calls,snapshot_calls,asc_reads,asc_writes,ram_writes;
static unsigned int control_calls,cycle_calls,trace_calls,send_calls,gpu_samples;
static unsigned int snapshot_error,pulse_error;
static struct apple_pmgr_gfx_reset_observation api_observation;
static char logs[65536];static size_t log_used;
static void test_log(const char *fmt,...)
{
 va_list ap;int n;va_start(ap,fmt);
 n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);
 assert(n>=0 && (size_t)n<sizeof(logs)-log_used);log_used+=(size_t)n;
}
#define pr_info(...) test_log(__VA_ARGS__)
#define lockdep_assert_held(p) do { (void)(p);assert(mutex_depth==1); } while (0)
static bool pm_runtime_active(struct test_device *d) {return d->active;}
static void mutex_lock(void *p) {(void)p;assert(!mutex_depth);mutex_depth=1;}
static void mutex_unlock(void *p) {(void)p;assert(mutex_depth==1);mutex_depth=0;}
static void cancel_delayed_work(void *p) {(void)p;assert(mutex_depth==1);cancel_calls++;}
static unsigned int msecs_to_jiffies(unsigned int n) {return n;}
static void schedule_delayed_work(void *p,unsigned int n) {(void)p;assert(mutex_depth==1 && n==10);schedule_calls++;}
static bool sysfs_streq(const char *a,const char *b) {return !strcmp(a,b);}
static u32 readl(void *p)
{
 u32 v;assert(p);memcpy(&v,p,4);
 if((u8 *)p>=asc_bytes && (u8 *)p<asc_bytes+sizeof(asc_bytes)) {assert(mutex_depth==1);asc_reads++;}
 return v;
}
static void writel(u32 v,void *p) {assert(p && mutex_depth==1);asc_writes++;memcpy(p,&v,4);}
static u32 recovery_read32(unsigned int o) {u32 v;assert(o+4<=sizeof(ram));memcpy(&v,ram+o,4);return v;}
static u64 recovery_read64(unsigned int o) {u64 v;assert(o+8<=sizeof(ram));memcpy(&v,ram+o,8);return v;}
static void put32(unsigned int o,u32 v) {assert(o+4<=sizeof(ram));memcpy(ram+o,&v,4);}
static void recovery_write32(unsigned int o,u32 v) {ram_writes++;put32(o,v);}
static void *recovery_ptr(unsigned int o) {assert(o<sizeof(ram));return ram+o;}
static void recovery_invalidate(void *p,size_t n) {(void)p;(void)n;}
static void replay_cache_clean(void *p,void *q) {(void)p;(void)q;}
static bool power_ack(unsigned int a,unsigned int b,unsigned int c) {(void)a;(void)b;(void)c;ack_calls++;return true;}
static bool recovery_messages(void) {receive_calls++;return true;}
static bool recovery_control(unsigned int n,bool publish) {(void)n;(void)publish;control_calls++;return true;}
static bool recovery_cycles(void) {cycle_calls++;return true;}
static bool recovery_trace_off(void) {trace_calls++;return true;}
static bool recovery_send(u64 packet) {(void)packet;send_calls++;return true;}
static void recovery_power_sample(const char *p) {(void)p;gpu_samples++;}
static void ksm_status_sample(const char *p) {(void)p;gpu_samples++;}
static void joined_output_sample(const char *p) {(void)p;gpu_samples++;}

/* The runner inserts unchanged actual C functions/header at this boundary. */
#include "actual-owner.inc"

int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o)
{
 assert(mutex_depth==1 && gfx_reset_scope_backing());
 for(unsigned int i=0;i<sizeof(*o);i++) assert(!((u8 *)o)[i]);
 snapshot_calls++;*o=api_observation;return -(int)snapshot_error;
}
int apple_pmgr_t6040_gfx_checked_pulse(struct apple_pmgr_gfx_reset_observation *o)
{
 assert(mutex_depth==1 && gfx_reset_scope_backing());
 assert(gfx_reset_scope_attempted && gfx_reset_scope_sealed && recovery_session_failed);
 assert(!ram_writes && !control_calls && !cycle_calls && !trace_calls && !send_calls);
 assert(!receive_calls && !ack_calls && !asc_writes && cancel_calls);
 for(unsigned int i=0;i<sizeof(*o);i++) assert(!((u8 *)o)[i]);
 pulse_calls++;*o=api_observation;return -(int)pulse_error;
}
static unsigned int cases;
static ssize_t command(const char *s) {ssize_t r=recovery_command_store(NULL,NULL,s,strlen(s));assert(!mutex_depth);return r;}
static void cursors(u32 n) {put32(RECOVERY_CONTROL,n);put32(RECOVERY_CONTROL+8,n);put32(RECOVERY_CONTROL+16,n);}
static void fixture(bool diagnostic)
{
 memset(ram,0,sizeof(ram));memset(asc_bytes,0,sizeof(asc_bytes));memset(logs,0,sizeof(logs));log_used=0;
 memset(&api_observation,0,sizeof(api_observation));
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++) owned[i]=&pages[i];
 consumer=&test_consumer;consumer->dev.active=true;asc=asc_bytes;mbox=mbox_bytes;
 held=asc_region=mbox_region=root_sent=installed=device_context_retained=resident_session=recovery_resident=true;
 root_detached=recovery_work_submitted=false;recovery_session_failed=diagnostic;recovery_trace_disabled=true;
 gfx_reset_scope_owner_pinned=true;gfx_reset_scope_attempted=gfx_reset_scope_sealed=gfx_reset_scope_host_stopped=false;
 recovery_operation=0;mutex_depth=cancel_calls=schedule_calls=receive_calls=ack_calls=0;
 pulse_calls=snapshot_calls=asc_reads=asc_writes=ram_writes=control_calls=cycle_calls=trace_calls=send_calls=gpu_samples=0;
 snapshot_error=pulse_error=0;memset(&receive_journal,0,sizeof(receive_journal));
 cursors(RECOVERY_CONTROL_INITIAL);put32(RECOVERY_STATUS+0x4900,diagnostic?2:0);
 if(diagnostic) {put32(RECOVERY_REQUEST,2);put32(RECOVERY_REQUEST+4,1);put32(RECOVERY_STATUS+0x4910,1);}
 u32 v=0x30;memcpy(asc_bytes+0x44,&v,4);
 api_observation.valid=APPLE_PMGR_GFX_VALID_BEFORE;api_observation.domain_on=1;api_observation.before=0xff;
}
static void no_publication(void)
{
 assert(!ram_writes && !control_calls && !cycle_calls && !trace_calls && !send_calls && !receive_calls && !ack_calls);
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++) assert(owned[i]==&pages[i]);
 assert(held && installed && root_sent && !root_detached && device_context_retained && recovery_resident);
}
static void blocked_after_reset(void)
{
 unsigned int prior_reads=asc_reads;
 assert(command("control")==-EIO && command("recover")==-EIO && command("trace-off")==-EIO && command("submit")==-EIO);
 assert(command("gfx-reset")==-EALREADY && pulse_calls==1);
 assert(command("sample")==6 && asc_reads>prior_reads && !gpu_samples);
 assert(command("gfx-snapshot")==12 && snapshot_calls==1);
 recovery_receive_worker(NULL);assert(!schedule_calls && !receive_calls);
 assert(command("stop")==4 && gfx_reset_scope_host_stopped && recovery_resident);
 assert(asc_writes==1);u32 v;memcpy(&v,asc_bytes+0x44,4);assert(v==0x20);
 assert(command("stop")==4 && asc_writes==1);
 assert(command("sample")==6 && command("gfx-snapshot")==12 && snapshot_calls==2);
 no_publication();cases++;
}
static void rejected(void)
{
 assert(command("gfx-reset")<0);
 assert(gfx_reset_scope_sealed && recovery_session_failed && !gfx_reset_scope_attempted && !pulse_calls);
 assert(command("gfx-reset")==-EALREADY && !pulse_calls);
 assert(command("submit")==-EIO && command("recover")==-EIO && command("control")==-EIO);
 assert(!ram_writes && !receive_calls && !ack_calls && !asc_writes && !send_calls);
 recovery_receive_worker(NULL);assert(!schedule_calls && !receive_calls);
 cases++;
}
int main(void)
{
 /* Actual phase2 wedge metadata is deliberately permitted once, even though
  * recovery is sealed. Neither snapshot nor reset drains/ACKs that metadata.
  */
 fixture(true);assert(command("gfx-snapshot")==12 && !gfx_reset_scope_attempted && !gfx_reset_scope_sealed);
 assert(snapshot_calls==1 && !pulse_calls && !receive_calls && !cancel_calls);
 assert(strstr(logs,"control40=") && strstr(logs,"control44=") && strstr(logs,"status48="));cases++;
 for(unsigned int phase=0;phase<5;phase++) for(unsigned int failed=0;failed<2;failed++) {
  fixture(failed);put32(RECOVERY_STATUS+0x4900,phase);
  if((phase==0&&!failed)||(phase==2&&failed)) {assert(command("gfx-reset")==9 && pulse_calls==1);blocked_after_reset();}
  else rejected();
 }
 puts("PASS actual phase0/phase2 selection, no RX publication, permanent one-attempt seal, diagnostic snapshot/sample and packet-free idempotent stop");

 for(unsigned int n=0;n<16;n++) {
  fixture(true);
  switch(n) {
  case 0: gfx_reset_scope_owner_pinned=false;break;
  case 1: resident_session=false;break;
  case 2: held=false;break;
  case 3: consumer=NULL;break;
  case 4: consumer->dev.active=false;break;
  case 5: asc=NULL;break;
  case 6: mbox=NULL;break;
  case 7: asc_region=false;break;
  case 8: mbox_region=false;break;
  case 9: root_sent=false;break;
  case 10: installed=false;break;
  case 11: root_detached=true;break;
  case 12: device_context_retained=false;break;
  case 13: recovery_work_submitted=true;break;
  case 14: cursors(RECOVERY_CONTROL_INITIAL-1);break;
  case 15: cursors(RECOVERY_CONTROL_LAST+1);break;
  }
  rejected();
 }
 for(unsigned int page=0;page<ARRAY_SIZE(owned);page++) {fixture(true);owned[page]=NULL;rejected();}
 for(unsigned int ring=0;ring<ARRAY_SIZE(recovery_work_cursors);ring++) for(unsigned int word=0;word<3;word++) {
  fixture(true);put32(recovery_work_cursors[ring]+word*8,1);rejected();
 }
 for(unsigned int record=0;record<256;record++) {fixture(true);put32(RECOVERY_STATUS+0x40b8+record*8,9);rejected();}
 for(unsigned int word=0;word<2;word++) {fixture(true);put32(RECOVERY_CONTROL+word*8,RECOVERY_CONTROL_INITIAL-1);rejected();}
 for(unsigned int n=0;n<4;n++) {
  fixture(true);u32 controls[]={32,33,127,128};cursors(controls[n]);
  put32(RECOVERY_STATUS+0x40b8,8);put32(RECOVERY_STATUS+0x40b8+255*8,1);
  assert(command("gfx-reset")==9 && pulse_calls==1);blocked_after_reset();
 }
 fixture(true);recovery_resident=false;assert(command("gfx-reset")==-ENODEV && !pulse_calls && !gfx_reset_scope_attempted);cases++;
 puts("PASS all174 page pins, PM/mapping/context guards, all36 work cursor words, all256 active TA records and consumed control bounds");

 for(unsigned int e=0;e<5;e++) {
  fixture(true);
  switch(e) {
  case 0: pulse_error=ENODEV;break; /* Provider refusal before register writes. */
  case 1: pulse_error=EIO;api_observation.operation_error=-EIO;break;
  case 2: pulse_error=ETIMEDOUT;api_observation.operation_error=-ETIMEDOUT;api_observation.cleanup_error=-EIO;break;
  case 3: api_observation.cleanup_error=-EIO;break; /* Defensive inconsistent API return. */
  case 4: api_observation.operation_error=-EBUSY;break;
  }
  assert(command("gfx-reset")<0 && pulse_calls==1 && gfx_reset_scope_attempted && gfx_reset_scope_sealed);
  assert(strstr(logs,"operation_error=") && strstr(logs,"cleanup_error="));
  pulse_error=0;api_observation.operation_error=api_observation.cleanup_error=0;blocked_after_reset();
 }
 fixture(true);api_observation.valid=255;api_observation.before=1;api_observation.auto_held=2;api_observation.disabled=3;
 api_observation.asserted=4;api_observation.deasserted=5;api_observation.released=6;api_observation.final=7;api_observation.cleanup_final=8;
 assert(command("gfx-reset")==9);
 const char *names[]={"before","auto_held","disabled","asserted","deasserted","released","final","cleanup_final"};
 for(unsigned int i=0;i<ARRAY_SIZE(names);i++) {char pattern[96];snprintf(pattern,sizeof(pattern),"field=%s valid=1 value=%#x",names[i],i+1);assert(strstr(logs,pattern));}
 cases++;
 fixture(true);api_observation.valid=0;api_observation.before=api_observation.cleanup_final=0xdeadbeef;
 assert(command("gfx-snapshot")==12 && !strstr(logs,"deadbeef"));cases++;
 fixture(false);snapshot_error=EIO;api_observation.operation_error=-EIO;
 assert(command("gfx-snapshot")==-EIO && recovery_session_failed && cancel_calls && !gfx_reset_scope_attempted);
 assert(command("control")==-EIO && command("submit")==-EIO);recovery_receive_worker(NULL);assert(!receive_calls && !schedule_calls);cases++;
 fixture(true);held=false;assert(command("gfx-snapshot")==-EBUSY && !snapshot_calls && !asc_reads);cases++;
 puts("PASS API refusal/error/cleanup uncertainty, attempt-before-entry, full valid-field logging and poisoned invalid observations");

 fixture(true);assert(command("stop")==4 && !gfx_reset_scope_attempted && gfx_reset_scope_sealed && recovery_resident);
 assert(command("gfx-reset")==-EALREADY && !pulse_calls);no_publication();cases++;
 fixture(false);assert(command("stop")==4 && !gfx_reset_scope_attempted && recovery_session_failed && recovery_resident);
 assert(command("control")==-EIO && command("gfx-reset")==-EALREADY);no_publication();cases++;
 fixture(false);recovery_receive_worker(NULL);assert(receive_calls==1 && schedule_calls==1);cases++;
 fixture(false);assert(command("nonsense")==-EINVAL && !gfx_reset_scope_sealed && !pulse_calls);cases++;
 printf("RAM owner C replay cases: %u\n",cases);return 0;
}
