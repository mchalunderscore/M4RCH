/* SPDX-License-Identifier: GPL-2.0-only */
/* Source-backed experimental transfer of AGXFenderChinook's native enable
 * operation to the existing firmware-mediated draw path. Native addKicks
 * brackets direct SGX+4090/+4098 stores with disable(old|4)/enable(old&~6).
 * This helper performs only the exact enable RMW, after fresh control33 and
 * before the first draw publication. EP33 is not native addKicks. No direct
 * kick, scheduler ACK/coverage write, teardown cleanup or retry is implied.
 * The preASC-owned Fender page and all GPU/PM backing remain retained.
 */
#ifndef GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL
#error Distinct native Fender draw cycle profile required
#endif
static bool gfx_native_fender_enable_intent,gfx_native_fender_enable_attempted;
static bool gfx_native_fender_enable_complete,gfx_native_fender_enable_unknown;
static void __iomem *gfx_native_fender_enable_map;
static u32 gfx_native_fender_enable_gpu_id,gfx_native_fender_enable_before;
static u32 gfx_native_fender_enable_requested,gfx_native_fender_enable_after;

static bool gfx_native_fender_enable_owned(void)
{
 return gfx_cold_running && !gfx_cold_sealed && !gfx_cold_complete &&
  gfx_cold_control_ready && !gfx_cold_draw_intent && !recovery_work_submitted &&
  !gfx_cold_draw_notify_attempted && !gfx_cold_draw_notify_sent &&
  !gfx_cold_record_attempted[0] && !gfx_cold_record_attempted[1] &&
  !gfx_cold_producer_attempted[0] && !gfx_cold_producer_attempted[1] &&
  gfx_gravity_preasc_complete && !gfx_gravity_preasc_unknown &&
  gfx_gravity_preasc_region[0] && gfx_gravity_preasc_region[1] &&
  gfx_gravity_preasc_io[0] && gfx_gravity_preasc_io[1] &&
  gfx_native_fender_enable_map==gfx_gravity_preasc_io[1] &&
  consumer==gfx_gravity_preasc_consumer && asc==gfx_gravity_preasc_asc &&
  mbox==gfx_gravity_preasc_mbox && gfx_cold_live();
}

static void gfx_native_fender_enable_log(const char *phase,const char *condition,int result)
{
 pr_info("m4rch gfx-native-fender-enable: phase=%s result=%d refused_condition=%s intent=%u attempted=%u complete=%u unknown=%u held=%u retained=1 transfer_hypothesis=1 native_addkicks=0 teardown_clear=0\n",
  phase,result,condition,gfx_native_fender_enable_intent,gfx_native_fender_enable_attempted,
  gfx_native_fender_enable_complete,gfx_native_fender_enable_unknown,held);
}

/* Caller holds graph_io_lock. Include after gfx-cold-render.h and the
 * retained gfx-gravity-preasc.h; forward-declare this function for the
 * cold-render caller. Never call on a management rejoin or from teardown.
 */
static int gfx_native_fender_enable(void)
{
 const char *condition="none";
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_native_fender_enable_intent) {
  gfx_native_fender_enable_log("refused","one-shot",-EALREADY);
  return -EALREADY;
 }
 gfx_native_fender_enable_intent=true;
 gfx_native_fender_enable_map=gfx_gravity_preasc_io[1];
 gfx_native_fender_enable_log("intent","none",0);
 if(!gfx_native_fender_enable_owned()) {ret=-EBUSY;condition="ownership-before-draw";goto refused;}
 /* Existing guard observes real physical ON, all control33 cursors, idle
  * work/recovery state and unchanged retained identities. It does not grant
  * DMA retirement or authorize reuse after an earlier draw.
  */
 if(!gfx_cold_guard(33,true,3U)) {ret=-EBUSY;condition="control33-physical-on";goto refused;}
 if(!gfx_native_fender_enable_owned()) {ret=-EBUSY;condition="guard-ownership";goto refused;}
 gfx_native_fender_enable_gpu_id=readl(gfx_native_fender_enable_map);
 if(!gfx_native_fender_enable_gpu_id || gfx_native_fender_enable_gpu_id==~0U ||
    gfx_native_fender_enable_gpu_id!=gfx_gravity_preasc_gpu_id) {
  ret=-ENODEV;condition="gpu-id";goto refused;
 }
 /* The exclusive 16K d04000 mapping includes d06030 at offset2030. Native
  * enable reads afresh and preserves every bit except clearing bits1/2.
  * An all-ones read is invalid and cannot be used as an RMW baseline.
  */
 gfx_native_fender_enable_before=readl(gfx_native_fender_enable_map+0x2030);
 if(gfx_native_fender_enable_before==~0U) {ret=-ENODATA;condition="baseline-invalid";goto refused;}
 gfx_native_fender_enable_requested=gfx_native_fender_enable_before&~6U;
 if(!gfx_native_fender_enable_owned()) {ret=-EBUSY;condition="prewrite-ownership";goto refused;}
 gfx_native_fender_enable_attempted=true;
 writel(gfx_native_fender_enable_requested,gfx_native_fender_enable_map+0x2030);
 gfx_native_fender_enable_after=readl(gfx_native_fender_enable_map+0x2030);
 pr_info("m4rch gfx-native-fender-enable-op: offset=0xd06030 gpu_id=%#x before=%#x requested=%#x after=%#x write_attempted=1 verified=%u policy=preserve-clear-six operand_samples_atomic=0\n",
  gfx_native_fender_enable_gpu_id,gfx_native_fender_enable_before,
  gfx_native_fender_enable_requested,gfx_native_fender_enable_after,
  gfx_native_fender_enable_after!=~0U &&
   gfx_native_fender_enable_after==gfx_native_fender_enable_requested);
 if(gfx_native_fender_enable_after==~0U ||
    gfx_native_fender_enable_after!=gfx_native_fender_enable_requested) {
  ret=-EIO;condition="readback";goto refused;
 }
 /* Ordered MMIO and the native readback precede a full system barrier.
  * Readback is register observation, not GPU execution or power completion.
  */
 asm volatile("dsb sy" ::: "memory");
 if(!gfx_native_fender_enable_owned()) {ret=-EBUSY;condition="postwrite-ownership";goto refused;}
 gfx_native_fender_enable_complete=true;
 gfx_native_fender_enable_log("complete","none",0);
 return 0;
refused:
 gfx_native_fender_enable_unknown=gfx_native_fender_enable_attempted;
 gfx_native_fender_enable_log("refused",condition,ret);
 return ret;
}
