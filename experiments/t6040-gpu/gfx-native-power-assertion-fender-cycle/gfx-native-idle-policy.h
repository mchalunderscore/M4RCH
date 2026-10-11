/* SPDX-License-Identifier: GPL-2.0-only */
/* One native-shaped idle-policy transfer, after the host seals the draw.
 * Opcode0a(bool1) permits idle policy; it is not direct OFF or cancellation.
 * Caller bool/order are hypotheses. Processing and firmware-off observations
 * remain independent of ASC ACK, physical OFF and work retirement.
 */
#ifndef GFX_NATIVE_POWER_ASSERTION_FENDER_CYCLE_TRIAL
#error Distinct native idle-policy cycle profile required
#endif
#define GFX_IDLE_POLICY_TIMEOUT_MS 2000U
#define GFX_IDLE_POLICY_POLLS 2001U
#define GFX_IDLE_POLICY_MESSAGES 256U
#define GFX_IDLE_POLICY_RECORD (0xb8000U+33U*64U)
#define GFX_IDLE_POLICY_COUNTER (RECOVERY_STATUS+0xe438U)
#define GFX_IDLE_POLICY_STATUS RECOVERY_TRACE_MASK
#define GFX_IDLE_POLICY_ASSERTION (0xc000U+0xe51U)
#define GFX_IDLE_POLICY_REGION_C (0xc000U)
#define GFX_IDLE_POLICY_ARENA_BASE 0xfffffc2000100000ULL
#define GFX_IDLE_POLICY_PACKET 0x0084000000000000ULL
static bool gfx_idle_policy_intent,gfx_idle_policy_complete,gfx_idle_policy_unknown;
static bool gfx_idle_policy_assertion_attempted,gfx_idle_policy_assertion_cleaned;
static bool gfx_idle_policy_assertion_verified;
static u32 gfx_idle_policy_assertion_before,gfx_idle_policy_assertion_requested,gfx_idle_policy_assertion;
static bool gfx_idle_policy_record_attempted,gfx_idle_policy_record_cleaned;
static bool gfx_idle_policy_record_verified,gfx_idle_policy_producer_attempted;
static bool gfx_idle_policy_producer_verified,gfx_idle_policy_notify_attempted;
static bool gfx_idle_policy_notify_sent,gfx_idle_policy_continue_teardown;
static bool gfx_idle_policy_command_processed,gfx_idle_policy_processing_timeout;
static bool gfx_idle_policy_gpu_off_observed,gfx_idle_policy_gpu_off_timeout;
static u32 gfx_idle_policy_control_before[3],gfx_idle_policy_control[3];
static u32 gfx_idle_policy_status_before[4],gfx_idle_policy_status[4];
static u32 gfx_idle_policy_counter_before,gfx_idle_policy_counter;
static u32 gfx_idle_policy_control44,gfx_idle_policy_status48,gfx_idle_policy_rx,gfx_idle_policy_tx;
static unsigned int gfx_idle_policy_processing_polls,gfx_idle_policy_off_polls;
static unsigned int gfx_idle_policy_messages;
static unsigned int gfx_idle_policy_processing_elapsed_ms,gfx_idle_policy_off_elapsed_ms;
static int gfx_idle_policy_processing_result=-EINPROGRESS,gfx_idle_policy_off_result=-EINPROGRESS;

static bool gfx_idle_policy_owned(void)
{
 return gfx_postdraw_cycle_intent && !gfx_postdraw_unknown && gfx_postdraw_active() &&
  !gfx_postdraw_off_attempted && !gfx_postdraw_pm_put_attempted && !gfx_postdraw_control_sealed &&
  gfx_native_powergate_intent && gfx_native_powergate_admission_complete &&
  !gfx_native_powergate_request_attempted && !gfx_postdraw_nmi_attempted &&
  !gfx_native_powergate_clear10_attempted && !gfx_native_powergate_clear20_attempted &&
  !gfx_native_powergate_cpu_stopped && receive_enabled && !receive_crashed &&
  !receive_journal.status && receive_journal.used<RECEIVE_CAPACITY &&
  gfx_cold_pipeline_intent && gfx_cold_complete && gfx_cold_sealed &&
  gfx_cold_software_stopped && !gfx_cold_running && !gfx_cold_terminal_result &&
  gfx_cold_draw_intent && gfx_cold_draw_notify_sent && recovery_work_submitted &&
  gfx_native_fender_enable_complete && !gfx_native_fender_enable_unknown &&
  !gfx_native_fender_disable_intent && gfx_gravity_preasc_complete &&
  !gfx_gravity_preasc_unknown && gfx_gravity_preasc_region[0] && gfx_gravity_preasc_region[1] &&
  gfx_gravity_preasc_io[0] && gfx_gravity_preasc_io[1] &&
  gfx_native_fender_enable_map==gfx_gravity_preasc_io[1] &&
  consumer==gfx_gravity_preasc_consumer && asc==gfx_gravity_preasc_asc &&
  mbox==gfx_gravity_preasc_mbox;
}

/* Native field is packed and unaligned. Cache maintenance is inherited;
 * memcpy avoids an undefined aligned u32 access in the Linux C producer. */
static u32 gfx_idle_policy_assertion_read(void)
{
 u32 value;void *p=recovery_ptr(GFX_IDLE_POLICY_ASSERTION);
 recovery_invalidate(p,sizeof(value));memcpy(&value,p,sizeof(value));return value;
}

static void gfx_idle_policy_log(const char *phase,const char *condition,int result)
{
 pr_info("m4rch gfx-native-idle-policy: phase=%s result=%d refused_condition=%s intent=%u complete=%u unknown=%u continue_teardown=%u processing_result=%d firmware_off_result=%d retained=1 transfer_hypothesis=1 retirement_verified=0\n",
  phase,result,condition,gfx_idle_policy_intent,gfx_idle_policy_complete,gfx_idle_policy_unknown,
  gfx_idle_policy_continue_teardown,gfx_idle_policy_processing_result,gfx_idle_policy_off_result);
 pr_info("m4rch gfx-native-idle-policy-state: phase=%s record_attempted=%u record_cleaned=%u record_verified=%u producer_attempted=%u producer_verified=%u notify_attempted=%u notify_sent=%u policy_command_processed=%u policy_processing_timeout=%u firmware_gpu_off_observed=%u firmware_gpu_off_timeout=%u processing_polls=%u off_polls=%u messages=%u\n",
  phase,gfx_idle_policy_record_attempted,gfx_idle_policy_record_cleaned,gfx_idle_policy_record_verified,
  gfx_idle_policy_producer_attempted,gfx_idle_policy_producer_verified,gfx_idle_policy_notify_attempted,
  gfx_idle_policy_notify_sent,gfx_idle_policy_command_processed,gfx_idle_policy_processing_timeout,
  gfx_idle_policy_gpu_off_observed,gfx_idle_policy_gpu_off_timeout,gfx_idle_policy_processing_polls,
  gfx_idle_policy_off_polls,gfx_idle_policy_messages);
 pr_info("m4rch gfx-native-idle-policy-bounds: phase=%s processing_elapsed_ms=%u off_elapsed_ms=%u timeout_ms=%u poll_limit=%u\n",
  phase,gfx_idle_policy_processing_elapsed_ms,gfx_idle_policy_off_elapsed_ms,
  GFX_IDLE_POLICY_TIMEOUT_MS,GFX_IDLE_POLICY_POLLS);
 pr_info("m4rch gfx-native-idle-policy-control: phase=%s before=%u/%u/%u current=%u/%u/%u counter_before=%u counter_current=%u counter_delta=%u counter_offset=0xe438 cached=1 operand_samples_atomic=0\n",
  phase,gfx_idle_policy_control_before[0],gfx_idle_policy_control_before[1],gfx_idle_policy_control_before[2],
  gfx_idle_policy_control[0],gfx_idle_policy_control[1],gfx_idle_policy_control[2],
  gfx_idle_policy_counter_before,gfx_idle_policy_counter,gfx_idle_policy_counter-gfx_idle_policy_counter_before);
 pr_info("m4rch gfx-native-idle-policy-power: phase=%s before=%u/%u/%u/%u current=%u/%u/%u/%u offsets=0x10/0x14/0x18/0x1c cached=1 native_off_expected=0 operand_samples_atomic=0\n",
  phase,gfx_idle_policy_status_before[0],gfx_idle_policy_status_before[1],gfx_idle_policy_status_before[2],gfx_idle_policy_status_before[3],
  gfx_idle_policy_status[0],gfx_idle_policy_status[1],gfx_idle_policy_status[2],gfx_idle_policy_status[3]);
 pr_info("m4rch gfx-native-idle-policy-application: phase=%s counter=%llu recovery_phase=%u host_stop=%u request_state=%u request_flag=%u trace=%u control44=%#x status48=%#x rx_status=%#x tx_status=%#x cached=1 operand_samples_atomic=0\n",
  phase,(unsigned long long)gfx_cold_counter,gfx_cold_phase,gfx_cold_host_stop,
  gfx_cold_request_state,gfx_cold_request_flag,gfx_cold_trace_after,gfx_idle_policy_control44,
  gfx_idle_policy_status48,gfx_idle_policy_rx,gfx_idle_policy_tx);
 pr_info("m4rch gfx-native-power-assertion: phase=%s root_offset=0x20 region_c_va=%#llx arena_offset=%#x field_offset=0xe51 bytes=4 unaligned=1 before=%u requested=%u current=%u consumed_baseline=%u consumed_current=%u attempted=%u cleaned=%u verified=%u dmbish=1 native_wrap_u32=1 near_wrap_supported=0 operand_samples_atomic=0\n",
  phase,(unsigned long long)(GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_REGION_C),
  GFX_IDLE_POLICY_ASSERTION,gfx_idle_policy_assertion_before,gfx_idle_policy_assertion_requested,
  gfx_idle_policy_assertion,gfx_idle_policy_counter_before,gfx_idle_policy_counter,
  gfx_idle_policy_assertion_attempted,gfx_idle_policy_assertion_cleaned,gfx_idle_policy_assertion_verified);
}

static bool gfx_idle_policy_pointers(void)
{
 return recovery_read64(0x20)==GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_REGION_C &&
  recovery_read64(0xa8)==GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_STATUS &&
  recovery_read64(0xb0)==GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_STATUS &&
  recovery_read64(0x4000U+0x1a0U)==GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_CONTROL &&
  recovery_read64(0x4000U+0x1a8U)==GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_CONTROL+8U &&
  recovery_read64(0x4000U+0x1b0U)==GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_CONTROL+16U &&
  recovery_read64(0x4000U+0x1b8U)==GFX_IDLE_POLICY_ARENA_BASE+0xb8000U;
}

/* Only the existing trace notification is serviced. Never infer ACK from it. */
static int gfx_idle_policy_transport(void)
{
 u64 message,metadata;
 if(!gfx_idle_policy_owned()) return -EBUSY;
 gfx_idle_policy_control44=readl(asc+0x44);gfx_idle_policy_status48=readl(asc+0x48);
 gfx_idle_policy_rx=readl(mbox+0x114);gfx_idle_policy_tx=readl(mbox+0x110);
 if(gfx_idle_policy_control44==~0U || gfx_idle_policy_status48==~0U ||
    gfx_idle_policy_rx==~0U || gfx_idle_policy_tx==~0U || !(gfx_idle_policy_control44&START)) return -EIO;
 if(!(gfx_idle_policy_rx&EMPTY)) {
  if(gfx_idle_policy_messages>=GFX_IDLE_POLICY_MESSAGES) return -EOVERFLOW;
  message=readq(mbox+0x830);metadata=readq(mbox+0x838);
  gfx_idle_policy_messages++;
  pr_info("m4rch gfx-native-idle-policy-rx: index=%u message=%#llx metadata=%#llx control44=%#x status48=%#x rx_status=%#x tx_status=%#x\n",
   gfx_idle_policy_messages,(unsigned long long)message,(unsigned long long)metadata,
   gfx_idle_policy_control44,gfx_idle_policy_status48,gfx_idle_policy_rx,gfx_idle_policy_tx);
  if(message!=0x0042000000000000ULL || metadata==~0ULL || (metadata&0xff)!=32) {
   if((metadata&0xff)==1) receive_crashed=true;
   return -EPROTO;
  }
  if(!receive_mailbox(message,metadata) || !gfx_idle_policy_owned()) return -EIO;
 }
 return gfx_idle_policy_owned()?0:-EBUSY;
}

static int gfx_idle_policy_sample(bool published)
{
 unsigned int i;int ret;
 if(!gfx_idle_policy_owned()) return -EBUSY;
 if(!gfx_idle_policy_pointers()) return -EFAULT;
 ret=gfx_idle_policy_transport();if(ret) return ret;
 gfx_cold_read_application();
 memcpy(gfx_idle_policy_control,gfx_cold_control,sizeof(gfx_idle_policy_control));
 /* Read counter after the read cursor: firmware increments it before read. */
 gfx_idle_policy_counter=recovery_read32(GFX_IDLE_POLICY_COUNTER);
 gfx_idle_policy_assertion=gfx_idle_policy_assertion_read();
 for(i=0;i<4;i++) gfx_idle_policy_status[i]=recovery_read32(GFX_IDLE_POLICY_STATUS+0x10U+i*4U);
 if(!gfx_idle_policy_owned()) return -EBUSY;
 if(gfx_cold_counter || gfx_cold_phase || gfx_cold_host_stop || gfx_cold_request_state ||
    gfx_cold_request_flag || gfx_cold_trace_after!=3) return -EBUSY;
 for(i=0;i<4;i++) if(gfx_idle_policy_status[i]==~0U) return -ENODATA;
 if(gfx_idle_policy_counter==~0U) return -ENODATA;
 if(!gfx_idle_policy_assertion_attempted) {
  /* Current trial retains old invalid-word rules; native wrap is understood
   * but UINT_MAX/UINT_MAX-1 baselines are unsupported before any store. */
  if(gfx_idle_policy_assertion>=~0U-1U ||
     gfx_idle_policy_assertion!=gfx_idle_policy_counter) return -EPROTO;
 } else if(gfx_idle_policy_assertion!=gfx_idle_policy_assertion_requested) return -EPROTO;
 if(!published) return gfx_idle_policy_control[0]==33 && gfx_idle_policy_control[1]==33 &&
  gfx_idle_policy_control[2]==33?0:-EPROTO;
 if(gfx_idle_policy_control[0]<33 || gfx_idle_policy_control[0]>34 ||
    gfx_idle_policy_control[1]<gfx_idle_policy_control[0] || gfx_idle_policy_control[1]>34 ||
    gfx_idle_policy_control[2]!=34 || gfx_idle_policy_counter<gfx_idle_policy_counter_before ||
    gfx_idle_policy_counter-gfx_idle_policy_counter_before>1 ||
    (gfx_idle_policy_control[0]==34 && gfx_idle_policy_counter-gfx_idle_policy_counter_before!=1)) return -EPROTO;
 return 0;
}

static bool gfx_idle_policy_record_matches(const u8 expected[64])
{
 u8 *p=recovery_ptr(GFX_IDLE_POLICY_RECORD);unsigned int i;
 recovery_invalidate(p,64);
 for(i=0;i<64;i++) if(READ_ONCE(p[i])!=expected[i]) return false;
 return true;
}

/* Include after retained postdraw/Fender/runtime helpers; graph_io_lock held. */
static int gfx_native_idle_policy_before_202(void)
{
 static const u8 staged[64]={0x16};
 static const u8 command[64]={0x0a,0,0,0,1};
 struct apple_pmgr_gfx_reset_observation physical={0};
 unsigned long until,start;unsigned int i;int ret;const char *condition="none";
 lockdep_assert_held(&graph_io_lock);
 if(gfx_idle_policy_intent) {gfx_idle_policy_log("refused","one-shot",-EALREADY);return -EALREADY;}
 gfx_idle_policy_intent=true;gfx_idle_policy_log("intent","none",0);
 if(!gfx_idle_policy_owned()) {ret=-EBUSY;condition="ownership-before-policy";goto refused;}
 ret=gfx_cold_snapshot("idle-policy-before",0,&physical);
 if(ret) {ret=ret>0?-EIO:ret;condition="physical-snapshot";goto refused;}
 if(!gfx_native_runtime_active("idle-policy-before",physical.valid,physical.domain_on,physical.before)) {
  ret=-EBUSY;condition="physical-on";goto refused;
 }
 ret=gfx_idle_policy_sample(false);if(ret) {condition="baseline-operands";goto refused;}
 if(!gfx_idle_policy_record_matches(staged)) {ret=-EBUSY;condition="unpublished-slot-baseline";goto refused;}
 memcpy(gfx_idle_policy_control_before,gfx_idle_policy_control,sizeof(gfx_idle_policy_control_before));
 memcpy(gfx_idle_policy_status_before,gfx_idle_policy_status,sizeof(gfx_idle_policy_status_before));
 gfx_idle_policy_counter_before=gfx_idle_policy_counter;
 gfx_idle_policy_assertion_before=gfx_idle_policy_assertion;
 gfx_idle_policy_assertion_requested=gfx_idle_policy_assertion_before+1U;
 gfx_idle_policy_log("baseline","none",0);
 ret=gfx_idle_policy_sample(false);if(ret) {condition="before-record-operands";goto refused;}
 if(gfx_idle_policy_counter!=gfx_idle_policy_counter_before || !gfx_idle_policy_record_matches(staged)) {
  ret=-EPROTO;condition="before-record-changed";goto refused;
 }
 gfx_idle_policy_record_attempted=true;
 memcpy(recovery_ptr(GFX_IDLE_POLICY_RECORD),command,64);
 recovery_clean(recovery_ptr(GFX_IDLE_POLICY_RECORD),64);gfx_idle_policy_record_cleaned=true;
 gfx_idle_policy_record_verified=gfx_idle_policy_record_matches(command);
 pr_info("m4rch gfx-native-idle-policy-record: slot=33 offset=%#x bytes=64 before_opcode=22 opcode=10 bool=1 bool_width=32 tail_zero=1 attempted=1 cleaned=%u verified=%u\n",
  GFX_IDLE_POLICY_RECORD,gfx_idle_policy_record_cleaned,gfx_idle_policy_record_verified);
 if(!gfx_idle_policy_record_verified) {ret=-EIO;condition="record-readback";goto refused;}
 ret=gfx_idle_policy_sample(false);if(ret) {condition="preproducer-operands";goto refused;}
 if(gfx_idle_policy_counter!=gfx_idle_policy_counter_before || !gfx_idle_policy_record_matches(command)) {
  ret=-EPROTO;condition="preproducer-changed";goto refused;
 }
 /* Native 89a6a70..89a6b10: copy64, class1 assertion, DMBISH,
  * producer. This new step never repairs or replays an ambiguous attempt. */
 gfx_idle_policy_assertion_attempted=true;
 memcpy(recovery_ptr(GFX_IDLE_POLICY_ASSERTION),&gfx_idle_policy_assertion_requested,sizeof(u32));
 /* recovery_clean supplies DMBISH before DC CVAC and DSB SY afterward. */
 recovery_clean(recovery_ptr(GFX_IDLE_POLICY_ASSERTION),sizeof(u32));
 gfx_idle_policy_assertion_cleaned=true;
 gfx_idle_policy_assertion=gfx_idle_policy_assertion_read();
 gfx_idle_policy_assertion_verified=gfx_idle_policy_assertion==gfx_idle_policy_assertion_requested;
 gfx_idle_policy_log("assertion-published","none",0);
 if(!gfx_idle_policy_assertion_verified) {ret=-EIO;condition="assertion-readback";goto refused;}
 ret=gfx_idle_policy_sample(false);if(ret) {condition="postassertion-operands";goto refused;}
 if(gfx_idle_policy_counter!=gfx_idle_policy_counter_before || !gfx_idle_policy_record_matches(command)) {
  ret=-EPROTO;condition="postassertion-changed";goto refused;
 }
 gfx_idle_policy_producer_attempted=true;recovery_write32(RECOVERY_CONTROL+16,34);
 gfx_idle_policy_producer_verified=recovery_read32(RECOVERY_CONTROL+16)==34;
 pr_info("m4rch gfx-native-idle-policy-producer: before=33 requested=34 attempted=1 verified=%u record_cleaned=%u\n",
  gfx_idle_policy_producer_verified,gfx_idle_policy_record_cleaned);
 if(!gfx_idle_policy_producer_verified) {ret=-EIO;condition="producer-readback";goto refused;}
 ret=gfx_idle_policy_sample(true);if(ret) {condition="prenotify-operands";goto refused;}
 if(gfx_idle_policy_tx&BIT(16)) {ret=-EBUSY;condition="tx-full-prenotify";goto refused;}
 if(!gfx_idle_policy_owned()) {ret=-EBUSY;condition="prenotify-ownership";goto refused;}
 gfx_idle_policy_notify_attempted=true;
 pr_info("m4rch gfx-native-idle-policy-tx: endpoint=33 packet=%#llx attempted=1 sent=0 producer=34\n",
  (unsigned long long)GFX_IDLE_POLICY_PACKET);
 wmb();writeq(GFX_IDLE_POLICY_PACKET,mbox+0x800);writeq(33,mbox+0x808);
 gfx_idle_policy_notify_sent=true;
 pr_info("m4rch gfx-native-idle-policy-tx: endpoint=33 packet=%#llx attempted=1 sent=1 producer=34\n",
  (unsigned long long)GFX_IDLE_POLICY_PACKET);
 start=jiffies;until=start+msecs_to_jiffies(GFX_IDLE_POLICY_TIMEOUT_MS);
 for(i=0;i<GFX_IDLE_POLICY_POLLS;i++) {
  ret=gfx_idle_policy_sample(true);gfx_idle_policy_processing_polls++;
  gfx_idle_policy_processing_elapsed_ms=jiffies_to_msecs(jiffies-start);
  if(ret) {condition="processing-operands";goto refused;}
  if(gfx_idle_policy_control[0]==34 && gfx_idle_policy_control[1]==34 &&
     gfx_idle_policy_counter-gfx_idle_policy_counter_before==1) {
   gfx_idle_policy_command_processed=true;gfx_idle_policy_processing_result=0;break;
  }
  if(!time_before(jiffies,until) || i+1==GFX_IDLE_POLICY_POLLS) {
   gfx_idle_policy_processing_timeout=true;gfx_idle_policy_processing_result=-ETIMEDOUT;break;
  }
  usleep_range(1000,2000);
 }
 gfx_idle_policy_log("processing-observed","none",0);
 start=jiffies;until=start+msecs_to_jiffies(GFX_IDLE_POLICY_TIMEOUT_MS);
 for(i=0;i<GFX_IDLE_POLICY_POLLS;i++) {
  ret=gfx_idle_policy_sample(true);gfx_idle_policy_off_polls++;
  gfx_idle_policy_off_elapsed_ms=jiffies_to_msecs(jiffies-start);
  if(ret) {condition="firmware-off-operands";goto refused;}
  if(!gfx_idle_policy_status[0]) {gfx_idle_policy_gpu_off_observed=true;gfx_idle_policy_off_result=0;break;}
  if(!time_before(jiffies,until) || i+1==GFX_IDLE_POLICY_POLLS) {
   gfx_idle_policy_gpu_off_timeout=true;gfx_idle_policy_off_result=-ETIMEDOUT;break;
  }
  usleep_range(1000,2000);
 }
 gfx_idle_policy_log("firmware-off-observed","none",0);
 /* A late processing result remains separate from the bounded first wait. */
 ret=gfx_idle_policy_sample(true);if(ret) {condition="pre202-operands";goto refused;}
 if(!gfx_idle_policy_record_matches(command)) {ret=-EIO;condition="terminal-record";goto refused;}
 gfx_idle_policy_complete=true;gfx_idle_policy_continue_teardown=true;
 gfx_idle_policy_log("complete","none",0);return 0;
refused:
 gfx_idle_policy_unknown=true;gfx_idle_policy_continue_teardown=false;
 gfx_idle_policy_log("refused",condition,ret);return ret;
}
