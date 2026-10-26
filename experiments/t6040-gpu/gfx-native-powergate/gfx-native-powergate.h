/* SPDX-License-Identifier: GPL-2.0-only */
/* One retained, no-work native PWRGATE observation. The matched RTBuddy
 * request is EP0 202; its ACK handler converts type7/low8=1 or2 to host
 * IOP status2. Either qualified ACK follows this owner's sole202 request.
 * ACK, CPU stop and provider OFF remain separate observations. */
#if !defined(GFX_NATIVE_POWERGATE_TRIAL) || !defined(GFX_NATIVE_STATUS_ZERO_TRIAL)
#error Native PWRGATE requires its distinct STATUS0 retained owner
#endif
#ifdef GFX_COORDINATED_EXECUTION_TRIAL
#error Native PWRGATE is a no-work profile
#endif

#define GFX_NATIVE_POWERGATE_REQUEST 0x0060000000000202ULL
#define GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS 2000U
#define GFX_NATIVE_POWERGATE_ACK_POLLS 2001U
#define GFX_NATIVE_POWERGATE_RX_MESSAGES 64U
#define GFX_NATIVE_POWERGATE_IDLE_POLLS 11U
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

static void gfx_native_powergate_log(const char *phase,int result)
{
 pr_info("m4rch gfx-native-powergate: phase=%s result=%d intent=%u initial_recovery_failed=%u initial_completed_cycles=%u request_attempted=%u request=%#llx ack_observed=%u ack_message=%#llx ack_metadata=%#llx ack_polls=%u rx_messages=%u rx_empty_after_ack=%u rx_empty_before_cpu=%u idle_observed=%u idle_polls=%u idle_status=%#x clear10_attempted=%u control_before=%#x control_after10=%#x clear20_attempted=%u control_after20=%#x cpu_stopped=%u off_delegated=%u held=%u allocations_retained=%u restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,gfx_native_powergate_intent,gfx_native_powergate_initial_recovery_failed,
  recovery_completed_total,gfx_native_powergate_request_attempted,
  (unsigned long long)GFX_NATIVE_POWERGATE_REQUEST,gfx_native_powergate_ack_observed,
  (unsigned long long)gfx_native_powergate_ack_message,
  (unsigned long long)gfx_native_powergate_ack_metadata,gfx_native_powergate_ack_polls,
  gfx_native_powergate_rx_messages,gfx_native_powergate_rx_empty_after_ack,
  gfx_native_powergate_rx_empty_before_cpu,gfx_native_powergate_idle_observed,
  gfx_native_powergate_idle_polls,gfx_native_powergate_idle_status,
  gfx_native_powergate_clear10_attempted,gfx_native_powergate_control_before,
  gfx_native_powergate_control_after10,gfx_native_powergate_clear20_attempted,
  gfx_native_powergate_control_after20,gfx_native_powergate_cpu_stopped,
  gfx_native_powergate_off_delegated,held,GFX_RESET_SCOPE_PAGES);
}

/* Application recovery phase2 does not imply that the separate management
 * endpoint can or cannot respond. This profile tests that boundary once in
 * the initial diagnostic or healthy state, with no application work published. */
static int gfx_native_powergate_preconditions(void)
{
 u32 control,phase,rx;
 if(gfx_native_powergate_startup_unknown || !gfx_reset_scope_backing() ||
    !receive_enabled || receive_crashed || receive_journal.status ||
    receive_journal.used>=RECEIVE_CAPACITY || recovery_work_submitted ||
    recovery_completed_total>2 || gfx_poweroff_gate_consumed ||
    gfx_reset_scope_host_stopped || gfx_poweroff_start_clear_attempted ||
    atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error)) return -EBUSY;
 if(!recovery_idle() || recovery_read32(RECOVERY_REQUEST)) return -EBUSY;
 phase=recovery_read32(RECOVERY_STATUS+0x4900);
 if(phase==2) {
  if(!gfx_native_powergate_initial_recovery_failed || recovery_completed_total>=2 ||
     recovery_read64(RECOVERY_STATUS+0x48f0)!=recovery_completed_total+1 ||
     recovery_read32(RECOVERY_STATUS+0x4910)!=1 ||
     recovery_read32(RECOVERY_REQUEST+4)!=1) return -EBUSY;
 } else if(phase==0) {
  if(gfx_native_powergate_initial_recovery_failed || recovery_completed_total!=2 ||
     recovery_read64(RECOVERY_STATUS+0x48f0)!=2 ||
     recovery_read32(RECOVERY_REQUEST+4)) return -EBUSY;
 } else return -EBUSY;
 control=recovery_read32(RECOVERY_CONTROL+16);
 if(control<RECOVERY_CONTROL_INITIAL+recovery_completed_total ||
    control>RECOVERY_CONTROL_LAST ||
    recovery_read32(RECOVERY_CONTROL)!=control ||
    recovery_read32(RECOVERY_CONTROL+8)!=control) return -EBUSY;
 gfx_native_powergate_control_before=readl(asc+0x44);
 if(!(gfx_native_powergate_control_before&START) ||
    gfx_native_powergate_control_before==~0U || readl(asc+0x48)==~0U)
  return -EBUSY;
 /* Empty RX before our request excludes an already pending management ACK.
  * No packet or shared-ring drain occurs on this admission path. */
 rx=readl(mbox+0x114);
 if(rx==~0U || !(rx&EMPTY) || (readl(mbox+0x110)&BIT(16))) return -EBUSY;
 return 0;
}

static int gfx_native_powergate_ack(void)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_NATIVE_POWERGATE_ACK_TIMEOUT_MS);
 unsigned int i;
 /* Intent is already durable in the owner. Mark this sole publication before
  * writing either transport word; there is no retransmission on any result. */
 gfx_native_powergate_request_attempted=true;
 wmb();writeq(GFX_NATIVE_POWERGATE_REQUEST,mbox+0x800);writeq(0,mbox+0x808);
 gfx_native_powergate_log("request-published",0);
 for(i=0;i<GFX_NATIVE_POWERGATE_ACK_POLLS;i++) {
  u64 message,metadata;
  if(!time_before(jiffies,until)) return -ETIMEDOUT;
  gfx_native_powergate_ack_polls++;
  if(!(readl(mbox+0x114)&EMPTY)) {
   message=readq(mbox+0x830);metadata=readq(mbox+0x838);
   gfx_native_powergate_rx_messages++;
   /* Preserve every removed frame, including invalid/unhandled frames. */
   pr_info("m4rch gfx-native-powergate-rx: index=%u message=%#llx metadata=%#llx\n",
    gfx_native_powergate_rx_messages,(unsigned long long)message,
    (unsigned long long)metadata);
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
 return -ETIMEDOUT;
}

static int gfx_native_powergate_stop_cpu(void)
{
 unsigned int i;
 u32 control,rx;
 /* Matched generic V6 tests either STATUS48 low bit before CPU-stop writes.
  * Optional CTRL40 idle gating is absent from the actual saved GFX ADT. */
 for(i=0;i<GFX_NATIVE_POWERGATE_IDLE_POLLS;i++) {
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

static int gfx_native_powergate_attempt(void)
{
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_native_powergate_intent) return gfx_reset_scope_result("gfx-powergate",-EALREADY);
 /* Seal and consume before reads or writes. Worker also takes this mutex;
  * nonblocking cancellation is sufficient because it observes this seal.
  * Never call cancel_delayed_work_sync while holding graph_io_lock. */
 gfx_native_powergate_initial_recovery_failed=recovery_session_failed;
 gfx_native_powergate_intent=true;gfx_reset_scope_sealed=true;
 recovery_session_failed=true;cancel_delayed_work(&recovery_receive_work);
 gfx_native_powergate_log("intent",0);
 ret=gfx_native_powergate_preconditions();
 if(!ret) ret=gfx_native_powergate_ack();
 gfx_native_powergate_log("handshake-return",ret);
 if(!ret) ret=gfx_native_powergate_stop_cpu();
 gfx_native_powergate_log("cpu-stop-return",ret);
 if(ret) return gfx_reset_scope_result("gfx-powergate",ret);
 /* Native firmware-unmap/mapper-inactive effects do not establish joined
  * backing retirement. Retain all174 pages/context/maps; test only the
  * qualified handshake, CPU control, paired coordination and provider OFF. */
 gfx_native_powergate_off_delegated=true;
 ret=gfx_poweroff_attempt();
 gfx_native_powergate_log("paired-off-return",ret);
 return ret;
}

static int gfx_native_powergate_command(const char *buf)
{
 if(gfx_native_powergate_startup_unknown) return -EPERM;
 if(sysfs_streq(buf,"sample")) return gfx_poweroff_sample();
 if(sysfs_streq(buf,"gfx-snapshot")) return gfx_reset_scope_snapshot();
 if(sysfs_streq(buf,"gfx-powergate")) return gfx_native_powergate_attempt();
 return -EPERM;
}

/* Every failure after native ON/START retains its exact existing resources.
 * No old AP/SLEEP201 exchange, stale CPU write, OFF, unmap or cleanup follows.
 * This marker does not establish a resident-management admission boundary. */
static int gfx_native_powergate_startup_retained(const char *phase,int result)
{
 unsigned int i,pages=0;
 mutex_lock(&graph_io_lock);
 gfx_native_powergate_startup_unknown=true;gfx_reset_scope_sealed=true;
 recovery_session_failed=true;cancel_delayed_work(&recovery_receive_work);
 gfx_coord_owner_pin();
 for(i=0;i<ARRAY_SIZE(owned);i++) pages+=owned[i]!=NULL;
 pr_info("m4rch gfx-native-powergate-startup-retained: phase=%s result=%d unknown=1 commands_allowed=0 started=%u root_published=%u context_retained=%u held=%u pages_present=%u pages_expected=%u allocations_released=0 restart_allowed=0 dma_retirement_verified=0\n",
  phase,result,started,root_sent,device_context_retained,held,pages,GFX_RESET_SCOPE_PAGES);
 mutex_unlock(&graph_io_lock);
 return 0;
}
