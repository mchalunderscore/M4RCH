/* SPDX-License-Identifier: GPL-2.0-only */
/* Actual owner C replay: memory, transport, provider and runtime PM are stubs. */
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
#define READ_ONCE(x) (x)
typedef struct { int counter; } atomic_t;
static int atomic_read(const atomic_t *a) {return a->counter;}
enum rpm_status {RPM_INVALID=-1,RPM_ACTIVE,RPM_RESUMING,RPM_SUSPENDED,RPM_SUSPENDING};
#include "recovery-contract.h"
#include <linux/soc/apple/pmgr-gfx-reset.h>
struct kobject { int unused; };
struct kobj_attribute { int unused; };
struct work_struct { int unused; };
struct test_device {
 struct {atomic_t usage_count;enum rpm_status runtime_status;int runtime_error;unsigned int disable_depth;} power;
};
struct platform_device {struct test_device dev;};
struct page {int unused;};
static struct platform_device test_consumer,*consumer;
static struct page pages[174],*owned[174],*saved_owned[174];
static u8 ram[2*1024*1024],saved_ram[sizeof(ram)],asc_bytes[256],mbox_bytes[4096];
static void *asc,*mbox;
static bool held,asc_region,mbox_region,root_sent,installed,root_detached;
static bool device_context_retained,resident_session,recovery_resident,recovery_work_submitted;
static bool recovery_session_failed,recovery_trace_disabled;
static unsigned int recovery_operation,graph_io_lock;
static struct {unsigned int used,status,doorbells;} receive_journal;
static struct work_struct recovery_receive_work;
/* Tentative declaration permits the MMIO recorders to enforce the actual
 * owner's gate even though its definition occurs in the inserted header. */
static bool gfx_poweroff_gate_consumed;
static unsigned int mutex_depth,cancel_calls,schedule_calls,receive_calls,ack_calls;
static unsigned int pm_put_calls,snapshot_calls,asc_reads,asc_writes,ram_writes;
static unsigned int control_calls,cycle_calls,trace_calls,send_calls,gpu_samples;
static unsigned int sleep_calls;
static bool start_write_sticks;
static int pm_result,post_usage,post_error;
static enum rpm_status post_status;
static unsigned int post_disable_depth;
static struct apple_pmgr_gfx_reset_observation observations[106];
static int snapshot_errors[106];
static char logs[131072];static size_t log_used;
static void test_log(const char *fmt,...)
{
 va_list ap;int n;va_start(ap,fmt);
 n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);
 assert(n>=0 && (size_t)n<sizeof(logs)-log_used);log_used+=(size_t)n;
}
#define pr_info(...) test_log(__VA_ARGS__)
#define lockdep_assert_held(p) do {(void)(p);assert(mutex_depth==1);} while(0)
static bool pm_runtime_enabled(struct test_device *d) {return !d->power.disable_depth;}
static bool pm_runtime_active(struct test_device *d) {return d->power.runtime_status==RPM_ACTIVE;}
static bool pm_runtime_suspended(struct test_device *d) {return d->power.runtime_status==RPM_SUSPENDED;}
static int pm_runtime_put_sync_suspend(struct test_device *d);
static void mutex_lock(void *p) {(void)p;assert(!mutex_depth);mutex_depth=1;}
static void mutex_unlock(void *p) {(void)p;assert(mutex_depth==1);mutex_depth=0;}
static void cancel_delayed_work(void *p) {(void)p;assert(mutex_depth==1);cancel_calls++;}
static unsigned int msecs_to_jiffies(unsigned int n) {return n;}
static void schedule_delayed_work(void *p,unsigned int n) {(void)p;assert(mutex_depth==1 && n==10);schedule_calls++;}
static bool sysfs_streq(const char *a,const char *b) {return !strcmp(a,b);}
static u32 readl(void *p)
{
 u32 v;assert(p && mutex_depth==1 && !gfx_poweroff_gate_consumed);
 assert((u8 *)p>=asc_bytes && (u8 *)p<asc_bytes+sizeof(asc_bytes));
 asc_reads++;memcpy(&v,p,4);return v;
}
static void writel(u32 v,void *p)
{
 assert(p && mutex_depth==1 && !gfx_poweroff_gate_consumed);
 assert((u8 *)p>=asc_bytes && (u8 *)p<asc_bytes+sizeof(asc_bytes));
 if(start_write_sticks && p==asc_bytes+0x44) v|=START;
 asc_writes++;memcpy(p,&v,4);
}
static u32 recovery_read32(unsigned int o) {u32 v;assert(o+4<=sizeof(ram));memcpy(&v,ram+o,4);return v;}
static u64 recovery_read64(unsigned int o) {u64 v;assert(o+8<=sizeof(ram));memcpy(&v,ram+o,8);return v;}
static void put32(unsigned int o,u32 v) {assert(o+4<=sizeof(ram));memcpy(ram+o,&v,4);}
static void recovery_write32(unsigned int o,u32 v) {ram_writes++;put32(o,v);}
static void *recovery_ptr(unsigned int o) {assert(o<sizeof(ram));return ram+o;}
static void recovery_invalidate(void *p,size_t n) {(void)p;(void)n;}
static void replay_cache_clean(void *p,void *q) {(void)p;(void)q;}
static bool power_ack(unsigned int a,unsigned int b,unsigned int c) {(void)a;(void)b;(void)c;ack_calls++;return true;}
static bool recovery_messages(void) {assert(!gfx_poweroff_gate_consumed);receive_calls++;return true;}
static bool recovery_control(unsigned int n,bool p) {(void)n;(void)p;control_calls++;return true;}
static bool recovery_cycles(void) {cycle_calls++;return true;}
static bool recovery_trace_off(void) {trace_calls++;return true;}
static bool recovery_send(u64 packet) {(void)packet;send_calls++;return true;}
static void recovery_power_sample(const char *p) {(void)p;gpu_samples++;}
static void ksm_status_sample(const char *p) {(void)p;gpu_samples++;}
static void joined_output_sample(const char *p) {(void)p;gpu_samples++;}
static void usleep_range(unsigned int lo,unsigned int hi)
{
 assert(mutex_depth==1 && gfx_poweroff_gate_consumed && pm_put_calls==1);
 assert(lo==1000 && hi==1100 && sleep_calls<100);sleep_calls++;
}

/* The runner inserts unchanged actual C functions/header at this boundary. */
#include "actual-owner.inc"

int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o)
{
 assert(mutex_depth==1 && snapshot_calls<ARRAY_SIZE(observations));
 for(unsigned int i=0;i<sizeof(*o);i++) assert(!((u8 *)o)[i]);
 *o=observations[snapshot_calls];return snapshot_errors[snapshot_calls++];
}
static int pm_runtime_put_sync_suspend(struct test_device *d)
{
 assert(mutex_depth==1 && consumer && d==&consumer->dev);
 assert(gfx_poweroff_gate_consumed && gfx_poweroff_pm_attempted && !held && !pm_put_calls);
 assert(gfx_reset_scope_sealed && gfx_reset_scope_host_stopped && recovery_session_failed && cancel_calls);
 assert(!ram_writes && !receive_calls && !ack_calls && !control_calls && !cycle_calls && !trace_calls && !send_calls);
 assert(atomic_read(&d->power.usage_count)==1);
 assert(pm_runtime_enabled(d) && pm_runtime_active(d) && !d->power.runtime_error && snapshot_calls==1);
 pm_put_calls++;
 d->power.usage_count.counter=post_usage;d->power.runtime_status=post_status;
 d->power.runtime_error=post_error;d->power.disable_depth=post_disable_depth;
 return pm_result;
}
static unsigned int cases;
static ssize_t command(const char *s) {ssize_t r=recovery_command_store(NULL,NULL,s,strlen(s));assert(!mutex_depth);return r;}
static void cursors(u32 n) {put32(RECOVERY_CONTROL,n);put32(RECOVERY_CONTROL+8,n);put32(RECOVERY_CONTROL+16,n);}
static void fixture(unsigned int phase)
{
 memset(ram,0,sizeof(ram));memset(asc_bytes,0,sizeof(asc_bytes));memset(logs,0,sizeof(logs));log_used=0;
 memset(observations,0,sizeof(observations));memset(snapshot_errors,0,sizeof(snapshot_errors));
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++) owned[i]=&pages[i];
 consumer=&test_consumer;memset(consumer,0,sizeof(*consumer));
 consumer->dev.power.usage_count.counter=1;consumer->dev.power.runtime_status=RPM_ACTIVE;
 asc=asc_bytes;mbox=mbox_bytes;
 held=asc_region=mbox_region=root_sent=installed=device_context_retained=resident_session=recovery_resident=true;
 root_detached=recovery_work_submitted=false;recovery_session_failed=phase==2;recovery_trace_disabled=true;
 gfx_reset_scope_owner_pinned=true;gfx_reset_scope_attempted=false;gfx_reset_scope_sealed=true;gfx_reset_scope_host_stopped=true;
 gfx_poweroff_start_clear_attempted=true;
 gfx_poweroff_gate_consumed=gfx_poweroff_pm_attempted=gfx_poweroff_provider_off_observed=gfx_poweroff_accounting_ok=false;
 gfx_poweroff_snapshot_count=gfx_poweroff_poll_delay_us=0;
 gfx_poweroff_pm_result=gfx_poweroff_snapshot_result=0;
 recovery_operation=0;mutex_depth=cancel_calls=schedule_calls=receive_calls=ack_calls=0;
 pm_put_calls=snapshot_calls=asc_reads=asc_writes=ram_writes=control_calls=cycle_calls=trace_calls=send_calls=gpu_samples=sleep_calls=0;
 pm_result=post_usage=post_error=post_disable_depth=0;post_status=RPM_SUSPENDED;
 start_write_sticks=false;
 memset(&receive_journal,0,sizeof(receive_journal));
 cursors(RECOVERY_CONTROL_INITIAL);put32(RECOVERY_STATUS+0x4900,phase);
 if(phase==2) {put32(RECOVERY_REQUEST,2);put32(RECOVERY_REQUEST+4,1);put32(RECOVERY_STATUS+0x4910,1);}
 u32 v=0x4e;memcpy(asc_bytes+0x48,&v,4);
 for(unsigned int i=0;i<ARRAY_SIZE(observations);i++) observations[i].valid=APPLE_PMGR_GFX_VALID_BEFORE;
 observations[0].domain_on=1;observations[0].before=0x1f0003ff;
}
static void preserve(void)
{
 assert(!ram_writes && !control_calls && !cycle_calls && !trace_calls && !send_calls && !receive_calls && !ack_calls && !gpu_samples);
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++) assert(owned[i]==saved_owned[i]);
 assert(!memcmp(ram,saved_ram,sizeof(ram)));
}
static void save_backing(void) {memcpy(saved_owned,owned,sizeof(owned));memcpy(saved_ram,ram,sizeof(ram));}
static void after_attempt(void)
{
 unsigned int reads=asc_reads,writes=asc_writes,puts=pm_put_calls,sleeps=sleep_calls;
 assert(gfx_poweroff_gate_consumed && recovery_session_failed && gfx_reset_scope_sealed);
 assert(gfx_poweroff_snapshot_count==(puts?snapshot_calls-1:0));
 assert(gfx_poweroff_poll_delay_us==1000*sleeps);
 assert(command("gfx-poweroff")==-EALREADY && pm_put_calls==puts);
 /* Provider/API failure fixtures must not accidentally poison subsequent
  * read-only diagnostics. They are independent calls, still no MMIO. */
 for(unsigned int i=snapshot_calls;i<ARRAY_SIZE(observations);i++) {
  observations[i]=(struct apple_pmgr_gfx_reset_observation){.valid=APPLE_PMGR_GFX_VALID_BEFORE};
  snapshot_errors[i]=0;
 }
 assert(command("sample")== (!recovery_resident?-ENODEV:gfx_poweroff_retained()?6:-EBUSY));
 assert(command("gfx-snapshot")== (!recovery_resident?-ENODEV:gfx_poweroff_retained()?12:-EBUSY));
 assert(command("stop")== (!recovery_resident?-ENODEV:gfx_reset_scope_host_stopped?4:-EPERM));
 assert(command("stop")== (!recovery_resident?-ENODEV:gfx_reset_scope_host_stopped?4:-EPERM));
 assert(command("gfx-reset")<0 && command("control")<0 && command("recover")<0 && command("trace-off")<0 && command("submit")<0);
 recovery_receive_worker(NULL);assert(!schedule_calls && !receive_calls);
 assert(asc_reads==reads && asc_writes==writes && pm_put_calls==puts && sleep_calls==sleeps);
 preserve();cases++;
}
static void rejected(void)
{
 save_backing();assert(command("gfx-poweroff")<0);
 assert(gfx_poweroff_gate_consumed && !gfx_poweroff_pm_attempted && !pm_put_calls);
 after_attempt();
}
static void set_asc(unsigned int offset,u32 value) {memcpy(asc_bytes+offset,&value,4);}

int main(void)
{
 for(unsigned int phase=0;phase<5;phase++) for(unsigned int failed=0;failed<2;failed++) {
  fixture(phase);recovery_session_failed=failed;save_backing();
  if(phase==0 || phase==2) {
   assert(command("gfx-poweroff")==12 && pm_put_calls==1 && snapshot_calls==2 && !sleep_calls);
   assert(!held && gfx_poweroff_pm_attempted && gfx_poweroff_provider_off_observed && gfx_poweroff_accounting_ok);
   assert(consumer->dev.power.usage_count.counter==0 && pm_runtime_suspended(&consumer->dev));after_attempt();
  } else rejected();
 }
 puts("PASS actual phase0/phase2 admission, one normal PM put, preserved174 pages, permanent attempt gate and MMIO-free post-attempt diagnostics/stop/worker");

 for(unsigned int n=0;n<28;n++) {
  fixture(2);
  switch(n) {
  case 0:gfx_reset_scope_owner_pinned=false;break;
  case 1:resident_session=false;break;
  case 2:held=false;break;
  case 3:consumer=NULL;break;
  case 4:consumer->dev.power.runtime_status=RPM_SUSPENDED;break;
  case 5:asc=NULL;break;
  case 6:mbox=NULL;break;
  case 7:asc_region=false;break;
  case 8:mbox_region=false;break;
  case 9:root_sent=false;break;
  case 10:installed=false;break;
  case 11:root_detached=true;break;
  case 12:device_context_retained=false;break;
  case 13:recovery_work_submitted=true;break;
  case 14:cursors(RECOVERY_CONTROL_INITIAL-1);break;
  case 15:cursors(RECOVERY_CONTROL_LAST+1);break;
  case 16:gfx_reset_scope_host_stopped=false;break;
  case 17:set_asc(0x44,START);break;
  case 18:set_asc(0x48,0x4c);break;
  case 19:consumer->dev.power.disable_depth=1;break;
  case 20:consumer->dev.power.usage_count.counter=0;break;
  case 21:consumer->dev.power.usage_count.counter=2;break;
  case 22:consumer->dev.power.usage_count.counter=-1;break;
  case 23:consumer->dev.power.runtime_error=-EIO;break;
  case 24:consumer->dev.power.runtime_status=RPM_RESUMING;break;
  case 25:consumer->dev.power.runtime_status=RPM_SUSPENDING;break;
  case 26:gfx_poweroff_start_clear_attempted=false;break;
  case 27:recovery_resident=false;break;
  }
  rejected();
 }
 for(unsigned int page=0;page<ARRAY_SIZE(owned);page++) {fixture(2);owned[page]=NULL;rejected();}
 for(unsigned int ring=0;ring<ARRAY_SIZE(recovery_work_cursors);ring++) for(unsigned int word=0;word<3;word++) {
  fixture(2);put32(recovery_work_cursors[ring]+word*8,1);rejected();
 }
 for(unsigned int record=0;record<256;record++) {fixture(2);put32(RECOVERY_STATUS+0x40b8+record*8,9);rejected();}
 for(unsigned int word=0;word<2;word++) {fixture(2);put32(RECOVERY_CONTROL+word*8,RECOVERY_CONTROL_INITIAL-1);rejected();}
 for(unsigned int n=0;n<4;n++) {
  fixture(2);u32 controls[]={32,33,127,128};cursors(controls[n]);
  put32(RECOVERY_STATUS+0x40b8,8);put32(RECOVERY_STATUS+0x40b8+255*8,1);
  save_backing();
  assert(command("gfx-poweroff")==12 && pm_put_calls==1);after_attempt();
 }
 for(unsigned int n=1;n<4;n++) {
  fixture(2);set_asc(0x48,0x4c|n);save_backing();
  assert(command("gfx-poweroff")==12 && pm_put_calls==1);after_attempt();
 }
 puts("PASS all174 page pins, mapping/context/private-consumer/PM-accounting guards, START-clear/native idle, all36 work words, all256 TA records and control32..128 equality");

 /* A failed suspend may have committed the decrement and physical OFF. The
  * negative PM result remains authoritative and must never permit a retry. */
 for(unsigned int n=0;n<6;n++) {
  fixture(2);save_backing();pm_result=-EIO;
  switch(n) {
  case 0:break;
  case 1:post_status=RPM_ACTIVE;observations[1].domain_on=1;observations[1].before=0xff;break;
  case 2:post_usage=1;break;
  case 3:post_error=-ETIMEDOUT;break;
  case 4:post_disable_depth=1;break;
  case 5:post_status=RPM_RESUMING;break;
  }
  assert(command("gfx-poweroff")==-EIO && pm_put_calls==1 && !held);
  after_attempt();
 }
 for(unsigned int n=0;n<5;n++) {
  fixture(2);save_backing();
  switch(n) {
  case 0:post_usage=1;break;
  case 1:post_usage=-1;break;
  case 2:post_status=RPM_ACTIVE;break;
  case 3:post_error=-EIO;break;
  case 4:post_disable_depth=1;break;
  }
  assert(command("gfx-poweroff")==-EIO && pm_put_calls==1 && gfx_poweroff_provider_off_observed && !gfx_poweroff_accounting_ok);
  after_attempt();
 }
 puts("PASS PM-error preservation with committed OFF, PM accounting inconsistencies, held flag cleared before call and no duplicate PM decrement");

 fixture(2);save_backing();pm_result=1;
 assert(command("gfx-poweroff")==12 && pm_put_calls==1 && gfx_poweroff_provider_off_observed && gfx_poweroff_accounting_ok);
 after_attempt();

 /* Provider OFF requires a valid snapshot, domain_on=0 and every relevant
  * RESET/AUTO/PS-reset/BUSY/disable/ACTUAL/TARGET bit clear. */
 for(unsigned int bit=0;bit<32;bit++) if((0x90001cffU>>bit)&1) {
  fixture(2);save_backing();
  for(unsigned int i=1;i<ARRAY_SIZE(observations);i++) observations[i].before=1U<<bit;
  assert(command("gfx-poweroff")==-ETIMEDOUT && pm_put_calls==1 && snapshot_calls==102 && sleep_calls==100);
  assert(!gfx_poweroff_provider_off_observed);after_attempt();
 }
 fixture(2);save_backing();
 for(unsigned int i=1;i<ARRAY_SIZE(observations);i++) observations[i].domain_on=1;
 assert(command("gfx-poweroff")==-ETIMEDOUT && snapshot_calls==102 && sleep_calls==100);
 assert(!gfx_poweroff_provider_off_observed);after_attempt();
 fixture(2);save_backing();
 for(unsigned int i=1;i<ARRAY_SIZE(observations);i++) {
  observations[i].domain_on=1;observations[i].before=0xff;
 }
 observations[101]=(struct apple_pmgr_gfx_reset_observation){.valid=APPLE_PMGR_GFX_VALID_BEFORE};
 snapshot_errors[101]=-EIO;
 assert(command("gfx-poweroff")==-EIO && snapshot_calls==102 && sleep_calls==100);
 assert(!gfx_poweroff_provider_off_observed);after_attempt();
 for(unsigned int off_at=1;off_at<=101;off_at+=25) {
  fixture(2);save_backing();
  for(unsigned int i=1;i<off_at;i++) {observations[i].domain_on=1;observations[i].before=0xff;}
  assert(command("gfx-poweroff")==12 && snapshot_calls==off_at+1 && sleep_calls==off_at-1);
  assert(gfx_poweroff_provider_off_observed);after_attempt();
 }
 for(unsigned int bit=0;bit<32;bit++) if(!((0x90001cffU>>bit)&1)) {
  fixture(2);save_backing();observations[1].before=1U<<bit;
  assert(command("gfx-poweroff")==12 && snapshot_calls==2 && !sleep_calls && gfx_poweroff_provider_off_observed);
  after_attempt();
 }
 puts("PASS provider OFF bit predicate, normal-PM-return/domain-still-ON timeout and101-sample/100-delay bounded observation including last-sample OFF");

 /* Observations with invalid BEFORE must not grant OFF based on poisoned
  * fields. API failures never turn into a second PM call or an MMIO probe. */
 for(unsigned int n=0;n<6;n++) {
  fixture(2);save_backing();
  switch(n) {
  case 0:snapshot_errors[0]=-EIO;break;
  case 1:observations[0].valid=0;break;
  case 2:observations[0].operation_error=-EIO;break;
  case 3:observations[0].cleanup_error=-EIO;break;
  case 4:observations[0].domain_on=0;observations[0].before=0;break;
  case 5:snapshot_errors[0]=1;break;
  }
  rejected();
 }
 for(unsigned int bit=0;bit<32;bit++) if((0x80001cffU>>bit)&1) {
  fixture(2);save_backing();observations[0].before^=1U<<bit;rejected();
 }
 for(unsigned int n=0;n<5;n++) {
  fixture(2);save_backing();
  for(unsigned int i=1;i<ARRAY_SIZE(observations);i++) {
   switch(n) {
   case 0:snapshot_errors[i]=-EIO;break;
   case 1:observations[i].valid=0;break;
   case 2:observations[i].operation_error=-EIO;break;
   case 3:observations[i].cleanup_error=-EIO;break;
   case 4:snapshot_errors[i]=1;break;
   }
  }
  assert(command("gfx-poweroff")<0 && pm_put_calls==1 && !gfx_poweroff_provider_off_observed && snapshot_calls==2 && !sleep_calls);
  after_attempt();
 }
 puts("PASS provider pre/post read errors, invalid/poisoned observations and no unsafe MMIO fallbacks after attempted or refused power-off");

 fixture(2);save_backing();
 assert(command("gfx-reset")<0 && command("control")<0 && command("recover")<0 && command("trace-off")<0 && command("submit")<0 && command("nonsense")<0);
 assert(!gfx_poweroff_gate_consumed && !pm_put_calls && !snapshot_calls);preserve();cases++;
 fixture(2);save_backing();
 assert(command("sample")==6 && command("gfx-snapshot")==12 && !gfx_poweroff_gate_consumed && !pm_put_calls);
 preserve();cases++;
 fixture(2);save_backing();gfx_reset_scope_host_stopped=false;gfx_poweroff_start_clear_attempted=false;set_asc(0x44,START|0x20);
 assert(command("stop")==4 && asc_writes==1 && gfx_reset_scope_host_stopped && !pm_put_calls);
 assert(command("stop")==4 && asc_writes==1);
 assert(command("gfx-poweroff")==12 && pm_put_calls==1);after_attempt();
 for(unsigned int n=0;n<2;n++) {
  fixture(2);save_backing();gfx_reset_scope_host_stopped=false;gfx_poweroff_start_clear_attempted=false;set_asc(0x44,START|0x20);
  if(n) set_asc(0x48,0x4c);else start_write_sticks=true;
  assert(command("stop")==-EAGAIN && asc_writes==1 && !pm_put_calls);
  assert(command("stop")==-EAGAIN && asc_writes==1);
  rejected();
 }
 puts("PASS restricted typed commands, pre-attempt read-only diagnostics and packet-free idempotent stop before the one power-off attempt");
 printf("RAM power-off owner C replay cases: %u\n",cases);return 0;
}
