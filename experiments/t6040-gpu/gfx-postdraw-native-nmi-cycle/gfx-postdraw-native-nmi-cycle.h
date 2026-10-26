/* SPDX-License-Identifier: GPL-2.0-only */
/* One experimental submitted-work management cycle. The immutable draw is
 * captured by the host first. The token is an audit join, not a C-side hash
 * verification. Native ACK/idle/OFF/ON do not authorize retirement or freeing.
 */
#ifndef GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL
#error Distinct postdraw native NMI cycle profile required
#endif
#ifndef GFX_POSTDRAW_NMI_ASC_BYTES
#error The new owner must reserve and map both ASC pages
#endif
#if GFX_POSTDRAW_NMI_ASC_BYTES != 0x2000U
#error Exact two-page ASC reservation required
#endif
#define GFX_POSTDRAW_NMI_MESSAGE 0x00f0000000000000ULL
#define GFX_POSTDRAW_NMI_TIMEOUT_MS 250U
#define GFX_POSTDRAW_NMI_POLLS 251U
#define GFX_POSTDRAW_NMI_MESSAGES 256U
static bool gfx_postdraw_nmi_asc_owned,gfx_postdraw_nmi_timeout_clean;
static bool gfx_postdraw_nmi_attempted,gfx_postdraw_nmi_ep0_published;
static bool gfx_postdraw_nmi_fiq1004_attempted,gfx_postdraw_nmi_fiq1014_attempted;
static bool gfx_postdraw_nmi_drain_complete,gfx_postdraw_nmi_idle_observed;
static unsigned int gfx_postdraw_nmi_messages,gfx_postdraw_nmi_polls,gfx_postdraw_nmi_crash_frames;
static u32 gfx_postdraw_nmi_status,gfx_postdraw_nmi_rx,gfx_postdraw_nmi_tx;
static unsigned long gfx_postdraw_nmi_sample_jiffies;
static struct {u64 message,metadata;} gfx_postdraw_nmi_journal[GFX_POSTDRAW_NMI_MESSAGES];
#define GFX_POSTDRAW_OFF_MASK 0x90001cffU
#define GFX_POSTDRAW_OFF_POLLS 101U
#define GFX_POSTDRAW_PROTOCOL_RECORDS 16U
#define GFX_POSTDRAW_PROTOCOL_POLLS 4001U
#define GFX_POSTDRAW_PROTOCOL_TIMEOUT_MS 4000U
#define GFX_POSTDRAW_BOOT_RUNNING 0x0070000000000020ULL
static bool gfx_postdraw_cycle_intent,gfx_postdraw_complete,gfx_postdraw_unknown;
static bool gfx_postdraw_identities_preserved,gfx_postdraw_device_access;
static bool gfx_postdraw_off_attempted,gfx_postdraw_pm_put_attempted;
static bool gfx_postdraw_provider_off,gfx_postdraw_accounting_ok;
static bool gfx_postdraw_pm_get_attempted,gfx_postdraw_second_ref_held;
static bool gfx_postdraw_start_attempted,gfx_postdraw_hello_replied;
static bool gfx_postdraw_endpoint_map,gfx_postdraw_boot_running_observed;
static bool gfx_postdraw_control_sealed;
static int gfx_postdraw_pm_put_result,gfx_postdraw_pm_get_result;
static int gfx_postdraw_terminal_result=-EINPROGRESS;
static const char *gfx_postdraw_refusal="none";
static char gfx_postdraw_capture_token[65]="none";
static u64 gfx_postdraw_boot_message,gfx_postdraw_boot_metadata;
static u8 gfx_postdraw_map_seen;
static u32 gfx_postdraw_advertised_appmap;
static unsigned int gfx_postdraw_protocol_records,gfx_postdraw_protocol_polls;
static unsigned int gfx_postdraw_hello_replies,gfx_postdraw_map_replies;
static u32 gfx_postdraw_control,gfx_postdraw_status,gfx_postdraw_rx,gfx_postdraw_tx;
static unsigned long gfx_postdraw_sample_jiffies;
static struct {u64 message,metadata;} gfx_postdraw_protocol_journal[GFX_POSTDRAW_PROTOCOL_RECORDS];
static struct gfx_coord_session gfx_postdraw_coord_session;
static struct gfx_coord_observation gfx_postdraw_coord_on;
/* Compatibility state belongs solely to the copied native stop helper. */
static bool gfx_poweroff_start_clear_attempted,gfx_reset_scope_host_stopped;

/* Metadata/retained DRAM only; valid with held0 after OFF. Preserve the original
 * cold identity and evidence rather than resetting or recapturing it. */
static bool gfx_postdraw_identity(void)
{
 unsigned int i;
 gfx_postdraw_identities_preserved=false;
 if(!gfx_cold_identity_captured || !resident_session || !gfx_coord_owner_retained() ||
    !gfx_coord_owner_module_pinned || !consumer || !asc || !mbox ||
    !asc_region || !mbox_region || !root_sent || !installed || root_detached ||
    !device_context_retained || !bootstrap || !target_slot || !target_page ||
    consumer!=gfx_cold_consumer || asc!=gfx_cold_asc || mbox!=gfx_cold_mbox ||
    bootstrap!=gfx_cold_bootstrap || borrowed_l1!=gfx_cold_borrowed_l1 ||
    target_page!=gfx_cold_target_page || target_slot!=gfx_cold_target_slot ||
    ARRAY_SIZE(owned)!=GFX_COLD_PAGES) return false;
 for(i=0;i<GFX_COLD_PAGES;i++)
  if(!owned[i] || owned[i]!=gfx_cold_pages[i] ||
     page_to_phys(owned[i])!=gfx_cold_page_pa[i]) return false;
 recovery_invalidate(target_slot,sizeof(*target_slot));
 if(READ_ONCE(*target_slot)!=gfx_cold_root_word ||
    gfx_cold_root_word!=(page_to_phys(owned[borrowed_l1?1:0])|3ULL)) return false;
 gfx_postdraw_identities_preserved=true;return true;
}
static bool gfx_postdraw_pm_active(void)
{
 return consumer && held && pm_runtime_enabled(&consumer->dev) &&
  pm_runtime_active(&consumer->dev) && !pm_runtime_suspended(&consumer->dev) &&
  atomic_read(&consumer->dev.power.usage_count)==1 &&
  !READ_ONCE(consumer->dev.power.runtime_error);
}
static bool gfx_postdraw_active(void)
{
 return gfx_postdraw_device_access && gfx_postdraw_pm_active() &&
  gfx_postdraw_identity() && gfx_cold_ap_known();
}
static bool gfx_postdraw_pm_off(void)
{
 return consumer && !held && pm_runtime_enabled(&consumer->dev) &&
  !pm_runtime_active(&consumer->dev) && pm_runtime_suspended(&consumer->dev) &&
  !atomic_read(&consumer->dev.power.usage_count) &&
  !READ_ONCE(consumer->dev.power.runtime_error);
}

/* Forward declarations used by copied admission/ACK/stop functions. */
static void gfx_postdraw_log(const char *phase,int result);
static int gfx_postdraw_refuse(const char *condition,int result);

/* Checked v12 native admission/ACK/idle/stop bodies. Distinct postdraw250ms/256frame
 * admission accommodates trace3 backlog; ACK2000ms and idle11polls unchanged.
 * Added own ACTIVE/identity checks precede device reads. */
#define GFX_NATIVE_POWERGATE_REQUEST 0x0060000000000202ULL
#define GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS 2000U
#define GFX_NATIVE_POWERGATE_ACK_POLLS 2001U
#define GFX_NATIVE_POWERGATE_RX_MESSAGES 64U
#define GFX_NATIVE_POWERGATE_IDLE_POLLS 11U
#define GFX_NATIVE_POWERGATE_ADMISSION_TIMEOUT_MS 250U
#define GFX_NATIVE_POWERGATE_ADMISSION_WAIT_POLLS 251U
#define GFX_NATIVE_POWERGATE_ADMISSION_MESSAGES 256U
static bool gfx_native_powergate_intent, gfx_native_powergate_request_attempted;
static bool gfx_native_powergate_ack_observed, gfx_native_powergate_idle_observed;
static bool gfx_native_powergate_clear10_attempted, gfx_native_powergate_clear20_attempted;
static bool gfx_native_powergate_cpu_stopped, gfx_native_powergate_off_delegated;
static bool gfx_native_powergate_initial_recovery_failed;
static bool gfx_native_powergate_startup_unknown;
static bool gfx_native_powergate_rx_empty_after_ack, gfx_native_powergate_rx_empty_before_cpu;
static u64 gfx_native_powergate_ack_message, gfx_native_powergate_ack_metadata;
static u32 gfx_native_powergate_control_before, gfx_native_powergate_control_after10;
static u32 gfx_native_powergate_control_after20, gfx_native_powergate_idle_status;
static unsigned int gfx_native_powergate_ack_polls, gfx_native_powergate_rx_messages;
static unsigned int gfx_native_powergate_idle_polls;
static const char *gfx_native_powergate_admission_refusal="none";
static unsigned long gfx_native_powergate_admission_until;
static unsigned int gfx_native_powergate_admission_samples;
static unsigned int gfx_native_powergate_admission_wait_polls;
static unsigned int gfx_native_powergate_admission_messages;
static u32 gfx_native_powergate_admission_control, gfx_native_powergate_admission_status;
static u32 gfx_native_powergate_admission_rx, gfx_native_powergate_admission_tx;
static bool gfx_native_powergate_admission_hardware_sampled;
static bool gfx_native_powergate_admission_complete;



static void gfx_native_powergate_admission_log(const char *phase,int result)
{
 pr_info("m4rch gfx-postdraw-native-drain-admission: epoch=1 phase=%s result=%d refused_condition=%s intent=%u hardware_sampled=%u status_samples=%u wait_polls=%u messages=%u complete=%u control44=%#x status48=%#x rx_status=%#x tx_status=%#x journal_used=%u journal_status=%#x receive_crashed=%u held=%u usage=%d runtime_error=%d request_attempted=%u\n",
  phase,result,gfx_native_powergate_admission_refusal,gfx_native_powergate_intent,
  gfx_native_powergate_admission_hardware_sampled,gfx_native_powergate_admission_samples,
  gfx_native_powergate_admission_wait_polls,gfx_native_powergate_admission_messages,
  gfx_native_powergate_admission_complete,gfx_native_powergate_admission_control,
  gfx_native_powergate_admission_status,gfx_native_powergate_admission_rx,
  gfx_native_powergate_admission_tx,receive_journal.used,receive_journal.status,
  receive_crashed,held,atomic_read(&consumer->dev.power.usage_count),
  READ_ONCE(consumer->dev.power.runtime_error),gfx_native_powergate_request_attempted);
}

static int gfx_native_powergate_admission_refuse(const char *condition,int result)
{
 gfx_native_powergate_admission_refusal=condition;
 gfx_native_powergate_admission_log("refused",result);
 return result;
}

static int gfx_native_powergate_admission_snapshot(const char *phase)
{
 if(!gfx_postdraw_active()) return gfx_native_powergate_admission_refuse("admission-ownership",-EBUSY);
 gfx_native_powergate_admission_control=readl(asc+0x44);
 gfx_native_powergate_admission_status=readl(asc+0x48);
 gfx_native_powergate_admission_rx=readl(mbox+0x114);
 gfx_native_powergate_admission_tx=readl(mbox+0x110);
 gfx_native_powergate_admission_hardware_sampled=true;
 gfx_native_powergate_admission_samples++;
 gfx_native_powergate_admission_log(phase,0);
 if(gfx_native_powergate_admission_control==~0U)
  return gfx_native_powergate_admission_refuse("control44-invalid",-EIO);
 if(gfx_native_powergate_admission_status==~0U)
  return gfx_native_powergate_admission_refuse("status48-invalid",-EIO);
 if(gfx_native_powergate_admission_rx==~0U)
  return gfx_native_powergate_admission_refuse("rx-status-invalid",-EIO);
 if(gfx_native_powergate_admission_tx==~0U)
  return gfx_native_powergate_admission_refuse("tx-status-invalid",-EIO);
 if(!(gfx_native_powergate_admission_control&START))
  return gfx_native_powergate_admission_refuse("start-clear",-EBUSY);
 return 0;
}

static int gfx_native_powergate_admission_drain(void)
{
 int ret;
 gfx_native_powergate_admission_until=jiffies+
  msecs_to_jiffies(GFX_NATIVE_POWERGATE_ADMISSION_TIMEOUT_MS);
 for(;;) {
  u64 message,metadata;
  if(!time_before(jiffies,gfx_native_powergate_admission_until))
   return gfx_native_powergate_admission_refuse("admission-deadline",-ETIMEDOUT);
  ret=gfx_native_powergate_admission_snapshot("poll");
  if(ret) return ret;
  if(!(gfx_native_powergate_admission_rx&EMPTY)) {
   message=readq(mbox+0x830);metadata=readq(mbox+0x838);
   gfx_native_powergate_admission_messages++;
   pr_info("m4rch gfx-postdraw-native-drain-rx: epoch=1 phase=admission index=%u message=%#llx metadata=%#llx rx_status=%#x tx_status=%#x control44=%#x status48=%#x\n",
    gfx_native_powergate_admission_messages,(unsigned long long)message,
    (unsigned long long)metadata,gfx_native_powergate_admission_rx,
    gfx_native_powergate_admission_tx,gfx_native_powergate_admission_control,
    gfx_native_powergate_admission_status);
   if(!time_before(jiffies,gfx_native_powergate_admission_until))
    return gfx_native_powergate_admission_refuse("frame-at-deadline",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL)
    return gfx_native_powergate_admission_refuse("admission-frame-invalid",-EIO);
   if((metadata&0xff)==0)
    return gfx_native_powergate_admission_refuse("preexisting-ep0",-EPROTO);
   if((metadata&0xff)!=32 || message!=0x0042000000000000ULL) {
    if((metadata&0xff)==1) receive_crashed=true;
    return gfx_native_powergate_admission_refuse("unqualified-admission-frame",-EPROTO);
   }
   /* Use only the frozen service's EP32 copy/consumer publication. This
    * never resets producer cursors, frees backing or handles management. */
   if(!receive_mailbox(message,metadata) || receive_crashed || receive_journal.status)
    return gfx_native_powergate_admission_refuse("receive-service-failed",-EIO);
   if(receive_journal.used>=RECEIVE_CAPACITY)
    return gfx_native_powergate_admission_refuse("journal-full-after-drain",-EOVERFLOW);
   if(gfx_native_powergate_admission_messages>=GFX_NATIVE_POWERGATE_ADMISSION_MESSAGES)
    return gfx_native_powergate_admission_refuse("admission-message-limit",-EOVERFLOW);
   if(!time_before(jiffies,gfx_native_powergate_admission_until))
    return gfx_native_powergate_admission_refuse("service-at-deadline",-ETIMEDOUT);
   continue;
  }
  gfx_native_powergate_admission_wait_polls++;
  if(!(gfx_native_powergate_admission_tx&BIT(16))) {
   gfx_native_powergate_admission_complete=true;
   gfx_native_powergate_admission_log("ready",0);
   return 0;
  }
  if(gfx_native_powergate_admission_wait_polls>=GFX_NATIVE_POWERGATE_ADMISSION_WAIT_POLLS)
   return gfx_native_powergate_admission_refuse("tx-wait-poll-limit",-ETIMEDOUT);
  usleep_range(1000,1100);
 }
}

static void gfx_native_powergate_log(const char *phase,int result)
{gfx_postdraw_log(phase,result);}

/* Only an owned published request with every removed frame already classified
 * can enter the NMI branch. A timeout after removing an unclassified frame,
 * admission timeout, invalid operand, crash, service failure or overflow cannot. */
static int gfx_postdraw_nmi_clean_ack_timeout(void)
{
 if(gfx_native_powergate_request_attempted && !gfx_native_powergate_ack_observed &&
    gfx_postdraw_active() && !receive_crashed && !receive_journal.status &&
    receive_journal.used<RECEIVE_CAPACITY &&
    gfx_native_powergate_rx_messages<GFX_NATIVE_POWERGATE_RX_MESSAGES)
  gfx_postdraw_nmi_timeout_clean=true;
 return -ETIMEDOUT;
}

static int gfx_native_powergate_ack(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS);
 unsigned int i;
 int ret;
 if(!gfx_postdraw_active()) return -EBUSY;
 /* Take one fresh four-operand sample immediately before the request. A new
  * frame after the bounded drain seals admission instead of counting as ACK. */
 if(!time_before(jiffies,gfx_native_powergate_admission_until))
  return gfx_native_powergate_admission_refuse("pre-request-deadline",-ETIMEDOUT);
 ret=gfx_native_powergate_admission_snapshot("before-request");
 if(ret) return ret;
 if(!(gfx_native_powergate_admission_rx&EMPTY))
  return gfx_native_powergate_admission_refuse("rx-returned-before-request",-EBUSY);
 if(gfx_native_powergate_admission_tx&BIT(16))
  return gfx_native_powergate_admission_refuse("tx-full-before-request",-EBUSY);
 if(!time_before(jiffies,gfx_native_powergate_admission_until))
  return gfx_native_powergate_admission_refuse("pre-request-sample-deadline",-ETIMEDOUT);
 /* Intent is already durable in the owner. Mark this sole publication before
  * writing either transport word; there is no retransmission on any result. */
 gfx_native_powergate_request_attempted=true;
 wmb();writeq(GFX_NATIVE_POWERGATE_REQUEST,mbox+0x800);writeq(0,mbox+0x808);
 gfx_native_powergate_log("request-published",0);
 for(i=0;i<GFX_NATIVE_POWERGATE_ACK_POLLS;i++) {
  u64 message,metadata;
  u32 rx;
  if(!time_before(jiffies,until)) return gfx_postdraw_nmi_clean_ack_timeout();
  gfx_native_powergate_ack_polls++;
  if(!gfx_postdraw_active()) return -EBUSY;
  rx=readl(mbox+0x114);
  if(rx==~0U) return -EIO;
  if(!(rx&EMPTY)) {
   message=readq(mbox+0x830);metadata=readq(mbox+0x838);
   gfx_native_powergate_rx_messages++;
   /* Preserve every removed frame, including invalid/unhandled frames. */
   pr_info("m4rch gfx-postdraw-native-drain-rx: epoch=1 phase=ack index=%u message=%#llx metadata=%#llx rx_status=%#x\n",
    gfx_native_powergate_rx_messages,(unsigned long long)message,
    (unsigned long long)metadata,rx);
   if(!time_before(jiffies,until)) return -ETIMEDOUT;
   if(message==~0ULL || metadata==~0ULL) return -EIO;
   if((metadata&0xff)==0) {
    if(((message>>52)&0xf)!=7 ||
       ((message&0xff)!=1 && (message&0xff)!=2)) return -EPROTO;
    gfx_native_powergate_ack_message=message;
    gfx_native_powergate_ack_metadata=metadata;
    gfx_native_powergate_ack_observed=true;
    {
     u32 rx=readl(mbox+0x114);
     if(rx==~0U) return -EIO;
     if(!(rx&EMPTY)) return -EBUSY;
     gfx_native_powergate_rx_empty_after_ack=true;
    }
    return 0;
   }
   /* The existing service preserves copied transport records and advances
    * only qualified consumers. Unknown/crash/overflow seals this attempt. */
   if(!receive_mailbox(message,metadata)) return -EIO;
   if(gfx_native_powergate_rx_messages>=GFX_NATIVE_POWERGATE_RX_MESSAGES)
    return -EOVERFLOW;
  }
  usleep_range(1000,1100);
 }
 return gfx_postdraw_nmi_clean_ack_timeout();
}

static void gfx_postdraw_nmi_log(const char *phase,int result)
{
 pr_info("m4rch gfx-postdraw-native-nmi: phase=%s result=%d eligible=%u attempted=%u ep0_published=%u fiq1004_attempted=%u fiq1014_attempted=%u drain_complete=%u idle_observed=%u messages=%u polls=%u crash_frames=%u status48=%#x rx_status=%#x tx_status=%#x sample_jiffies=%lu asc_extent=%#x asc_owned=%u ack_observed=%u operand_samples_atomic=0\n",
  phase,result,gfx_postdraw_nmi_timeout_clean,gfx_postdraw_nmi_attempted,
  gfx_postdraw_nmi_ep0_published,gfx_postdraw_nmi_fiq1004_attempted,
  gfx_postdraw_nmi_fiq1014_attempted,gfx_postdraw_nmi_drain_complete,
  gfx_postdraw_nmi_idle_observed,gfx_postdraw_nmi_messages,gfx_postdraw_nmi_polls,
  gfx_postdraw_nmi_crash_frames,gfx_postdraw_nmi_status,gfx_postdraw_nmi_rx,
  gfx_postdraw_nmi_tx,gfx_postdraw_nmi_sample_jiffies,GFX_POSTDRAW_NMI_ASC_BYTES,
  gfx_postdraw_nmi_asc_owned,gfx_native_powergate_ack_observed);
}

/* Firmware-side subset of native RTBuddy type0 NMI. macOS host panic policy,
 * crash buffer allocation/replies and firmware DMA release are deliberately
 * absent. EP1 is preserved raw; it never proves ACK, idle or retirement. */
static int gfx_postdraw_nmi(void)
{
 unsigned long until;unsigned int i;int ret=0;u32 control;
 if(!gfx_postdraw_nmi_timeout_clean || gfx_native_powergate_ack_observed ||
    !gfx_native_powergate_request_attempted || gfx_postdraw_nmi_attempted ||
    !gfx_postdraw_nmi_asc_owned || !asc_region || !gfx_postdraw_active() ||
    receive_crashed || receive_journal.status || receive_journal.used>=RECEIVE_CAPACITY)
  return -EBUSY;
 control=readl(asc+0x44);gfx_postdraw_nmi_status=readl(asc+0x48);
 gfx_postdraw_nmi_rx=readl(mbox+0x114);gfx_postdraw_nmi_tx=readl(mbox+0x110);
 gfx_postdraw_nmi_sample_jiffies=jiffies;
 if(control==~0U || gfx_postdraw_nmi_status==~0U ||
    gfx_postdraw_nmi_rx==~0U || gfx_postdraw_nmi_tx==~0U) return -EIO;
 if(!(control&START) || !(gfx_postdraw_nmi_rx&EMPTY) ||
    (gfx_postdraw_nmi_tx&BIT(16)) || !gfx_postdraw_active()) return -EBUSY;
 gfx_postdraw_nmi_log("eligible",0);
 if(!gfx_postdraw_active() || !gfx_postdraw_nmi_asc_owned) return -EBUSY;
 gfx_postdraw_nmi_attempted=true;
 wmb();writeq(GFX_POSTDRAW_NMI_MESSAGE,mbox+0x800);writeq(0,mbox+0x808);
 gfx_postdraw_nmi_ep0_published=true;gfx_postdraw_nmi_log("request-published",0);
 if(!gfx_postdraw_active()) {ret=-EBUSY;goto done;}
 gfx_postdraw_nmi_fiq1004_attempted=true;writel(0x10U,asc+0x1004);
 gfx_postdraw_nmi_fiq1014_attempted=true;writel(1U,asc+0x1014);
 gfx_postdraw_nmi_log("fiq-published",0);
 until=jiffies+msecs_to_jiffies(GFX_POSTDRAW_NMI_TIMEOUT_MS);
 for(i=0;i<GFX_POSTDRAW_NMI_POLLS;i++) {
  u64 message,metadata;unsigned int ep;
  if(!time_before(jiffies,until)) {ret=-ETIMEDOUT;goto done;}
  if(!gfx_postdraw_active() || receive_crashed || receive_journal.status ||
     receive_journal.used>=RECEIVE_CAPACITY) {ret=-EBUSY;goto done;}
  gfx_postdraw_nmi_polls++;
  gfx_postdraw_nmi_status=readl(asc+0x48);gfx_postdraw_nmi_rx=readl(mbox+0x114);
  gfx_postdraw_nmi_tx=readl(mbox+0x110);gfx_postdraw_nmi_sample_jiffies=jiffies;
  if(gfx_postdraw_nmi_status==~0U || gfx_postdraw_nmi_rx==~0U ||
     gfx_postdraw_nmi_tx==~0U) {ret=-EIO;goto done;}
  if(!time_before(jiffies,until)) {ret=-ETIMEDOUT;goto done;}
  if(!(gfx_postdraw_nmi_rx&EMPTY)) {
   if(gfx_postdraw_nmi_messages>=GFX_POSTDRAW_NMI_MESSAGES) {ret=-EOVERFLOW;goto done;}
   message=readq(mbox+0x830);metadata=readq(mbox+0x838);
   gfx_postdraw_nmi_journal[gfx_postdraw_nmi_messages].message=message;
   gfx_postdraw_nmi_journal[gfx_postdraw_nmi_messages].metadata=metadata;
   gfx_postdraw_nmi_messages++;
   pr_info("m4rch gfx-postdraw-native-nmi-rx: direction=rx index=%u message=%#llx metadata=%#llx rx_status=%#x raw_only=1\n",
    gfx_postdraw_nmi_messages,(unsigned long long)message,(unsigned long long)metadata,gfx_postdraw_nmi_rx);
   if(!time_before(jiffies,until)) {ret=-ETIMEDOUT;goto done;}
   if(message==~0ULL || metadata==~0ULL) {ret=-EIO;goto done;}
   ep=metadata&0xff;
   if(ep==1) gfx_postdraw_nmi_crash_frames++;
   else if(ep==32 && message==0x0042000000000000ULL) {
    if(!receive_mailbox(message,metadata) || receive_crashed || receive_journal.status ||
       receive_journal.used>=RECEIVE_CAPACITY) {ret=-EIO;goto done;}
   } else {ret=-EPROTO;goto done;}
   continue;
  }
  if((gfx_postdraw_nmi_status&3) && !(gfx_postdraw_nmi_tx&BIT(16))) {
   /* Fresh separate operands; this is not an atomic hardware snapshot. */
   gfx_postdraw_nmi_idle_observed=true;gfx_postdraw_nmi_drain_complete=true;
   gfx_postdraw_nmi_log("drain-ready",0);goto done;
  }
  if(i+1<GFX_POSTDRAW_NMI_POLLS) usleep_range(1000,1100);
 }
 ret=-ETIMEDOUT;
done:
 gfx_postdraw_nmi_log("return",ret);return ret;
}

static int gfx_native_powergate_stop_cpu(void)
{
 unsigned int i;
 u32 control,rx;
 if(!gfx_postdraw_active()) return -EBUSY;
 /* Matched generic V6 tests either STATUS48 low bit before CPU-stop writes.
  * Optional CTRL40 idle gating is absent from the actual saved GFX ADT. */
 for(i=0;i<GFX_NATIVE_POWERGATE_IDLE_POLLS;i++) {
  if(!gfx_postdraw_active()) return -EBUSY;
  gfx_native_powergate_idle_status=readl(asc+0x48);
  gfx_native_powergate_idle_polls++;
  if(gfx_native_powergate_idle_status==~0U) return -EIO;
  if(gfx_native_powergate_idle_status&3) {
   gfx_native_powergate_idle_observed=true;break;
  }
  if(i+1<GFX_NATIVE_POWERGATE_IDLE_POLLS) usleep_range(1000,1100);
 }
 if(!gfx_native_powergate_idle_observed) return -ETIMEDOUT;
 rx=readl(mbox+0x114);
 if(rx==~0U) return -EIO;
 if(!(rx&EMPTY)) return -EBUSY;
 gfx_native_powergate_rx_empty_before_cpu=true;
 control=readl(asc+0x44);
 if(control==~0U || !(control&START)) return -EIO;
 gfx_native_powergate_control_before=control;
 gfx_native_powergate_clear10_attempted=true;
 gfx_poweroff_start_clear_attempted=true;
 writel(control&~0x10U,asc+0x44);
 gfx_native_powergate_control_after10=readl(asc+0x44);
 if(gfx_native_powergate_control_after10==~0U ||
    (gfx_native_powergate_control_after10&0x10U)) return -EIO;
 /* Fresh second RMW; do not replay the entry value over hardware changes. */
 control=readl(asc+0x44);
 if(control==~0U || (control&START)) return -EIO;
 gfx_native_powergate_clear20_attempted=true;
 writel(control&~0x20U,asc+0x44);
 gfx_native_powergate_control_after20=readl(asc+0x44);
 if(gfx_native_powergate_control_after20==~0U ||
    (gfx_native_powergate_control_after20&0x30U)) return -EIO;
 gfx_native_powergate_idle_status=readl(asc+0x48);
 if(gfx_native_powergate_idle_status==~0U ||
    !(gfx_native_powergate_idle_status&3)) return -EIO;
 gfx_native_powergate_cpu_stopped=true;gfx_reset_scope_host_stopped=true;
 return 0;
}

static void gfx_postdraw_log(const char *phase,int result)
{
 pr_info("m4rch gfx-postdraw-native-cycle: phase=%s result=%d refused_condition=%s intent=%u complete=%u unknown=%u capture_token=%s token_host_verified=0 allocations_retained=%u retirement_verified=0 management_rejoin_verified=%u\n",
  phase,result,gfx_postdraw_refusal,gfx_postdraw_cycle_intent,gfx_postdraw_complete,
  gfx_postdraw_unknown,gfx_postdraw_capture_token,gfx_cold_retained_pages(),gfx_postdraw_complete);
 pr_info("m4rch gfx-postdraw-native-cycle-state: phase=%s held=%u usage=%d runtime_error=%d active=%u suspended=%u identities_preserved=%u device_access_allowed=%u epoch=%u operand_samples_atomic=0\n",
  phase,held,consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_error):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  consumer?pm_runtime_suspended(&consumer->dev):false,gfx_postdraw_identities_preserved,
  gfx_postdraw_device_access,gfx_cold_current_epoch);
 pr_info("m4rch gfx-postdraw-native-cycle-off: phase=%s request_attempted=%u ack_observed=%u ack_message=%#llx ack_metadata=%#llx idle_observed=%u clear10_attempted=%u clear20_attempted=%u cpu_stopped=%u off_attempted=%u coordinate_off_complete=%u pm_put_attempted=%u pm_put_result=%d provider_off_observed=%u accounting_ok=%u\n",
  phase,gfx_native_powergate_request_attempted,gfx_native_powergate_ack_observed,
  (unsigned long long)gfx_native_powergate_ack_message,
  (unsigned long long)gfx_native_powergate_ack_metadata,gfx_native_powergate_idle_observed,
  gfx_native_powergate_clear10_attempted,gfx_native_powergate_clear20_attempted,
  gfx_native_powergate_cpu_stopped,gfx_postdraw_off_attempted,gfx_coord_owner_session.off_complete,
  gfx_postdraw_pm_put_attempted,gfx_postdraw_pm_put_result,gfx_postdraw_provider_off,
  gfx_postdraw_accounting_ok);
 pr_info("m4rch gfx-postdraw-native-cycle-on: phase=%s get_attempted=%u get_result=%d coordinate_on_complete=%u start_attempted=%u hello_replied=%u map_seen=%u endpoint_map=%u boot_running_observed=%u host_on_requests=0 root_publications=0 application_starts=0 work_replays=0\n",
  phase,gfx_postdraw_pm_get_attempted,gfx_postdraw_pm_get_result,
  gfx_postdraw_coord_session.on_complete,gfx_postdraw_start_attempted,
  gfx_postdraw_hello_replied,gfx_postdraw_map_seen,gfx_postdraw_endpoint_map,
  gfx_postdraw_boot_running_observed);
 pr_info("m4rch gfx-postdraw-native-cycle-management: phase=%s boot_message=%#llx boot_metadata=%#llx hello_replies=%u map_replies=%u advertised_appmap=%u application_bitmap_selected=0 AP_carried_known=%u AP_carried_state=%#x application_starts=0 root_publications=0 work_replays=0\n",
  phase,(unsigned long long)gfx_postdraw_boot_message,(unsigned long long)gfx_postdraw_boot_metadata,
  gfx_postdraw_hello_replies,gfx_postdraw_map_replies,gfx_postdraw_advertised_appmap,
  gfx_cold_ap_known(),gfx_ap_remote_state);
 pr_info("m4rch gfx-postdraw-native-cycle-transport: phase=%s control44=%#x status48=%#x rx_status=%#x tx_status=%#x sample_jiffies=%lu cached=1 epoch=%u operand_samples_atomic=0\n",
  phase,gfx_postdraw_control,gfx_postdraw_status,gfx_postdraw_rx,gfx_postdraw_tx,
  gfx_postdraw_sample_jiffies,gfx_cold_current_epoch);
}
static int gfx_postdraw_refuse(const char *condition,int result)
{
 gfx_postdraw_refusal=condition;gfx_postdraw_unknown=true;
 gfx_postdraw_terminal_result=result>0?-EIO:result;receive_enabled=false;
 gfx_postdraw_log("refused",gfx_postdraw_terminal_result);return gfx_postdraw_terminal_result;
}
static int gfx_postdraw_physical(const char *phase,unsigned int index,bool on)
{
 struct apple_pmgr_gfx_reset_observation o;
 int ret=gfx_cold_snapshot(phase,index,&o);
 pr_info("m4rch gfx-postdraw-native-cycle-physical: phase=%s index=%u result=%d valid=%#x domain_on=%u word=%#x state_mask=%#x expected_on=%u operand_samples_atomic=0\n",
  phase,index,ret,o.valid,o.domain_on,o.before,GFX_POSTDRAW_OFF_MASK,on);
 if(ret) return ret;
 if(on) return o.domain_on && (o.before&0x80001cffU)==0xffU?0:-EBUSY;
 return !o.domain_on && !(o.before&GFX_POSTDRAW_OFF_MASK)?0:-EBUSY;
}

static bool gfx_postdraw_draw_qualified(void)
{
 unsigned int i;
 if(!gfx_cold_pipeline_intent || !gfx_cold_complete || !gfx_cold_sealed ||
    !gfx_cold_software_stopped || gfx_cold_running || gfx_cold_terminal_result ||
    strcmp(gfx_cold_refusal,"none") || !gfx_cold_draw_intent || !recovery_work_submitted ||
    !gfx_cold_draw_notify_attempted || !gfx_cold_draw_notify_sent ||
    gfx_cold_observation_samples!=6 || gfx_cold_sample_index!=5 ||
    gfx_cold_elapsed_ms<GFX_COLD_OBSERVE_MS || !gfx_cold_control_ready ||
    !gfx_cold_control_notify_attempted || !gfx_cold_control_notify_sent ||
    !gfx_cold_record_verified || gfx_cold_apps_started!=3 || !gfx_cold_ap_known() ||
    !gfx_coord_owner_session.on_complete || gfx_coord_owner_session.off_attempted ||
    receive_enabled || receive_crashed || receive_journal.status ||
    receive_journal.used>=RECEIVE_CAPACITY || !gfx_postdraw_identity() ||
    !gfx_postdraw_pm_active()) return false;
 for(i=0;i<2;i++)
  if(!gfx_cold_record_attempted[i] || !gfx_cold_record_cleaned[i] ||
     !gfx_cold_producer_attempted[i] || !gfx_cold_producer_verified[i]) return false;
 /* Submitted cursors are retained and may be nonzero. A management abort is
  * experimental; these DRAM observations are not work retirement evidence. */
 gfx_cold_read_application();
 return !gfx_cold_counter && !gfx_cold_phase && !gfx_cold_host_stop &&
  !gfx_cold_request_state && !gfx_cold_request_flag &&
  gfx_cold_control[0]==33 && gfx_cold_control[1]==33 && gfx_cold_control[2]==33 &&
  gfx_cold_trace_after==3;
}

static int gfx_postdraw_off(void)
{
 unsigned int i;int ret;
 if(!(gfx_native_powergate_ack_observed || (gfx_postdraw_nmi_timeout_clean &&
       gfx_postdraw_nmi_attempted && gfx_postdraw_nmi_ep0_published &&
       gfx_postdraw_nmi_fiq1004_attempted && gfx_postdraw_nmi_fiq1014_attempted &&
       gfx_postdraw_nmi_drain_complete && gfx_postdraw_nmi_idle_observed)) ||
    !gfx_native_powergate_idle_observed ||
    !gfx_native_powergate_cpu_stopped || !gfx_native_powergate_clear10_attempted ||
    !gfx_native_powergate_clear20_attempted || !gfx_postdraw_active())
  return gfx_postdraw_refuse("off-native-premise",-EBUSY);
 ret=gfx_postdraw_physical("before-off",0,true);
 if(ret) return gfx_postdraw_refuse("off-physical-on",ret);
 if(!gfx_coord_owner_pmp || !gfx_coord_owner_pmc || !gfx_coord_owner_pmp_region ||
    !gfx_coord_owner_pmc_region || !gfx_coord_owner_session.on_complete ||
    gfx_coord_owner_session.off_attempted)
  return gfx_postdraw_refuse("off-coordinate-premise",-EBUSY);
 ret=gfx_coord_owner_alias_check();if(ret) return gfx_postdraw_refuse("off-coordinate-alias",ret);
 /* From this point even a refused OFF keeps ASC/SGX/mailbox inaccessible. */
 gfx_postdraw_off_attempted=true;gfx_postdraw_control_sealed=true;
 gfx_postdraw_device_access=false;receive_enabled=false;gfx_postdraw_log("off-intent",0);
 if(!gfx_postdraw_identity() || !gfx_postdraw_pm_active())
  return gfx_postdraw_refuse("off-intent-ownership",-EBUSY);
 ret=gfx_coord_owner_transition(false);
 if(ret) return gfx_postdraw_refuse("off-coordinate",ret);
 if(!gfx_coord_owner_session.off_complete || !gfx_postdraw_identity() || !gfx_postdraw_pm_active())
  return gfx_postdraw_refuse("off-before-put-ownership",-EBUSY);
 gfx_postdraw_pm_put_attempted=true;held=false;
 gfx_postdraw_log("off-put-intent",0);
 gfx_postdraw_pm_put_result=pm_runtime_put_sync_suspend(&consumer->dev);
 gfx_postdraw_accounting_ok=gfx_postdraw_pm_off();
 gfx_postdraw_log("off-put-return",gfx_postdraw_pm_put_result);
 if(gfx_postdraw_pm_put_result<0) return gfx_postdraw_refuse("off-pm-put",gfx_postdraw_pm_put_result);
 for(i=0;i<GFX_POSTDRAW_OFF_POLLS;i++) {
  ret=gfx_postdraw_physical("after-off",i,false);
  if(!ret) {gfx_postdraw_provider_off=true;break;}
  if(ret!=-EBUSY) return gfx_postdraw_refuse("off-physical-observation",ret);
  if(i+1<GFX_POSTDRAW_OFF_POLLS) usleep_range(1000,1100);
 }
 gfx_postdraw_accounting_ok=gfx_postdraw_pm_off();
 if(!gfx_postdraw_provider_off || !gfx_postdraw_accounting_ok || !gfx_postdraw_identity())
  return gfx_postdraw_refuse("off-not-qualified",-EIO);
 gfx_postdraw_log("off-qualified",0);return 0;
}

/* Fresh ON validity permits the frozen V12 preON6a/6c and postON6a/6c/6d
 * hypotheses. No general START or INIT fallback is admitted. */
static int gfx_postdraw_cold_boundary(bool after_coordinate)
{
 if(!gfx_postdraw_active() || !gfx_postdraw_second_ref_held ||
    (after_coordinate && !gfx_postdraw_coord_session.on_complete))
  return gfx_postdraw_refuse("on-cold-ownership",-EBUSY);
 gfx_postdraw_control=readl(asc+0x44);gfx_postdraw_status=readl(asc+0x48);
 gfx_postdraw_rx=readl(mbox+0x114);gfx_postdraw_tx=readl(mbox+0x110);
 gfx_postdraw_sample_jiffies=jiffies;
 if(gfx_postdraw_control==~0U || gfx_postdraw_status==~0U ||
    gfx_postdraw_rx==~0U || gfx_postdraw_tx==~0U)
  return gfx_postdraw_refuse("on-cold-invalid",-EIO);
 if((gfx_postdraw_control&START) ||
    (gfx_postdraw_status!=0x6a && gfx_postdraw_status!=0x6c &&
     !(after_coordinate && gfx_postdraw_status==0x6d)) ||
    !(gfx_postdraw_rx&EMPTY) || (gfx_postdraw_tx&BIT(16)))
  return gfx_postdraw_refuse("on-cold-unqualified",-EBUSY);
 return 0;
}
static int gfx_postdraw_protocol_send(u64 packet,bool hello)
{
 u32 tx;
 if(!gfx_postdraw_active()) return gfx_postdraw_refuse("protocol-send-ownership",-EBUSY);
 tx=readl(mbox+0x110);
 if(tx==~0U || (tx&BIT(16))) return gfx_postdraw_refuse("protocol-send-tx",-EBUSY);
 if(hello) gfx_postdraw_hello_replies++;else gfx_postdraw_map_replies++;
 wmb();writeq(packet,mbox+0x800);writeq(0,mbox+0x808);
 pr_info("m4rch gfx-postdraw-native-cycle-tx: epoch=2 hello=%u packet=%#llx endpoint=0 root_publications=0 application_starts=0 host_on_requests=0 work_replays=0\n",hello,(unsigned long long)packet);
 return 0;
}
static int gfx_postdraw_protocol(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_POSTDRAW_PROTOCOL_TIMEOUT_MS);
 unsigned int i;
 for(i=0;i<GFX_POSTDRAW_PROTOCOL_POLLS;i++) {
  u32 rx;
  if(!time_before(jiffies,until)) return gfx_postdraw_refuse("protocol-deadline",-ETIMEDOUT);
  if(!gfx_postdraw_active()) return gfx_postdraw_refuse("protocol-ownership",-EBUSY);
  gfx_postdraw_protocol_polls++;rx=readl(mbox+0x114);
  if(rx==~0U) return gfx_postdraw_refuse("protocol-rx-invalid",-EIO);
  if(!(rx&EMPTY)) {
   u64 message,metadata;unsigned int type,base;bool last;int ret;
   if(gfx_postdraw_protocol_records>=GFX_POSTDRAW_PROTOCOL_RECORDS)
    return gfx_postdraw_refuse("protocol-record-limit",-EOVERFLOW);
   message=readq(mbox+0x830);metadata=readq(mbox+0x838);
   gfx_postdraw_protocol_journal[gfx_postdraw_protocol_records].message=message;
   gfx_postdraw_protocol_journal[gfx_postdraw_protocol_records].metadata=metadata;
   gfx_postdraw_protocol_records++;
   pr_info("m4rch gfx-postdraw-native-cycle-rx: epoch=2 index=%u message=%#llx metadata=%#llx\n",
    gfx_postdraw_protocol_records,(unsigned long long)message,(unsigned long long)metadata);
   if(!time_before(jiffies,until)) return gfx_postdraw_refuse("protocol-frame-late",-ETIMEDOUT);
   if(message==~0ULL || metadata==~0ULL) return gfx_postdraw_refuse("protocol-frame-invalid",-EIO);
   if(metadata&0xff) return gfx_postdraw_refuse("protocol-endpoint",-EPROTO);
   type=(message>>52)&0xff;
   if(gfx_postdraw_endpoint_map) {
    if(message!=GFX_POSTDRAW_BOOT_RUNNING) return gfx_postdraw_refuse("boot-running-frame",-EPROTO);
    gfx_postdraw_boot_message=message;gfx_postdraw_boot_metadata=metadata;
    gfx_postdraw_boot_running_observed=true;gfx_postdraw_log("boot-running-observed",0);return 0;
   } else if(!gfx_postdraw_hello_replied && type==1) {
    if((message&0xffff)!=12 || ((message>>16)&0xffff)!=12)
     return gfx_postdraw_refuse("hello-version",-EPROTO);
    ret=gfx_postdraw_protocol_send((2ULL<<52)|(12ULL<<16)|12ULL,true);if(ret) return ret;
    gfx_postdraw_hello_replied=true;
   } else if(gfx_postdraw_hello_replied && type==8) {
    base=(message>>32)&0x3f;last=!!(message&(1ULL<<51));
    if(base>1 || (u32)message!=3 ||
       (!gfx_postdraw_map_seen && (base || last)) ||
       (gfx_postdraw_map_seen && (base!=1 || !last)) ||
       (gfx_postdraw_map_seen&BIT(base)))
     return gfx_postdraw_refuse("endpoint-map-shape",-EPROTO);
    ret=gfx_postdraw_protocol_send((8ULL<<52)|((u64)base<<32)|(last?(1ULL<<51):1ULL),false);
    if(ret) return ret;
    gfx_postdraw_map_seen|=BIT(base);
    if(base==1) gfx_postdraw_advertised_appmap=(u32)message;
    if(last) {gfx_postdraw_endpoint_map=true;gfx_postdraw_log("autonomous-map-retained",0);}
   } else return gfx_postdraw_refuse("protocol-message",-EPROTO);
   if(gfx_postdraw_protocol_records>=GFX_POSTDRAW_PROTOCOL_RECORDS)
    return gfx_postdraw_refuse("protocol-record-limit",-EOVERFLOW);
  }
  usleep_range(1000,1100);
 }
 return gfx_postdraw_refuse("protocol-poll-limit",-ETIMEDOUT);
}
static int gfx_postdraw_on(void)
{
 int ret;
 if(!gfx_postdraw_provider_off || !gfx_postdraw_accounting_ok ||
    !gfx_coord_owner_session.off_complete || !gfx_postdraw_identity() ||
    !gfx_postdraw_pm_off() || !gfx_cold_ap_known())
  return gfx_postdraw_refuse("on-off-premise",-EBUSY);
 ret=gfx_postdraw_physical("before-get",0,false);
 if(ret) return gfx_postdraw_refuse("on-fresh-off",ret);
 gfx_cold_current_epoch=2;gfx_postdraw_pm_get_attempted=true;gfx_postdraw_log("on-get-intent",0);
 if(!gfx_postdraw_identity() || !gfx_postdraw_pm_off())
  return gfx_postdraw_refuse("on-get-intent-ownership",-EBUSY);
 gfx_postdraw_pm_get_result=pm_runtime_resume_and_get(&consumer->dev);
 if(gfx_postdraw_pm_get_result<0) return gfx_postdraw_refuse("on-pm-get",gfx_postdraw_pm_get_result);
 held=true;gfx_postdraw_second_ref_held=true;
 if(!gfx_postdraw_pm_active() || !gfx_postdraw_identity())
  return gfx_postdraw_refuse("on-accounting-identity",-EBUSY);
 ret=gfx_postdraw_physical("after-get",0,true);
 if(ret) return gfx_postdraw_refuse("on-fresh-physical",ret);
 /* Separately qualified physical ACTIVE and owned reference restore device
  * access. No device operand was sampled since off-intent until here. */
 gfx_postdraw_device_access=true;gfx_postdraw_log("on-get-return",0);
 ret=gfx_postdraw_cold_boundary(false);if(ret) return ret;
 if(!gfx_coord_owner_pmp || !gfx_coord_owner_pmc || !gfx_coord_owner_pmp_region ||
    !gfx_coord_owner_pmc_region || !gfx_coord_owner_session.off_complete)
  return gfx_postdraw_refuse("on-coordinate-premise",-EBUSY);
 ret=gfx_coord_owner_alias_check();if(ret) return gfx_postdraw_refuse("on-coordinate-alias",ret);
 ret=gfx_coord_transition(&gfx_postdraw_coord_session,&gfx_coord_owner_ops,true,&gfx_postdraw_coord_on);
 gfx_postdraw_log("on-coordinate-return",ret);
 if(ret) return gfx_postdraw_refuse("on-coordinate",ret);
 ret=gfx_postdraw_cold_boundary(true);if(ret) return ret;
 gfx_postdraw_start_attempted=true;gfx_postdraw_log("start-intent",0);
 ret=gfx_postdraw_cold_boundary(true);if(ret) return ret;
 gfx_postdraw_control=readl(asc+0x44);
 if(gfx_postdraw_control==~0U || (gfx_postdraw_control&START))
  return gfx_postdraw_refuse("start-fresh-control",-EBUSY);
 writel(gfx_postdraw_control|START,asc+0x44);
 gfx_postdraw_control=readl(asc+0x44);
 if(gfx_postdraw_control==~0U || !(gfx_postdraw_control&START))
  return gfx_postdraw_refuse("start-readback",-EIO);
 gfx_postdraw_log("start-return",0);ret=gfx_postdraw_protocol();if(ret) return ret;
 if(!gfx_postdraw_active() || !gfx_postdraw_coord_session.on_complete ||
    !gfx_postdraw_hello_replied || !gfx_postdraw_endpoint_map || gfx_postdraw_map_seen!=3 ||
    gfx_postdraw_advertised_appmap!=3 || !gfx_postdraw_boot_running_observed ||
    gfx_postdraw_boot_message!=GFX_POSTDRAW_BOOT_RUNNING ||
    gfx_postdraw_boot_metadata==~0ULL || (gfx_postdraw_boot_metadata&0xff))
  return gfx_postdraw_refuse("management-rejoin-premise",-EBUSY);
 ret=gfx_postdraw_physical("rejoin-final",0,true);
 if(ret) return gfx_postdraw_refuse("management-rejoin-physical",ret);
 gfx_postdraw_control=readl(asc+0x44);gfx_postdraw_status=readl(asc+0x48);
 gfx_postdraw_rx=readl(mbox+0x114);gfx_postdraw_tx=readl(mbox+0x110);
 gfx_postdraw_sample_jiffies=jiffies;
 if(gfx_postdraw_control==~0U || gfx_postdraw_status==~0U ||
    gfx_postdraw_rx==~0U || gfx_postdraw_tx==~0U || !(gfx_postdraw_control&START) ||
    !(gfx_postdraw_rx&EMPTY) || (gfx_postdraw_tx&BIT(16)) || !gfx_postdraw_active())
  return gfx_postdraw_refuse("management-rejoin-final-guard",-EBUSY);
 return 0;
}
static int gfx_postdraw_command(const char *buf,size_t count)
{
 static const char prefix[]="postdraw-native-cycle ";
 size_t n=count;unsigned int i;int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_postdraw_cycle_intent || gfx_postdraw_unknown) return -EALREADY;
 gfx_postdraw_cycle_intent=true;
 if(n && buf[n-1]=='\n') n--;
 if(n!=sizeof(prefix)-1+64 || memcmp(buf,prefix,sizeof(prefix)-1))
  return gfx_postdraw_refuse("capture-token-syntax",-EINVAL);
 for(i=0;i<64;i++) {
  char c=buf[sizeof(prefix)-1+i];
  if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))
   return gfx_postdraw_refuse("capture-token-syntax",-EINVAL);
 }
 memcpy(gfx_postdraw_capture_token,buf+sizeof(prefix)-1,64);gfx_postdraw_capture_token[64]=0;
 gfx_postdraw_log("intent",0);
 if(!gfx_postdraw_draw_qualified()) return gfx_postdraw_refuse("captured-draw-premise",-EBUSY);
 gfx_postdraw_device_access=true;
 ret=gfx_postdraw_physical("admission-before",0,true);
 if(ret) return gfx_postdraw_refuse("admission-physical",ret);
 /* Re-enable only synchronous transport consumption under this lock. Never
  * create a worker, replay a publication, reset a cursor or touch old captures. */
 receive_enabled=true;gfx_native_powergate_intent=true;
 ret=gfx_native_powergate_admission_drain();
 if(ret) return gfx_postdraw_refuse("admission-drain",ret);
 gfx_postdraw_log("admission-ready",0);
 if(!gfx_postdraw_active()) return gfx_postdraw_refuse("pre202-ownership",-EBUSY);
 ret=gfx_native_powergate_ack();gfx_postdraw_log("handshake-return",ret);
 if(ret==-ETIMEDOUT && gfx_postdraw_nmi_timeout_clean) {
  ret=gfx_postdraw_nmi();gfx_postdraw_log("nmi-return",ret);
  if(ret) return gfx_postdraw_refuse("native-nmi",ret);
 } else if(ret) return gfx_postdraw_refuse("native202-ack",ret);
 if(!gfx_postdraw_active()) return gfx_postdraw_refuse("pre-stop-ownership",-EBUSY);
 ret=gfx_native_powergate_stop_cpu();gfx_postdraw_log("cpu-stop-return",ret);
 if(ret) return gfx_postdraw_refuse("native-cpu-stop",ret);
 ret=gfx_postdraw_off();if(!ret) ret=gfx_postdraw_on();
 receive_enabled=false;
 if(!ret) {gfx_postdraw_complete=true;gfx_postdraw_terminal_result=0;}
 gfx_postdraw_log("retained-final",ret);return ret;
}
static int gfx_postdraw_diagnostic(const char *command)
{
 if(!sysfs_streq(command,"sample") && !sysfs_streq(command,"gfx-snapshot")) return -EPERM;
 gfx_postdraw_log("diagnostic-cached",gfx_postdraw_terminal_result);return 0;
}
