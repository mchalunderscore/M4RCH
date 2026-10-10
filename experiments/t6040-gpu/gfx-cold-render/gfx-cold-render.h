/* SPDX-License-Identifier: GPL-2.0-only */
/* One automatic cold control transaction and immutable TA/3D publication.
 * Post-submit observation is synchronous and bounded: no delayed worker is
 * scheduled, no submitted-work OFF/PM put or firmware stop is attempted.
 */
#ifndef GFX_COLD_RENDER_TRIAL
#error Distinct cold-render profile required
#endif
#define GFX_COLD_CONTROL_TIMEOUT_MS 5000U
#define GFX_COLD_CONTROL_POLLS 5001U
#define GFX_COLD_OBSERVE_MS 15000U
#define GFX_COLD_OBSERVE_POLLS 15001U
#define GFX_COLD_CONTROL_RECORD (0xb8000U+32U*64U)
static bool gfx_cold_pipeline_intent,gfx_cold_running,gfx_cold_sealed;
static bool gfx_cold_complete,gfx_cold_software_stopped,gfx_cold_identity_captured;
static bool gfx_cold_identities_preserved,gfx_cold_record_verified;
static bool gfx_cold_control_intent,gfx_cold_trace_attempted,gfx_cold_control_producer_attempted;
static bool gfx_cold_control_notify_attempted,gfx_cold_control_notify_sent,gfx_cold_control_ready;
static bool gfx_cold_draw_intent,gfx_cold_record_attempted[2],gfx_cold_record_cleaned[2];
static bool gfx_cold_producer_attempted[2],gfx_cold_producer_verified[2];
static bool gfx_cold_draw_notify_attempted,gfx_cold_draw_notify_sent;
static struct page *gfx_cold_pages[GFX_COLD_PAGES];
static u64 gfx_cold_page_pa[GFX_COLD_PAGES];
static struct platform_device *gfx_cold_consumer;
static void __iomem *gfx_cold_asc,*gfx_cold_mbox;
static u64 *gfx_cold_bootstrap,*gfx_cold_borrowed_l1,*gfx_cold_target_page,*gfx_cold_target_slot;
static u64 gfx_cold_root_word,gfx_cold_counter;
static u32 gfx_cold_phase,gfx_cold_host_stop,gfx_cold_request_state,gfx_cold_request_flag;
static u32 gfx_cold_control[3],gfx_cold_baseline_control[3],gfx_cold_ready_control[3];
static u32 gfx_cold_trace_before,gfx_cold_trace_after;
static unsigned int gfx_cold_control_polls,gfx_cold_observe_polls;
static unsigned int gfx_cold_observation_samples;
static unsigned long gfx_cold_observe_start;
static int gfx_cold_terminal_result;
static const char *gfx_cold_refusal="none";

static unsigned int gfx_cold_retained_pages(void)
{
 unsigned int i,count=0;
 for(i=0;i<ARRAY_SIZE(owned);i++) count+=!!owned[i];
 return count;
}

static void gfx_cold_log(const char *phase,int result)
{
 pr_info("m4rch gfx-cold-render: phase=%s result=%d refused_condition=%s pipeline_intent=%u sealed=%u complete=%u software_stopped=%u allocations_retained=%u pm_put_attempted=0 off_attempted=0 retirement_verified=0 gpu_execution_verified=0 rendering_verified=0\n",
  phase,result,gfx_cold_refusal,gfx_cold_pipeline_intent,gfx_cold_sealed,
  gfx_cold_complete,gfx_cold_software_stopped,gfx_cold_retained_pages());
 pr_info("m4rch gfx-cold-render-state: phase=%s identities_captured=%u identities_preserved=%u held=%u usage=%d runtime_error=%d active=%u suspended=%u apps_started=%u ap_known=%u journal_used=%u journal_status=%#x receive_crashed=%u running=%u sample_index=%u elapsed_ms=%u operand_samples_atomic=0\n",
  phase,gfx_cold_identity_captured,gfx_cold_identities_preserved,held,
  consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?READ_ONCE(consumer->dev.power.runtime_error):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  consumer?pm_runtime_suspended(&consumer->dev):false,gfx_cold_apps_started,
  gfx_cold_ap_known(),receive_journal.used,receive_journal.status,receive_crashed,
  gfx_cold_running,gfx_cold_sample_index,gfx_cold_elapsed_ms);
 pr_info("m4rch gfx-cold-render-control: phase=%s control_intent=%u trace_attempted=%u producer_attempted=%u notify_attempted=%u notify_sent=%u ready=%u record_verified=%u baseline=%u/%u/%u current=%u/%u/%u ready_cursors=%u/%u/%u trace_before=%u trace_after=%u polls=%u cached=1 operand_samples_atomic=0\n",
  phase,gfx_cold_control_intent,gfx_cold_trace_attempted,gfx_cold_control_producer_attempted,
  gfx_cold_control_notify_attempted,gfx_cold_control_notify_sent,gfx_cold_control_ready,
  gfx_cold_record_verified,gfx_cold_baseline_control[0],gfx_cold_baseline_control[1],gfx_cold_baseline_control[2],
  gfx_cold_control[0],gfx_cold_control[1],gfx_cold_control[2],
  gfx_cold_ready_control[0],gfx_cold_ready_control[1],gfx_cold_ready_control[2],
  gfx_cold_trace_before,gfx_cold_trace_after,gfx_cold_control_polls);
 pr_info("m4rch gfx-cold-render-draw: phase=%s draw_intent=%u record0_attempted=%u record1_attempted=%u record0_cleaned=%u record1_cleaned=%u producer0_attempted=%u producer1_attempted=%u producer0_verified=%u producer1_verified=%u notify_attempted=%u notify_sent=%u work_submitted=%u samples=%u observe_polls=%u terminal_result=%d\n",
  phase,gfx_cold_draw_intent,gfx_cold_record_attempted[0],gfx_cold_record_attempted[1],
  gfx_cold_record_cleaned[0],gfx_cold_record_cleaned[1],
  gfx_cold_producer_attempted[0],gfx_cold_producer_attempted[1],
  gfx_cold_producer_verified[0],gfx_cold_producer_verified[1],
  gfx_cold_draw_notify_attempted,gfx_cold_draw_notify_sent,recovery_work_submitted,
  gfx_cold_observation_samples,gfx_cold_observe_polls,gfx_cold_terminal_result);
 pr_info("m4rch gfx-cold-render-application: phase=%s counter=%llu recovery_phase=%u host_stop=%u request_state=%u request_flag=%u cached=1 operand_samples_atomic=0\n",
  phase,(unsigned long long)gfx_cold_counter,gfx_cold_phase,gfx_cold_host_stop,
  gfx_cold_request_state,gfx_cold_request_flag);
}

static int gfx_cold_refuse(const char *condition,int result)
{
 gfx_cold_refusal=condition;gfx_cold_sealed=true;
 gfx_cold_terminal_result=result>0?-EIO:result;
 return gfx_cold_terminal_result;
}

static bool gfx_cold_live(void)
{
 unsigned int i;
 if(gfx_cold_identity_captured) gfx_cold_identities_preserved=false;
 if(!consumer || !held || !asc || !mbox || !asc_region || !mbox_region ||
    !started || !root_sent || !installed || root_detached || !device_context_retained ||
    !resident_session || !gfx_coord_owner_retained() || !gfx_coord_owner_module_pinned ||
    !gfx_coord_owner_session.on_complete || !gfx_cold_ap_known() || gfx_cold_apps_started!=3 ||
    ARRAY_SIZE(owned)!=GFX_COLD_PAGES ||
    atomic_read(&consumer->dev.power.usage_count)!=1 ||
    READ_ONCE(consumer->dev.power.runtime_error) ||
    !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev) ||
    pm_runtime_suspended(&consumer->dev) || receive_crashed || receive_journal.status) return false;
 for(i=0;i<GFX_COLD_PAGES;i++) if(!owned[i]) return false;
 if(!bootstrap || !target_slot || !target_page) return false;
 if(!gfx_cold_identity_captured) return true;
 if(consumer!=gfx_cold_consumer || asc!=gfx_cold_asc || mbox!=gfx_cold_mbox ||
    bootstrap!=gfx_cold_bootstrap || borrowed_l1!=gfx_cold_borrowed_l1 ||
    target_page!=gfx_cold_target_page || target_slot!=gfx_cold_target_slot ||
    READ_ONCE(*target_slot)!=gfx_cold_root_word) return false;
 for(i=0;i<GFX_COLD_PAGES;i++)
  if(owned[i]!=gfx_cold_pages[i] || page_to_phys(owned[i])!=gfx_cold_page_pa[i]) return false;
 gfx_cold_identities_preserved=true;
 return true;
}

static bool gfx_cold_capture_identity(void)
{
 unsigned int i;
 if(gfx_cold_identity_captured || !gfx_cold_live()) return false;
 gfx_cold_consumer=consumer;gfx_cold_asc=asc;gfx_cold_mbox=mbox;
 gfx_cold_bootstrap=bootstrap;gfx_cold_borrowed_l1=borrowed_l1;
 gfx_cold_target_page=target_page;gfx_cold_target_slot=target_slot;
 gfx_cold_root_word=READ_ONCE(*target_slot);
 if(gfx_cold_root_word!=(page_to_phys(owned[borrowed_l1?1:0])|3)) return false;
 for(i=0;i<GFX_COLD_PAGES;i++) {
  gfx_cold_pages[i]=owned[i];gfx_cold_page_pa[i]=page_to_phys(owned[i]);
 }
 gfx_cold_identity_captured=true;return gfx_cold_live();
}

static void gfx_cold_read_application(void)
{
 gfx_cold_counter=recovery_read64(RECOVERY_STATUS+0x48f0);
 gfx_cold_phase=recovery_read32(RECOVERY_STATUS+0x4900);
 gfx_cold_host_stop=recovery_read32(RECOVERY_STATUS+0x4910);
 gfx_cold_request_state=recovery_read32(RECOVERY_REQUEST);
 gfx_cold_request_flag=recovery_read32(RECOVERY_REQUEST+4);
 gfx_cold_control[0]=recovery_read32(RECOVERY_CONTROL);
 gfx_cold_control[1]=recovery_read32(RECOVERY_CONTROL+8);
 gfx_cold_control[2]=recovery_read32(RECOVERY_CONTROL+16);
 gfx_cold_trace_after=recovery_read32(RECOVERY_TRACE_MASK);
}

static bool gfx_cold_guard(unsigned int count,bool idle,unsigned int trace)
{
 struct apple_pmgr_gfx_reset_observation physical;
 if(!gfx_cold_live() || !recovery_messages()) return false;
 if(gfx_cold_snapshot("cold-guard",count,&physical) || !physical.domain_on ||
    (physical.before&0x80001cffU)!=0xffU) return false;
 gfx_cold_read_application();
 return !gfx_cold_counter && !gfx_cold_phase && !gfx_cold_host_stop &&
  !gfx_cold_request_state && !gfx_cold_request_flag &&
  gfx_cold_control[0]==count && gfx_cold_control[1]==count && gfx_cold_control[2]==count &&
  gfx_cold_trace_after==trace && (!idle || recovery_idle()) && gfx_cold_live();
}

static bool gfx_cold_immutable_backing(void)
{
 unsigned int page,i;
 if(!gfx_cold_live()) return false;
 for(page=0;page<POOL_PAGES;page++) {
  u8 *p=page_address(owned[POOL_FIRST_PAGE+page]);
  recovery_invalidate(p,PAGE_SIZE);
  for(i=0;i<PAGE_SIZE;i++) {
   size_t offset=(size_t)page*PAGE_SIZE+i;
   u8 expected=offset<sizeof(job_bytes)?((const u8 *)job_bytes)[offset]:0;
   if(READ_ONCE(p[i])!=expected) return false;
  }
 }
 for(page=0;page<RENDER_BACKING_PAGES;page++) {
  u8 *p=page_address(owned[RENDER_FIRST_PAGE+page]);
  recovery_invalidate(p,PAGE_SIZE);
  if(memcmp(p,render_bytes+(size_t)page*PAGE_SIZE,PAGE_SIZE)) return false;
 }
 return gfx_cold_live();
}

static bool gfx_cold_control_record(void)
{
 u8 *p=recovery_ptr(GFX_COLD_CONTROL_RECORD);unsigned int i;
 recovery_invalidate(p,64);
 if(READ_ONCE(p[0])!=0x16) return false;
 for(i=1;i<64;i++) if(READ_ONCE(p[i])) return false;
 gfx_cold_record_verified=true;return true;
}

static int gfx_cold_wait_control(unsigned int count)
{
 unsigned long until=jiffies+msecs_to_jiffies(GFX_COLD_CONTROL_TIMEOUT_MS);
 unsigned int polls;
 for(polls=0;polls<GFX_COLD_CONTROL_POLLS;polls++) {
  if(!time_before(jiffies,until)) return -ETIMEDOUT;
  gfx_cold_control_polls++;
  if(!gfx_cold_live() || !recovery_messages()) return -EIO;
  gfx_cold_read_application();
  if(gfx_cold_counter || gfx_cold_phase || gfx_cold_host_stop ||
     gfx_cold_request_state || gfx_cold_request_flag) return -EBUSY;
  if(gfx_cold_control[0]>count || gfx_cold_control[1]>count || gfx_cold_control[2]!=count)
   return -EPROTO;
  if(gfx_cold_control[0]==count && gfx_cold_control[1]==count) return 0;
  usleep_range(1000,2000);
 }
 return -ETIMEDOUT;
}

static bool gfx_cold_notify(const char *phase,u64 packet,bool *attempted,bool *sent)
{
 u32 tx;
 if(*attempted || !gfx_cold_live()) return false;
 *attempted=true;
 pr_info("m4rch gfx-cold-render-tx: phase=%s endpoint=33 packet=%#llx attempted=1 sent=0 sample_index=%u elapsed_ms=%u\n",
  phase,(unsigned long long)packet,gfx_cold_sample_index,gfx_cold_elapsed_ms);
 tx=readl(mbox+0x110);
 if(tx==~0U || (tx&BIT(16)) || !gfx_cold_live()) return false;
 wmb();writeq(packet,mbox+0x800);writeq(33,mbox+0x808);*sent=true;
 pr_info("m4rch gfx-cold-render-tx: phase=%s endpoint=33 packet=%#llx attempted=1 sent=1 sample_index=%u elapsed_ms=%u\n",
  phase,(unsigned long long)packet,gfx_cold_sample_index,gfx_cold_elapsed_ms);
 return true;
}

static int gfx_cold_fresh_control(void)
{
 int ret;
 if(gfx_cold_control_intent || !gfx_cold_guard(32,true,3) ||
    !gfx_cold_immutable_backing() || !gfx_cold_control_record())
  return gfx_cold_refuse("cold-control-baseline",-EBUSY);
 memcpy(gfx_cold_baseline_control,gfx_cold_control,sizeof(gfx_cold_control));
 gfx_cold_trace_before=gfx_cold_trace_after;
 gfx_cold_control_intent=true;gfx_cold_log("control-intent",0);
 if(!gfx_cold_guard(32,true,3) || !gfx_cold_control_record())
  return gfx_cold_refuse("control-intent-recheck",-EBUSY);
 gfx_cold_trace_attempted=true;recovery_write32(RECOVERY_TRACE_MASK,0);
 if(recovery_read32(RECOVERY_TRACE_MASK)) return gfx_cold_refuse("trace-mask-readback",-EIO);
 gfx_cold_control_producer_attempted=true;recovery_write32(RECOVERY_CONTROL+16,33);
 if(recovery_read32(RECOVERY_CONTROL+16)!=33) return gfx_cold_refuse("control-producer-readback",-EIO);
 if(!gfx_cold_notify("control-notify",0x0084000000000000ULL,
                    &gfx_cold_control_notify_attempted,&gfx_cold_control_notify_sent))
  return gfx_cold_refuse("control-notify",-EIO);
 ret=gfx_cold_wait_control(33);
 if(ret) return gfx_cold_refuse("fresh-control-wait",ret);
 if(!gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())
  return gfx_cold_refuse("fresh-control-recheck",-EBUSY);
 memcpy(gfx_cold_ready_control,gfx_cold_control,sizeof(gfx_cold_control));
 gfx_cold_control_ready=true;gfx_cold_log("control-ready",0);return 0;
}

static int gfx_cold_sample(const char *phase,unsigned int index,unsigned long start)
{
 gfx_cold_sample_index=index;gfx_cold_elapsed_ms=jiffies_to_msecs(jiffies-start);
 gfx_cold_sample_jiffies=jiffies;
 pr_info("m4rch gfx-cold-render-sample: phase=%s sample_index=%u elapsed_ms=%u sample_jiffies=%lu begin=1 complete=0 operand_samples_atomic=0\n",
  phase,index,gfx_cold_elapsed_ms,gfx_cold_sample_jiffies);
 if(!gfx_cold_live()) return -EIO;
 gfx_cold_read_application();
 /* A failed KSM map must not retain a preceding sample's valid fault flag. */
 gfx_cold_fault_valid=false;gfx_cold_fault_info=0;gfx_cold_fault_addr=0;
 ksm_status_sample(phase);joined_output_sample(phase);
 gfx_cold_observation_samples++;
 pr_info("m4rch gfx-cold-render-sample: phase=%s sample_index=%u elapsed_ms=%u sample_jiffies=%lu begin=0 complete=1 fault_valid=%u fault_info=%#llx fault_addr=%#llx journal_used=%u journal_status=%#x operand_samples_atomic=0\n",
  phase,index,gfx_cold_elapsed_ms,gfx_cold_sample_jiffies,gfx_cold_fault_valid,
  (unsigned long long)gfx_cold_fault_info,(unsigned long long)gfx_cold_fault_addr,
  receive_journal.used,receive_journal.status);
 if(!gfx_cold_fault_valid) return -ENODATA;
 if(gfx_cold_fault_info || gfx_cold_fault_addr) return -EIO;
 return gfx_cold_live()?0:-EIO;
}

static int gfx_cold_publish_draw(void)
{
 unsigned int i;
 if(gfx_cold_draw_intent || !gfx_cold_control_ready ||
    !gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())
  return gfx_cold_refuse("draw-admission",-EBUSY);
 if(gfx_cold_sample("before-submit",0,jiffies)) return gfx_cold_refuse("before-submit-sample",-EIO);
 gfx_cold_draw_intent=true;recovery_work_submitted=true;gfx_cold_log("draw-intent",0);
 if(!gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())
  return gfx_cold_refuse("draw-intent-recheck",-EBUSY);
 for(i=0;i<2;i++) {
  u8 *p=recovery_ptr(recovery_work_rings[i]);
  if(!gfx_cold_live()) return gfx_cold_refuse("draw-record-ownership",-EIO);
  gfx_cold_record_attempted[i]=true;
  recovery_invalidate(p,24);memcpy(p,recovery_work_records[i],24);recovery_clean(p,24);
  gfx_cold_record_cleaned[i]=true;
  pr_info("m4rch gfx-cold-render-record: phase=record-cleaned index=%u bytes=24 copy_attempted=1 cleaned=1 producer_attempted=0 producer_verified=0\n",i);
  if(!gfx_cold_live()) return gfx_cold_refuse("draw-producer-ownership",-EIO);
  gfx_cold_producer_attempted[i]=true;recovery_write32(recovery_work_cursors[i]+16,1);
  gfx_cold_producer_verified[i]=recovery_read32(recovery_work_cursors[i]+16)==1;
  pr_info("m4rch gfx-cold-render-record: phase=producer-published index=%u bytes=24 copy_attempted=1 cleaned=1 producer_attempted=1 producer_verified=%u\n",
   i,gfx_cold_producer_verified[i]);
  if(!gfx_cold_producer_verified[i]) return gfx_cold_refuse("draw-producer-readback",-EIO);
 }
 if(!gfx_cold_notify("draw-notify",0x0083000000000000ULL,
                    &gfx_cold_draw_notify_attempted,&gfx_cold_draw_notify_sent))
  return gfx_cold_refuse("draw-notify",-EIO);
 gfx_cold_observe_start=jiffies;gfx_cold_log("draw-published",0);return 0;
}

static int gfx_cold_observe(void)
{
 static const unsigned int times[]={0,100,1000,5000,15000};
 unsigned int next=0;
 unsigned long until=gfx_cold_observe_start+msecs_to_jiffies(GFX_COLD_OBSERVE_MS);
 for(gfx_cold_observe_polls=0;gfx_cold_observe_polls<GFX_COLD_OBSERVE_POLLS;gfx_cold_observe_polls++) {
  if(!gfx_cold_live() || !recovery_messages()) return gfx_cold_refuse("observe-rx-or-ownership",-EIO);
  if(next<ARRAY_SIZE(times) &&
     time_after_eq(jiffies,gfx_cold_observe_start+msecs_to_jiffies(times[next]))) {
   int ret=gfx_cold_sample("post-submit",next+1,gfx_cold_observe_start);
   if(ret) return gfx_cold_refuse("post-submit-sample",ret);
   next++;
  }
  if(time_after_eq(jiffies,until)) {
   if(next!=ARRAY_SIZE(times)) return gfx_cold_refuse("observe-incomplete",-ETIMEDOUT);
   gfx_cold_complete=true;return 0;
  }
  usleep_range(1000,2000);
 }
 return gfx_cold_refuse("observe-poll-limit",-ETIMEDOUT);
}

static void gfx_cold_stop_software(int result)
{
 /* Synchronous module-init observation owns the lock throughout. No worker is
  * scheduled and this stops the only RX/journal writer, retaining firmware/PM. */
 gfx_cold_terminal_result=result;gfx_cold_running=false;
 receive_enabled=false;recovery_resident=false;
 gfx_cold_software_stopped=true;gfx_cold_sealed=true;
 gfx_cold_log("retained-final",result);
}

static int gfx_cold_run(void)
{
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(gfx_cold_pipeline_intent) return -EALREADY;
 gfx_cold_pipeline_intent=true;gfx_cold_running=true;gfx_coord_owner_pin();
 gfx_cold_log("pipeline-intent",0);
 if(!gfx_cold_capture_identity()) {ret=gfx_cold_refuse("cold-identity",-EBUSY);goto done;}
 ret=gfx_cold_wait_control(32);
 if(ret) {ret=gfx_cold_refuse("initial-control-wait",ret);goto done;}
 ret=gfx_cold_fresh_control();if(ret)goto done;
 ret=gfx_cold_publish_draw();if(ret)goto done;
 ret=gfx_cold_observe();
done:
 gfx_cold_stop_software(ret);return ret;
}

static int gfx_cold_startup_retained(const char *condition,int result)
{
 mutex_lock(&graph_io_lock);gfx_coord_owner_pin();
 gfx_cold_pipeline_intent=true;gfx_cold_refuse(condition,result);
 gfx_cold_stop_software(gfx_cold_terminal_result);mutex_unlock(&graph_io_lock);return 0;
}

static int gfx_cold_diagnostic(const char *command)
{
 lockdep_assert_held(&graph_io_lock);
 if(!sysfs_streq(command,"sample") && !sysfs_streq(command,"gfx-snapshot")) return -EPERM;
 if(gfx_cold_running || !gfx_cold_software_stopped) return -EBUSY;
 gfx_cold_log("diagnostic-cached",gfx_cold_terminal_result);return 0;
}
