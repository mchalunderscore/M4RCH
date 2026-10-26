/* SPDX-License-Identifier: GPL-2.0-only */
/* Two bounded memory-preserving, separately owned transport re-entry epochs.
 * The first proven drain/PWRGATE/OFF epoch stays immutable. A second PM
 * reference and paired coordination epoch never reopen application work.
 * Autonomous HELLO/map observation is not an application rejoin contract. */
#ifndef GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL
#error Distinct retained power-cycle profile required
#endif
#include "gfx-native-powergate-drain.h"
#include "gfx-coordinate-core.h"
#define GFX_RETAINED_CYCLE_PROTOCOL_RECORDS 16U
#define GFX_RETAINED_CYCLE_BOOT_RUNNING 0x0070000000000020ULL
#define GFX_RETAINED_CYCLE_HOST_ON 0x00b0000000000020ULL
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
static bool gfx_retained_cycle_boot_running_observed;
static bool gfx_retained_cycle_host_on_skip_attempted, gfx_retained_cycle_host_on_skipped;
static u64 gfx_retained_cycle_boot_running_message, gfx_retained_cycle_boot_running_metadata;
static u64 gfx_retained_cycle_ack_message, gfx_retained_cycle_ack_metadata;
static unsigned int gfx_retained_cycle_ack_polls, gfx_retained_cycle_idle_polls;
static unsigned int gfx_retained_cycle_off_samples;
static int gfx_retained_cycle_pm_put_result, gfx_retained_cycle_off_snapshot_result;
static int gfx_retained_cycle_pm_get_result;
static int gfx_retained_cycle_terminal_result=-EINPROGRESS;
static u32 gfx_retained_cycle_off_word;
static unsigned long gfx_retained_cycle_sample_jiffies;
static u32 gfx_retained_cycle_control, gfx_retained_cycle_status, gfx_retained_cycle_rx, gfx_retained_cycle_tx;
static unsigned int gfx_retained_cycle_records, gfx_retained_cycle_polls;
static unsigned int gfx_retained_cycle_hello_reply_attempts, gfx_retained_cycle_map_reply_attempts;
static u8 gfx_retained_cycle_map_seen;
static u32 gfx_retained_cycle_appmap;
static const char *gfx_retained_cycle_refusal="none";
static struct gfx_coord_session gfx_retained_cycle_coord_session;
static struct gfx_coord_observation gfx_retained_cycle_coord_on;
static struct gfx_coord_observation gfx_retained_cycle_coord_off;
static bool gfx_retained_cycle_ap_on_known(void);
static int gfx_retained_cycle_coordinate_on(void);
static int gfx_retained_cycle_coordinate_off(void);
static bool gfx_retained_cycle_first_coord_complete(void);

static void gfx_retained_cycle_log(const char *phase,int result)
{
 /* Each complete newline row fits below 512 bytes, including worst-case
  * numeric fields. Preserve phase in every row so captures bind one state. */
 pr_info("m4rch gfx-native-ap-repeat-cycle: phase=%s epoch=2 result=%d refused_condition=%s intent=%u first_off_fields_historical=1 powercycle_complete=%u application_rejoined=0 allocations_retained=%u unknown=%u terminal_result=%d restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_retained_cycle_refusal,gfx_retained_cycle_intent,
  gfx_retained_cycle_complete,GFX_RESET_SCOPE_PAGES,gfx_ap_repeat_unknown,gfx_retained_cycle_terminal_result);
 pr_info("m4rch gfx-native-ap-repeat-cycle-state: phase=%s epoch=2 identity_captured=%u identities_preserved=%u first_off_preserved=%u pm_get_attempted=%u pm_get_result=%d second_ref_held=%u held=%u usage=%d runtime_error=%d runtime_status=%d active=%u suspended=%u\n",
  phase,gfx_retained_cycle_identity_captured,gfx_retained_cycle_identities_preserved,
  gfx_retained_cycle_first_off_preserved,gfx_retained_cycle_pm_get_attempted,
  gfx_retained_cycle_pm_get_result,gfx_retained_cycle_second_ref_held,held,
  consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_error):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_status):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  consumer?pm_runtime_suspended(&consumer->dev):false);
 pr_info("m4rch gfx-native-ap-repeat-cycle-transport: phase=%s epoch=2 second_on_attempted=%u second_on_complete=%u boundary_qualified=%u control44=%#x status48=%#x rx_status=%#x tx_status=%#x start_attempted=%u hello_reply_attempts=%u hello_replied=%u map_reply_attempts=%u endpoint_map=%u appmap=%#x map_seen=%#x protocol_records=%u protocol_polls=%u guard_jiffies=%lu cached=1 operand_samples_atomic=0\n",
  phase,gfx_retained_cycle_coord_session.on_attempted,gfx_retained_cycle_coord_session.on_complete,
  gfx_retained_cycle_boundary_qualified,gfx_retained_cycle_control,gfx_retained_cycle_status,
  gfx_retained_cycle_rx,gfx_retained_cycle_tx,gfx_retained_cycle_start_attempted,
  gfx_retained_cycle_hello_reply_attempts,gfx_retained_cycle_hello_replied,
  gfx_retained_cycle_map_reply_attempts,gfx_retained_cycle_endpoint_map,
  gfx_retained_cycle_appmap,gfx_retained_cycle_map_seen,
  gfx_retained_cycle_records,gfx_retained_cycle_polls,gfx_retained_cycle_sample_jiffies);
 pr_info("m4rch gfx-native-ap-repeat-cycle-management: phase=%s epoch=2 second_request_attempted=%u second_ack_observed=%u second_ack_message=%#llx second_ack_metadata=%#llx second_ack_polls=%u second_idle_polls=%u second_clear10_attempted=%u second_clear20_attempted=%u second_cpu_stopped=%u\n",
  phase,gfx_retained_cycle_request_attempted,gfx_retained_cycle_ack_observed,
  (unsigned long long)gfx_retained_cycle_ack_message,
  (unsigned long long)gfx_retained_cycle_ack_metadata,
  gfx_retained_cycle_ack_polls,gfx_retained_cycle_idle_polls,
  gfx_retained_cycle_clear10_attempted,gfx_retained_cycle_clear20_attempted,
  gfx_retained_cycle_cpu_stopped);
 pr_info("m4rch gfx-native-ap-repeat-cycle-off: phase=%s epoch=2 second_off_attempted=%u second_off_complete=%u second_pm_put_attempted=%u second_pm_put_result=%d second_off_snapshot_result=%d second_off_samples=%u second_provider_off_observed=%u second_accounting_ok=%u\n",
  phase,gfx_retained_cycle_off_attempted,gfx_retained_cycle_coord_session.off_complete,
  gfx_retained_cycle_pm_put_attempted,gfx_retained_cycle_pm_put_result,
  gfx_retained_cycle_off_snapshot_result,gfx_retained_cycle_off_samples,
  gfx_retained_cycle_provider_off_observed,gfx_retained_cycle_accounting_ok);
 pr_info("m4rch gfx-native-ap-repeat-cycle-on: phase=%s epoch=2 boot_running_observed=%u boot_running_message=%#llx boot_running_metadata=%#llx cold_ap_request_attempted=%u cold_ap_reply_observed=%u cold_ap_reply_message=%#llx cold_ap_reply_metadata=%#llx ap_remote_state=%#x ap_remote_known=%u host_on_skip_attempted=%u host_on_skipped=%u\n",
  phase,gfx_retained_cycle_boot_running_observed,
  (unsigned long long)gfx_retained_cycle_boot_running_message,
  (unsigned long long)gfx_retained_cycle_boot_running_metadata,
  gfx_ap_cold_request_attempted,gfx_ap_cold_reply_observed,
  (unsigned long long)gfx_ap_cold_reply_message,(unsigned long long)gfx_ap_cold_reply_metadata,
  gfx_ap_remote_state,gfx_ap_remote_known,
  gfx_retained_cycle_host_on_skip_attempted,gfx_retained_cycle_host_on_skipped);
}

/* A refused new command seals controls without rewriting prior epoch proof. */
static int gfx_ap_repeat_control_refuse(const char *condition,int result)
{
 gfx_ap_repeat_unknown=true;
 pr_info("m4rch gfx-native-ap-repeat-control: epoch=%u result=%d refused_condition=%s unknown=1 historical_epoch_fields_unchanged=1\n",
  gfx_ap_repeat_current_epoch,result,condition);
 return result;
}

static int gfx_retained_cycle_refuse(const char *condition,int result)
{
 gfx_ap_repeat_unknown=true;gfx_retained_cycle_terminal_result=result;
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

enum gfx_retained_cycle_start_stage {
 GFX_RETAINED_CYCLE_PRE_ON,
 GFX_RETAINED_CYCLE_POST_ON,
};

/* Exact6d is an idle-state hypothesis only after separately qualified ON.
 * Before ON, known6a/6c remains unchanged. No general warm restart/INIT. */
static int gfx_retained_cycle_cold_boundary(enum gfx_retained_cycle_start_stage stage,bool log)
{
 if(stage!=GFX_RETAINED_CYCLE_PRE_ON && stage!=GFX_RETAINED_CYCLE_POST_ON)
  return gfx_retained_cycle_refuse("start-stage-invalid",-EINVAL);
 if(stage==GFX_RETAINED_CYCLE_POST_ON &&
    (!gfx_retained_cycle_coord_session.on_attempted || !gfx_retained_cycle_coord_session.on_complete ||
     !gfx_retained_cycle_second_ref_held || !held || !consumer ||
     !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
     pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
     READ_ONCE(consumer->dev.power.runtime_error) || !gfx_retained_cycle_first_off_preserved ||
     !gfx_retained_cycle_first_off()))
  return gfx_retained_cycle_refuse("post-on-stage-unqualified",-EBUSY);
 gfx_retained_cycle_control=readl(asc+0x44);
 gfx_retained_cycle_status=readl(asc+0x48);
 gfx_retained_cycle_rx=readl(mbox+0x114);
 gfx_retained_cycle_tx=readl(mbox+0x110);
 gfx_retained_cycle_sample_jiffies=jiffies;
 if(log) gfx_retained_cycle_log("cold-boundary",0);
 if(gfx_retained_cycle_control==~0U || gfx_retained_cycle_status==~0U ||
    gfx_retained_cycle_rx==~0U || gfx_retained_cycle_tx==~0U)
  return gfx_retained_cycle_refuse("cold-boundary-invalid",-EIO);
 if((gfx_retained_cycle_control&START) ||
    (gfx_retained_cycle_status!=0x6a && gfx_retained_cycle_status!=0x6c &&
     !(stage==GFX_RETAINED_CYCLE_POST_ON && gfx_retained_cycle_status==0x6d)) ||
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
 pr_info("m4rch gfx-native-ap-repeat-cycle-tx: epoch=2 hello=%u packet=%#llx endpoint=0 root_publications=0 application_starts=0 init220_requests=0\n",
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
   if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
    return gfx_retained_cycle_refuse("protocol-record-limit",-EOVERFLOW);
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   unsigned int type=(message>>52)&0xff,endpoint=metadata&0xff;
   int ret;
   /* Preserve every removed word before interpreting it or issuing a reply. */
   gfx_retained_cycle_journal[gfx_retained_cycle_records].message=message;
   gfx_retained_cycle_journal[gfx_retained_cycle_records].metadata=metadata;
   gfx_retained_cycle_records++;
   pr_info("m4rch gfx-native-ap-repeat-cycle-rx: epoch=2 index=%u message=%#llx metadata=%#llx\n",
    gfx_retained_cycle_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_retained_cycle_refuse("protocol-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_retained_cycle_refuse("protocol-frame-invalid",-EIO);
   if(endpoint!=0) return gfx_retained_cycle_refuse("protocol-endpoint-unqualified",-EPROTO);
   if(gfx_retained_cycle_endpoint_map) {
    if(message!=GFX_RETAINED_CYCLE_BOOT_RUNNING)
     return gfx_retained_cycle_refuse("boot-running-frame-unqualified",-EPROTO);
    gfx_retained_cycle_boot_running_message=message;
    gfx_retained_cycle_boot_running_metadata=metadata;
    gfx_retained_cycle_boot_running_observed=true;
    gfx_retained_cycle_log("boot-running-observed",0);
    return 0;
   } else if(!gfx_retained_cycle_hello_replied && type==1) {
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
     /* Ready6 is not generic Running8. Continue the same bounded receive
      * epoch until exact autonomous type7/20; never count it as a202 ACK. */
     gfx_retained_cycle_log("autonomous-map-retained",0);
    }
   } else return gfx_retained_cycle_refuse("protocol-message-unqualified",-EPROTO);
   if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
    return gfx_retained_cycle_refuse("protocol-record-limit",-EOVERFLOW);
  }
  usleep_range(1000,1100);
 }
 return gfx_retained_cycle_refuse("protocol-poll-limit",-ETIMEDOUT);
}

/* Fresh ownership guards bind the retained cold AP proof before and after
 * skip-intent logging, and immediately before owned202. No new HOST exchange. */
static int gfx_retained_cycle_on_boundary(void)
{
 if(!gfx_retained_cycle_ap_on_known() || !gfx_retained_cycle_first_off_preserved || !gfx_retained_cycle_first_off() ||
    !gfx_retained_cycle_identity(false) || !gfx_retained_cycle_coord_session.on_attempted ||
    !gfx_retained_cycle_coord_session.on_complete ||
    !gfx_retained_cycle_second_ref_held || !held || !consumer ||
    !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
    pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_retained_cycle_refuse("host-on-state-unqualified",-EBUSY);
 gfx_retained_cycle_control=readl(asc+0x44);gfx_retained_cycle_status=readl(asc+0x48);
 gfx_retained_cycle_rx=readl(mbox+0x114);gfx_retained_cycle_tx=readl(mbox+0x110);
 gfx_retained_cycle_sample_jiffies=jiffies;
 if(gfx_retained_cycle_control==~0U || gfx_retained_cycle_status==~0U ||
    gfx_retained_cycle_rx==~0U || gfx_retained_cycle_tx==~0U)
  return gfx_retained_cycle_refuse("host-on-operands-invalid",-EIO);
 if(!(gfx_retained_cycle_control&START) || !(gfx_retained_cycle_rx&EMPTY) ||
    (gfx_retained_cycle_tx&BIT(16)))
  return gfx_retained_cycle_refuse("host-on-operands-unqualified",-EBUSY);
 return 0;
}

/* This profile never issues another HOST B20. Its cached AP20 proof comes
 * only from the owned exact cold request/reply, not from IOP Running7/20. */
static bool gfx_retained_cycle_ap_on_known(void)
{
 return gfx_ap_cold_request_attempted && gfx_ap_cold_request_write_attempted &&
  gfx_ap_cold_request_message==GFX_RETAINED_CYCLE_HOST_ON && !gfx_ap_cold_request_metadata &&
  gfx_ap_cold_reply_observed && gfx_ap_cold_reply_message==GFX_RETAINED_CYCLE_HOST_ON &&
  gfx_ap_cold_reply_metadata!=~0ULL && !(gfx_ap_cold_reply_metadata&0xff) &&
  gfx_ap_remote_known && gfx_ap_remote_state==0x20;
}

static void gfx_retained_cycle_cold_ap_log(const char *phase)
{
 pr_info("m4rch gfx-native-ap-repeat-cold: phase=%s epoch=1 request_attempted=%u request_write_attempted=%u request_message=%#llx request_metadata=%#llx reply_observed=%u reply_message=%#llx reply_metadata=%#llx ap_remote_state=%#x ap_remote_known=%u\n",
  phase,gfx_ap_cold_request_attempted,gfx_ap_cold_request_write_attempted,
  (unsigned long long)gfx_ap_cold_request_message,(unsigned long long)gfx_ap_cold_request_metadata,
  gfx_ap_cold_reply_observed,(unsigned long long)gfx_ap_cold_reply_message,
  (unsigned long long)gfx_ap_cold_reply_metadata,gfx_ap_remote_state,gfx_ap_remote_known);
}

static bool gfx_retained_cycle_on_completion(void)
{
 return gfx_retained_cycle_ap_on_known() && gfx_retained_cycle_host_on_skip_attempted &&
  gfx_retained_cycle_host_on_skipped && gfx_retained_cycle_boot_running_observed &&
  gfx_retained_cycle_boot_running_message==GFX_RETAINED_CYCLE_BOOT_RUNNING &&
  gfx_retained_cycle_boot_running_metadata!=~0ULL &&
  !(gfx_retained_cycle_boot_running_metadata&0xff) && gfx_retained_cycle_hello_replied &&
  gfx_retained_cycle_endpoint_map && gfx_retained_cycle_map_seen==3 && gfx_retained_cycle_appmap==3;
}

static int gfx_retained_cycle_skip_host_on(void)
{
 int ret;
 if(gfx_retained_cycle_host_on_skip_attempted)
  return gfx_retained_cycle_refuse("host-on-skip-intent-consumed",-EALREADY);
 if(!gfx_retained_cycle_ap_on_known() || !gfx_retained_cycle_boot_running_observed ||
    gfx_retained_cycle_boot_running_message!=GFX_RETAINED_CYCLE_BOOT_RUNNING ||
    gfx_retained_cycle_boot_running_metadata==~0ULL || (gfx_retained_cycle_boot_running_metadata&0xff) ||
    !gfx_retained_cycle_endpoint_map || !gfx_retained_cycle_hello_replied)
  return gfx_retained_cycle_refuse("retained-ap-running-unqualified",-EPERM);
 if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_retained_cycle_refuse("skip-journal-no-ack-capacity",-EOVERFLOW);
 ret=gfx_retained_cycle_on_boundary();if(ret) return ret;
 gfx_retained_cycle_host_on_skip_attempted=true;
 gfx_retained_cycle_log("retained-ap-on-skip-intent",0);
 ret=gfx_retained_cycle_on_boundary();if(ret) return ret;
 if(!gfx_retained_cycle_ap_on_known() || !gfx_retained_cycle_boot_running_observed ||
    !gfx_retained_cycle_hello_replied || !gfx_retained_cycle_endpoint_map)
  return gfx_retained_cycle_refuse("retained-ap-changed-after-skip-intent",-EBUSY);
 gfx_retained_cycle_host_on_skipped=true;
 gfx_retained_cycle_log("retained-ap-on-skipped",0);
 return 0;
}

static int gfx_retained_cycle_management(void)
{
 unsigned long until;
 unsigned int i;
 int boundary;
 u32 rx,tx,control,status;
 if(!gfx_retained_cycle_on_completion())
  return gfx_retained_cycle_refuse("second-on-completion-unqualified",-EPERM);
 boundary=gfx_retained_cycle_on_boundary();if(boundary) return boundary;
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
 gfx_retained_cycle_sample_jiffies=jiffies;
 if(control==~0U || status==~0U || rx==~0U || tx==~0U)
  return gfx_retained_cycle_refuse("second-management-fifo-invalid",-EIO);
 if(!(control&START)) return gfx_retained_cycle_refuse("second-management-start-clear",-EBUSY);
 if(!(rx&EMPTY) || (tx&BIT(16)))
  return gfx_retained_cycle_refuse("second-management-fifo-unqualified",-EBUSY);
 gfx_retained_cycle_request_attempted=true;
 gfx_retained_cycle_log("second-pwr-gate-intent",0);
 boundary=gfx_retained_cycle_on_boundary();if(boundary) return boundary;
 if(!gfx_retained_cycle_on_completion())
  return gfx_retained_cycle_refuse("second-on-completion-changed-after-intent",-EPERM);
 if(gfx_retained_cycle_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_retained_cycle_refuse("second-journal-no-ack-capacity",-EOVERFLOW);
 until=jiffies+msecs_to_jiffies(GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS);
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
    pr_info("m4rch gfx-native-ap-repeat-cycle-rx: epoch=2 index=overflow message=%#llx metadata=%#llx\n",
     (unsigned long long)message,(unsigned long long)metadata);
    return gfx_retained_cycle_refuse("second-journal-full",-EOVERFLOW);
   }
   pr_info("m4rch gfx-native-ap-repeat-cycle-rx: epoch=2 index=%u message=%#llx metadata=%#llx\n",
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
   gfx_retained_cycle_off_word=observation.before;
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
 if(gfx_ap_repeat_unknown) return -EPERM;
 if(gfx_retained_cycle_intent) return gfx_ap_repeat_control_refuse("second-intent-already-consumed",-EALREADY);
 gfx_ap_repeat_current_epoch=2;gfx_retained_cycle_intent=true;
 /* The distinct intent also seals the copied worker. Do not repair, clear or
  * rewrite historical first-epoch flags to manufacture a successful premise. */
 cancel_delayed_work(&recovery_receive_work);
 gfx_retained_cycle_log("intent",0);
 if(!gfx_retained_cycle_ap_on_known())
  return gfx_retained_cycle_refuse("cold-ap-on-unqualified",-EPERM);
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
 ret=gfx_retained_cycle_cold_boundary(GFX_RETAINED_CYCLE_PRE_ON,true);
 if(ret) return ret;
 ret=gfx_retained_cycle_coordinate_on();
 if(ret) return gfx_retained_cycle_refuse("second-coordinate-on-failed",ret);
 /* The coordinator may take time. Refresh every START admission operand. */
 ret=gfx_retained_cycle_cold_boundary(GFX_RETAINED_CYCLE_POST_ON,true);
 if(ret) return ret;
 gfx_retained_cycle_boundary_qualified=true;gfx_retained_cycle_start_attempted=true;
 gfx_retained_cycle_log("second-start-intent",0);
 /* Refresh all four operands after intent logging, then the final CTRL RMW. */
 ret=gfx_retained_cycle_cold_boundary(GFX_RETAINED_CYCLE_POST_ON,false);
 if(ret) return ret;
 gfx_retained_cycle_control=readl(asc+0x44);
 if(gfx_retained_cycle_control==~0U || (gfx_retained_cycle_control&START))
  return gfx_retained_cycle_refuse("second-start-fresh-control-unqualified",-EBUSY);
 writel(gfx_retained_cycle_control|START,asc+0x44);
 gfx_retained_cycle_control=readl(asc+0x44);
 if(gfx_retained_cycle_control==~0U || !(gfx_retained_cycle_control&START))
  return gfx_retained_cycle_refuse("second-start-readback-failed",-EIO);
 gfx_retained_cycle_log("second-start-return",0);
 ret=gfx_retained_cycle_protocol();
 if(!ret) ret=gfx_retained_cycle_skip_host_on();
 if(!ret) ret=gfx_retained_cycle_management();
 if(!ret) ret=gfx_retained_cycle_stop_cpu();
 if(!ret) ret=gfx_retained_cycle_poweroff();
 gfx_retained_cycle_first_off_preserved=gfx_retained_cycle_first_off();
 gfx_retained_cycle_identities_preserved=gfx_retained_cycle_identity(false);
 if(!ret && (!gfx_retained_cycle_first_off_preserved || !gfx_retained_cycle_identities_preserved))
  ret=gfx_retained_cycle_refuse("retained-evidence-changed-after-protocol",-EIO);
 if(!ret) {gfx_retained_cycle_terminal_result=0;gfx_retained_cycle_complete=true;}
 gfx_retained_cycle_log("retained-final",ret);
 return ret;
}


/* E2 history is immutable during E3. Completion alone never grants admission.
 * The exact own ACK remains in E2's separate journal; physical OFF and its
 * accounting observation belong to E2, not to E1 or the current E3 reference. */
static bool gfx_ap_repeat_second_qualified(void)
{
 unsigned int n=gfx_retained_cycle_records;
 return gfx_retained_cycle_complete && !gfx_retained_cycle_terminal_result &&
  !strcmp(gfx_retained_cycle_refusal,"none") && gfx_retained_cycle_intent &&
  gfx_retained_cycle_first_off() && gfx_retained_cycle_identity_captured &&
  gfx_retained_cycle_identities_preserved && gfx_retained_cycle_first_off_preserved &&
  gfx_retained_cycle_pm_get_attempted && gfx_retained_cycle_pm_get_result>=0 &&
  !gfx_retained_cycle_second_ref_held && gfx_retained_cycle_boundary_qualified &&
  gfx_retained_cycle_start_attempted && gfx_retained_cycle_on_completion() &&
  gfx_retained_cycle_hello_reply_attempts==1 && gfx_retained_cycle_map_reply_attempts==2 &&
  gfx_retained_cycle_polls>0 && gfx_retained_cycle_polls<=GFX_RETAINED_CYCLE_PROTOCOL_POLLS &&
  gfx_retained_cycle_request_attempted && gfx_retained_cycle_ack_observed &&
  gfx_retained_cycle_ack_polls>0 && gfx_retained_cycle_ack_polls<=GFX_NATIVE_POWERGATE_ACK_POLLS &&
  gfx_retained_cycle_idle_polls>0 && gfx_retained_cycle_idle_polls<=GFX_NATIVE_POWERGATE_IDLE_POLLS &&
  gfx_retained_cycle_ack_metadata!=~0ULL && !(gfx_retained_cycle_ack_metadata&0xff) &&
  ((gfx_retained_cycle_ack_message>>52)&0xf)==7 &&
  ((gfx_retained_cycle_ack_message&0xff)==1 || (gfx_retained_cycle_ack_message&0xff)==2) &&
  n>=5 && n<=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS &&
  gfx_retained_cycle_journal[n-1].message==gfx_retained_cycle_ack_message &&
  gfx_retained_cycle_journal[n-1].metadata==gfx_retained_cycle_ack_metadata &&
  gfx_retained_cycle_clear10_attempted && gfx_retained_cycle_clear20_attempted &&
  gfx_retained_cycle_cpu_stopped && !(gfx_retained_cycle_control&0x30U) &&
  gfx_retained_cycle_control!=~0U && gfx_retained_cycle_status!=~0U &&
  (gfx_retained_cycle_status&3) && gfx_retained_cycle_off_attempted &&
  gfx_retained_cycle_coord_session.on_attempted && gfx_retained_cycle_coord_session.on_complete &&
  gfx_retained_cycle_coord_session.off_attempted && gfx_retained_cycle_coord_session.off_complete &&
  !gfx_retained_cycle_coord_on.result && !gfx_retained_cycle_coord_off.result &&
  ((gfx_retained_cycle_coord_on.request_acked && !gfx_retained_cycle_coord_on.ack_bypassed) ||
   (!gfx_retained_cycle_coord_on.request_acked && gfx_retained_cycle_coord_on.ack_bypassed)) &&
  ((gfx_retained_cycle_coord_off.request_acked && !gfx_retained_cycle_coord_off.ack_bypassed) ||
   (!gfx_retained_cycle_coord_off.request_acked && gfx_retained_cycle_coord_off.ack_bypassed)) &&
  gfx_retained_cycle_coord_on.request_attempted && gfx_retained_cycle_coord_off.request_attempted &&
  gfx_retained_cycle_coord_on.votes_attempted==3 && gfx_retained_cycle_coord_on.votes_verified==3 &&
  gfx_retained_cycle_coord_off.votes_attempted==3 && gfx_retained_cycle_coord_off.votes_verified==3 &&
  gfx_retained_cycle_pm_put_attempted && gfx_retained_cycle_pm_put_result>=0 &&
  !gfx_retained_cycle_off_snapshot_result && gfx_retained_cycle_off_samples>0 &&
  gfx_retained_cycle_off_samples<=GFX_POWER_OFF_POLL_SAMPLES &&
  gfx_retained_cycle_provider_off_observed && !(gfx_retained_cycle_off_word&GFX_POWER_OFF_STATE_MASK) &&
  gfx_retained_cycle_accounting_ok;
}

struct gfx_ap_repeat_third_record { u64 message, metadata; };
static struct gfx_ap_repeat_third_record gfx_ap_repeat_third_journal[GFX_RETAINED_CYCLE_PROTOCOL_RECORDS];
static bool gfx_ap_repeat_third_intent;
static bool gfx_ap_repeat_third_identities_preserved, gfx_ap_repeat_third_first_off_preserved;
static bool gfx_ap_repeat_third_pm_get_attempted, gfx_ap_repeat_third_third_ref_held;
static bool gfx_ap_repeat_third_boundary_qualified, gfx_ap_repeat_third_start_attempted;
static bool gfx_ap_repeat_third_hello_replied, gfx_ap_repeat_third_endpoint_map;
static bool gfx_ap_repeat_third_request_attempted, gfx_ap_repeat_third_ack_observed;
static bool gfx_ap_repeat_third_cpu_stopped, gfx_ap_repeat_third_clear10_attempted;
static bool gfx_ap_repeat_third_clear20_attempted, gfx_ap_repeat_third_off_attempted;
static bool gfx_ap_repeat_third_pm_put_attempted, gfx_ap_repeat_third_provider_off_observed;
static bool gfx_ap_repeat_third_accounting_ok, gfx_ap_repeat_third_complete;
static bool gfx_ap_repeat_third_boot_running_observed;
static bool gfx_ap_repeat_third_host_on_skip_attempted, gfx_ap_repeat_third_host_on_skipped;
static u64 gfx_ap_repeat_third_boot_running_message, gfx_ap_repeat_third_boot_running_metadata;
static u64 gfx_ap_repeat_third_ack_message, gfx_ap_repeat_third_ack_metadata;
static unsigned int gfx_ap_repeat_third_ack_polls, gfx_ap_repeat_third_idle_polls;
static unsigned int gfx_ap_repeat_third_off_samples;
static int gfx_ap_repeat_third_pm_put_result, gfx_ap_repeat_third_off_snapshot_result;
static int gfx_ap_repeat_third_pm_get_result;
static int gfx_ap_repeat_third_terminal_result=-EINPROGRESS;
static u32 gfx_ap_repeat_third_off_word;
static unsigned long gfx_ap_repeat_third_sample_jiffies;
static u32 gfx_ap_repeat_third_control, gfx_ap_repeat_third_status, gfx_ap_repeat_third_rx, gfx_ap_repeat_third_tx;
static unsigned int gfx_ap_repeat_third_records, gfx_ap_repeat_third_polls;
static unsigned int gfx_ap_repeat_third_hello_reply_attempts, gfx_ap_repeat_third_map_reply_attempts;
static u8 gfx_ap_repeat_third_map_seen;
static u32 gfx_ap_repeat_third_appmap;
static const char *gfx_ap_repeat_third_refusal="none";
static struct gfx_coord_session gfx_ap_repeat_third_coord_session;
static struct gfx_coord_observation gfx_ap_repeat_third_coord_on;
static struct gfx_coord_observation gfx_ap_repeat_third_coord_off;
static bool gfx_ap_repeat_third_ap_on_known(void);
static int gfx_ap_repeat_third_coordinate_on(void);
static int gfx_ap_repeat_third_coordinate_off(void);
static bool gfx_ap_repeat_third_first_coord_complete(void);

static void gfx_ap_repeat_third_log(const char *phase,int result)
{
 /* Each complete newline row fits below 512 bytes, including worst-case
  * numeric fields. Preserve phase in every row so captures bind one state. */
 pr_info("m4rch gfx-native-ap-repeat-third: phase=%s epoch=3 result=%d refused_condition=%s intent=%u first_off_fields_historical=1 powercycle_complete=%u application_rejoined=0 allocations_retained=%u unknown=%u terminal_result=%d second_epoch_preserved=%u restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_ap_repeat_third_refusal,gfx_ap_repeat_third_intent,
  gfx_ap_repeat_third_complete,GFX_RESET_SCOPE_PAGES,gfx_ap_repeat_unknown,gfx_ap_repeat_third_terminal_result,gfx_ap_repeat_second_qualified());
 pr_info("m4rch gfx-native-ap-repeat-third-state: phase=%s epoch=3 identity_captured=%u identities_preserved=%u first_off_preserved=%u pm_get_attempted=%u pm_get_result=%d third_ref_held=%u held=%u usage=%d runtime_error=%d runtime_status=%d active=%u suspended=%u\n",
  phase,gfx_retained_cycle_identity_captured,gfx_ap_repeat_third_identities_preserved,
  gfx_ap_repeat_third_first_off_preserved,gfx_ap_repeat_third_pm_get_attempted,
  gfx_ap_repeat_third_pm_get_result,gfx_ap_repeat_third_third_ref_held,held,
  consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_error):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_status):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  consumer?pm_runtime_suspended(&consumer->dev):false);
 pr_info("m4rch gfx-native-ap-repeat-third-transport: phase=%s epoch=3 third_on_attempted=%u third_on_complete=%u boundary_qualified=%u control44=%#x status48=%#x rx_status=%#x tx_status=%#x start_attempted=%u hello_reply_attempts=%u hello_replied=%u map_reply_attempts=%u endpoint_map=%u appmap=%#x map_seen=%#x protocol_records=%u protocol_polls=%u guard_jiffies=%lu cached=1 operand_samples_atomic=0\n",
  phase,gfx_ap_repeat_third_coord_session.on_attempted,gfx_ap_repeat_third_coord_session.on_complete,
  gfx_ap_repeat_third_boundary_qualified,gfx_ap_repeat_third_control,gfx_ap_repeat_third_status,
  gfx_ap_repeat_third_rx,gfx_ap_repeat_third_tx,gfx_ap_repeat_third_start_attempted,
  gfx_ap_repeat_third_hello_reply_attempts,gfx_ap_repeat_third_hello_replied,
  gfx_ap_repeat_third_map_reply_attempts,gfx_ap_repeat_third_endpoint_map,
  gfx_ap_repeat_third_appmap,gfx_ap_repeat_third_map_seen,
  gfx_ap_repeat_third_records,gfx_ap_repeat_third_polls,gfx_ap_repeat_third_sample_jiffies);
 pr_info("m4rch gfx-native-ap-repeat-third-management: phase=%s epoch=3 third_request_attempted=%u third_ack_observed=%u third_ack_message=%#llx third_ack_metadata=%#llx third_ack_polls=%u third_idle_polls=%u third_clear10_attempted=%u third_clear20_attempted=%u third_cpu_stopped=%u\n",
  phase,gfx_ap_repeat_third_request_attempted,gfx_ap_repeat_third_ack_observed,
  (unsigned long long)gfx_ap_repeat_third_ack_message,
  (unsigned long long)gfx_ap_repeat_third_ack_metadata,
  gfx_ap_repeat_third_ack_polls,gfx_ap_repeat_third_idle_polls,
  gfx_ap_repeat_third_clear10_attempted,gfx_ap_repeat_third_clear20_attempted,
  gfx_ap_repeat_third_cpu_stopped);
 pr_info("m4rch gfx-native-ap-repeat-third-off: phase=%s epoch=3 third_off_attempted=%u third_off_complete=%u third_pm_put_attempted=%u third_pm_put_result=%d third_off_snapshot_result=%d third_off_samples=%u third_provider_off_observed=%u third_accounting_ok=%u\n",
  phase,gfx_ap_repeat_third_off_attempted,gfx_ap_repeat_third_coord_session.off_complete,
  gfx_ap_repeat_third_pm_put_attempted,gfx_ap_repeat_third_pm_put_result,
  gfx_ap_repeat_third_off_snapshot_result,gfx_ap_repeat_third_off_samples,
  gfx_ap_repeat_third_provider_off_observed,gfx_ap_repeat_third_accounting_ok);
 pr_info("m4rch gfx-native-ap-repeat-third-on: phase=%s epoch=3 boot_running_observed=%u boot_running_message=%#llx boot_running_metadata=%#llx cold_ap_request_attempted=%u cold_ap_reply_observed=%u cold_ap_reply_message=%#llx cold_ap_reply_metadata=%#llx ap_remote_state=%#x ap_remote_known=%u host_on_skip_attempted=%u host_on_skipped=%u\n",
  phase,gfx_ap_repeat_third_boot_running_observed,
  (unsigned long long)gfx_ap_repeat_third_boot_running_message,
  (unsigned long long)gfx_ap_repeat_third_boot_running_metadata,
  gfx_ap_cold_request_attempted,gfx_ap_cold_reply_observed,
  (unsigned long long)gfx_ap_cold_reply_message,(unsigned long long)gfx_ap_cold_reply_metadata,
  gfx_ap_remote_state,gfx_ap_remote_known,
  gfx_ap_repeat_third_host_on_skip_attempted,gfx_ap_repeat_third_host_on_skipped);
}

static int gfx_ap_repeat_third_refuse(const char *condition,int result)
{
 gfx_ap_repeat_unknown=true;gfx_ap_repeat_third_terminal_result=result;
 gfx_ap_repeat_third_refusal=condition;
 gfx_ap_repeat_third_log("retained-return",result);
 return result;
}

/* Compare exact retained host identities and root descriptor. This does not
 * prove that GPU hardware has retained its UAT state through physical OFF. */
static bool gfx_ap_repeat_third_identity(bool capture)
{
 return !capture && gfx_retained_cycle_identity(false);
}

static bool gfx_ap_repeat_third_first_off(void)
{
 return gfx_ap_repeat_second_qualified();
}

/* Only PMGR/software and retained DRAM are touched before the third get. */
static int gfx_ap_repeat_third_off_admission(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 gfx_ap_repeat_third_first_off_preserved=gfx_ap_repeat_third_first_off();
 if(!gfx_ap_repeat_third_first_off_preserved)
  return gfx_ap_repeat_third_refuse("first-off-unqualified",-EPERM);
 gfx_ap_repeat_third_identities_preserved=gfx_ap_repeat_third_identity(false);
 if(!gfx_ap_repeat_third_identities_preserved)
  return gfx_ap_repeat_third_refuse("retained-identity-changed",-EBUSY);
 if(held || !consumer || !pm_runtime_enabled(&consumer->dev) ||
    !pm_runtime_suspended(&consumer->dev) || pm_runtime_active(&consumer->dev) ||
    atomic_read(&consumer->dev.power.usage_count) || READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_ap_repeat_third_refuse("first-off-accounting-changed",-EBUSY);
 ret=gfx_poweroff_snapshot("repeat-third-before-get",0,&observation);
 if(ret) return gfx_ap_repeat_third_refuse("fresh-off-snapshot-error",ret);
 if(observation.domain_on || (observation.before&GFX_POWER_OFF_STATE_MASK))
  return gfx_ap_repeat_third_refuse("fresh-physical-off-unqualified",-EBUSY);
 return 0;
}

enum gfx_ap_repeat_third_start_stage {
 GFX_AP_REPEAT_THIRD_PRE_ON,
 GFX_AP_REPEAT_THIRD_POST_ON,
};

/* Exact6d is an idle-state hypothesis only after separately qualified ON.
 * Before ON, known6a/6c remains unchanged. No general warm restart/INIT. */
static int gfx_ap_repeat_third_cold_boundary(enum gfx_ap_repeat_third_start_stage stage,bool log)
{
 if(stage!=GFX_AP_REPEAT_THIRD_PRE_ON && stage!=GFX_AP_REPEAT_THIRD_POST_ON)
  return gfx_ap_repeat_third_refuse("start-stage-invalid",-EINVAL);
 if(stage==GFX_AP_REPEAT_THIRD_POST_ON &&
    (!gfx_ap_repeat_third_coord_session.on_attempted || !gfx_ap_repeat_third_coord_session.on_complete ||
     !gfx_ap_repeat_third_third_ref_held || !held || !consumer ||
     !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
     pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
     READ_ONCE(consumer->dev.power.runtime_error) || !gfx_ap_repeat_third_first_off_preserved ||
     !gfx_ap_repeat_third_first_off()))
  return gfx_ap_repeat_third_refuse("post-on-stage-unqualified",-EBUSY);
 gfx_ap_repeat_third_control=readl(asc+0x44);
 gfx_ap_repeat_third_status=readl(asc+0x48);
 gfx_ap_repeat_third_rx=readl(mbox+0x114);
 gfx_ap_repeat_third_tx=readl(mbox+0x110);
 gfx_ap_repeat_third_sample_jiffies=jiffies;
 if(log) gfx_ap_repeat_third_log("cold-boundary",0);
 if(gfx_ap_repeat_third_control==~0U || gfx_ap_repeat_third_status==~0U ||
    gfx_ap_repeat_third_rx==~0U || gfx_ap_repeat_third_tx==~0U)
  return gfx_ap_repeat_third_refuse("cold-boundary-invalid",-EIO);
 if((gfx_ap_repeat_third_control&START) ||
    (gfx_ap_repeat_third_status!=0x6a && gfx_ap_repeat_third_status!=0x6c &&
     !(stage==GFX_AP_REPEAT_THIRD_POST_ON && gfx_ap_repeat_third_status==0x6d)) ||
    !(gfx_ap_repeat_third_rx&EMPTY) || (gfx_ap_repeat_third_tx&BIT(16)))
  return gfx_ap_repeat_third_refuse("cold-boundary-unqualified",-EBUSY);
 return 0;
}

static int gfx_ap_repeat_third_send(u64 packet,bool hello)
{
 u32 tx=readl(mbox+0x110);
 if(tx==~0U) return gfx_ap_repeat_third_refuse("protocol-tx-invalid",-EIO);
 if(tx&BIT(16)) return gfx_ap_repeat_third_refuse("protocol-tx-full",-EBUSY);
 if(hello) gfx_ap_repeat_third_hello_reply_attempts++;
 else gfx_ap_repeat_third_map_reply_attempts++;
 wmb();writeq(packet,mbox+0x800);writeq(0,mbox+0x808);
 pr_info("m4rch gfx-native-ap-repeat-third-tx: epoch=3 hello=%u packet=%#llx endpoint=0 root_publications=0 application_starts=0 init220_requests=0\n",
  hello,(unsigned long long)packet);
 return 0;
}

static int gfx_ap_repeat_third_protocol(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_RETAINED_CYCLE_PROTOCOL_TIMEOUT_MS);
 unsigned int i;
 for(i=0;i<GFX_RETAINED_CYCLE_PROTOCOL_POLLS;i++) {
  u32 rx;
  if(!time_before(jiffies,until)) return gfx_ap_repeat_third_refuse("protocol-deadline",-ETIMEDOUT);
  gfx_ap_repeat_third_polls++;
  rx=readl(mbox+0x114);
  if(rx==~0U) return gfx_ap_repeat_third_refuse("protocol-rx-invalid",-EIO);
  if(!(rx&EMPTY)) {
   if(gfx_ap_repeat_third_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
    return gfx_ap_repeat_third_refuse("protocol-record-limit",-EOVERFLOW);
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   unsigned int type=(message>>52)&0xff,endpoint=metadata&0xff;
   int ret;
   /* Preserve every removed word before interpreting it or issuing a reply. */
   gfx_ap_repeat_third_journal[gfx_ap_repeat_third_records].message=message;
   gfx_ap_repeat_third_journal[gfx_ap_repeat_third_records].metadata=metadata;
   gfx_ap_repeat_third_records++;
   pr_info("m4rch gfx-native-ap-repeat-third-rx: epoch=3 index=%u message=%#llx metadata=%#llx\n",
    gfx_ap_repeat_third_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_ap_repeat_third_refuse("protocol-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_ap_repeat_third_refuse("protocol-frame-invalid",-EIO);
   if(endpoint!=0) return gfx_ap_repeat_third_refuse("protocol-endpoint-unqualified",-EPROTO);
   if(gfx_ap_repeat_third_endpoint_map) {
    if(message!=GFX_RETAINED_CYCLE_BOOT_RUNNING)
     return gfx_ap_repeat_third_refuse("boot-running-frame-unqualified",-EPROTO);
    gfx_ap_repeat_third_boot_running_message=message;
    gfx_ap_repeat_third_boot_running_metadata=metadata;
    gfx_ap_repeat_third_boot_running_observed=true;
    gfx_ap_repeat_third_log("boot-running-observed",0);
    return 0;
   } else if(!gfx_ap_repeat_third_hello_replied && type==1) {
    if((message&0xffff)!=12 || ((message>>16)&0xffff)!=12)
     return gfx_ap_repeat_third_refuse("hello-version-unqualified",-EPROTO);
    ret=gfx_ap_repeat_third_send((2ULL<<52)|(12ULL<<16)|12ULL,true);
    if(ret) return ret;
    gfx_ap_repeat_third_hello_replied=true;
   } else if(gfx_ap_repeat_third_hello_replied && type==8) {
    unsigned int base=(message>>32)&0x3f;
    bool last=!!(message&(1ULL<<51));
    if(base>1 || (u32)message!=3 ||
       (!gfx_ap_repeat_third_map_seen && (base!=0 || last)) ||
       (gfx_ap_repeat_third_map_seen && (base!=1 || !last)))
     return gfx_ap_repeat_third_refuse("endpoint-map-shape-unqualified",-EPROTO);
    if(gfx_ap_repeat_third_map_seen&BIT(base))
     return gfx_ap_repeat_third_refuse("duplicate-endpoint-map",-EPROTO);
    ret=gfx_ap_repeat_third_send((8ULL<<52)|((u64)base<<32)|(last?(1ULL<<51):1ULL),false);
    if(ret) return ret;
    gfx_ap_repeat_third_map_seen|=BIT(base);
    if(base==1) gfx_ap_repeat_third_appmap=(u32)message;
    if(last) {
     gfx_ap_repeat_third_endpoint_map=true;
     /* Ready6 is not generic Running8. Continue the same bounded receive
      * epoch until exact autonomous type7/20; never count it as a202 ACK. */
     gfx_ap_repeat_third_log("autonomous-map-retained",0);
    }
   } else return gfx_ap_repeat_third_refuse("protocol-message-unqualified",-EPROTO);
   if(gfx_ap_repeat_third_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
    return gfx_ap_repeat_third_refuse("protocol-record-limit",-EOVERFLOW);
  }
  usleep_range(1000,1100);
 }
 return gfx_ap_repeat_third_refuse("protocol-poll-limit",-ETIMEDOUT);
}

/* Fresh ownership guards bind the retained cold AP proof before and after
 * skip-intent logging, and immediately before owned202. No new HOST exchange. */
static int gfx_ap_repeat_third_on_boundary(void)
{
 if(!gfx_ap_repeat_third_ap_on_known() || !gfx_ap_repeat_third_first_off_preserved || !gfx_ap_repeat_third_first_off() ||
    !gfx_ap_repeat_third_identity(false) || !gfx_ap_repeat_third_coord_session.on_attempted ||
    !gfx_ap_repeat_third_coord_session.on_complete ||
    !gfx_ap_repeat_third_third_ref_held || !held || !consumer ||
    !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
    pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_ap_repeat_third_refuse("host-on-state-unqualified",-EBUSY);
 gfx_ap_repeat_third_control=readl(asc+0x44);gfx_ap_repeat_third_status=readl(asc+0x48);
 gfx_ap_repeat_third_rx=readl(mbox+0x114);gfx_ap_repeat_third_tx=readl(mbox+0x110);
 gfx_ap_repeat_third_sample_jiffies=jiffies;
 if(gfx_ap_repeat_third_control==~0U || gfx_ap_repeat_third_status==~0U ||
    gfx_ap_repeat_third_rx==~0U || gfx_ap_repeat_third_tx==~0U)
  return gfx_ap_repeat_third_refuse("host-on-operands-invalid",-EIO);
 if(!(gfx_ap_repeat_third_control&START) || !(gfx_ap_repeat_third_rx&EMPTY) ||
    (gfx_ap_repeat_third_tx&BIT(16)))
  return gfx_ap_repeat_third_refuse("host-on-operands-unqualified",-EBUSY);
 return 0;
}

/* This profile never issues another HOST B20. Its cached AP20 proof comes
 * only from the owned exact cold request/reply, not from IOP Running7/20. */
static bool gfx_ap_repeat_third_ap_on_known(void)
{
 return gfx_retained_cycle_ap_on_known();
}



static bool gfx_ap_repeat_third_on_completion(void)
{
 return gfx_ap_repeat_third_ap_on_known() && gfx_ap_repeat_third_host_on_skip_attempted &&
  gfx_ap_repeat_third_host_on_skipped && gfx_ap_repeat_third_boot_running_observed &&
  gfx_ap_repeat_third_boot_running_message==GFX_RETAINED_CYCLE_BOOT_RUNNING &&
  gfx_ap_repeat_third_boot_running_metadata!=~0ULL &&
  !(gfx_ap_repeat_third_boot_running_metadata&0xff) && gfx_ap_repeat_third_hello_replied &&
  gfx_ap_repeat_third_endpoint_map && gfx_ap_repeat_third_map_seen==3 && gfx_ap_repeat_third_appmap==3;
}

static int gfx_ap_repeat_third_skip_host_on(void)
{
 int ret;
 if(gfx_ap_repeat_third_host_on_skip_attempted)
  return gfx_ap_repeat_third_refuse("host-on-skip-intent-consumed",-EALREADY);
 if(!gfx_ap_repeat_third_ap_on_known() || !gfx_ap_repeat_third_boot_running_observed ||
    gfx_ap_repeat_third_boot_running_message!=GFX_RETAINED_CYCLE_BOOT_RUNNING ||
    gfx_ap_repeat_third_boot_running_metadata==~0ULL || (gfx_ap_repeat_third_boot_running_metadata&0xff) ||
    !gfx_ap_repeat_third_endpoint_map || !gfx_ap_repeat_third_hello_replied)
  return gfx_ap_repeat_third_refuse("retained-ap-running-unqualified",-EPERM);
 if(gfx_ap_repeat_third_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_ap_repeat_third_refuse("skip-journal-no-ack-capacity",-EOVERFLOW);
 ret=gfx_ap_repeat_third_on_boundary();if(ret) return ret;
 gfx_ap_repeat_third_host_on_skip_attempted=true;
 gfx_ap_repeat_third_log("retained-ap-on-skip-intent",0);
 ret=gfx_ap_repeat_third_on_boundary();if(ret) return ret;
 if(!gfx_ap_repeat_third_ap_on_known() || !gfx_ap_repeat_third_boot_running_observed ||
    !gfx_ap_repeat_third_hello_replied || !gfx_ap_repeat_third_endpoint_map)
  return gfx_ap_repeat_third_refuse("retained-ap-changed-after-skip-intent",-EBUSY);
 gfx_ap_repeat_third_host_on_skipped=true;
 gfx_ap_repeat_third_log("retained-ap-on-skipped",0);
 return 0;
}

static int gfx_ap_repeat_third_management(void)
{
 unsigned long until;
 unsigned int i;
 int boundary;
 u32 rx,tx,control,status;
 if(!gfx_ap_repeat_third_on_completion())
  return gfx_ap_repeat_third_refuse("third-on-completion-unqualified",-EPERM);
 boundary=gfx_ap_repeat_third_on_boundary();if(boundary) return boundary;
 if(!gfx_ap_repeat_third_hello_replied || !gfx_ap_repeat_third_endpoint_map ||
    !gfx_ap_repeat_third_coord_session.on_complete || !gfx_ap_repeat_third_third_ref_held)
  return gfx_ap_repeat_third_refuse("third-management-state-unqualified",-EPERM);
 if(gfx_ap_repeat_third_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_ap_repeat_third_refuse("third-journal-no-ack-capacity",-EOVERFLOW);
 if(!held || !pm_runtime_active(&consumer->dev) || !pm_runtime_enabled(&consumer->dev) ||
    atomic_read(&consumer->dev.power.usage_count)!=1 || READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_ap_repeat_third_refuse("third-management-pm-unqualified",-EBUSY);
 control=readl(asc+0x44);status=readl(asc+0x48);
 rx=readl(mbox+0x114);tx=readl(mbox+0x110);
 gfx_ap_repeat_third_control=control;gfx_ap_repeat_third_status=status;
 gfx_ap_repeat_third_rx=rx;gfx_ap_repeat_third_tx=tx;
 gfx_ap_repeat_third_sample_jiffies=jiffies;
 if(control==~0U || status==~0U || rx==~0U || tx==~0U)
  return gfx_ap_repeat_third_refuse("third-management-fifo-invalid",-EIO);
 if(!(control&START)) return gfx_ap_repeat_third_refuse("third-management-start-clear",-EBUSY);
 if(!(rx&EMPTY) || (tx&BIT(16)))
  return gfx_ap_repeat_third_refuse("third-management-fifo-unqualified",-EBUSY);
 gfx_ap_repeat_third_request_attempted=true;
 gfx_ap_repeat_third_log("third-pwr-gate-intent",0);
 boundary=gfx_ap_repeat_third_on_boundary();if(boundary) return boundary;
 if(!gfx_ap_repeat_third_on_completion())
  return gfx_ap_repeat_third_refuse("third-on-completion-changed-after-intent",-EPERM);
 if(gfx_ap_repeat_third_records>=GFX_RETAINED_CYCLE_PROTOCOL_RECORDS)
  return gfx_ap_repeat_third_refuse("third-journal-no-ack-capacity",-EOVERFLOW);
 until=jiffies+msecs_to_jiffies(GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS);
 wmb();writeq(GFX_NATIVE_POWERGATE_REQUEST,mbox+0x800);writeq(0,mbox+0x808);
 for(i=0;i<GFX_NATIVE_POWERGATE_ACK_POLLS;i++) {
  if(!time_before(jiffies,until)) return gfx_ap_repeat_third_refuse("third-ack-deadline",-ETIMEDOUT);
  gfx_ap_repeat_third_ack_polls++;rx=readl(mbox+0x114);
  if(rx==~0U) return gfx_ap_repeat_third_refuse("third-ack-rx-invalid",-EIO);
  if(!(rx&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   /* Record removed frames independently of the first application journal. */
   if(gfx_ap_repeat_third_records<GFX_RETAINED_CYCLE_PROTOCOL_RECORDS) {
    gfx_ap_repeat_third_journal[gfx_ap_repeat_third_records].message=message;
    gfx_ap_repeat_third_journal[gfx_ap_repeat_third_records].metadata=metadata;
    gfx_ap_repeat_third_records++;
   } else {
    pr_info("m4rch gfx-native-ap-repeat-third-rx: epoch=3 index=overflow message=%#llx metadata=%#llx\n",
     (unsigned long long)message,(unsigned long long)metadata);
    return gfx_ap_repeat_third_refuse("third-journal-full",-EOVERFLOW);
   }
   pr_info("m4rch gfx-native-ap-repeat-third-rx: epoch=3 index=%u message=%#llx metadata=%#llx\n",
    gfx_ap_repeat_third_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_ap_repeat_third_refuse("third-ack-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_ap_repeat_third_refuse("third-ack-frame-invalid",-EIO);
   if((metadata&0xff)!=0 || ((message>>52)&0xf)!=7 ||
      ((message&0xff)!=1 && (message&0xff)!=2))
    return gfx_ap_repeat_third_refuse("third-ack-unqualified",-EPROTO);
   gfx_ap_repeat_third_ack_message=message;gfx_ap_repeat_third_ack_metadata=metadata;
   gfx_ap_repeat_third_ack_observed=true;
   rx=readl(mbox+0x114);
   if(rx==~0U) return gfx_ap_repeat_third_refuse("third-post-ack-rx-invalid",-EIO);
   if(!(rx&EMPTY)) return gfx_ap_repeat_third_refuse("third-post-ack-rx-pending",-EBUSY);
   return 0;
  }
  usleep_range(1000,1100);
 }
 return gfx_ap_repeat_third_refuse("third-ack-poll-limit",-ETIMEDOUT);
}

static int gfx_ap_repeat_third_stop_cpu(void)
{
 unsigned int i;
 u32 control,rx,status;
 bool idle=false;
 for(i=0;i<GFX_NATIVE_POWERGATE_IDLE_POLLS;i++) {
  status=readl(asc+0x48);gfx_ap_repeat_third_idle_polls++;
  if(status==~0U) return gfx_ap_repeat_third_refuse("third-idle-invalid",-EIO);
  if(status&3) {idle=true;break;}
  if(i+1<GFX_NATIVE_POWERGATE_IDLE_POLLS) usleep_range(1000,1100);
 }
 if(!idle) return gfx_ap_repeat_third_refuse("third-idle-timeout",-ETIMEDOUT);
 rx=readl(mbox+0x114);control=readl(asc+0x44);
 if(rx==~0U || control==~0U) return gfx_ap_repeat_third_refuse("third-stop-invalid",-EIO);
 if(!(rx&EMPTY) || !(control&START)) return gfx_ap_repeat_third_refuse("third-stop-unqualified",-EBUSY);
 gfx_ap_repeat_third_clear10_attempted=true;writel(control&~0x10U,asc+0x44);
 control=readl(asc+0x44);
 if(control==~0U || (control&START)) return gfx_ap_repeat_third_refuse("third-clear10-failed",-EIO);
 control=readl(asc+0x44);
 if(control==~0U || (control&START)) return gfx_ap_repeat_third_refuse("third-start-reasserted",-EIO);
 gfx_ap_repeat_third_clear20_attempted=true;writel(control&~0x20U,asc+0x44);
 control=readl(asc+0x44);status=readl(asc+0x48);
 if(control==~0U || status==~0U || (control&0x30U) || !(status&3))
  return gfx_ap_repeat_third_refuse("third-clear20-or-idle-failed",-EIO);
 gfx_ap_repeat_third_control=control;gfx_ap_repeat_third_status=status;
 gfx_ap_repeat_third_cpu_stopped=true;
 gfx_ap_repeat_third_log("third-cpu-stop-return",0);
 return 0;
}

static int gfx_ap_repeat_third_poweroff(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 unsigned int i;
 u32 control,status;
 int ret;
 if(!gfx_ap_repeat_third_cpu_stopped || !gfx_ap_repeat_third_ack_observed ||
    !gfx_ap_repeat_third_third_ref_held || !held || !pm_runtime_active(&consumer->dev) ||
    !pm_runtime_enabled(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error) || !recovery_idle() ||
    !gfx_ap_repeat_third_identity(false))
  return gfx_ap_repeat_third_refuse("third-off-preconditions-unqualified",-EBUSY);
 control=readl(asc+0x44);status=readl(asc+0x48);
 if(control==~0U || status==~0U)
  return gfx_ap_repeat_third_refuse("third-off-cpu-state-invalid",-EIO);
 if((control&START) || !(status&3))
  return gfx_ap_repeat_third_refuse("third-off-cpu-state-changed",-EBUSY);
 ret=gfx_poweroff_snapshot("repeat-third-before-third-off",0,&observation);
 if(ret) return gfx_ap_repeat_third_refuse("third-before-off-snapshot-error",ret);
 if(!observation.domain_on || (observation.before&0x80001cffU)!=0xffU)
  return gfx_ap_repeat_third_refuse("third-before-off-active-unqualified",-EBUSY);
 /* The new epoch's OFF intent is consumed before coordination callbacks. */
 gfx_ap_repeat_third_off_attempted=true;
 gfx_ap_repeat_third_log("third-coordinate-off-intent",0);
 ret=gfx_ap_repeat_third_coordinate_off();
 if(ret) return gfx_ap_repeat_third_refuse("third-coordinate-off-failed",ret);
 gfx_ap_repeat_third_pm_put_attempted=true;
 held=false;gfx_ap_repeat_third_third_ref_held=false;
 gfx_ap_repeat_third_pm_put_result=pm_runtime_put_sync_suspend(&consumer->dev);
 /* No ASC/SGX/mailbox/PMP/PMC reads or writes follow this consumed put. */
 gfx_ap_repeat_third_off_snapshot_result=-ETIMEDOUT;
 for(i=0;i<GFX_POWER_OFF_POLL_SAMPLES;i++) {
  gfx_ap_repeat_third_off_samples++;
  ret=gfx_poweroff_snapshot("repeat-third-after-third-off",i,&observation);
  if(ret) {gfx_ap_repeat_third_off_snapshot_result=ret;break;}
  if(!observation.domain_on && !(observation.before&GFX_POWER_OFF_STATE_MASK)) {
   gfx_ap_repeat_third_off_word=observation.before;
   gfx_ap_repeat_third_provider_off_observed=true;
   gfx_ap_repeat_third_off_snapshot_result=0;break;
  }
  if(i+1<GFX_POWER_OFF_POLL_SAMPLES)
   usleep_range(GFX_POWER_OFF_POLL_DELAY_US,GFX_POWER_OFF_POLL_DELAY_US+100);
 }
 gfx_ap_repeat_third_accounting_ok=pm_runtime_enabled(&consumer->dev) &&
  pm_runtime_suspended(&consumer->dev) && !pm_runtime_active(&consumer->dev) &&
  !atomic_read(&consumer->dev.power.usage_count) && !READ_ONCE(consumer->dev.power.runtime_error) && !held;
 ret=gfx_ap_repeat_third_pm_put_result<0?gfx_ap_repeat_third_pm_put_result:gfx_ap_repeat_third_off_snapshot_result;
 if(!ret && !gfx_ap_repeat_third_accounting_ok) ret=-EIO;
 if(ret) return gfx_ap_repeat_third_refuse("third-off-observation-failed",ret);
 gfx_ap_repeat_third_log("third-physical-off",0);
 return 0;
}

static int gfx_ap_repeat_third_attempt(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_ap_repeat_unknown) return -EPERM;
 if(gfx_ap_repeat_third_intent) return gfx_ap_repeat_control_refuse("third-intent-already-consumed",-EALREADY);
 gfx_ap_repeat_current_epoch=3;gfx_ap_repeat_third_intent=true;
 /* The distinct intent also seals the copied worker. Do not repair, clear or
  * rewrite historical first-epoch flags to manufacture a successful premise. */
 cancel_delayed_work(&recovery_receive_work);
 gfx_ap_repeat_third_log("intent",0);
 if(!gfx_ap_repeat_third_ap_on_known())
  return gfx_ap_repeat_third_refuse("cold-ap-on-unqualified",-EPERM);
 ret=gfx_ap_repeat_third_off_admission();
 if(ret) return ret;
 /* A new reference is consumed once; first epoch's put and gate stay intact.
  * resume_and_get does not transfer a reference on a negative return. */
 gfx_ap_repeat_third_pm_get_attempted=true;
 gfx_ap_repeat_third_log("third-pm-get-intent",0);
 gfx_ap_repeat_third_pm_get_result=pm_runtime_resume_and_get(&consumer->dev);
 if(gfx_ap_repeat_third_pm_get_result<0)
  return gfx_ap_repeat_third_refuse("third-pm-get-failed",gfx_ap_repeat_third_pm_get_result);
 held=true;gfx_ap_repeat_third_third_ref_held=true;
 if(!pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
    pm_runtime_suspended(&consumer->dev) || atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error))
  return gfx_ap_repeat_third_refuse("third-pm-accounting-unqualified",-EBUSY);
 ret=gfx_poweroff_snapshot("repeat-third-after-get",0,&observation);
 if(ret) return gfx_ap_repeat_third_refuse("fresh-active-snapshot-error",ret);
 if(!observation.domain_on || (observation.before&0x80001cffU)!=0xffU)
  return gfx_ap_repeat_third_refuse("fresh-physical-active-unqualified",-EBUSY);
 gfx_ap_repeat_third_identities_preserved=gfx_ap_repeat_third_identity(false);
 if(!gfx_ap_repeat_third_identities_preserved)
  return gfx_ap_repeat_third_refuse("retained-identity-changed-after-get",-EBUSY);
 ret=gfx_ap_repeat_third_cold_boundary(GFX_AP_REPEAT_THIRD_PRE_ON,true);
 if(ret) return ret;
 ret=gfx_ap_repeat_third_coordinate_on();
 if(ret) return gfx_ap_repeat_third_refuse("third-coordinate-on-failed",ret);
 /* The coordinator may take time. Refresh every START admission operand. */
 ret=gfx_ap_repeat_third_cold_boundary(GFX_AP_REPEAT_THIRD_POST_ON,true);
 if(ret) return ret;
 gfx_ap_repeat_third_boundary_qualified=true;gfx_ap_repeat_third_start_attempted=true;
 gfx_ap_repeat_third_log("third-start-intent",0);
 /* Refresh all four operands after intent logging, then the final CTRL RMW. */
 ret=gfx_ap_repeat_third_cold_boundary(GFX_AP_REPEAT_THIRD_POST_ON,false);
 if(ret) return ret;
 gfx_ap_repeat_third_control=readl(asc+0x44);
 if(gfx_ap_repeat_third_control==~0U || (gfx_ap_repeat_third_control&START))
  return gfx_ap_repeat_third_refuse("third-start-fresh-control-unqualified",-EBUSY);
 writel(gfx_ap_repeat_third_control|START,asc+0x44);
 gfx_ap_repeat_third_control=readl(asc+0x44);
 if(gfx_ap_repeat_third_control==~0U || !(gfx_ap_repeat_third_control&START))
  return gfx_ap_repeat_third_refuse("third-start-readback-failed",-EIO);
 gfx_ap_repeat_third_log("third-start-return",0);
 ret=gfx_ap_repeat_third_protocol();
 if(!ret) ret=gfx_ap_repeat_third_skip_host_on();
 if(!ret) ret=gfx_ap_repeat_third_management();
 if(!ret) ret=gfx_ap_repeat_third_stop_cpu();
 if(!ret) ret=gfx_ap_repeat_third_poweroff();
 gfx_ap_repeat_third_first_off_preserved=gfx_ap_repeat_third_first_off();
 gfx_ap_repeat_third_identities_preserved=gfx_ap_repeat_third_identity(false);
 if(!ret && (!gfx_ap_repeat_third_first_off_preserved || !gfx_ap_repeat_third_identities_preserved))
  ret=gfx_ap_repeat_third_refuse("retained-evidence-changed-after-protocol",-EIO);
 if(!ret) {gfx_ap_repeat_third_terminal_result=0;gfx_ap_repeat_third_complete=true;}
 gfx_ap_repeat_third_log("retained-final",ret);
 return ret;
}


static int gfx_retained_cycle_command(const char *buf)
{
 int ret;
 /* Diagnostics precede the persistent unknown gate and cannot create a new
  * reference. Their ASC operands remain cached after any consumed OFF put. */
 if(sysfs_streq(buf,"sample") || sysfs_streq(buf,"gfx-snapshot")) {
  ret=gfx_native_powergate_command(buf);
  gfx_retained_cycle_log("diagnostic-current",ret);
  gfx_ap_repeat_third_log("diagnostic-current",ret);
  return ret;
 }
 if(gfx_ap_repeat_unknown || gfx_native_powergate_startup_unknown) return -EPERM;
 if(sysfs_streq(buf,"gfx-native-ap-repeat-cycle")) return gfx_retained_cycle_attempt();
 if(sysfs_streq(buf,"gfx-native-ap-repeat-third")) return gfx_ap_repeat_third_attempt();
 if(sysfs_streq(buf,"gfx-powergate")) {
  if(gfx_retained_cycle_intent || gfx_ap_repeat_third_intent || !gfx_retained_cycle_ap_on_known()) {
   return gfx_ap_repeat_control_refuse("first-control-unqualified",-EPERM);
  }
  if(!gfx_retained_cycle_identity_captured && !gfx_retained_cycle_identity(true)) {
   return gfx_ap_repeat_control_refuse("original-identity-capture-failed",-EBUSY);
  }
  ret=gfx_native_powergate_command(buf);
  if(ret<0) gfx_ap_repeat_unknown=true;
  return ret;
 }
 /* No fourth epoch, arbitrary control or latch reset is defined. */
 return gfx_ap_repeat_control_refuse("control-not-defined",-EPERM);
}

static int gfx_retained_cycle_startup_retained(const char *phase,int result)
{
 gfx_ap_repeat_unknown=true;
 int ret=gfx_native_powergate_startup_retained(phase,result);
 pr_info("m4rch gfx-native-ap-repeat-cycle-startup-retained: epoch=1 phase=%s result=%d unknown=1 commands_allowed=0 first_intent=%u second_intent=%u allocations_released=0 restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_native_powergate_intent,gfx_retained_cycle_intent);
 return ret;
}
