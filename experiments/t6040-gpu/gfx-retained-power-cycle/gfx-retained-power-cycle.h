/* SPDX-License-Identifier: GPL-2.0-only */
/* One memory-preserving, separately owned transport re-entry experiment.
 * The first proven drain/PWRGATE/OFF epoch stays immutable. A second PM
 * reference and paired coordination epoch never reopen application work.
 * Autonomous HELLO/map observation is not an application rejoin contract. */
#ifndef GFX_RETAINED_POWER_CYCLE_TRIAL
#error Distinct retained power-cycle profile required
#endif
#include "gfx-native-powergate-drain.h"
#include "gfx-coordinate-core.h"
#define GFX_RETAINED_CYCLE_PROTOCOL_RECORDS 16U
#define GFX_RETAINED_CYCLE_PROTOCOL_POLLS 4001U
#define GFX_RETAINED_CYCLE_PROTOCOL_TIMEOUT_MS 4000U
struct gfx_retained_cycle_record { u64 message, metadata; };
static struct gfx_retained_cycle_record gfx_retained_cycle_journal[GFX_RETAINED_CYCLE_PROTOCOL_RECORDS];
static struct page *gfx_retained_cycle_pages[GFX_RESET_SCOPE_PAGES];
static u64 gfx_retained_cycle_pas[GFX_RESET_SCOPE_PAGES];
static struct platform_device *gfx_retained_cycle_consumer;
static void __iomem *gfx_retained_cycle_asc, *gfx_retained_cycle_mbox;
static u64 *gfx_retained_cycle_bootstrap, *gfx_retained_cycle_borrowed;
static u64 *gfx_retained_cycle_target_page, *gfx_retained_cycle_target_slot;
static u64 gfx_retained_cycle_root_entry;
static bool gfx_retained_cycle_identity_captured, gfx_retained_cycle_intent;
static bool gfx_retained_cycle_identities_preserved, gfx_retained_cycle_first_off_preserved;
static bool gfx_retained_cycle_pm_get_attempted, gfx_retained_cycle_second_ref_held;
static bool gfx_retained_cycle_boundary_qualified, gfx_retained_cycle_start_attempted;
static bool gfx_retained_cycle_hello_replied, gfx_retained_cycle_endpoint_map;
static bool gfx_retained_cycle_request_attempted, gfx_retained_cycle_ack_observed;
static bool gfx_retained_cycle_cpu_stopped, gfx_retained_cycle_clear10_attempted;
static bool gfx_retained_cycle_clear20_attempted, gfx_retained_cycle_off_attempted;
static bool gfx_retained_cycle_pm_put_attempted, gfx_retained_cycle_provider_off_observed;
static bool gfx_retained_cycle_accounting_ok, gfx_retained_cycle_complete;
static u64 gfx_retained_cycle_ack_message, gfx_retained_cycle_ack_metadata;
static unsigned int gfx_retained_cycle_ack_polls, gfx_retained_cycle_idle_polls;
static unsigned int gfx_retained_cycle_off_samples;
static int gfx_retained_cycle_pm_put_result, gfx_retained_cycle_off_snapshot_result;
static int gfx_retained_cycle_pm_get_result;
static u32 gfx_retained_cycle_control, gfx_retained_cycle_status, gfx_retained_cycle_rx, gfx_retained_cycle_tx;
static unsigned int gfx_retained_cycle_records, gfx_retained_cycle_polls;
static unsigned int gfx_retained_cycle_hello_reply_attempts, gfx_retained_cycle_map_reply_attempts;
static u8 gfx_retained_cycle_map_seen;
static u32 gfx_retained_cycle_appmap;
static const char *gfx_retained_cycle_refusal="none";
static struct gfx_coord_session gfx_retained_cycle_coord_session;
static struct gfx_coord_observation gfx_retained_cycle_coord_on;
static struct gfx_coord_observation gfx_retained_cycle_coord_off;
static int gfx_retained_cycle_coordinate_on(void);
static int gfx_retained_cycle_coordinate_off(void);
static bool gfx_retained_cycle_first_coord_complete(void);

static void gfx_retained_cycle_log(const char *phase,int result)
{
 pr_info("m4rch gfx-retained-cycle: phase=%s result=%d refused_condition=%s intent=%u identity_captured=%u identities_preserved=%u first_off_preserved=%u first_off_fields_historical=1 pm_get_attempted=%u pm_get_result=%d second_ref_held=%u held=%u usage=%d runtime_error=%d runtime_status=%d active=%u suspended=%u second_on_attempted=%u second_on_complete=%u boundary_qualified=%u control44=%#x status48=%#x rx_status=%#x tx_status=%#x start_attempted=%u hello_reply_attempts=%u hello_replied=%u map_reply_attempts=%u endpoint_map=%u appmap=%#x map_seen=%#x protocol_records=%u protocol_polls=%u second_request_attempted=%u second_ack_observed=%u second_ack_message=%#llx second_ack_metadata=%#llx second_ack_polls=%u second_idle_polls=%u second_clear10_attempted=%u second_clear20_attempted=%u second_cpu_stopped=%u second_off_attempted=%u second_off_complete=%u second_pm_put_attempted=%u second_pm_put_result=%d second_off_snapshot_result=%d second_off_samples=%u second_provider_off_observed=%u second_accounting_ok=%u powercycle_complete=%u application_rejoined=0 allocations_retained=%u restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_retained_cycle_refusal,gfx_retained_cycle_intent,
  gfx_retained_cycle_identity_captured,gfx_retained_cycle_identities_preserved,
  gfx_retained_cycle_first_off_preserved,gfx_retained_cycle_pm_get_attempted,
  gfx_retained_cycle_pm_get_result,gfx_retained_cycle_second_ref_held,held,
  consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_error):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_status):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  consumer?pm_runtime_suspended(&consumer->dev):false,
  gfx_retained_cycle_coord_session.on_attempted,gfx_retained_cycle_coord_session.on_complete,
  gfx_retained_cycle_boundary_qualified,gfx_retained_cycle_control,gfx_retained_cycle_status,
  gfx_retained_cycle_rx,gfx_retained_cycle_tx,gfx_retained_cycle_start_attempted,gfx_retained_cycle_hello_reply_attempts,
  gfx_retained_cycle_hello_replied,gfx_retained_cycle_map_reply_attempts,
  gfx_retained_cycle_endpoint_map,gfx_retained_cycle_appmap,gfx_retained_cycle_map_seen,
  gfx_retained_cycle_records,gfx_retained_cycle_polls,gfx_retained_cycle_request_attempted,
  gfx_retained_cycle_ack_observed,(unsigned long long)gfx_retained_cycle_ack_message,
  (unsigned long long)gfx_retained_cycle_ack_metadata,gfx_retained_cycle_ack_polls,
  gfx_retained_cycle_idle_polls,gfx_retained_cycle_clear10_attempted,
  gfx_retained_cycle_clear20_attempted,gfx_retained_cycle_cpu_stopped,
  gfx_retained_cycle_off_attempted,gfx_retained_cycle_coord_session.off_complete,
  gfx_retained_cycle_pm_put_attempted,gfx_retained_cycle_pm_put_result,
  gfx_retained_cycle_off_snapshot_result,gfx_retained_cycle_off_samples,
  gfx_retained_cycle_provider_off_observed,gfx_retained_cycle_accounting_ok,
  gfx_retained_cycle_complete,GFX_RESET_SCOPE_PAGES);
}

static int gfx_retained_cycle_refuse(const char *condition,int result)
{
 gfx_retained_cycle_refusal=condition;
 gfx_retained_cycle_log("retained-return",result);
 return result;
}

/* Compare exact retained host identities and root descriptor. This does not
 * prove that GPU hardware has retained its UAT state through physical OFF. */
static bool gfx_retained_cycle_identity(bool capture)
{
 unsigned int i;
 u64 entry;
 if(!gfx_poweroff_retained() || !target_slot || !target_page || !bootstrap)
  return false;
 recovery_invalidate(target_slot,sizeof(*target_slot));
 entry=READ_ONCE(*target_slot);
 if(entry!=(page_to_phys(owned[borrowed_l1?1:0])|3ULL)) return false;
 if(capture) {
  if(gfx_retained_cycle_identity_captured) return false;
  gfx_retained_cycle_consumer=consumer;gfx_retained_cycle_asc=asc;
  gfx_retained_cycle_mbox=mbox;gfx_retained_cycle_bootstrap=bootstrap;
  gfx_retained_cycle_borrowed=borrowed_l1;gfx_retained_cycle_target_page=target_page;
  gfx_retained_cycle_target_slot=target_slot;gfx_retained_cycle_root_entry=entry;
  for(i=0;i<ARRAY_SIZE(owned);i++) {
   gfx_retained_cycle_pages[i]=owned[i];gfx_retained_cycle_pas[i]=page_to_phys(owned[i]);
  }
  gfx_retained_cycle_identity_captured=true;
 } else {
  if(!gfx_retained_cycle_identity_captured || consumer!=gfx_retained_cycle_consumer ||
     asc!=gfx_retained_cycle_asc || mbox!=gfx_retained_cycle_mbox ||
     bootstrap!=gfx_retained_cycle_bootstrap || borrowed_l1!=gfx_retained_cycle_borrowed ||
     target_page!=gfx_retained_cycle_target_page || target_slot!=gfx_retained_cycle_target_slot ||
     entry!=gfx_retained_cycle_root_entry) return false;
  for(i=0;i<ARRAY_SIZE(owned);i++)
   if(owned[i]!=gfx_retained_cycle_pages[i] || page_to_phys(owned[i])!=gfx_retained_cycle_pas[i])
    return false;
 }
 return true;
}

static bool gfx_retained_cycle_first_off(void)
{
 return gfx_native_powergate_intent && gfx_native_powergate_request_attempted &&
  gfx_native_powergate_ack_observed && gfx_native_powergate_cpu_stopped &&
  gfx_native_powergate_clear10_attempted && gfx_native_powergate_clear20_attempted &&
  gfx_native_powergate_off_delegated && gfx_poweroff_gate_consumed &&
  gfx_poweroff_pm_attempted && gfx_poweroff_pm_result>=0 &&
  gfx_poweroff_provider_off_observed && !gfx_poweroff_snapshot_result &&
  gfx_poweroff_accounting_ok && gfx_reset_scope_host_stopped &&
  gfx_reset_scope_sealed && recovery_session_failed && !recovery_work_submitted &&
  gfx_retained_cycle_first_coord_complete();
}

/* Only PMGR/software and retained DRAM are touched before the second get. */
static int gfx_retained_cycle_off_admission(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 gfx_retained_cycle_first_off_preserved=gfx_retained_cycle_first_off();
 if(!gfx_retained_cycle_first_off_preserved)
  return gfx_retained_cycle_refuse("first-off-unqualified",-EPERM);
 gfx_retained_cycle_identities_preserved=gfx_retained_cycle_identity(false);
 if(!gfx_retained_cycle_identities_preserved)
  return gfx_retained_cycle_refuse("retained-identity-changed",-EBUSY);
 if(held || !consumer || !pm_runtime_enabled(&consumer->dev) ||
    !pm_runtime_suspended(&consumer->dev) || pm_runtime_active(&consumer->dev) ||
    atomic_read(&consumer->dev.power.usage_count) || READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_retained_cycle_refuse("first-off-accounting-changed",-EBUSY);
 ret=gfx_poweroff_snapshot("retained-cycle-before-get",0,&observation);
 if(ret) return gfx_retained_cycle_refuse("fresh-off-snapshot-error",ret);
 if(observation.domain_on || (observation.before&GFX_POWER_OFF_STATE_MASK))
  return gfx_retained_cycle_refuse("fresh-physical-off-unqualified",-EBUSY);
 return 0;
}

/* Called only with a fresh owned second reference and physical ACTIVE.
 * Status6e/6c/48 refuses before START; it never invokes old warm START/INIT. */
static int gfx_retained_cycle_cold_boundary(void)
{
 gfx_retained_cycle_control=readl(asc+0x44);
 gfx_retained_cycle_status=readl(asc+0x48);
 gfx_retained_cycle_rx=readl(mbox+0x114);
 gfx_retained_cycle_tx=readl(mbox+0x110);
 gfx_retained_cycle_log("cold-boundary",0);
 if(gfx_retained_cycle_control==~0U || gfx_retained_cycle_status==~0U ||
    gfx_retained_cycle_rx==~0U || gfx_retained_cycle_tx==~0U)
  return gfx_retained_cycle_refuse("cold-boundary-invalid",-EIO);
 if((gfx_retained_cycle_control&START) || gfx_retained_cycle_status!=0x6a ||
    !(gfx_retained_cycle_rx&EMPTY) || (gfx_retained_cycle_tx&BIT(16)))
  return gfx_retained_cycle_refuse("cold-boundary-unqualified",-EBUSY);
 return 0;
}

static int gfx_retained_cycle_send(u64 packet,bool hello)
{
 u32 tx=readl(mbox+0x110);
 if(tx==~0U) return gfx_retained_cycle_refuse("protocol-tx-invalid",-EIO);
 if(tx&BIT(16)) return gfx_retained_cycle_refuse("protocol-tx-full",-EBUSY);
 if(hello) gfx_retained_cycle_hello_reply_attempts++;
 else gfx_retained_cycle_map_reply_attempts++;
 wmb();writeq(packet,mbox+0x800);writeq(0,mbox+0x808);
 pr_info("m4rch gfx-retained-cycle-tx: hello=%u packet=%#llx endpoint=0 root_publications=0 application_starts=0 init220_requests=0\n",
  hello,(unsigned long long)packet);
 return 0;
}

static int gfx_retained_cycle_protocol(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_RETAINED_CYCLE_PROTOCOL_TIMEOUT_MS);
 unsigned int i;
 for(i=0;i<GFX_RETAINED_CYCLE_PROTOCOL_POLLS;i++) {
  u32 rx;
  if(!time_before(jiffies,until)) return gfx_retained_cycle_refuse("protocol-deadline",-ETIMEDOUT);
  gfx_retained_cycle_polls++;
  rx=readl(mbox+0x114);
  if(rx==~0U) return gfx_retained_cycle_refuse("protocol-rx-invalid",-EIO);
  if(!(rx&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   unsigned int type=(message>>52)&0xff,endpoint=metadata&0xff;
   int ret;
   /* Preserve every removed word before interpreting it or issuing a reply. */
   gfx_retained_cycle_journal[gfx_retained_cycle_records].message=message;
   gfx_retained_cycle_journal[gfx_retained_cycle_records].metadata=metadata;
   gfx_retained_cycle_records++;
   pr_info("m4rch gfx-retained-cycle-rx: epoch=2 index=%u message=%#llx metadata=%#llx\n",
    gfx_retained_cycle_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_retained_cycle_refuse("protocol-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_retained_cycle_refuse("protocol-frame-invalid",-EIO);
   if(endpoint!=0) return gfx_retained_cycle_refuse("protocol-endpoint-unqualified",-EPROTO);
   if(!gfx_retained_cycle_hello_replied && type==1) {
    if((message&0xffff)!=12 || ((message>>16)&0xffff)!=12)
     return gfx_retained_cycle_refuse("hello-version-unqualified",-EPROTO);
    ret=gfx_retained_cycle_send((2ULL<<52)|(12ULL<<16)|12ULL,true);
    if(ret) return ret;
    gfx_retained_cycle_hello_replied=true;
   } else if(gfx_retained_cycle_hello_replied && type==8) {
    unsigned int base=(message>>32)&0x3f;
    bool last=!!(message&(1ULL<<51));
    if(base>1 || (u32)message!=3 ||
       (!gfx_retained_cycle_map_seen && (base!=0 || last)) ||
       (gfx_retained_cycle_map_seen && (base!=1 || !last)))
     return gfx_retained_cycle_refuse("endpoint-map-shape-unqualified",-EPROTO);
    if(gfx_retained_cycle_map_seen&BIT(base))
     return gfx_retained_cycle_refuse("duplicate-endpoint-map",-EPROTO);
    ret=gfx_retained_cycle_send((8ULL<<52)|((u64)base<<32)|(last?(1ULL<<51):1ULL),false);
    if(ret) return ret;
    gfx_retained_cycle_map_seen|=BIT(base);
    if(base==1) gfx_retained_cycle_appmap=(u32)message;
    if(last) {
     gfx_retained_cycle_endpoint_map=true;
     /* Native HELLO→status5/finalmapACK→status6 permits a separately owned
      * status7/PWRGATE202 management hypothesis, without application rejoin. */
     gfx_retained_cycle_log("autonomous-map-retained",0);
     return 0;
    }
   } else return gfx_retained_cycle_refuse("protocol-message-unqualified",-EPROTO);
   if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
    return gfx_retained_cycle_refuse("protocol-record-limit",-EOVERFLOW);
  }
  usleep_range(1000,1100);
 }
 return gfx_retained_cycle_refuse("protocol-poll-limit",-ETIMEDOUT);
}

static int gfx_retained_cycle_management(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS);
 unsigned int i;
 u32 rx,tx,control,status;
 if(!gfx_retained_cycle_hello_replied || !gfx_retained_cycle_endpoint_map ||
    !gfx_retained_cycle_coord_session.on_complete || !gfx_retained_cycle_second_ref_held)
  return gfx_retained_cycle_refuse("second-management-state-unqualified",-EPERM);
 if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_retained_cycle_refuse("second-journal-no-ack-capacity",-EOVERFLOW);
 if(!held || !pm_runtime_active(&consumer->dev) || !pm_runtime_enabled(&consumer->dev) ||
    atomic_read(&consumer->dev.power.usage_count)!=1 || READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_retained_cycle_refuse("second-management-pm-unqualified",-EBUSY);
 control=readl(asc+0x44);status=readl(asc+0x48);
 rx=readl(mbox+0x114);tx=readl(mbox+0x110);
 gfx_retained_cycle_control=control;gfx_retained_cycle_status=status;
 gfx_retained_cycle_rx=rx;gfx_retained_cycle_tx=tx;
 if(control==~0U || status==~0U || rx==~0U || tx==~0U)
  return gfx_retained_cycle_refuse("second-management-fifo-invalid",-EIO);
 if(!(control&START)) return gfx_retained_cycle_refuse("second-management-start-clear",-EBUSY);
 if(!(rx&EMPTY) || (tx&BIT(16)))
  return gfx_retained_cycle_refuse("second-management-fifo-unqualified",-EBUSY);
 gfx_retained_cycle_request_attempted=true;
 gfx_retained_cycle_log("second-pwr-gate-intent",0);
 wmb();writeq(GFX_NATIVE_POWERGATE_REQUEST,mbox+0x800);writeq(0,mbox+0x808);
 for(i=0;i<GFX_NATIVE_POWERGATE_ACK_POLLS;i++) {
  if(!time_before(jiffies,until)) return gfx_retained_cycle_refuse("second-ack-deadline",-ETIMEDOUT);
  gfx_retained_cycle_ack_polls++;rx=readl(mbox+0x114);
  if(rx==~0U) return gfx_retained_cycle_refuse("second-ack-rx-invalid",-EIO);
  if(!(rx&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   /* Record removed frames independently of the first application journal. */
   if(gfx_retained_cycle_records<GFX_RETAINED_CYCLE_PROTOCOL_RECORDS) {
    gfx_retained_cycle_journal[gfx_retained_cycle_records].message=message;
    gfx_retained_cycle_journal[gfx_retained_cycle_records].metadata=metadata;
    gfx_retained_cycle_records++;
   } else {
    pr_info("m4rch gfx-retained-cycle-rx: epoch=2 index=overflow message=%#llx metadata=%#llx\n",
     (unsigned long long)message,(unsigned long long)metadata);
    return gfx_retained_cycle_refuse("second-journal-full",-EOVERFLOW);
   }
   pr_info("m4rch gfx-retained-cycle-rx: epoch=2 index=%u message=%#llx metadata=%#llx\n",
    gfx_retained_cycle_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_retained_cycle_refuse("second-ack-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_retained_cycle_refuse("second-ack-frame-invalid",-EIO);
   if((metadata&0xff)!=0 || ((message>>52)&0xf)!=7 ||
      ((message&0xff)!=1 && (message&0xff)!=2))
    return gfx_retained_cycle_refuse("second-ack-unqualified",-EPROTO);
   gfx_retained_cycle_ack_message=message;gfx_retained_cycle_ack_metadata=metadata;
   gfx_retained_cycle_ack_observed=true;
   rx=readl(mbox+0x114);
   if(rx==~0U) return gfx_retained_cycle_refuse("second-post-ack-rx-invalid",-EIO);
   if(!(rx&EMPTY)) return gfx_retained_cycle_refuse("second-post-ack-rx-pending",-EBUSY);
   return 0;
  }
  usleep_range(1000,1100);
 }
 return gfx_retained_cycle_refuse("second-ack-poll-limit",-ETIMEDOUT);
}

static int gfx_retained_cycle_stop_cpu(void)
{
 unsigned int i;
 u32 control,rx,status;
 bool idle=false;
 for(i=0;i<GFX_NATIVE_POWERGATE_IDLE_POLLS;i++) {
  status=readl(asc+0x48);gfx_retained_cycle_idle_polls++;
  if(status==~0U) return gfx_retained_cycle_refuse("second-idle-invalid",-EIO);
  if(status&3) {idle=true;break;}
  if(i+1<GFX_NATIVE_POWERGATE_IDLE_POLLS) usleep_range(1000,1100);
 }
 if(!idle) return gfx_retained_cycle_refuse("second-idle-timeout",-ETIMEDOUT);
 rx=readl(mbox+0x114);control=readl(asc+0x44);
 if(rx==~0U || control==~0U) return gfx_retained_cycle_refuse("second-stop-invalid",-EIO);
 if(!(rx&EMPTY) || !(control&START)) return gfx_retained_cycle_refuse("second-stop-unqualified",-EBUSY);
 gfx_retained_cycle_clear10_attempted=true;writel(control&~0x10U,asc+0x44);
 control=readl(asc+0x44);
 if(control==~0U || (control&START)) return gfx_retained_cycle_refuse("second-clear10-failed",-EIO);
 control=readl(asc+0x44);
 if(control==~0U || (control&START)) return gfx_retained_cycle_refuse("second-start-reasserted",-EIO);
 gfx_retained_cycle_clear20_attempted=true;writel(control&~0x20U,asc+0x44);
 control=readl(asc+0x44);status=readl(asc+0x48);
 if(control==~0U || status==~0U || (control&0x30U) || !(status&3))
  return gfx_retained_cycle_refuse("second-clear20-or-idle-failed",-EIO);
 gfx_retained_cycle_control=control;gfx_retained_cycle_status=status;
 gfx_retained_cycle_cpu_stopped=true;
 gfx_retained_cycle_log("second-cpu-stop-return",0);
 return 0;
}

static int gfx_retained_cycle_poweroff(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 unsigned int i;
 u32 control,status;
 int ret;
 if(!gfx_retained_cycle_cpu_stopped || !gfx_retained_cycle_ack_observed ||
    !gfx_retained_cycle_second_ref_held || !held || !pm_runtime_active(&consumer->dev) ||
    !pm_runtime_enabled(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error) || !recovery_idle() ||
    !gfx_retained_cycle_identity(false))
  return gfx_retained_cycle_refuse("second-off-preconditions-unqualified",-EBUSY);
 control=readl(asc+0x44);status=readl(asc+0x48);
 if(control==~0U || status==~0U)
  return gfx_retained_cycle_refuse("second-off-cpu-state-invalid",-EIO);
 if((control&START) || !(status&3))
  return gfx_retained_cycle_refuse("second-off-cpu-state-changed",-EBUSY);
 ret=gfx_poweroff_snapshot("retained-cycle-before-second-off",0,&observation);
 if(ret) return gfx_retained_cycle_refuse("second-before-off-snapshot-error",ret);
 if(!observation.domain_on || (observation.before&0x80001cffU)!=0xffU)
  return gfx_retained_cycle_refuse("second-before-off-active-unqualified",-EBUSY);
 /* The new epoch's OFF intent is consumed before coordination callbacks. */
 gfx_retained_cycle_off_attempted=true;
 gfx_retained_cycle_log("second-coordinate-off-intent",0);
 ret=gfx_retained_cycle_coordinate_off();
 if(ret) return gfx_retained_cycle_refuse("second-coordinate-off-failed",ret);
 gfx_retained_cycle_pm_put_attempted=true;
 held=false;gfx_retained_cycle_second_ref_held=false;
 gfx_retained_cycle_pm_put_result=pm_runtime_put_sync_suspend(&consumer->dev);
 /* No ASC/SGX/mailbox/PMP/PMC reads or writes follow this consumed put. */
 gfx_retained_cycle_off_snapshot_result=-ETIMEDOUT;
 for(i=0;i<GFX_POWER_OFF_POLL_SAMPLES;i++) {
  gfx_retained_cycle_off_samples++;
  ret=gfx_poweroff_snapshot("retained-cycle-after-second-off",i,&observation);
  if(ret) {gfx_retained_cycle_off_snapshot_result=ret;break;}
  if(!observation.domain_on && !(observation.before&GFX_POWER_OFF_STATE_MASK)) {
   gfx_retained_cycle_provider_off_observed=true;
   gfx_retained_cycle_off_snapshot_result=0;break;
  }
  if(i+1<GFX_POWER_OFF_POLL_SAMPLES)
   usleep_range(GFX_POWER_OFF_POLL_DELAY_US,GFX_POWER_OFF_POLL_DELAY_US+100);
 }
 gfx_retained_cycle_accounting_ok=pm_runtime_enabled(&consumer->dev) &&
  pm_runtime_suspended(&consumer->dev) && !pm_runtime_active(&consumer->dev) &&
  !atomic_read(&consumer->dev.power.usage_count) && !READ_ONCE(consumer->dev.power.runtime_error) && !held;
 ret=gfx_retained_cycle_pm_put_result<0?gfx_retained_cycle_pm_put_result:gfx_retained_cycle_off_snapshot_result;
 if(!ret && !gfx_retained_cycle_accounting_ok) ret=-EIO;
 if(ret) return gfx_retained_cycle_refuse("second-off-observation-failed",ret);
 gfx_retained_cycle_log("second-physical-off",0);
 return 0;
}

static int gfx_retained_cycle_attempt(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_retained_cycle_intent) return gfx_retained_cycle_refuse("intent-already-consumed",-EALREADY);
 gfx_retained_cycle_intent=true;
 /* The distinct intent also seals the copied worker. Do not repair, clear or
  * rewrite historical first-epoch flags to manufacture a successful premise. */
 cancel_delayed_work(&recovery_receive_work);
 gfx_retained_cycle_log("intent",0);
 ret=gfx_retained_cycle_off_admission();
 if(ret) return ret;
 /* A new reference is consumed once; first epoch's put and gate stay intact.
  * resume_and_get does not transfer a reference on a negative return. */
 gfx_retained_cycle_pm_get_attempted=true;
 gfx_retained_cycle_log("second-pm-get-intent",0);
 gfx_retained_cycle_pm_get_result=pm_runtime_resume_and_get(&consumer->dev);
 if(gfx_retained_cycle_pm_get_result<0)
  return gfx_retained_cycle_refuse("second-pm-get-failed",gfx_retained_cycle_pm_get_result);
 held=true;gfx_retained_cycle_second_ref_held=true;
 if(!pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
    pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_retained_cycle_refuse("second-pm-accounting-unqualified",-EBUSY);
 ret=gfx_poweroff_snapshot("retained-cycle-after-get",0,&observation);
 if(ret) return gfx_retained_cycle_refuse("fresh-active-snapshot-error",ret);
 if(!observation.domain_on || (observation.before&0x80001cffU)!=0xffU)
  return gfx_retained_cycle_refuse("fresh-physical-active-unqualified",-EBUSY);
 gfx_retained_cycle_identities_preserved=gfx_retained_cycle_identity(false);
 if(!gfx_retained_cycle_identities_preserved)
  return gfx_retained_cycle_refuse("retained-identity-changed-after-get",-EBUSY);
 ret=gfx_retained_cycle_cold_boundary();
 if(ret) return ret;
 ret=gfx_retained_cycle_coordinate_on();
 if(ret) return gfx_retained_cycle_refuse("second-coordinate-on-failed",ret);
 /* The coordinator may take time. Refresh every START admission operand. */
 ret=gfx_retained_cycle_cold_boundary();
 if(ret) return ret;
 gfx_retained_cycle_boundary_qualified=true;gfx_retained_cycle_start_attempted=true;
 gfx_retained_cycle_log("second-start-intent",0);
 gfx_retained_cycle_control=readl(asc+0x44);
 if(gfx_retained_cycle_control==~0U || (gfx_retained_cycle_control&START))
  return gfx_retained_cycle_refuse("second-start-fresh-control-unqualified",-EBUSY);
 writel(gfx_retained_cycle_control|START,asc+0x44);
 gfx_retained_cycle_control=readl(asc+0x44);
 if(gfx_retained_cycle_control==~0U || !(gfx_retained_cycle_control&START))
  return gfx_retained_cycle_refuse("second-start-readback-failed",-EIO);
 ret=gfx_retained_cycle_protocol();
 if(!ret) ret=gfx_retained_cycle_management();
 if(!ret) ret=gfx_retained_cycle_stop_cpu();
 if(!ret) ret=gfx_retained_cycle_poweroff();
 gfx_retained_cycle_first_off_preserved=gfx_retained_cycle_first_off();
 gfx_retained_cycle_identities_preserved=gfx_retained_cycle_identity(false);
 if(!ret && (!gfx_retained_cycle_first_off_preserved || !gfx_retained_cycle_identities_preserved))
  ret=gfx_retained_cycle_refuse("retained-evidence-changed-after-protocol",-EIO);
 if(!ret) gfx_retained_cycle_complete=true;
 gfx_retained_cycle_log("retained-final",ret);
 return ret;
}

static int gfx_retained_cycle_command(const char *buf)
{
 if(gfx_native_powergate_startup_unknown) return -EPERM;
 if(sysfs_streq(buf,"sample") || sysfs_streq(buf,"gfx-snapshot"))
 {
  int ret=gfx_native_powergate_command(buf);
  gfx_retained_cycle_log("diagnostic-current",ret);
  return ret;
 }
 if(sysfs_streq(buf,"gfx-retained-cycle")) return gfx_retained_cycle_attempt();
 if(sysfs_streq(buf,"gfx-powergate")) {
  if(gfx_retained_cycle_intent) return -EPERM;
  if(!gfx_retained_cycle_identity_captured && !gfx_retained_cycle_identity(true)) return -EBUSY;
  return gfx_native_powergate_command(buf);
 }
 return -EPERM;
}

static int gfx_retained_cycle_startup_retained(const char *phase,int result)
{
 int ret=gfx_native_powergate_startup_retained(phase,result);
 pr_info("m4rch gfx-retained-power-cycle-startup-retained: phase=%s result=%d unknown=1 commands_allowed=0 first_intent=%u second_intent=%u allocations_released=0 restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_native_powergate_intent,gfx_retained_cycle_intent);
 return ret;
}
