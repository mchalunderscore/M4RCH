/* SPDX-License-Identifier: GPL-2.0-only */
/* Explicit, one-attempt GFX device-reset scope experiment. The caller owns
 * graph_io_lock and retains every allocation, mapping and PM reference.
 * A command/readback result never establishes DMA retirement or restart.
 */
#include <linux/soc/apple/pmgr-gfx-reset.h>

#define GFX_RESET_SCOPE_PAGES 174U
static bool gfx_reset_scope_owner_pinned, gfx_reset_scope_attempted;
static bool gfx_reset_scope_sealed, gfx_reset_scope_host_stopped;

static bool gfx_reset_scope_backing(void)
{
 unsigned int i;
 if (!gfx_reset_scope_owner_pinned || !recovery_resident || !resident_session ||
     !held || !consumer || !pm_runtime_active(&consumer->dev) || !asc || !mbox ||
     !asc_region || !mbox_region || !root_sent || !installed || root_detached ||
     !device_context_retained || ARRAY_SIZE(owned)!=GFX_RESET_SCOPE_PAGES)
  return false;
 for (i=0;i<ARRAY_SIZE(owned);i++) if (!owned[i]) return false;
 return true;
}

/* No receive drain here: receive handlers may ACK or publish host cursors.
 * Protocol fields and journal prefix remain readable in a sealed owner.
 */
static void gfx_reset_scope_protocol(const char *phase)
{
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_reset_scope_backing()) {
  pr_info("m4rch gfx-reset-protocol: phase=%s available=0 attempted=%d sealed=%d allocations_retained=1\n",
   phase,gfx_reset_scope_attempted,gfx_reset_scope_sealed);
  return;
 }
 pr_info("m4rch gfx-reset-asc: phase=%s control40=%#x control44=%#x status48=%#x coverage_verified=0\n",
  phase,readl(asc+0x40),readl(asc+0x44),readl(asc+0x48));
 recovery_sample(0,phase);
 pr_info("m4rch gfx-reset-protocol: phase=%s records=%u status=%#x doorbells=%u attempted=%d sealed=%d host_stopped=%d allocations_retained=%u\n",
  phase,receive_journal.used,receive_journal.status,receive_journal.doorbells,
  gfx_reset_scope_attempted,gfx_reset_scope_sealed,gfx_reset_scope_host_stopped,
  GFX_RESET_SCOPE_PAGES);
}

static void gfx_reset_scope_observation(const char *command,int ret,
 const struct apple_pmgr_gfx_reset_observation *o)
{
 const char * const names[]={"before","auto_held","disabled","asserted",
  "deasserted","released","final","cleanup_final"};
 const u32 values[]={o->before,o->auto_held,o->disabled,o->asserted,
  o->deasserted,o->released,o->final,o->cleanup_final};
 const u32 bits[]={APPLE_PMGR_GFX_VALID_BEFORE,APPLE_PMGR_GFX_VALID_AUTO_HELD,
  APPLE_PMGR_GFX_VALID_DISABLED,APPLE_PMGR_GFX_VALID_ASSERTED,
  APPLE_PMGR_GFX_VALID_DEASSERTED,APPLE_PMGR_GFX_VALID_RELEASED,
  APPLE_PMGR_GFX_VALID_FINAL,APPLE_PMGR_GFX_VALID_CLEANUP_FINAL};
 unsigned int i;
 pr_info("m4rch gfx-reset-observation: command=%s result=%d valid=%#x domain_on=%u reset_users_present=%u auto_policy_restored=%u operation_error=%d cleanup_error=%d coverage_verified=0 retirement_verified=0\n",
  command,ret,o->valid,o->domain_on,o->reset_users_present,o->auto_policy_restored,
  o->operation_error,o->cleanup_error);
 for (i=0;i<ARRAY_SIZE(names);i++) {
  if (o->valid&bits[i])
   pr_info("m4rch gfx-reset-field: command=%s field=%s valid=1 value=%#x\n",command,names[i],values[i]);
  else
   pr_info("m4rch gfx-reset-field: command=%s field=%s valid=0\n",command,names[i]);
 }
}

static int gfx_reset_scope_result(const char *command,int ret)
{
 recovery_operation++;
 pr_info("m4rch gfx-reset-scope: command=%s operation=%u result=%d attempted=%d sealed=%d session_failed=%d resident=%d host_stopped=%d allocations_retained=1 restart_allowed=0\n",
  command,recovery_operation,ret,gfx_reset_scope_attempted,gfx_reset_scope_sealed,
  recovery_session_failed,recovery_resident,gfx_reset_scope_host_stopped);
 return ret;
}

#ifdef GFX_RESET_NATIVE_SEQUENCE_TRIAL
static void gfx_reset_scope_native_observation(const struct apple_pmgr_gfx_native_observation *o)
{
 const char * const commands[]={"inhibit","disable","combined-assert","release",
  "restore","cleanup-inhibit","cleanup-release","cleanup-restore"};
 const char * const reads[]={"before","auto-held","disabled","asserted",
  "released","final","cleanup-release","cleanup-final"};
 unsigned int i;
 pr_info("m4rch gfx-native-contract: api=apple_pmgr_t6040_gfx_native_probe command_bit_ack_required=0 full_word_forced_writes=1 physical_reset_acknowledged=0 retirement_verified=0\n");
 pr_info("m4rch gfx-native-result: command_attempts=%#x base=%#x base_from_auto_held=%u original_auto=%#x release_command_verified=%u sequence_completed=%u disable_delay_us=%u pulse_delay_us=%u read_attempts=%#x\n",
  o->command_attempts,o->command_base,o->base_from_auto_held,o->original_auto,
  o->release_command_verified,o->sequence_completed,o->disable_delay_us,
  o->pulse_delay_us,o->read_attempts);
 for(i=0;i<ARRAY_SIZE(commands);i++)
  pr_info("m4rch gfx-native-command: field=%s attempted=%u forced=1 desired_full_word=%#x write_error=%d\n",
   commands[i],!!(o->command_attempts&BIT(i)),o->desired[i],o->write_error[i]);
 for(i=0;i<ARRAY_SIZE(reads);i++)
  pr_info("m4rch gfx-native-read: field=%s attempted=%u count=%u poll_delay_us=%u read_error=%d\n",
   reads[i],!!(o->read_attempts&BIT(i)),o->read_count[i],o->poll_delay_us[i],o->read_error[i]);
}
#endif

static int gfx_reset_scope_snapshot(void)
{
 struct apple_pmgr_gfx_reset_observation observation={};
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_reset_scope_backing()) {
  recovery_session_failed=true;
  cancel_delayed_work(&recovery_receive_work);
  return gfx_reset_scope_result("gfx-snapshot",-EBUSY);
 }
 ret=apple_pmgr_t6040_gfx_snapshot(&observation);
 gfx_reset_scope_observation("gfx-snapshot",ret,&observation);
 gfx_reset_scope_protocol("gfx-snapshot");
 if (!ret && (observation.operation_error || observation.cleanup_error))
  ret=observation.operation_error?observation.operation_error:observation.cleanup_error;
 if (ret) {
  recovery_session_failed=true;
  cancel_delayed_work(&recovery_receive_work);
 }
 return gfx_reset_scope_result("gfx-snapshot",ret);
}

static int gfx_reset_scope_preconditions(void)
{
 u32 phase,control;
 if (!gfx_reset_scope_backing()) return -EBUSY;
 if (recovery_work_submitted || !recovery_idle()) return -EBUSY;
 phase=recovery_read32(RECOVERY_STATUS+0x4900);
 if (!((phase==0 && !recovery_session_failed) ||
       (phase==2 && recovery_session_failed))) return -EPERM;
 control=recovery_read32(RECOVERY_CONTROL+16);
 if (control<RECOVERY_CONTROL_INITIAL || control>RECOVERY_CONTROL_LAST ||
     recovery_read32(RECOVERY_CONTROL)!=control ||
     recovery_read32(RECOVERY_CONTROL+8)!=control) return -EBUSY;
 return 0;
}

static int gfx_reset_scope_reset(void)
{
 struct apple_pmgr_gfx_reset_observation observation={};
#ifdef GFX_RESET_NATIVE_SEQUENCE_TRIAL
 struct apple_pmgr_gfx_native_observation native_observation={};
#endif
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (gfx_reset_scope_sealed || gfx_reset_scope_attempted)
  return gfx_reset_scope_result("gfx-reset",-EALREADY);
 ret=gfx_reset_scope_preconditions();
 /* An explicit reset command consumes this gate even when a precondition
  * refuses the API. Existing phase2 failure alone has not consumed it.
  */
 gfx_reset_scope_sealed=true;
 recovery_session_failed=true;
 /* Do not synchronously cancel a worker which acquires graph_io_lock. Any
  * pending/running worker sees the seal under that same lock and cannot drain
  * receive packets, publish cursors, or requeue itself after this point.
  */
 cancel_delayed_work(&recovery_receive_work);
 if (ret) {
  gfx_reset_scope_protocol("gfx-reset-refused");
  return gfx_reset_scope_result("gfx-reset",ret);
 }
 /* The API may commit a write and then return an error. Mark before entry,
  * retain all backing on every result, and never run/wake/publish afterward.
  */
 gfx_reset_scope_attempted=true;
 gfx_reset_scope_protocol("gfx-reset-before");
#ifdef GFX_RESET_NATIVE_SEQUENCE_TRIAL
 ret=apple_pmgr_t6040_gfx_native_probe(&native_observation);
 observation=native_observation.common;
 gfx_reset_scope_native_observation(&native_observation);
 if(!ret && (!native_observation.sequence_completed ||
             !native_observation.release_command_verified ||
             !observation.auto_policy_restored ||
             (native_observation.command_attempts &
              (BIT(APPLE_PMGR_GFX_NATIVE_DISABLE) | BIT(APPLE_PMGR_GFX_NATIVE_ASSERT) |
               BIT(APPLE_PMGR_GFX_NATIVE_RELEASE))) !=
              (BIT(APPLE_PMGR_GFX_NATIVE_DISABLE) | BIT(APPLE_PMGR_GFX_NATIVE_ASSERT) |
               BIT(APPLE_PMGR_GFX_NATIVE_RELEASE)))) ret=-EIO;
#else
 ret=apple_pmgr_t6040_gfx_checked_pulse(&observation);
#endif
 gfx_reset_scope_observation("gfx-reset",ret,&observation);
 gfx_reset_scope_protocol("gfx-reset-after");
 if (!ret && (observation.operation_error || observation.cleanup_error))
  ret=observation.operation_error?observation.operation_error:observation.cleanup_error;
 return gfx_reset_scope_result("gfx-reset",ret);
}

static int gfx_reset_scope_stop(void)
{
 lockdep_assert_held(&graph_io_lock);
 gfx_reset_scope_sealed=true;
 recovery_session_failed=true;
 cancel_delayed_work(&recovery_receive_work);
 /* Explicit host stop only. No AP_QUIESCED, IOP_SLEEP, RX ACK, INIT, root,
  * control, work notification, PM put, unmap, or allocation release.
  */
 if (!gfx_reset_scope_backing()) return gfx_reset_scope_result("stop",-EBUSY);
 if (!gfx_reset_scope_host_stopped) {
  writel(readl(asc+0x44)&~START,asc+0x44);
  readl(asc+0x44);
  gfx_reset_scope_host_stopped=true;
 }
 gfx_reset_scope_protocol("gfx-host-stop");
 pr_info("m4rch recovery-session: host_stop_requested_and_pinned=1 management_packets=0 resident=1 diagnostics_available=1 retirement_verified=0\n");
 return gfx_reset_scope_result("stop",0);
}
