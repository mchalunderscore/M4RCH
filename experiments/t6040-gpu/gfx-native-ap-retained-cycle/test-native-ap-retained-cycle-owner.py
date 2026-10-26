#!/usr/bin/env python3
"""Qualify actual new cold AP receipt/retained skip code with bounded RAM mocks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_TEST=HERE.parent/'gfx-native-running-cycle/test-native-running-cycle-owner.py'
BASE_TEST_SHA='82b0b6563edcb65690d0bf53b0ce71c242e6fccee96af71f0dc4c451aecc0b10'
FROZEN_C=ROOT/'out/gfx-native-idle-cycle/owner-qualification-final-v1.json'
FROZEN_C_SHA='5f1de50846c2b4b51488e37e103fa1277b17b20547f8a7c1390f288ec5b348f2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def extract_function(text,marker):
 start=text.index(marker);brace=text.index('{',start);end=brace+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]

COLD_MOCK=r'''
static bool cold_phase,cold_request_log,cold_reply_log;
static unsigned int cold_writes,root_publications,firmware_ap_state,firmware_iop_state;
static unsigned int cold_rows,cold_maximum_row;
static u64 cold_message,cold_metadata;
static bool cold_ready;
static void inject_cold_phase(const char *row);
'''
INJECT=r'''
static void inject_cold_phase(const char *row)
{
 if(strstr(row,"phase=request"))cold_request_log=true;
 if(strstr(row,"phase=reply")) {
  cold_reply_log=true;
  if(is("cold-reply-log-known"))gfx_ap_remote_known=false;
  if(is("cold-reply-log-state"))gfx_ap_remote_state=0x21;
  if(is("cold-reply-log-ownership"))gfx_ap_cold_request_write_attempted=false;
 }
}
static void invalidate_ap(const char *prefix)
{
 char key[100];
 #define FAIL(n,statement) snprintf(key,sizeof(key),"%s-%s",prefix,n);if(is(key)){statement;}
 FAIL("known",gfx_ap_remote_known=false)
 FAIL("state",gfx_ap_remote_state=0x21)
 FAIL("request",gfx_ap_cold_request_attempted=false)
 FAIL("write",gfx_ap_cold_request_write_attempted=false)
 FAIL("request-word",gfx_ap_cold_request_message^=1)
 FAIL("request-meta",gfx_ap_cold_request_metadata=1)
 FAIL("reply",gfx_ap_cold_reply_observed=false)
 FAIL("reply-word",gfx_ap_cold_reply_message^=1)
 FAIL("reply-meta",gfx_ap_cold_reply_metadata=1)
 FAIL("reply-meta-invalid",gfx_ap_cold_reply_metadata=~0ULL)
 #undef FAIL
}
static void inject_on_phase(const char *row)
{
 bool boot=strstr(row,"phase=boot-running-observed")!=NULL;
 bool intent=strstr(row,"phase=retained-ap-on-skip-intent")!=NULL;
 bool skipped=strstr(row,"phase=retained-ap-on-skipped")!=NULL;
 bool request=strstr(row,"phase=second-pwr-gate-intent")!=NULL;
 if(boot) {
  invalidate_ap("skip-before");
  if(is("skip-missing-running"))gfx_retained_cycle_boot_running_observed=false;
  if(is("skip-missing-map"))gfx_retained_cycle_endpoint_map=false;
  if(is("skip-missing-hello"))gfx_retained_cycle_hello_replied=false;
  if(is("skip-queued-b20")){messages[count]=GFX_RETAINED_CYCLE_HOST_ON;metadata[count++]=0;}
  if(is("skip-queued-ep1")){messages[count]=0x0010110001de4000ULL;metadata[count++]=1;}
  if(is("skip-capacity-one"))gfx_retained_cycle_records=15;
  if(is("skip-capacity-zero"))gfx_retained_cycle_records=16;
  if(is("skip-intent-used"))gfx_retained_cycle_host_on_skip_attempted=true;
 }
 if(intent||request) {
  const char *prefix=intent?"skip-intent":"request-intent";
  char key[100];invalidate_ap(prefix);
  #define FAIL(n,statement) snprintf(key,sizeof(key),"%s-%s",prefix,n);if(is(key)){statement;}
  FAIL("first",gfx_native_powergate_ack_observed=false)
  FAIL("identity",*target_slot^=0x4000)
  FAIL("pm-error",consumer->dev.power.runtime_error=-EIO)
  FAIL("usage",consumer->dev.power.usage_count=2)
  FAIL("ref",gfx_retained_cycle_second_ref_held=false)
  FAIL("start",control44=0)
  FAIL("running",gfx_retained_cycle_boot_running_observed=false)
  FAIL("map",gfx_retained_cycle_endpoint_map=false)
  FAIL("skip",gfx_retained_cycle_host_on_skipped=false)
  #undef FAIL
 }
 if(skipped) {
  invalidate_ap("after-skip");
  if(is("after-skip-intent"))gfx_retained_cycle_host_on_skip_attempted=false;
  if(is("after-skip-bit"))gfx_retained_cycle_host_on_skipped=false;
  if(is("after-skip-running"))gfx_retained_cycle_boot_running_observed=false;
  if(is("after-skip-map"))gfx_retained_cycle_endpoint_map=false;
 }
}
'''
MAIN=r'''
/* ACTUAL_COLD_POWER_ACK */
static bool crashlog_boot(void){return true;}
static bool actual_cold_before_root(void)
{
 bool epmap=true;
 if /* ACTUAL_COLD_ROOT_CONDITION */ {
  root_publications++;return true;
 }
 return false;
}
static void cold_setup(void)
{
 cold_phase=true;receive_enabled=false;firmware_ap_state=is("cold-duplicate-ap")?33:0;
 firmware_iop_state=8;cold_ready=false;
}
int main(int argc,char **argv)
{
 assert(argc==2);reset(argv[1]);cold_setup();
 (void)recovery_operation;(void)hwreads;(void)diagcalls;(void)cancels;(void)snapshot_calls;(void)firmware_iop_state;
 if(strstr(fault,"cold-")==fault&&!is("cold-status6d")) {
  bool ok;
  if(is("cold-forbidden-b0")||is("cold-forbidden-b201"))
   ok=power_ack(0xb,0xb,is("cold-forbidden-b0")?0:0x201);
  else ok=actual_cold_before_root();
  bool success=is("cold-success")||is("cold-repeat-intent");
  assert(ok==success);
  if(success) {
   assert(cold_writes==1&&root_publications==1&&gfx_retained_cycle_ap_on_known());
   assert(cold_rows==2&&firmware_ap_state==33&&cold_reply_log&&cold_request_log);
   if(is("cold-repeat-intent"))assert(!power_ack(0xb,0xb,0x20)&&cold_writes==1);
  } else assert(!root_publications);
  if(is("cold-duplicate-ap"))assert(cold_writes==1&&!gfx_ap_remote_known&&cold_metadata==1);
  if(is("cold-forbidden-b0")||is("cold-forbidden-b201"))assert(!cold_writes&&!cold_rows);
  assert(cold_writes<=1&&!hostons&&!requests&&!pmgets&&!pmputs&&!starts);
  assert(cold_maximum_row<512&&!log_group_position);
  printf("PASS %s cold_writes=%u root_publications=%u ret=%u cold_rows=%u maximum_new_log_row=%u\n",fault,cold_writes,root_publications,ok,cold_rows,maximum_log_row>cold_maximum_row?maximum_log_row:cold_maximum_row);return 0;
 }
 assert(actual_cold_before_root()&&cold_writes==1&&root_publications==1&&gfx_retained_cycle_ap_on_known());
 cold_phase=false;receive_enabled=true;pos=count=0;
 /* First management-only202 fixture changes IOP status, never AP state. */
 firmware_iop_state=2;assert(firmware_ap_state==33);
 invalidate_ap("mirror");
 if(is("first-history-false"))gfx_native_powergate_ack_observed=false;
 if(is("first-sealed-false"))gfx_reset_scope_sealed=false;
 if(is("first-failed-false"))recovery_session_failed=false;
 if(is("startup-unknown"))gfx_native_powergate_startup_unknown=true;
 if(is("row-bound")) {
  gfx_retained_cycle_pm_get_result=gfx_retained_cycle_pm_put_result=gfx_retained_cycle_off_snapshot_result=INT32_MIN;
  consumer->dev.power.usage_count=consumer->dev.power.runtime_error=consumer->dev.power.runtime_status=INT32_MIN;
  gfx_retained_cycle_control=gfx_retained_cycle_status=gfx_retained_cycle_rx=gfx_retained_cycle_tx=UINT32_MAX;
  gfx_retained_cycle_hello_reply_attempts=gfx_retained_cycle_map_reply_attempts=UINT32_MAX;
  gfx_retained_cycle_appmap=UINT32_MAX;gfx_retained_cycle_map_seen=UINT8_MAX;
  gfx_retained_cycle_records=gfx_retained_cycle_polls=gfx_retained_cycle_ack_polls=UINT32_MAX;
  gfx_retained_cycle_idle_polls=gfx_retained_cycle_off_samples=UINT32_MAX;
  gfx_retained_cycle_ack_message=gfx_retained_cycle_ack_metadata=UINT64_MAX;
  gfx_retained_cycle_boot_running_message=gfx_retained_cycle_boot_running_metadata=UINT64_MAX;
  gfx_ap_cold_request_message=gfx_ap_cold_request_metadata=gfx_ap_cold_reply_message=gfx_ap_cold_reply_metadata=UINT64_MAX;
  gfx_ap_remote_state=UINT32_MAX;gfx_retained_cycle_refusal="retained-ap-changed-after-skip-intent";
  gfx_retained_cycle_cold_ap_log("request");gfx_retained_cycle_cold_ap_log("reply");
  gfx_retained_cycle_log("second-coordinate-off-intent",INT32_MIN);
  assert(maximum_log_row<512&&cold_maximum_row<512&&!log_group_position);
  printf("PASS %s maximum_new_log_row=%u\n",fault,maximum_log_row>cold_maximum_row?maximum_log_row:cold_maximum_row);return 0;
 }
 if(is("queued-worker")) {
  gfx_retained_cycle_intent=true;graph_io_lock=0;struct work_struct work={0};recovery_receive_worker(&work);
  assert(!worker_reads&&!worker_schedules&&!pmgets&&!requests&&!hostons);
  printf("PASS %s maximum_new_log_row=%u\n",fault,maximum_log_row>cold_maximum_row?maximum_log_row:cold_maximum_row);return 0;
 }
 int ret=gfx_retained_cycle_command("gfx-native-ap-retained-cycle");
 bool success=is("success")||is("ack-one")||is("native-observed-6c-to-6d")||is("skip-capacity-one");
 if(success) {
  assert(ret==0&&gfx_retained_cycle_complete&&pmgets==1&&pmputs==1&&starts==1&&requests==1&&cpuwrites==2);
  assert(!hostons&&cold_writes==1&&gfx_retained_cycle_host_on_skipped&&gfx_retained_cycle_host_on_skip_attempted);
  assert(coordinate_on_calls==1&&coordinate_off_calls==1&&!held&&!gfx_retained_cycle_second_ref_held);
  assert(gfx_retained_cycle_records==(is("skip-capacity-one")?16:5));
  assert(gfx_retained_cycle_journal[3].message==GFX_RETAINED_CYCLE_BOOT_RUNNING);
  assert(gfx_retained_cycle_journal[is("skip-capacity-one")?15:4].message==(is("ack-one")?0x0070000000000201ULL:0x0070000000000202ULL));
 } else assert(ret<0&&!gfx_retained_cycle_complete);
 assert(!hostons&&cold_writes==1&&firmware_ap_state==33);
 assert(pmgets<=1&&pmputs<=1&&starts<=1&&requests<=1&&cpuwrites<=2&&!reads_after_put);
 if(strstr(fault,"mirror-")==fault)assert(!pmgets&&!starts&&!requests&&!pmputs);
 if(strstr(fault,"skip-")==fault||strstr(fault,"after-skip-")==fault||strstr(fault,"request-intent-")==fault) {
  if(!success)assert(!requests&&!cpuwrites&&!pmputs);
 }
 if(strstr(fault,"request-intent-")==fault)assert(gfx_retained_cycle_request_attempted&&!requests);
 if(is("ack-boot20")||is("ack-host20")||is("ack-endpoint")||is("ack-wrong")||is("no-ack")||is("ack-clock-stalled"))assert(requests==1&&!gfx_retained_cycle_ack_observed&&!cpuwrites&&!pmputs);
 if(is("first-history-false"))assert(!gfx_native_powergate_ack_observed&&!pmgets);
 if(is("first-sealed-false"))assert(!gfx_reset_scope_sealed&&!pmgets);
 if(is("first-failed-false"))assert(!recovery_session_failed&&!pmgets);
 unsigned int oldgets=pmgets,oldputs=pmputs,oldstarts=starts,oldreq=requests;
 if(gfx_retained_cycle_intent) {
  assert(gfx_retained_cycle_command("gfx-native-ap-retained-cycle")==-EALREADY);
  assert(gfx_retained_cycle_command("gfx-powergate")==-EPERM);
  assert(pmgets==oldgets&&pmputs==oldputs&&starts==oldstarts&&requests==oldreq);
 }
 assert(!log_group_position&&maximum_log_row<512&&cold_maximum_row<512);
 printf("PASS %s ret=%d get=%u start=%u request=%u put=%u records=%u maximum_new_log_row=%u\n",fault,ret,pmgets,starts,requests,pmputs,gfx_retained_cycle_records,maximum_log_row>cold_maximum_row?maximum_log_row:cold_maximum_row);
 return 0;
}
'''
COLD_CASES=['cold-success','cold-repeat-intent','cold-duplicate-ap','cold-forbidden-b0','cold-forbidden-b201','cold-tx-full','cold-tx-invalid','cold-rx-pending','cold-rx-invalid','cold-intent-rx-pending','cold-intent-rx-invalid','cold-intent-tx-full','cold-intent-tx-invalid','cold-no-reply','cold-clock-stalled','cold-reply-word','cold-reply-type','cold-reply-state','cold-reply-invalid','cold-reply-meta-invalid','cold-reply-ep1','cold-reply-late','cold-post-reply-rx-pending','cold-post-reply-rx-invalid','cold-reply-log-known','cold-reply-log-state','cold-reply-log-ownership']
MIRRORS=['known','state','request','write','request-word','request-meta','reply','reply-word','reply-meta','reply-meta-invalid']
CASES=COLD_CASES+['success','ack-one','native-observed-6c-to-6d','row-bound','queued-worker','startup-unknown','first-history-false','first-sealed-false','first-failed-false','cold-status6d']
CASES+=['mirror-'+x for x in MIRRORS]
CASES+=['skip-before-'+x for x in MIRRORS]
CASES+=['skip-missing-running','skip-missing-map','skip-missing-hello','skip-queued-b20','skip-queued-ep1','skip-capacity-one','skip-capacity-zero','skip-intent-used']
CASES+=['skip-intent-'+x for x in ['known','state','first','identity','pm-error','usage','ref','start','running','map','rx-pending','rx-invalid','tx-full','tx-invalid']]
CASES+=['after-skip-'+x for x in ['known','state','reply','intent','bit','running','map']]
CASES+=['request-intent-'+x for x in ['known','state','request','write','reply','first','identity','pm-error','usage','ref','start','running','map','skip','rx-pending','rx-invalid','tx-full','tx-invalid']]
CASES+=['boot-host20','boot-endpoint','boot-missing','boot-late','no-ack','clock-stalled','ack-clock-stalled','ack-boot20','ack-host20','ack-endpoint','ack-wrong','post-ack-rx-pending','idle-timeout','clear10-dropped','clear20-dropped','coord-off-write','pm-put-error','second-off-busy']

def make_harness(source):
 assert sha(BASE_TEST)==BASE_TEST_SHA
 base=runpy.run_path(str(BASE_TEST))['HARNESS']
 base=base[:base.index('int main(int argc,char **argv)')]
 base=base.replace('#define GFX_NATIVE_RUNNING_CYCLE_TRIAL 1','#define GRAPH_RECOVERY_EXPERIMENT 1\n#define GFX_NATIVE_RUNNING_CYCLE_TRIAL 1')
 base=base.replace('typedef uint64_t u64;','typedef uint16_t u16;typedef uint64_t u64;')
 base=base.replace('GFX_NATIVE_RUNNING_CYCLE_TRIAL','GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL').replace('gfx-native-running-cycle','gfx-native-ap-retained-cycle')
 base=base.replace('gfx_retained_cycle_host_on_attempted','gfx_retained_cycle_host_on_skip_attempted').replace('gfx_retained_cycle_host_on_reply_observed','gfx_retained_cycle_host_on_skipped')
 base=base.replace('static char logs[524288];',COLD_MOCK+'static char logs[524288];')
 base=base.replace('if(strstr(fmt,"m4rch gfx-native-ap-retained-cycle")==fmt)', 'if(strstr(fmt,"m4rch gfx-native-ap-retained-cold:")==fmt){assert(n<512&&logs[log_used+n-1]==\'\\n\');cold_rows++;if((unsigned int)n>cold_maximum_row)cold_maximum_row=n;inject_cold_phase(logs+log_used);}if(strstr(fmt,"m4rch gfx-native-ap-retained-cycle")==fmt)')
 # Allow the old cold helper's fixed sleep interval and add bounded stalled-clock test.
 base=base.replace('assert(lo==1000&&hi==1100);','assert(lo==1000&&(hi==1100||hi==2000));').replace('!is("host-clock-stalled")','!is("host-clock-stalled")&&!is("cold-clock-stalled")&&!is("ack-clock-stalled")')
 a=base.index('static void inject_on_phase(const char *row)\n{');b=base.index('\nstatic int gfx_poweroff_snapshot(',a);base=base[:a]+INJECT+base[b:]
 owner=(source/'asc-graph-init.c').read_text()
 a=owner.index('#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL\nstatic bool gfx_ap_cold_request_attempted');b=owner.index('#endif',a)+len('#endif')
 base=base.replace('#include "gfx-native-ap-retained-cycle.h"',owner[a:b]+'\n#include "gfx-native-ap-retained-cycle.h"')
 a=base.index('static void writeq(u64 value,void *p)\n{');b=base.index('\nstatic void writel(',a)
 base=base[:a]+r'''
static void writeq(u64 value,void *p)
{
 if(cold_phase) {
  if(p==(char*)mbox+0x808){assert(value==0);return;}
  assert(p==(char*)mbox+0x800&&value==GFX_RETAINED_CYCLE_HOST_ON&&gfx_ap_cold_request_write_attempted);
  cold_writes++;assert(cold_writes==1);cold_ready=true;
  if(firmware_ap_state==33){cold_message=0x0010110001de4000ULL;cold_metadata=1;return;}
  firmware_ap_state=33;
  cold_message=is("cold-reply-word")?0x00b0000000010020ULL:is("cold-reply-type")?0x0070000000000020ULL:is("cold-reply-state")?0x00b0000000000201ULL:is("cold-reply-invalid")?~0ULL:GFX_RETAINED_CYCLE_HOST_ON;
  cold_metadata=is("cold-reply-ep1")?1:is("cold-reply-meta-invalid")?~0ULL:0;
  if(is("cold-no-reply")||is("cold-clock-stalled"))cold_ready=false;
  return;
 }
 assert(graph_io_lock==1&&held&&gfx_retained_cycle_intent&&starts&&!put_done);
 if(p==(char*)mbox+0x808){assert(value==0);return;}
 assert(p==(char*)mbox+0x800);
 if(value==GFX_RETAINED_CYCLE_HOST_ON){hostons++;assert(!"second B20 forbidden; firmware AP33 would panic");}
 if(value==GFX_NATIVE_POWERGATE_REQUEST) {
  assert(gfx_retained_cycle_request_attempted&&hellos==1&&mapacks==2&&pos==count&&!requests&&!hostons);
  assert(gfx_retained_cycle_on_completion()&&firmware_ap_state==33);requests++;stage=3;firmware_iop_state=2;
  if(is("no-ack")||is("clock-stalled")||is("ack-clock-stalled"))return;
  messages[count]=is("ack-boot20")?GFX_RETAINED_CYCLE_BOOT_RUNNING:is("ack-host20")?GFX_RETAINED_CYCLE_HOST_ON:is("ack-wrong")?0x0070000000000220ULL:is("ack-one")?0x0070000000000201ULL:0x0070000000000202ULL;
  metadata[count]=is("ack-endpoint")?32:0;count++;return;
 }
 if(((value>>52)&0xf)==2){assert(value==0x00200000000c000cULL&&gfx_retained_cycle_hello_reply_attempts==1&&!hellos);hellos++;}
 else {assert(((value>>52)&0xf)==8&&mapacks<2);mapacks++;}
}
'''+base[b:]
 base=base.replace('static u32 readl(void *p)\n{',r'''static u32 readl(void *p)
{
 if(cold_phase) {
  if(p==(char*)mbox+0x110){if(is("cold-tx-invalid")||(cold_request_log&&is("cold-intent-tx-invalid")))return ~0U;if(is("cold-tx-full")||(cold_request_log&&is("cold-intent-tx-full")))return BIT(16);return 0;}
  assert(p==(char*)mbox+0x114);
  if(is("cold-rx-invalid")||(cold_request_log&&!cold_writes&&is("cold-intent-rx-invalid")))return ~0U;
  if(is("cold-rx-pending")||(cold_request_log&&!cold_writes&&is("cold-intent-rx-pending")))return 0;
  if(cold_writes&&!cold_ready&&is("cold-post-reply-rx-invalid"))return ~0U;
  if(cold_writes&&!cold_ready&&is("cold-post-reply-rx-pending"))return 0;
  return cold_ready?0:EMPTY;
 }
 if((gfx_retained_cycle_host_on_skip_attempted&&!gfx_retained_cycle_host_on_skipped)||(gfx_retained_cycle_request_attempted&&!requests)) {
  const char *prefix=gfx_retained_cycle_request_attempted?"request-intent":"skip-intent";char key[80];
  snprintf(key,sizeof(key),"%s-rx-pending",prefix);if(p==(char*)mbox+0x114&&is(key))return 0;
  snprintf(key,sizeof(key),"%s-rx-invalid",prefix);if(p==(char*)mbox+0x114&&is(key))return ~0U;
  snprintf(key,sizeof(key),"%s-tx-full",prefix);if(p==(char*)mbox+0x110&&is(key))return BIT(16);
  snprintf(key,sizeof(key),"%s-tx-invalid",prefix);if(p==(char*)mbox+0x110&&is(key))return ~0U;
 }
''')
 base=base.replace('static u64 readq(void *p)\n{',r'''static u64 readq(void *p)
{
 if(cold_phase) {
  assert(cold_ready);
  if(p==(char*)mbox+0x830)return cold_message;
  assert(p==(char*)mbox+0x838);cold_ready=false;if(is("cold-reply-late"))jiffies+=2000;return cold_metadata;
 }
''')
 base=base.replace('  starts++;stage=2;','  starts++;stage=2;firmware_iop_state=8;assert(firmware_ap_state==33);')
 worker=extract_function((source/'recovery-cycle.h').read_text(),'static void recovery_receive_worker(struct work_struct *work)\n{')
 base=base.replace('/* ACTUAL_RECEIVE_WORKER */',worker)
 cold=extract_function(owner,'static bool power_ack(unsigned int request, unsigned int reply, u16 state)')
 main=MAIN.replace('/* ACTUAL_COLD_POWER_ACK */',cold)
 a=owner.index(' if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)');b=owner.index(' {',a)
 condition=owner[a+4:b].strip()
 main=main.replace('/* ACTUAL_COLD_ROOT_CONDITION */',condition)
 return base+'\n'+main

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve()
 receipt_path=source/'native-ap-retained-cycle-owner-source-receipt.json';receipt=json.loads(receipt_path.read_text())
 for row in receipt['output_source_pins']:assert sha(source/row['name'])==row['sha256'],row['name']
 assert receipt['profile']['version']==11 and receipt['profile']['second_host_on_requests_maximum']==0
 assert 'fresh_pm_identity_cpu_fifo_required_after_host_reply_before_second_202' not in receipt['profile']
 assert sha(FROZEN_C)==FROZEN_C_SHA;frozen=json.loads(FROZEN_C.read_text());assert frozen['passed'] and frozen['case_count']==135
 environment=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1');results=[]
 with tempfile.TemporaryDirectory(prefix='ap-retained-c-q-') as td:
  unit=Path(td)/'actual-owner.c';unit.write_text(make_harness(source));binary=Path(td)/'actual-owner'
  command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(unit),'-o',str(binary)]
  compiled=subprocess.run(command,capture_output=True,text=True)
  if compiled.returncode:raise RuntimeError(compiled.stdout+'\n'+compiled.stderr)
  for case in CASES:
   r=subprocess.run([str(binary),case],env=environment,capture_output=True,text=True)
   if r.returncode:raise RuntimeError(case+'\n'+r.stdout+'\n'+r.stderr)
   results.append({'case':case,'returncode':r.returncode,'stdout':r.stdout.strip()})
 inputs=[{'path':str(HERE/n),'sha256':sha(HERE/n)} for n in ['gfx-native-ap-retained-cycle.h','prepare-native-ap-retained-cycle-owner.py','test-native-ap-retained-cycle-owner.py']]
 inputs+=[{'path':str(receipt_path),'sha256':sha(receipt_path)},{'path':str(BASE_TEST),'sha256':BASE_TEST_SHA},{'path':str(FROZEN_C),'sha256':FROZEN_C_SHA}]
 inputs+=[{'path':str(source/r['name']),'sha256':r['sha256']} for r in receipt['output_source_pins']]
 for name,expected in [('2026-10-10-gfx-native-running-cycle-crashlog-diagnosis.json','b8b218602d959f21b6f945def61117d65019895814d35761a0d28bf796efb35d'),('2026-10-10-gfx-native-running-cycle-retained-ap-notification-native-boundary.json','7cbe46bf9f7d72806dec5835aba0ab21693c61cf3c0040901f1f7278c990f845')]:
  basis=ROOT/'docs/evidence'/name;assert sha(basis)==expected;inputs.append({'path':str(basis),'sha256':expected})
 value={'schema':'m4rch.gfx-native-ap-retained-cycle-c-qualification.v1','passed':True,'hardware_access':False,'ASan_UBSan':True,'case_count':len(results),
  'actual_headers':True,'actual_second_coordinate_core':True,'actual_cold_power_ack':True,'actual_cold_root_publication_condition':True,'actual_receive_worker':True,
  'actual_retained_ap20_skip_before202':True,'duplicate_B20_panics_in_firmware_model':True,'actual_complete_six_row_groups':True,'second_log_row_count':6,
  'new_log_rows_bounded':True,'maximum_new_log_row_bytes':max(int(r['stdout'].split('maximum_new_log_row=')[-1]) for r in results),
  'stage_specific_start_guards_exercised':True,'actual_observed_6c_to_paired_on_to_6d_sequence_simulated':True,
  'cold_exact_owned_reply_and_missing_mirror_refusals_exercised':True,'no_second_B20_path':True,'post_skip_and_second202_intent_fresh_guards_exercised':True,
  'frozen_135_composition':{'path':str(FROZEN_C),'sha256':FROZEN_C_SHA,'case_count':135,'rerun':False},
  'source_path':str(source),'source_receipt_sha256':sha(receipt_path),'inputs':inputs,'cases':results,
  'limitations':['RAM callbacks model PM/provider/CPU/mailbox/DRAM; kernel module never built or loaded.','First management-only202 history is an immutable qualified fixture; unchanged135-case source proof composes without rerun.','Simulated AP33 duplicate assertion is based on saved diagnosis; no new firmware execution.','No actual reentry/secondACK/physicalOFF/application rejoin/rendering/retirement proven.']}
 assert not a.output.exists();a.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'path':str(a.output),'sha256':sha(a.output),'cases':len(results),'maxrow':value['maximum_new_log_row_bytes']}))
if __name__=='__main__':main()
