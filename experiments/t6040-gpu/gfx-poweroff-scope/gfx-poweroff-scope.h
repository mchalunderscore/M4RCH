/* SPDX-License-Identifier: GPL-2.0-only */
/* Distinct retained no-work owner: consume one normal GFX PM reference.
 * Copy as gfx-reset-scope.h only in the new prepared candidate. No reset API,
 * warm restart, mapping retirement or backing release is admitted here.
 */
#include <linux/soc/apple/pmgr-gfx-reset.h>
#if !defined(GFX_RESET_SCOPE_TRIAL) || !defined(GFX_POWER_OFF_SCOPE_TRIAL)
#error GFX power-off scope requires its distinct retained feature profile
#endif
#ifdef GFX_RESET_NATIVE_SEQUENCE_TRIAL
#error GFX power-off scope cannot include the native reset command profile
#endif

#define GFX_RESET_SCOPE_PAGES 174U
#define GFX_POWER_OFF_STATE_MASK 0x90001cffU
#define GFX_POWER_OFF_POLL_SAMPLES 101U
#define GFX_POWER_OFF_POLL_DELAY_US 1000U
/* Compatibility with the existing cold owner's lifetime pin and startup. */
static bool gfx_reset_scope_owner_pinned, gfx_reset_scope_attempted;
static bool gfx_reset_scope_sealed, gfx_reset_scope_host_stopped;
static bool gfx_poweroff_gate_consumed, gfx_poweroff_pm_attempted;
static bool gfx_poweroff_provider_off_observed, gfx_poweroff_accounting_ok;
static bool gfx_poweroff_start_clear_attempted;
static unsigned int gfx_poweroff_snapshot_count, gfx_poweroff_poll_delay_us;
static int gfx_poweroff_pm_result, gfx_poweroff_snapshot_result;

/* Retention remains valid after the sole PM reference has been consumed.
 * Pointer presence is metadata; this predicate never dereferences MMIO.
 */
static bool gfx_poweroff_retained(void)
{
 unsigned int i;
 if (!gfx_reset_scope_owner_pinned || !recovery_resident || !resident_session ||
     !consumer || !asc || !mbox || !asc_region || !mbox_region ||
     !root_sent || !installed || root_detached || !device_context_retained ||
     ARRAY_SIZE(owned)!=GFX_RESET_SCOPE_PAGES) return false;
 for (i=0;i<ARRAY_SIZE(owned);i++) if (!owned[i]) return false;
 return true;
}

static bool gfx_reset_scope_backing(void)
{
 return gfx_poweroff_retained() && held &&
        pm_runtime_enabled(&consumer->dev) && pm_runtime_active(&consumer->dev);
}

/* Software accounting is sampled, not a globally atomic hardware witness. */
static bool gfx_poweroff_accounting(const char *phase)
{
 int usage,status,error;
 bool enabled,active,suspended;
 if (!consumer) {
  pr_info("m4rch gfx-poweroff-pm: phase=%s available=0 held=%u\n",phase,held);
  return false;
 }
 usage=atomic_read(&consumer->dev.power.usage_count);
 status=READ_ONCE(consumer->dev.power.runtime_status);
 error=READ_ONCE(consumer->dev.power.runtime_error);
 enabled=pm_runtime_enabled(&consumer->dev);
 active=pm_runtime_active(&consumer->dev);
 suspended=pm_runtime_suspended(&consumer->dev);
 pr_info("m4rch gfx-poweroff-pm: phase=%s available=1 usage_count=%d runtime_status=%d runtime_error=%d enabled=%u active=%u suspended=%u held=%u pm_attempted=%u\n",
  phase,usage,status,error,enabled,active,suspended,held,gfx_poweroff_pm_attempted);
 return enabled && usage==0 && suspended && !active && !error && !held;
}

static void gfx_poweroff_dram(const char *phase)
{
 if (!gfx_poweroff_retained()) {
  pr_info("m4rch gfx-poweroff-dram: phase=%s available=0 allocations_retained=1\n",phase);
  return;
 }
 recovery_sample(0,phase);
 pr_info("m4rch gfx-poweroff-dram: phase=%s power652c=%u records=%u status=%#x doorbells=%u allocations_retained=%u dma_retirement_verified=0\n",
  phase,recovery_read32(RECOVERY_POWER+0x652c),receive_journal.used,
  receive_journal.status,receive_journal.doorbells,GFX_RESET_SCOPE_PAGES);
}

/* Once the explicit OFF gate is consumed, even a refusal permits no ASC,
 * SGX or mailbox access. PMGR snapshots and retained DRAM remain available.
 */
static void gfx_reset_scope_protocol(const char *phase)
{
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_poweroff_gate_consumed && gfx_reset_scope_backing())
  pr_info("m4rch gfx-poweroff-asc: phase=%s control40=%#x control44=%#x status48=%#x\n",
   phase,readl(asc+0x40),readl(asc+0x44),readl(asc+0x48));
 else
  pr_info("m4rch gfx-poweroff-asc: phase=%s sampled=0 gate_consumed=%u mmio_after_off_allowed=0\n",
   phase,gfx_poweroff_gate_consumed);
 gfx_poweroff_accounting(phase);
 gfx_poweroff_dram(phase);
}

static int gfx_reset_scope_result(const char *command,int ret)
{
 recovery_operation++;
 pr_info("m4rch gfx-poweroff-result: command=%s operation=%u result=%d gate_consumed=%u pm_attempted=%u pm_result=%d snapshot_result=%d snapshot_count=%u poll_min_delay_us=%u provider_off_observed=%u accounting_ok=%u held=%u host_stopped=%u sealed=%u allocations_retained=%u restart_allowed=0 dma_retirement_verified=0\n",
  command,recovery_operation,ret,gfx_poweroff_gate_consumed,
  gfx_poweroff_pm_attempted,gfx_poweroff_pm_result,gfx_poweroff_snapshot_result,
  gfx_poweroff_snapshot_count,gfx_poweroff_poll_delay_us,
  gfx_poweroff_provider_off_observed,gfx_poweroff_accounting_ok,held,
  gfx_reset_scope_host_stopped,gfx_reset_scope_sealed,GFX_RESET_SCOPE_PAGES);
 return ret;
}

static int gfx_poweroff_snapshot(const char *phase,unsigned int index,
 struct apple_pmgr_gfx_reset_observation *observation)
{
 int ret;
 memset(observation,0,sizeof(*observation));
 ret=apple_pmgr_t6040_gfx_snapshot(observation);
 if (!ret && observation->operation_error) ret=observation->operation_error;
 if (!ret && observation->cleanup_error) ret=observation->cleanup_error;
 if (ret>0) ret=-EIO;
 if (!ret && !(observation->valid&APPLE_PMGR_GFX_VALID_BEFORE)) ret=-ENODATA;
 pr_info("m4rch gfx-poweroff-snapshot: phase=%s index=%u result=%d valid=%#x domain_on=%u operation_error=%d cleanup_error=%d word_valid=%u\n",
  phase,index,ret,observation->valid,observation->domain_on,
  observation->operation_error,observation->cleanup_error,
  !!(observation->valid&APPLE_PMGR_GFX_VALID_BEFORE));
 if (observation->valid&APPLE_PMGR_GFX_VALID_BEFORE)
  pr_info("m4rch gfx-poweroff-word: phase=%s index=%u value=%#x actual=%u target=%u auto=%u reset=%u disable=%u ps_reset=%u busy=%u\n",
   phase,index,observation->before,(observation->before>>4)&15,
   observation->before&15,!!(observation->before&BIT(28)),
   !!(observation->before&BIT(31)),!!(observation->before&BIT(10)),
   !!(observation->before&BIT(12)),!!(observation->before&BIT(11)));
 return ret;
}

static int gfx_reset_scope_snapshot(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_poweroff_retained()) return gfx_reset_scope_result("gfx-snapshot",-EBUSY);
 ret=gfx_poweroff_snapshot("diagnostic",0,&observation);
 gfx_reset_scope_protocol("gfx-snapshot");
 return gfx_reset_scope_result("gfx-snapshot",ret);
}

static int gfx_poweroff_sample(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_poweroff_retained()) return gfx_reset_scope_result("sample",-EBUSY);
 ret=gfx_poweroff_snapshot("sample",0,&observation);
 gfx_reset_scope_protocol("sample");
 return gfx_reset_scope_result("sample",ret);
}

static int gfx_reset_scope_stop(void)
{
 u32 control,status;
 int ret=0;
 lockdep_assert_held(&graph_io_lock);
 gfx_reset_scope_sealed=true;
 recovery_session_failed=true;
 cancel_delayed_work(&recovery_receive_work);
 if (gfx_poweroff_gate_consumed) {
  gfx_reset_scope_protocol("stop-after-off");
  return gfx_reset_scope_result("stop",gfx_reset_scope_host_stopped?0:-EPERM);
 }
 if (!gfx_reset_scope_backing()) return gfx_reset_scope_result("stop",-EBUSY);
 if (!gfx_poweroff_start_clear_attempted) {
  gfx_poweroff_start_clear_attempted=true;
  writel(readl(asc+0x44)&~START,asc+0x44);
 }
 control=readl(asc+0x44);status=readl(asc+0x48);
 gfx_reset_scope_host_stopped=!(control&START);
 if (!gfx_reset_scope_host_stopped || !(status&3)) ret=-EAGAIN;
 gfx_reset_scope_protocol("packet-free-stop");
 pr_info("m4rch gfx-poweroff-stop: clear_attempted=%u start_clear=%u native_idle=%u management_packets=0 allocations_retained=%u\n",
  gfx_poweroff_start_clear_attempted,gfx_reset_scope_host_stopped,
  !!(status&3),GFX_RESET_SCOPE_PAGES);
 return gfx_reset_scope_result("stop",ret);
}

static int gfx_poweroff_preconditions(void)
{
 u32 phase,control;
 if (!gfx_reset_scope_backing() || !gfx_reset_scope_host_stopped ||
     !gfx_poweroff_start_clear_attempted || recovery_work_submitted ||
     atomic_read(&consumer->dev.power.usage_count)!=1 ||
     READ_ONCE(consumer->dev.power.runtime_error)) return -EBUSY;
 if (!recovery_idle()) return -EBUSY;
 phase=recovery_read32(RECOVERY_STATUS+0x4900);
 if (phase!=0 && phase!=2) return -EPERM;
 control=recovery_read32(RECOVERY_CONTROL+16);
 if (control<RECOVERY_CONTROL_INITIAL || control>RECOVERY_CONTROL_LAST ||
     recovery_read32(RECOVERY_CONTROL)!=control ||
     recovery_read32(RECOVERY_CONTROL+8)!=control) return -EBUSY;
 if ((readl(asc+0x44)&START) || !(readl(asc+0x48)&3)) return -EBUSY;
 return 0;
}

static int gfx_poweroff_attempt(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 unsigned int i;
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (gfx_poweroff_gate_consumed) return gfx_reset_scope_result("gfx-poweroff",-EALREADY);
 /* Seal first. A queued worker must take this mutex and observes the seal;
  * do not synchronously cancel a worker waiting on graph_io_lock.
  */
 gfx_reset_scope_sealed=true;recovery_session_failed=true;
 cancel_delayed_work(&recovery_receive_work);
 gfx_poweroff_accounting("before-off");
 ret=gfx_poweroff_preconditions();
 if (!ret) {
  ret=gfx_poweroff_snapshot("before-off",0,&observation);
  if (!ret && (!observation.domain_on ||
               (observation.before&0x80001cffU)!=0xffU)) ret=-EBUSY;
 }
 /* Consume even on refusal. No hardware diagnostic access after this point. */
 gfx_poweroff_gate_consumed=true;
 if (ret) {
  gfx_poweroff_snapshot_result=ret;
  gfx_reset_scope_protocol("poweroff-refused");
  return gfx_reset_scope_result("gfx-poweroff",ret);
 }
 gfx_poweroff_pm_attempted=true;gfx_reset_scope_attempted=true;
 /* RPM_GET_PUT decrements the sole usage reference even on suspend errors.
  * Clear local ownership before entry and never compensate with get/put.
  */
 held=false;
 gfx_poweroff_pm_result=pm_runtime_put_sync_suspend(&consumer->dev);
 gfx_poweroff_accounting_ok=gfx_poweroff_accounting("after-put");
 gfx_poweroff_snapshot_result=-ETIMEDOUT;
 for (i=0;i<GFX_POWER_OFF_POLL_SAMPLES;i++) {
  gfx_poweroff_snapshot_count++;
  ret=gfx_poweroff_snapshot("after-off",i,&observation);
  if (ret) {gfx_poweroff_snapshot_result=ret;break;}
  if (!observation.domain_on &&
      !(observation.before&GFX_POWER_OFF_STATE_MASK)) {
   gfx_poweroff_provider_off_observed=true;
   gfx_poweroff_snapshot_result=0;break;
  }
  if (i+1<GFX_POWER_OFF_POLL_SAMPLES) {
   usleep_range(GFX_POWER_OFF_POLL_DELAY_US,GFX_POWER_OFF_POLL_DELAY_US+100);
   gfx_poweroff_poll_delay_us+=GFX_POWER_OFF_POLL_DELAY_US;
  }
 }
 gfx_poweroff_accounting_ok=gfx_poweroff_accounting("after-observation");
 gfx_reset_scope_protocol("poweroff-final");
 ret=gfx_poweroff_pm_result<0?gfx_poweroff_pm_result:gfx_poweroff_snapshot_result;
 if (!ret && !gfx_poweroff_accounting_ok) ret=-EIO;
 return gfx_reset_scope_result("gfx-poweroff",ret);
}
