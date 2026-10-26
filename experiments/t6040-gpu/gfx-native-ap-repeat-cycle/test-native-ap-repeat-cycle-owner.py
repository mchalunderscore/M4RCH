#!/usr/bin/env python3
"""Qualify actual bounded E1/E2/E3 C flow and isolation with RAM-only ASan/UBSan mocks."""
import argparse,hashlib,json,os,runpy,subprocess,tempfile,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_TEST=HERE.parent/'gfx-native-ap-retained-cycle/test-native-ap-retained-cycle-owner.py'
BASE_TEST_SHA='30a202db12b322b058f284e165046c0c8ff93ac569e6bf0f922944b170c672e5'
BASE_SOURCE=ROOT/'out/gfx-native-ap-retained-cycle/prepared-owner-v2'
FROZEN_Q=ROOT/'out/gfx-native-ap-retained-cycle/owner-qualification-v2.json'
FROZEN_Q_SHA='aa875ccdecb07b2944dee2066a53d955b613582929e6e232581dd4b4b096d334'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def extract(t,marker):
 a=t.index(marker);b=t.index('{',a);c=b+1;depth=1
 while depth:depth+=(t[c]=='{')-(t[c]=='}');c+=1
 return t[a:c]
def replace_function(t,marker,new):
 old=extract(t,marker);return t.replace(old,new,1)
MOCK=r'''
#define R(f) (*(gfx_ap_repeat_current_epoch==3?&gfx_ap_repeat_third_##f:&gfx_retained_cycle_##f))
static bool reference_owned_for_epoch(void){return gfx_ap_repeat_current_epoch==3?gfx_ap_repeat_third_third_ref_held:gfx_retained_cycle_second_ref_held;}
static void inject_on_phase(const char *row)
{
 if(strstr(row,"phase=retained-ap-on-skip-intent")||strstr(row,"phase=second-pwr-gate-intent")||strstr(row,"phase=third-pwr-gate-intent")) {
  if(is("intent-ap-unknown"))gfx_ap_remote_known=false;
  if(is("intent-identity"))*target_slot^=0x4000;
  if(is("intent-error"))consumer->dev.power.runtime_error=-EIO;
  if(is("intent-start"))control44=0;
 }
 if(strstr(row,"phase=boot-running-observed")) {
  if(is("skip-capacity-zero"))R(records)=16;
  if(is("skip-missing-running"))R(boot_running_observed)=false;
 }
}
static void inject_after_on(void)
{
 status48=is("post-on-6e")?0x6e:0x6d;
 if(is("post-on-start"))control44=START;
}
static void inject_after_intent(void)
{if(is("start-intent-error"))consumer->dev.power.runtime_error=-EIO;}
static int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o)
{
 snapshot_calls++;o->valid=APPLE_PMGR_GFX_VALID_BEFORE;o->domain_on=held;
 o->before=held?0x1f0003ff:0x0f000300;
 if(is("fresh-off-busy")&&!held&&!get_done)o->before=0x0f000b00;
 if(is("fresh-off-error")&&!held&&!get_done)return -EIO;
 if(is("active-busy")&&held)o->before=0x1f000bff;
 if(is("active-snapshot-error")&&held)return -EIO;
 if(is("second-off-busy")&&gfx_ap_repeat_current_epoch>1&&R(pm_put_attempted)&&!held&&put_done)o->before=0x0f000b00;
 if(is("second-off-error")&&gfx_ap_repeat_current_epoch>1&&R(pm_put_attempted)&&!held&&put_done)return -EIO;
 if(is("snapshot-invalid"))o->valid=0;
 return 0;
}
static int pm_runtime_resume_and_get(struct fake_device *d)
{
 assert(graph_io_lock==1&&!held&&!d->power.usage_count&&put_done);
 assert(gfx_ap_repeat_current_epoch==2||gfx_ap_repeat_current_epoch==3);
 assert(gfx_ap_repeat_current_epoch==3?gfx_ap_repeat_third_pm_get_attempted:gfx_retained_cycle_pm_get_attempted);
 pmgets++;assert(pmgets==gfx_ap_repeat_current_epoch-1);
 if(is("pm-get-negative"))return -EIO;
 d->power.usage_count=1;d->active=true;d->suspended=false;d->power.runtime_status=0;
 get_done=true;put_done=false;stage=1;control44=0;status48=0x6c;pos=count=0;epoch_requests=epoch_starts=epoch_cpuwrites=epoch_hellos=epoch_mapacks=0;
 if(is("pm-get-usage"))d->power.usage_count=2;
 if(is("pm-get-error"))d->power.runtime_error=-EIO;
 if(is("after-get-pa"))owned[7]->pa+=0x4000;
 if(is("after-get-root"))*target_slot^=0x4000;
 if(is("pre-on-6d"))status48=0x6d;
 if(is("pre-on-6e"))status48=0x6e;
 return 0;
}
static int pm_runtime_put_sync_suspend(struct fake_device *d)
{
 assert(graph_io_lock==1&&!held&&d->power.usage_count==1&&!put_done);
 if(gfx_ap_repeat_current_epoch==1)assert(gfx_native_powergate_cpu_stopped&&gfx_coord_owner_session.off_complete&&gfx_poweroff_pm_attempted);
 else assert(R(cpu_stopped)&&R(coord_session).off_complete&&R(pm_put_attempted)&&!reference_owned_for_epoch());
 pmputs++;assert(pmputs==gfx_ap_repeat_current_epoch);put_done=true;get_done=false;
 d->power.usage_count=0;d->active=false;d->suspended=true;d->power.runtime_status=2;
 if(is("pm-put-error")){d->power.runtime_error=-EIO;return -EIO;}
 if(is("pm-put-accounting"))d->power.usage_count=1;
 return 0;
}
static u32 readl(void *p)
{
 if(cold_phase) {
  if(p==(char*)mbox+0x110)return is("cold-tx-full")?BIT(16):0;
  assert(p==(char*)mbox+0x114);return cold_ready?0:EMPTY;
 }
 assert(graph_io_lock==1&&held&&get_done&&!put_done);hwreads++;
 if(put_done)reads_after_put++;
 if(p==(char*)asc+0x44) {
  if(is("control-invalid"))return ~0U;
  if(epoch_cpuwrites==1&&is("start-reasserted"))control44|=START;
  return control44;
 }
 if(p==(char*)asc+0x48) {
  if(is("status-invalid"))return ~0U;
  if(epoch_requests&&is("idle-timeout"))return 0x6c;
  return status48;
 }
 if(p==(char*)mbox+0x110) {
  if(is("tx-invalid"))return ~0U;
  if(is("tx-full"))return BIT(16);
  if(gfx_ap_repeat_current_epoch>1&&R(request_attempted)&&!epoch_requests&&is("request-intent-tx-full"))return BIT(16);
  return 0;
 }
 if(p==(char*)mbox+0x114) {
  if(is("rx-invalid"))return ~0U;
  if(epoch_requests&&pos==count&&is("post-ack-rx-pending"))return 0;
  if(gfx_ap_repeat_current_epoch>1&&R(host_on_skip_attempted)&&!R(host_on_skipped)&&is("skip-intent-rx-pending"))return 0;
  return pos<count?0:EMPTY;
 }
 assert(false);return 0;
}
static u64 readq(void *p)
{
 if(cold_phase) {
  assert(cold_ready);if(p==(char*)mbox+0x830)return cold_message;
  assert(p==(char*)mbox+0x838);cold_ready=false;return cold_metadata;
 }
 assert(graph_io_lock==1&&held&&get_done&&pos<count&&!put_done);
 if(p==(char*)mbox+0x830)return messages[pos];
 assert(p==(char*)mbox+0x838);u64 value=metadata[pos++];
 if(epoch_requests&&is("late-ack"))jiffies+=2000;
 if(pos==4&&is("boot-late"))jiffies+=4000;
 return value;
}
static void writeq(u64 value,void *p)
{
 if(cold_phase) {
  if(p==(char*)mbox+0x808){assert(value==0);return;}
  assert(p==(char*)mbox+0x800&&value==GFX_RETAINED_CYCLE_HOST_ON&&gfx_ap_cold_request_write_attempted);
  cold_writes++;assert(cold_writes==1);cold_ready=true;
  if(firmware_ap_state==33){cold_message=0x0010110001de4000ULL;cold_metadata=1;return;}
  firmware_ap_state=33;cold_message=is("cold-reply-word")?0x00b0000000010020ULL:GFX_RETAINED_CYCLE_HOST_ON;cold_metadata=0;return;
 }
 assert(graph_io_lock==1&&held&&get_done&&!put_done);
 if(p==(char*)mbox+0x808){assert(value==0);return;}
 assert(p==(char*)mbox+0x800);
 if(value==GFX_RETAINED_CYCLE_HOST_ON){hostons++;assert(!"retained B20 forbidden: firmware AP33 would panic");}
 if(value==GFX_NATIVE_POWERGATE_REQUEST) {
  assert(!epoch_requests&&pos==count);epoch_requests++;requests++;stage=3;firmware_iop_state=2;
  if(gfx_ap_repeat_current_epoch==1)assert(gfx_native_powergate_request_attempted);
  else assert(R(request_attempted)&&R(host_on_skipped)&&reference_owned_for_epoch()&&epoch_hellos==1&&epoch_mapacks==2);
  if(is("no-ack")||is("ack-clock-stalled"))return;
  messages[count]=is("ack-boot20")?GFX_RETAINED_CYCLE_BOOT_RUNNING:is("ack-host20")?GFX_RETAINED_CYCLE_HOST_ON:is("ack-wrong")?0x0070000000000220ULL:is("ack-one")?0x0070000000000201ULL:0x0070000000000202ULL;
  metadata[count]=is("ack-endpoint")?32:0;count++;return;
 }
 assert(gfx_ap_repeat_current_epoch>1&&epoch_starts==1);
 if(((value>>52)&0xf)==2){assert(value==0x00200000000c000cULL&&!epoch_hellos);epoch_hellos++;hellos++;}
 else {
  assert(((value>>52)&0xf)==8&&epoch_mapacks<2);
  assert(value==(epoch_mapacks?0x0088000100000000ULL:0x0080000000000001ULL));epoch_mapacks++;mapacks++;
 }
}
static void writel(u32 value,void *p)
{
 assert(graph_io_lock==1&&held&&get_done&&!put_done&&p==(char*)asc+0x44);
 if(value&START) {
  assert(gfx_ap_repeat_current_epoch>1&&R(start_attempted)&&R(boundary_qualified)&&!epoch_starts);
  starts++;epoch_starts++;stage=2;firmware_iop_state=8;assert(firmware_ap_state==33);
  if(!is("start-dropped"))control44=value;status48=0x6d;
  if(is("no-hello")||is("clock-stalled"))return;
  messages[0]=is("hello-version")?0x00100000000b000bULL:0x00100000000c000cULL;metadata[0]=0;
  messages[1]=0x0080000000000003ULL;metadata[1]=0;
  messages[2]=is("map-bitmap")?0x0088000100000001ULL:0x0088000100000003ULL;metadata[2]=0;
  messages[3]=is("boot-host20")?GFX_RETAINED_CYCLE_HOST_ON:GFX_RETAINED_CYCLE_BOOT_RUNNING;
  metadata[3]=is("boot-endpoint")?1:0;count=is("boot-missing")?3:4;pos=0;return;
 }
 assert(epoch_requests==1);cpuwrites++;epoch_cpuwrites++;
 if(epoch_cpuwrites==1&&is("clear10-dropped"))return;
 if(epoch_cpuwrites==2&&is("clear20-dropped")){control44=value|0x20;return;}
 control44=value;
}
'''
PRINFO=r'''
static void pr_info(const char *fmt,...)
{
 char row[2048];va_list ap;va_start(ap,fmt);int n=vsnprintf(row,sizeof(row),fmt,ap);va_end(ap);
 assert(n>0&&(size_t)n<sizeof(row)&&row[n-1]=='\n');
 if(strstr(row,"m4rch gfx-native-powergate-drain")==row || strstr(row,"m4rch gfx-native-ap-repeat-coordinate:")==row || strstr(row,"m4rch gfx-poweroff-")==row || strstr(row,"m4rch gfx-coordinate-")==row) {
  assert(n<512);if((unsigned int)n>maximum_log_row)maximum_log_row=n;
 }
 bool own=strstr(row,"m4rch gfx-native-ap-repeat-cycle:")==row||strstr(row,"m4rch gfx-native-ap-repeat-cycle-")==row||strstr(row,"m4rch gfx-native-ap-repeat-third:")==row||strstr(row,"m4rch gfx-native-ap-repeat-third-")==row;
 if(own&&!strstr(row,"startup-retained")&&!strstr(row,"session:")) {
  assert(n<512);if((unsigned int)n>maximum_log_row)maximum_log_row=n;
  const char *family=strstr(row,"m4rch gfx-native-ap-repeat-third")==row?"m4rch gfx-native-ap-repeat-third":"m4rch gfx-native-ap-repeat-cycle";
  char head[100];bool grouped=false;
  const char *suffixes[]={": ","-state: ","-transport: ","-management: ","-off: ","-on: "};
  for(unsigned int k=0;k<6;k++){snprintf(head,sizeof(head),"%s%s",family,suffixes[k]);if(strstr(row,head)==row){assert(k==log_group_position);log_group_position=(k+1)%6;grouped=true;}}
  /* A diagnostic intentionally prints the two independent families. */
  if(!grouped&&strstr(row,"phase=diagnostic-current")){const char *other=gfx_ap_repeat_current_epoch==3?"m4rch gfx-native-ap-repeat-cycle":"m4rch gfx-native-ap-repeat-third";for(unsigned int k=0;k<6;k++){snprintf(head,sizeof(head),"%s%s",other,suffixes[k]);if(strstr(row,head)==row){assert(k==log_group_position);log_group_position=(k+1)%6;grouped=true;}}}
  if(!grouped)assert(strstr(row,"-rx:")||strstr(row,"-tx:"));
 }
 int written=snprintf(logs+log_used,sizeof(logs)-log_used,"[%12.6f] %s",jiffies/1000.0,row);assert(written>0&&(size_t)written<sizeof(logs)-log_used);log_used+=(size_t)written;
 if(strstr(row,"gfx-native-ap-repeat-coordinate:")&&strstr(row,"enabled=1 result=0"))inject_after_on();
 if((strstr(row,"gfx-native-ap-repeat-cycle: ")||strstr(row,"gfx-native-ap-repeat-third: "))&&strstr(row,"start-intent"))inject_after_intent();
 if(strstr(row,"gfx-native-ap-repeat-cycle: ")||strstr(row,"gfx-native-ap-repeat-third: "))inject_on_phase(row);
}
'''
MAIN=r'''
static void setup(const char *selected)
{
 fault_epoch=0;fault="none";
 if(!strncmp(selected,"e1-",3)||!strncmp(selected,"e2-",3)||!strncmp(selected,"e3-",3)){fault_epoch=(unsigned int)(selected[1]-'0');fault=selected+3;}
 if(!strcmp(selected,"success-second-low1")){fault_epoch=2;fault="ack-one";}
 if(!strcmp(selected,"success-third-low1")){fault_epoch=3;fault="ack-one";}
 graph_io_lock=1;held=true;recovery_resident=resident_session=true;
 asc_region=mbox_region=installed=root_sent=device_context_retained=true;
 gfx_reset_scope_owner_pinned=true;recovery_session_failed=true;receive_enabled=true;
 receive_journal.used=51176;consumer->dev=(struct fake_device){.power={1,0,0},.enabled=true,.active=true,.suspended=false};
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++){page_storage[i].pa=0x400000ULL+i*0x4000;owned[i]=&page_storage[i];}
 *target_slot=page_to_phys(owned[0])|3;get_done=true;control44=START;status48=0x6d;started=true;
 gfx_coord_owner_module_pinned=gfx_coord_owner_startup_retained=true;gfx_coord_owner_pmp_region=gfx_coord_owner_pmc_region=true;
 gfx_coord_owner_pmp=&ptd_request;gfx_coord_owner_pmc=votes;
 assert(gfx_coord_owner_transition(true)==0);
 cold_phase=true;receive_enabled=false;firmware_ap_state=!strcmp(selected,"cold-duplicate-ap")?33:0;
 if(!strncmp(selected,"cold-",5)){fault_epoch=1;fault=selected;}
 bool cold_ok=actual_cold_before_root();cold_phase=false;receive_enabled=true;
 if(!strncmp(selected,"cold-",5)) {assert(!cold_ok&&!root_publications);return;}
 assert(cold_ok&&cold_writes==1&&root_publications==1&&gfx_retained_cycle_ap_on_known());
 assert(!gfx_retained_cycle_identity_captured&&!gfx_native_powergate_intent&&!gfx_poweroff_gate_consumed);
}
static void poison_predecessor(const char *selected)
{
 #define BAD(n,s) if(!strcmp(selected,"predecessor-" n)){s;}
 BAD("complete",gfx_retained_cycle_complete=false)
 BAD("terminal",gfx_retained_cycle_terminal_result=-EIO)
 BAD("refusal",gfx_retained_cycle_refusal="prior-refusal")
 BAD("request",gfx_retained_cycle_request_attempted=false)
 BAD("ack",gfx_retained_cycle_ack_observed=false)
 BAD("ack-word",gfx_retained_cycle_ack_message=GFX_RETAINED_CYCLE_BOOT_RUNNING)
 BAD("ack-ep",gfx_retained_cycle_ack_metadata=32)
 BAD("ack-journal-meta",gfx_retained_cycle_journal[4].metadata=32)
 BAD("ack-journal",gfx_retained_cycle_journal[4].message=GFX_RETAINED_CYCLE_BOOT_RUNNING)
 BAD("clear10",gfx_retained_cycle_clear10_attempted=false)
 BAD("clear20",gfx_retained_cycle_clear20_attempted=false)
 BAD("cpu",gfx_retained_cycle_cpu_stopped=false)
 BAD("control",gfx_retained_cycle_control=START)
 BAD("off",gfx_retained_cycle_off_attempted=false)
 BAD("off-coord",gfx_retained_cycle_coord_session.off_complete=false)
 BAD("on-coord",gfx_retained_cycle_coord_session.on_complete=false)
 BAD("on-vote",gfx_retained_cycle_coord_on.votes_verified=2)
 BAD("off-vote",gfx_retained_cycle_coord_off.votes_verified=2)
 BAD("on-branch",gfx_retained_cycle_coord_on.ack_bypassed=false)
 BAD("off-branch",gfx_retained_cycle_coord_off.ack_bypassed=false)
 BAD("hello-count",gfx_retained_cycle_hello_reply_attempts=0)
 BAD("map-count",gfx_retained_cycle_map_reply_attempts=0)
 BAD("protocol-count",gfx_retained_cycle_polls=4002)
 BAD("ack-count",gfx_retained_cycle_ack_polls=2002)
 BAD("idle-count",gfx_retained_cycle_idle_polls=0)
 BAD("off-count",gfx_retained_cycle_off_samples=102)
 BAD("off-result",gfx_retained_cycle_coord_off.result=-EIO)
 BAD("on-result",gfx_retained_cycle_coord_on.result=-EIO)
 BAD("put",gfx_retained_cycle_pm_put_attempted=false)
 BAD("put-result",gfx_retained_cycle_pm_put_result=-EIO)
 BAD("snapshot",gfx_retained_cycle_off_snapshot_result=-EIO)
 BAD("physical",gfx_retained_cycle_off_word=0x0f000b00)
 BAD("accounting",gfx_retained_cycle_accounting_ok=false)
 BAD("root",*target_slot^=0x4000)
 BAD("page",owned[7]=&page_storage[174])
 BAD("pa",owned[7]->pa+=0x4000)
 BAD("current-held",held=true)
 BAD("current-error",consumer->dev.power.runtime_error=-EIO)
 BAD("current-usage",consumer->dev.power.usage_count=1)
 BAD("current-active",consumer->dev.active=true)
 BAD("ap20",gfx_ap_remote_state=0x21)
 #undef BAD
}
/* Snapshot every E2 static declaration (except baseline allocations captured
 * before E1) with byte copies generated from the actual header. This checks
 * E3 does not mutate any E2 protocol, ownership, coordinator or terminal field. */
static void freeze_e2(bool compare)
{
 /* FREEZE_E2_FIELDS */
}
int main(int argc,char **argv)
{
 assert(argc==2);setup(argv[1]);
 (void)hellos;(void)mapacks;(void)diagcalls;(void)cancels;(void)snapshot_calls;(void)firmware_iop_state;
 if(!strncmp(argv[1],"cold-",5)){printf("PASS %s\n",argv[1]);return 0;}
 if(!strcmp(argv[1],"third-before-first")){unsigned int oldreads=hwreads;int r=gfx_retained_cycle_command("gfx-native-ap-repeat-third");assert(r<0&&gfx_ap_repeat_unknown&&!pmgets&&!requests&&hwreads==oldreads);goto sealed;}
 if(strstr(argv[1],"-worker")) {
  recovery_session_failed=false;
  if(!strcmp(argv[1],"unknown-worker"))gfx_ap_repeat_unknown=true;
  if(!strcmp(argv[1],"second-worker"))gfx_retained_cycle_intent=true;
  if(!strcmp(argv[1],"third-worker"))gfx_ap_repeat_third_intent=true;
  graph_io_lock=0;struct work_struct work={0};recovery_receive_worker(&work);
  assert(!worker_reads&&!worker_schedules&&!pmgets&&!requests);printf("PASS %s maxrow=0\n",argv[1]);return 0;
 }
 int first=gfx_retained_cycle_command("gfx-powergate");
 if(fault_epoch==1){assert(first<0&&gfx_ap_repeat_unknown&&!pmgets);goto sealed;}
 assert(!first&&gfx_reset_scope_attempted&&gfx_retained_cycle_first_off()&&pmputs==1&&requests==1&&cpuwrites==2);
 assert(gfx_retained_cycle_identity_captured&&gfx_retained_cycle_identity(false)&&!held);
 if(!strcmp(argv[1],"third-before-second")){unsigned int oldreads=hwreads;assert(gfx_retained_cycle_command("gfx-native-ap-repeat-third")<0&&gfx_ap_repeat_unknown&&!pmgets&&hwreads==oldreads);goto sealed;}
 int second=gfx_retained_cycle_command("gfx-native-ap-repeat-cycle");
 if(fault_epoch==2&&strcmp(fault,"ack-one")){assert(second<0&&!gfx_retained_cycle_complete&&gfx_ap_repeat_unknown);goto sealed;}
 assert(!second&&gfx_ap_repeat_second_qualified()&&pmgets==1&&pmputs==2&&requests==2&&starts==1&&cpuwrites==4);
 freeze_e2(false);
 if(!strcmp(argv[1],"second-duplicate")) {
  assert(gfx_retained_cycle_command("gfx-native-ap-repeat-cycle")==-EALREADY&&gfx_ap_repeat_unknown);
  freeze_e2(true);assert(gfx_retained_cycle_complete&&!gfx_retained_cycle_terminal_result&&!strcmp(gfx_retained_cycle_refusal,"none"));goto sealed;
 }
 poison_predecessor(argv[1]);
 unsigned int oldgets=pmgets,oldreads=hwreads;
 int third=gfx_retained_cycle_command("gfx-native-ap-repeat-third");
 if(!strncmp(argv[1],"predecessor-",12)) {assert(third<0&&pmgets==oldgets&&hwreads==oldreads&&gfx_ap_repeat_unknown);goto sealed;}
 freeze_e2(true);
 if(fault_epoch==3&&strcmp(fault,"ack-one")){assert(third<0&&!gfx_ap_repeat_third_complete&&gfx_ap_repeat_unknown);goto sealed;}
 assert(!third&&gfx_ap_repeat_third_complete&&!gfx_ap_repeat_third_terminal_result&&!gfx_ap_repeat_unknown);
 assert(pmgets==2&&pmputs==3&&requests==3&&starts==2&&cpuwrites==6&&coordinate_on_calls==3&&coordinate_off_calls==3);
 assert(gfx_retained_cycle_records==5&&gfx_ap_repeat_third_records==5&&!held&&!hostons&&cold_writes==1);
 assert(&gfx_retained_cycle_journal[0]!= (void*)&gfx_ap_repeat_third_journal[0]);
 assert(gfx_ap_repeat_third_identity(false)&&!gfx_ap_repeat_third_identity(true));
 if(!strcmp(argv[1],"third-duplicate")) {assert(gfx_retained_cycle_command("gfx-native-ap-repeat-third")==-EALREADY&&gfx_ap_repeat_unknown&&gfx_ap_repeat_third_complete&&!gfx_ap_repeat_third_terminal_result);goto sealed;}
 if(!strcmp(argv[1],"row-bound")) {
  gfx_native_powergate_ack_polls=gfx_native_powergate_rx_messages=gfx_native_powergate_idle_polls=UINT32_MAX;
  gfx_native_powergate_control_before=gfx_native_powergate_control_after10=gfx_native_powergate_control_after20=gfx_native_powergate_idle_status=UINT32_MAX;
  gfx_native_powergate_ack_message=gfx_native_powergate_ack_metadata=UINT64_MAX;
  gfx_native_powergate_log("second-coordinate-off-intent",INT32_MIN);
  /* ROW_BOUND_FIELDS */
  gfx_retained_cycle_log("second-coordinate-off-intent",INT32_MIN);
  gfx_ap_repeat_third_log("third-coordinate-off-intent",INT32_MIN);
 }
 if(!strcmp(argv[1],"success"))fputs(logs,stdout);
 /* No fourth cycle is defined, even after clean E3. */
 assert(gfx_retained_cycle_command("gfx-native-ap-repeat-fourth")==-EPERM&&gfx_ap_repeat_unknown);
sealed:
 if(is("second-off-busy")||is("second-off-error")||is("pm-put-error")||is("pm-put-accounting")) {
  assert(pmgets==gfx_ap_repeat_current_epoch-1&&pmputs==gfx_ap_repeat_current_epoch&&requests==gfx_ap_repeat_current_epoch&&cpuwrites==2*gfx_ap_repeat_current_epoch);
 }
 {
 unsigned int og=pmgets,op=pmputs,os=starts,orr=requests,rd=hwreads;
 assert(gfx_retained_cycle_command("gfx-native-ap-repeat-cycle")==-EPERM);
 assert(gfx_retained_cycle_command("gfx-native-ap-repeat-third")==-EPERM);
 assert(gfx_retained_cycle_command("gfx-powergate")==-EPERM);
 assert(gfx_retained_cycle_attempt()==-EPERM&&gfx_ap_repeat_third_attempt()==-EPERM);
 assert(gfx_retained_cycle_command("gfx-snapshot")==0&&gfx_retained_cycle_command("sample")==0);
 assert(pmgets==og&&pmputs==op&&starts==os&&requests==orr&&hwreads==rd);
 graph_io_lock=0;struct work_struct work={0};recovery_receive_worker(&work);assert(!worker_reads&&!worker_schedules);graph_io_lock=1;
 }
 assert(!hostons&&cold_writes==1&&!reads_after_put&&!log_group_position&&maximum_log_row<512);
 printf("PASS %s get=%u request=%u put=%u maxrow=%u\n",argv[1],pmgets,requests,pmputs,maximum_log_row);
 return 0;
}
'''
FAULTS=['pm-get-negative','pm-get-usage','pm-get-error','after-get-pa','after-get-root','pre-on-6d','pre-on-6e','post-on-6e','post-on-start','start-intent-error','control-invalid','status-invalid','tx-invalid','tx-full','rx-invalid','start-dropped','no-hello','hello-version','map-bitmap','boot-host20','boot-endpoint','boot-missing','boot-late','skip-capacity-zero','skip-missing-running','skip-intent-rx-pending','intent-ap-unknown','intent-identity','intent-error','intent-start','request-intent-tx-full','no-ack','ack-clock-stalled','ack-boot20','ack-host20','ack-wrong','ack-endpoint','late-ack','post-ack-rx-pending','idle-timeout','clear10-dropped','clear20-dropped','start-reasserted','coord-on-write','coord-off-write','coord-on-vote','coord-off-vote','pm-put-error','pm-put-accounting','fresh-off-busy','fresh-off-error','active-busy','active-snapshot-error','second-off-busy','second-off-error','snapshot-invalid']
PREDECESSOR=['complete','terminal','refusal','request','ack','ack-word','ack-ep','ack-journal','clear10','clear20','cpu','control','off','off-coord','off-result','on-result','put','put-result','snapshot','physical','accounting','root','page','pa','current-held','current-error','current-usage','current-active','ap20']
PREDECESSOR+=['ack-journal-meta','on-coord','on-vote','off-vote','on-branch','off-branch','hello-count','map-count','protocol-count','ack-count','idle-count','off-count']
CASES=['success','success-second-low1','success-third-low1','row-bound','second-duplicate','third-duplicate','third-before-first','third-before-second','unknown-worker','second-worker','third-worker','cold-duplicate-ap','cold-reply-word','cold-tx-full']+['e1-'+x for x in ['no-ack','ack-boot20','clear10-dropped','coord-off-write','pm-put-error']]+['e%d-%s'%(n,f) for n in [2,3] for f in FAULTS]+['predecessor-'+x for x in PREDECESSOR]

def make_harness(source):
 assert sha(BASE_TEST)==BASE_TEST_SHA
 old=runpy.run_path(str(BASE_TEST));base=old['make_harness'](BASE_SOURCE)
 base=base[:base.index('static bool power_ack(unsigned int request, unsigned int reply, u16 state)')]
 base=base.replace('GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL').replace('gfx-native-ap-retained-cycle.h','gfx-native-ap-repeat-cycle.h').replace('gfx-retained-power-cycle-coordinate.h','gfx-ap-repeat-cycle-coordinate.h')
 base=base.replace('static const char *fault;','static const char *fault;\nstatic unsigned int gfx_ap_repeat_current_epoch=1,fault_epoch;static bool gfx_ap_repeat_unknown,gfx_ap_repeat_third_intent;\nstatic unsigned int epoch_requests,epoch_starts,epoch_cpuwrites,epoch_hellos,epoch_mapacks;')
 base=base.replace('#define RECOVERY_CONTROL 0x300000U','#define RECOVERY_CONTROL 0x300000U\n#define RECOVERY_POWER 0x400000U')
 base=base.replace(' if(o==RECOVERY_STATUS+0x4900)return 2;',' if(o==RECOVERY_POWER+0x652c)return 2;\n if(o==RECOVERY_STATUS+0x4900)return 2;')
 base=base.replace('u32 before,valid; bool domain_on;','u32 before,valid; bool domain_on;int operation_error,cleanup_error;')
 base=base.replace('static bool is(const char *s){return !strcmp(fault,s);}','static bool is(const char *s){return fault_epoch==gfx_ap_repeat_current_epoch&&!strcmp(fault,s);}')
 base=replace_function(base,'static void pr_info(const char *fmt,...)',PRINFO)
 base=base.replace('assert(p==&recovery_receive_work&&gfx_retained_cycle_intent);','assert(p==&recovery_receive_work);')
 base=base.replace('static int gfx_poweroff_pm_result,gfx_poweroff_snapshot_result;','static int gfx_poweroff_pm_result,gfx_poweroff_snapshot_result;static unsigned int gfx_poweroff_snapshot_count,gfx_poweroff_poll_delay_us;')
 base=base.replace('static int gfx_poweroff_attempt(void){assert(false);return -EIO;}','static int gfx_poweroff_attempt(void);\nstatic int gfx_coord_owner_before_off(void);\nstatic bool gfx_reset_scope_attempted;')
 base=base.replace('static struct gfx_coord_session gfx_coord_owner_session;','static struct gfx_coord_session gfx_coord_owner_session;\nstatic struct gfx_coord_observation gfx_coord_owner_on,gfx_coord_owner_off;\nstatic unsigned int gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events;')
 base=base.replace('static bool gfx_coord_owner_module_pinned,gfx_coord_owner_startup_retained;','static bool gfx_coord_owner_module_pinned,gfx_coord_owner_startup_retained;\nstatic bool gfx_coord_owner_retained(void){return gfx_coord_owner_startup_retained;}')
 # Replace hardware-only callbacks and copied fault infrastructure. Actual source functions remain included/extracted.
 for marker in ['static void inject_after_on(void)\n{','static void inject_after_intent(void)\n{','static void inject_on_phase(const char *row)\n{','static int gfx_poweroff_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o)\n{','static int pm_runtime_resume_and_get(struct fake_device *d)\n{','static int pm_runtime_put_sync_suspend(struct fake_device *d)\n{','static u32 readl(void *p)\n{','static u64 readq(void *p)\n{','static void writeq(u64 value,void *p)\n{','static void writel(u32 value,void *p)\n{','static void reset(const char *selected)\n{']:
  base=replace_function(base,marker,'')
 base=base.replace('static void inject_cold_phase(const char *row);','')
 if 'static void inject_cold_phase(const char *row)\n{' in base:base=replace_function(base,'static void inject_cold_phase(const char *row)\n{','')
 if 'static void invalidate_ap(const char *prefix)' in base:base=replace_function(base,'static void invalidate_ap(const char *prefix)','')
 base=base.replace('static void event(void *ctx,const char *s,unsigned int i,u64 v,u64 st,int r)\n{(void)ctx;(void)s;(void)i;(void)v;(void)st;(void)r;}',r'''static void event(void *ctx,const char *s,unsigned int i,u64 v,u64 st,int r)
{(void)ctx;pr_info("m4rch gfx-coordinate-event: epoch=%u phase=%s index=%u value=%#llx status=%#llx result=%d\n",gfx_ap_repeat_current_epoch,s,i,(unsigned long long)v,(unsigned long long)st,r);}''')
 worker=extract((source/'recovery-cycle.h').read_text(),'static void recovery_receive_worker(struct work_struct *work)\n{')
 base=replace_function(base,'static void recovery_receive_worker(struct work_struct *work)\n{',worker)
 # Replace E1 scope mocks with exact actual functions where they are meaningful to its full teardown flow.
 scope=(source/'gfx-reset-scope.h').read_text();coord=(source/'gfx-coordinate-owner.h').read_text();owner=(source/'asc-graph-init.c').read_text()
 base=replace_function(base,'static int gfx_reset_scope_result(const char *cmd,int ret)',extract(scope,'static int gfx_reset_scope_result('))
 funcs=[extract(scope,'static bool gfx_poweroff_accounting('),extract(scope,'static int gfx_poweroff_snapshot('),extract(scope,'static int gfx_poweroff_preconditions('),extract(scope,'static int gfx_poweroff_attempt(')]
 base+='\n'+MOCK+'\nstatic void recovery_sample(unsigned int index,const char *phase){(void)index;(void)phase;}\nstatic bool gfx_poweroff_accounting(const char *phase);\n'
 base+=extract(scope,'static void gfx_poweroff_dram(')+'\n'+extract(scope,'static void gfx_reset_scope_protocol(')+'\n'
 base+=extract(coord,'static int gfx_coord_owner_transition(')+'\n'+extract(coord,'static void gfx_coord_owner_log(')+'\n'
 base+='\n'.join(funcs)+'\n'+extract(coord,'static int gfx_coord_owner_before_off(')+'\n'
 cold=extract(owner,'static bool power_ack(unsigned int request, unsigned int reply, u16 state)')
 a=owner.index(' if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)');b=owner.index(' {',a);condition=owner[a+4:b].strip()
 base+='\n'+cold+'\nstatic bool crashlog_boot(void){return true;}\nstatic bool actual_cold_before_root(void){bool epmap=true;if '+condition+' {root_publications++;return true;}return false;}\n'
 header=(source/'gfx-native-ap-repeat-cycle.h').read_text();prefix=header[:header.index('static void gfx_retained_cycle_log(')]
 fields=[]
 for line in prefix.splitlines():
  if line.startswith('static ') and ';' in line and '(' not in line:
   fields += [f for f in re.findall(r'\bgfx_retained_cycle_\w+',line) if f!='gfx_retained_cycle_record']
 # Baseline identity fields also get copied and compared; arrays included.
 freeze='\n'.join('{static unsigned char saved_%s[sizeof(%s)];if(compare)assert(!memcmp(saved_%s,&%s,sizeof(%s)));else memcpy(saved_%s,&%s,sizeof(%s));}'%(f,f,f,f,f,f,f,f) for f in fields)
 main=MAIN.replace('/* FREEZE_E2_FIELDS */',freeze)
 rows=[]
 for pre in ['gfx_retained_cycle','gfx_ap_repeat_third']:
  for f in ['control','status','rx','tx','hello_reply_attempts','map_reply_attempts','appmap','records','polls','ack_polls','idle_polls','off_samples']:
   rows.append(f'{pre}_{f}=UINT32_MAX;')
  for f in ['ack_message','ack_metadata','boot_running_message','boot_running_metadata']:rows.append(f'{pre}_{f}=UINT64_MAX;')
  for f in ['pm_get_result','pm_put_result','off_snapshot_result','terminal_result']:rows.append(f'{pre}_{f}=INT32_MIN;')
  rows.append(f'{pre}_sample_jiffies=~0UL;')
 main=main.replace('/* ROW_BOUND_FIELDS */',''.join(rows))
 return base+'\n'+main

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
 if output.exists():raise ValueError('Never overwrite frozen qualification')
 receipt_path=source/'native-ap-repeat-cycle-owner-source-receipt.json';receipt=json.loads(receipt_path.read_text())
 for r in receipt['output_source_pins']:assert sha(source/r['name'])==r['sha256'],r['name']
 assert receipt['profile']['version']==12
 assert sha(FROZEN_Q)==FROZEN_Q_SHA;frozen=json.loads(FROZEN_Q.read_text());assert frozen['passed'] and frozen['case_count']==122
 results=[];harness=make_harness(source);env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 output.parent.mkdir(parents=True,exist_ok=True)
 harness_path=output.with_suffix('.actual-owner.c');harness_path.write_text(harness)
 tester_snapshot=output.with_suffix('.tester.py');tester_snapshot.write_bytes(Path(__file__).read_bytes())
 fixture_path=output.with_suffix('.success.log');epoch_pins=[]
 with tempfile.TemporaryDirectory(prefix='repeat-c-q-') as td:
  unit=Path(td)/'owner.c';unit.write_text(harness);binary=Path(td)/'owner'
  command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(unit),'-o',str(binary)]
  c=subprocess.run(command,capture_output=True,text=True)
  if c.returncode:raise RuntimeError(c.stdout+'\n'+c.stderr)
  for case in CASES:
   r=subprocess.run([str(binary),case],env=env,capture_output=True,text=True)
   if r.returncode:raise RuntimeError(case+'\n'+r.stdout+'\n'+r.stderr)
   if case=='success':
    full='\n'.join(x for x in r.stdout.splitlines() if 'm4rch ' in x)+'\n';fixture_path.write_text(full)
    start2=full.index('m4rch gfx-native-ap-repeat-cycle: phase=intent ');start2=full.rfind('[',0,start2)
    start3=full.index('m4rch gfx-native-ap-repeat-third: phase=intent ');start3=full.rfind('[',0,start3)
    for epoch,raw in [(1,full[:start2]),(2,full[start2:start3]),(3,full[start3:])]:
     path=output.with_suffix('.epoch%d.log'%epoch);path.write_text(raw);epoch_pins.append({'epoch':epoch,'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
   results.append({'case':case,'returncode':r.returncode,'stdout':r.stdout.splitlines()[-1]})
 pins=[{'path':str(receipt_path),'sha256':sha(receipt_path)},{'path':str(BASE_TEST),'sha256':BASE_TEST_SHA},{'path':str(FROZEN_Q),'sha256':FROZEN_Q_SHA},{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},{'path':str(harness_path),'sha256':sha(harness_path)},{'path':str(tester_snapshot),'sha256':sha(tester_snapshot)},{'path':str(fixture_path),'sha256':sha(fixture_path)}]
 pins += [{k:v for k,v in row.items() if k in ['path','sha256']} for row in epoch_pins]
 pins+=[{'path':str(source/r['name']),'sha256':r['sha256']} for r in receipt['output_source_pins']]
 q={'schema':'m4rch.gfx-native-ap-repeat-cycle-c-qualification.v1','passed':True,'ASan_UBSan':True,'hardware_access':False,'case_count':len(results),'actual_headers':True,'actual_complete_E1_E2_E3_flow':True,'actual_complete_six_row_groups':True,'second_log_row_count':6,'third_log_row_count':6,'both_retained_own_low1_or_low2_ACK_exercised':True,'post_put_faults_bound_to_own_epoch_put':True,'actual_first_powergate_and_scope_off':True,'actual_second_and_third_coordinate_core':True,'actual_receive_worker':True,'actual_cold_power_ack':True,'actual_cold_root_publication_condition':True,'exact_second_state_byte_immutability_during_third':True,'global_unknown_and_no_fourth_controls_exercised':True,'maximum_new_log_row_bytes':max(int(re.search(r'maxrow=(\d+)',r['stdout']).group(1)) for r in results if 'maxrow=' in r['stdout']),'source_path':str(source),'source_receipt_sha256':sha(receipt_path),'frozen_v11_composition':{'path':str(FROZEN_Q),'sha256':FROZEN_Q_SHA,'case_count':122,'rerun':False},'successful_epoch_log_pins':epoch_pins,'complete_successful_actual_C_log_fixture':{'path':str(fixture_path),'sha256':sha(fixture_path)},'input_pins':pins,'cases':results,'limitations':['RAM mocks qualify C ordering, isolation, seals and log parsing, not hardware behavior.','Original cold initialization and unmodified fixture/UAT contracts compose frozen qualification; no original kernel/module build or hardware action.','Fixed protocol polls do not bound runtime PM callback wallclock.']}
 with output.open('x') as f:json.dump(q,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'case_count':len(results),'maximum_new_log_row_bytes':q['maximum_new_log_row_bytes'],'output':str(output),'fixture':str(fixture_path),'hardware_access':False}))
if __name__=='__main__':main()
