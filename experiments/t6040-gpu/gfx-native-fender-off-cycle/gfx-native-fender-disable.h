/* SPDX-License-Identifier: GPL-2.0-only */
/* Source-backed experimental Fender OFF leaf transfer. Native G16
 * setFenderPowerEnabled(false) invokes its disable callback (fresh old|4 at
 * SGX+d06030, exact readback) before conditional provider vote-disable calls.
 * This existing owner transfers that leaf after native idle/CPU stop and
 * before paired coordinate OFF. The full native enclosure is not reproduced.
 * No PMGR waiver, scheduler ACK cleanup, new mapping or backing release.
 */
#ifndef GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL
#error Distinct native Fender OFF cycle profile required
#endif
static bool gfx_native_fender_disable_intent,gfx_native_fender_disable_attempted;
static bool gfx_native_fender_disable_complete,gfx_native_fender_disable_unknown;
static void __iomem *gfx_native_fender_disable_map;
static u32 gfx_native_fender_disable_gpu_id,gfx_native_fender_disable_before;
static u32 gfx_native_fender_disable_requested,gfx_native_fender_disable_after;

static bool gfx_native_fender_disable_owned(void)
{
 return gfx_postdraw_cycle_intent && !gfx_postdraw_unknown &&
  !gfx_postdraw_off_attempted && !gfx_postdraw_pm_put_attempted &&
  !gfx_postdraw_control_sealed && gfx_postdraw_active() &&
  gfx_native_powergate_idle_observed && gfx_native_powergate_cpu_stopped &&
  gfx_native_powergate_clear10_attempted && gfx_native_powergate_clear20_attempted &&
  gfx_native_powergate_control_after20!=~0U &&
  !(gfx_native_powergate_control_after20&0x30U) &&
  gfx_native_powergate_idle_status!=~0U && (gfx_native_powergate_idle_status&3U) &&
  gfx_native_fender_enable_intent && gfx_native_fender_enable_attempted &&
  gfx_native_fender_enable_complete && !gfx_native_fender_enable_unknown &&
  gfx_gravity_preasc_complete && !gfx_gravity_preasc_unknown &&
  gfx_gravity_preasc_region[0] && gfx_gravity_preasc_region[1] &&
  gfx_gravity_preasc_io[0] && gfx_gravity_preasc_io[1] &&
  gfx_native_fender_disable_map==gfx_gravity_preasc_io[1] &&
  gfx_native_fender_enable_map==gfx_gravity_preasc_io[1] &&
  consumer==gfx_gravity_preasc_consumer && asc==gfx_gravity_preasc_asc &&
  mbox==gfx_gravity_preasc_mbox;
}

static void gfx_native_fender_disable_log(const char *phase,const char *condition,int result)
{
 pr_info("m4rch gfx-native-fender-disable: phase=%s result=%d refused_condition=%s intent=%u attempted=%u complete=%u unknown=%u held=%u retained=1 transfer_hypothesis=1 native_poweroff=0 pmgr_writes=0 ack_cleanup=0\n",
  phase,result,condition,gfx_native_fender_disable_intent,gfx_native_fender_disable_attempted,
  gfx_native_fender_disable_complete,gfx_native_fender_disable_unknown,held);
}

/* Caller holds graph_io_lock. Include after the postdraw, preASC, verified
 * Fender enable and runtime-state helpers. Root inserts this after fresh
 * before-off physical/coordinate/alias checks, before off-intent and sealing.
 * No replay on a management rejoin, and no retry in this owner.
 */
static int gfx_native_fender_disable(void)
{
 struct apple_pmgr_gfx_reset_observation physical={0};
 const char *condition="none";
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_native_fender_disable_intent) {
  gfx_native_fender_disable_log("refused","one-shot",-EALREADY);
  return -EALREADY;
 }
 gfx_native_fender_disable_intent=true;
 gfx_native_fender_disable_map=gfx_gravity_preasc_io[1];
 gfx_native_fender_disable_log("intent","none",0);
 if(!gfx_native_fender_disable_owned()) {ret=-EBUSY;condition="ownership-before-off";goto refused;}
 ret=gfx_cold_snapshot("fender-off-before",0,&physical);
 if(ret) {ret=ret>0?-EIO:ret;condition="physical-snapshot";goto refused;}
 if(!gfx_native_runtime_active("fender-off-before",physical.valid,physical.domain_on,physical.before)) {
  ret=-EBUSY;condition="physical-on";goto refused;
 }
 if(!gfx_native_fender_disable_owned()) {ret=-EBUSY;condition="snapshot-ownership";goto refused;}
 gfx_native_fender_disable_gpu_id=readl(gfx_native_fender_disable_map);
 if(!gfx_native_fender_disable_gpu_id || gfx_native_fender_disable_gpu_id==~0U ||
    gfx_native_fender_disable_gpu_id!=gfx_gravity_preasc_gpu_id ||
    gfx_native_fender_disable_gpu_id!=gfx_native_fender_enable_gpu_id) {
  ret=-ENODEV;condition="gpu-id";goto refused;
 }
 if(!gfx_native_fender_disable_owned()) {ret=-EBUSY;condition="gpu-ownership";goto refused;}
 /* The same retained d04000/16K page owns d06030 at offset2030. Preserve
  * every current bit and set only bit2; do not replay a cached prefix value.
  */
 gfx_native_fender_disable_before=readl(gfx_native_fender_disable_map+0x2030);
 if(gfx_native_fender_disable_before==~0U) {ret=-ENODATA;condition="baseline-invalid";goto refused;}
 gfx_native_fender_disable_requested=gfx_native_fender_disable_before|4U;
 if(!gfx_native_fender_disable_owned()) {ret=-EBUSY;condition="prewrite-ownership";goto refused;}
 gfx_native_fender_disable_attempted=true;
 writel(gfx_native_fender_disable_requested,gfx_native_fender_disable_map+0x2030);
 gfx_native_fender_disable_after=readl(gfx_native_fender_disable_map+0x2030);
 pr_info("m4rch gfx-native-fender-disable-op: offset=0xd06030 gpu_id=%#x before=%#x requested=%#x after=%#x write_attempted=1 verified=%u policy=preserve-set-four operand_samples_atomic=0\n",
  gfx_native_fender_disable_gpu_id,gfx_native_fender_disable_before,
  gfx_native_fender_disable_requested,gfx_native_fender_disable_after,
  gfx_native_fender_disable_after!=~0U &&
   gfx_native_fender_disable_after==gfx_native_fender_disable_requested);
 if(gfx_native_fender_disable_after==~0U ||
    gfx_native_fender_disable_after!=gfx_native_fender_disable_requested) {
  ret=-EIO;condition="readback";goto refused;
 }
 /* Added experimental ordering; register readback is not physical OFF or
  * work retirement. Strict OFF remains a later independent observation.
  */
 asm volatile("dsb sy" ::: "memory");
 if(!gfx_native_fender_disable_owned()) {ret=-EBUSY;condition="postwrite-ownership";goto refused;}
 gfx_native_fender_disable_complete=true;
 gfx_native_fender_disable_log("complete","none",0);
 return 0;
refused:
 gfx_native_fender_disable_unknown=gfx_native_fender_disable_attempted;
 gfx_native_fender_disable_log("refused",condition,ret);
 return ret;
}
