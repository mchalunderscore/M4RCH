/* SPDX-License-Identifier: GPL-2.0-only */
/* Host-owned shared trace mask only; no trace MMIO or extra notification. */
#ifndef GFX_NATIVE_DISPATCH_CONTRACT_TRIAL
#error Distinct native dispatch contract profile required
#endif

static void gfx_dispatch_trace_log(const char *phase)
{
 pr_info("m4rch gfx-native-dispatch-trace: phase=%s result=%d refused_condition=%s intent=%u write_attempted=%u complete=%u before=%u written=%u after=%u control_ready=%u control=%u/%u/%u identities_preserved=%u sample_index=%u elapsed_ms=%u operand_samples_atomic=0\n",
  phase,gfx_dispatch_trace_result,gfx_dispatch_trace_refusal,
  gfx_dispatch_trace_intent,gfx_dispatch_trace_write_attempted,
  gfx_dispatch_trace_ready,gfx_dispatch_trace_before,gfx_dispatch_trace_written,
  gfx_dispatch_trace_after,gfx_cold_control_ready,gfx_cold_control[0],
  gfx_cold_control[1],gfx_cold_control[2],gfx_cold_identities_preserved,
  gfx_cold_sample_index,gfx_cold_elapsed_ms);
}

static int gfx_dispatch_trace_fail(const char *condition,int result)
{
 gfx_dispatch_trace_refusal=condition;gfx_dispatch_trace_result=result;
 gfx_dispatch_trace_log("refused");return result;
}

static unsigned int gfx_dispatch_expected_trace(void)
{
 return gfx_dispatch_trace_ready?3U:0U;
}

static int gfx_dispatch_trace_restore(void)
{
 if(gfx_dispatch_trace_intent) return -EALREADY;
 if(!gfx_cold_control_ready || gfx_cold_draw_intent || recovery_work_submitted ||
    !gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())
  return gfx_dispatch_trace_fail("trace-admission",-EBUSY);
 gfx_dispatch_trace_before=gfx_cold_trace_after;
 gfx_dispatch_trace_after=gfx_cold_trace_after;
 gfx_dispatch_trace_intent=true;gfx_dispatch_trace_log("intent");
 if(!gfx_cold_control_ready || gfx_cold_draw_intent || recovery_work_submitted ||
    !gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())
  return gfx_dispatch_trace_fail("trace-intent-recheck",-EBUSY);
 gfx_dispatch_trace_log("write-intent");
 /* A log hook, firmware action or changed identity must not bypass the last
  * own-PM/control/idle/trace check. This is still a non-atomic host sample. */
 if(!gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing() ||
    !gfx_cold_live() || gfx_cold_draw_intent || recovery_work_submitted)
  return gfx_dispatch_trace_fail("trace-write-recheck",-EBUSY);
 gfx_dispatch_trace_write_attempted=true;gfx_dispatch_trace_written=3;
 recovery_write32(RECOVERY_TRACE_MASK,3);
 gfx_dispatch_trace_after=recovery_read32(RECOVERY_TRACE_MASK);
 if(gfx_dispatch_trace_after!=3 || !gfx_cold_live())
  return gfx_dispatch_trace_fail("trace-readback",-EIO);
 if(!gfx_cold_guard(33,true,3) || !gfx_cold_immutable_backing())
  return gfx_dispatch_trace_fail("trace-restored-recheck",-EBUSY);
 gfx_dispatch_trace_ready=true;gfx_dispatch_trace_log("readback");return 0;
}
