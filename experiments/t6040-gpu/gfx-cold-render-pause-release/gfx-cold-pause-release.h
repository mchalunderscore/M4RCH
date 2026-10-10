/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded intervention in the captured cold stall, not native reason ownership.
 * FW1b1f0..1b1fc computes request&~1 and invokes32104 with expectedACKbit0=0.
 * We lack the firmware mutex/reason lifecycle. No ACK or bit1 write is allowed.
 */
#ifndef GFX_COLD_RENDER_PAUSE_RELEASE_TRIAL
#error Distinct scheduler pause release profile required
#endif
#define GFX_PAUSE_TIMEOUT_MS 100U
#define GFX_PAUSE_POLLS 101U
static bool gfx_pause_intent,gfx_pause_write_attempted,gfx_pause_write_issued;
static bool gfx_pause_complete,gfx_pause_rewritten,gfx_pause_reasserted;
static u64 gfx_pause_before,gfx_pause_written,gfx_pause_after,gfx_pause_ack;
static unsigned int gfx_pause_polls;
static int gfx_pause_result;
static const char *gfx_pause_refusal="none";

static void gfx_pause_log(const char *phase)
{
 pr_info("m4rch gfx-cold-pause-release: phase=%s result=%d refused_condition=%s intent=%u write_attempted=%u write_issued=%u complete=%u before=%#llx written=%#llx after=%#llx ack=%#llx polls=%u rewritten=%u reasserted=%u sample_index=%u elapsed_ms=%u operand_samples_atomic=0\n",
  phase,gfx_pause_result,gfx_pause_refusal,gfx_pause_intent,gfx_pause_write_attempted,
  gfx_pause_write_issued,gfx_pause_complete,(unsigned long long)gfx_pause_before,
  (unsigned long long)gfx_pause_written,(unsigned long long)gfx_pause_after,
  (unsigned long long)gfx_pause_ack,gfx_pause_polls,gfx_pause_rewritten,
  gfx_pause_reasserted,gfx_cold_sample_index,gfx_cold_elapsed_ms);
}

static bool gfx_pause_exact(const struct gfx_pause_operands *v)
{
 unsigned int i;
 if(!v->ksm_valid || !v->fault_valid || v->request!=3 || v->ack!=2 ||
    v->enabled0!=3 || v->enabled1 || v->fault_info || v->fault_addr) return false;
 for(i=0;i<4;i++)
  if(v->config[i]!=(BIT_ULL(54)|render_vas[RENDER_HW_COMPLETION_FIRST+i]|1ULL) ||
     v->status[i]) return false;
 return true;
}

static bool gfx_pause_owned(void)
{
 unsigned int i,j;
 if(!gfx_cold_running || gfx_cold_sealed || !gfx_cold_control_ready ||
    !gfx_cold_draw_intent || !gfx_cold_draw_notify_sent ||
    !gfx_cold_record_cleaned[0] || !gfx_cold_record_cleaned[1] ||
    !gfx_cold_producer_verified[0] || !gfx_cold_producer_verified[1] ||
    !gfx_cold_guard(33,false,0)) return false;
 for(i=0;i<2;i++) for(j=0;j<3;j++)
  if(recovery_read32(recovery_work_cursors[i]+j*8)!=1) return false;
 return gfx_cold_live();
}

static bool gfx_pause_fresh(void __iomem *ksm,struct gfx_pause_operands *v)
{
 unsigned int i;
 void __iomem *fault;
 memset(v,0,sizeof(*v));
 if(!gfx_pause_owned()) return false;
 v->enabled0=readq(ksm+0x1038);v->enabled1=readq(ksm+0x1040);
 v->request=readq(ksm+0x11c8);v->ack=readq(ksm+0x11d0);
 for(i=0;i<4;i++) {
  v->config[i]=readq(ksm+0x1148+i*8);v->status[i]=readq(ksm+0x1168+i*8);
 }
 v->ksm_valid=true;fault=ioremap(0x28800c000ULL,0x4000);
 if(!fault) return false;
 v->fault_info=readq(fault+0x18c0);v->fault_addr=readq(fault+0x18c8);
 v->fault_valid=true;iounmap(fault);
 return gfx_pause_exact(v)&&gfx_cold_live();
}

static int gfx_pause_fail(const char *condition,int result)
{
 gfx_pause_refusal=condition;gfx_pause_result=result;
 gfx_pause_log("refused");return result;
}

static int gfx_cold_pause_release(void)
{
 struct gfx_pause_operands fresh;
 void __iomem *ksm;
 unsigned long until;
 unsigned int i;
 int ret;
 if(gfx_pause_intent) return -EALREADY;
 if(gfx_cold_sample_index!=2 || gfx_cold_elapsed_ms<100 ||
    gfx_cold_observation_samples!=3 || !gfx_pause_sample.output_valid ||
    !gfx_pause_exact(&gfx_pause_sample)) return gfx_pause_fail("sample-eligibility",-EBUSY);
 for(i=0;i<6;i++) if(gfx_pause_sample.changed[i])
  return gfx_pause_fail("already-progressed",-EBUSY);
 ksm=ioremap(0x288020000ULL,0x4000);
 if(!ksm) return gfx_pause_fail("ksm-map",-ENODATA);
 if(!gfx_pause_fresh(ksm,&fresh)) {ret=gfx_pause_fail("fresh-eligibility",-EBUSY);goto done;}
 gfx_pause_before=fresh.request;gfx_pause_after=fresh.request;gfx_pause_ack=fresh.ack;
 gfx_pause_log("eligible");
 gfx_pause_intent=true;gfx_pause_log("intent");
 if(!gfx_pause_fresh(ksm,&fresh)) {ret=gfx_pause_fail("intent-recheck",-EBUSY);goto done;}
 gfx_pause_written=fresh.request&~1ULL;
 gfx_pause_write_attempted=true;gfx_pause_log("write-intent");
 if(!gfx_cold_live()) {ret=gfx_pause_fail("write-ownership",-EIO);goto done;}
 /* Last fresh request read follows every guard and the logged once intent.
  * The remaining firmware race cannot be eliminated without its mutex. */
 gfx_pause_before=readq(ksm+0x11c8);
 if(gfx_pause_before!=3) {ret=gfx_pause_fail("last-request-changed",-EPROTO);goto done;}
 gfx_pause_written=gfx_pause_before&~1ULL;
 writeq(gfx_pause_written,ksm+0x11c8);gfx_pause_write_issued=true;
 until=jiffies+msecs_to_jiffies(GFX_PAUSE_TIMEOUT_MS);
 for(gfx_pause_polls=0;gfx_pause_polls<GFX_PAUSE_POLLS;gfx_pause_polls++) {
  if(!gfx_cold_live() || !recovery_messages()) {ret=gfx_pause_fail("poll-ownership",-EIO);goto done;}
  gfx_pause_after=readq(ksm+0x11c8);gfx_pause_ack=readq(ksm+0x11d0);
  gfx_pause_log("readback");
  if(gfx_pause_after!=gfx_pause_written) {
   gfx_pause_rewritten=true;gfx_pause_reasserted=!!(gfx_pause_after&1);
   ret=gfx_pause_fail("request-rewritten",-EPROTO);goto done;
  }
  if(gfx_pause_ack==~0ULL) {ret=gfx_pause_fail("ack-invalid",-EIO);goto done;}
  if(!(gfx_pause_ack&1)) {
   gfx_pause_complete=true;gfx_pause_result=0;gfx_pause_log("released");ret=0;goto done;
  }
  if(!time_before(jiffies,until)) {ret=gfx_pause_fail("ack-timeout",-ETIMEDOUT);goto done;}
  usleep_range(1000,2000);
 }
 ret=gfx_pause_fail("poll-limit",-ETIMEDOUT);
done:
 iounmap(ksm);return ret;
}

static void gfx_cold_pause_watch(void)
{
 if(!gfx_pause_write_issued || gfx_cold_sample_index<3 || !gfx_pause_sample.ksm_valid) return;
 gfx_pause_after=gfx_pause_sample.request;gfx_pause_ack=gfx_pause_sample.ack;
 if(gfx_pause_after!=gfx_pause_written) gfx_pause_rewritten=true;
 if(gfx_pause_after&1) gfx_pause_reasserted=true;
 gfx_pause_log("observe");
}
