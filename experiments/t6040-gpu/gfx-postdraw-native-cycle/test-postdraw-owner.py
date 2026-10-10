#!/usr/bin/env python3
"""Essential actual-C v16 draw/retained management cases with RAM services."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE=ROOT/'experiments/t6040-gpu/gfx-cold-render/test-cold-render-owner.py'
FROZEN=ROOT/'out/gfx-native-dispatch-contract/owner-qualification-v1.json'
FROZEN_SHA='4aab6fd97353c3731584b615c71354989df1d3634d708e3a1513aad470d5ac21'
NATIVE_Q=ROOT/'out/gfx-native-ap-repeat-cycle/owner-qualification-v8.json'
NATIVE_SHA='68f5f2de51794d7c93cd6c4b077a4e023605b9266266db8b114290769ff99776'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t,a,b):
 if t.count(a)!=1:raise ValueError('Frozen test hook changed: '+a[:100])
 return t.replace(a,b,1)
spec=importlib.util.spec_from_file_location('cold_base',BASE);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

EXTRA_PREFIX=r'''
static bool gfx_postdraw_cycle_intent,gfx_postdraw_off_attempted,gfx_postdraw_pm_get_attempted;
static bool gfx_postdraw_device_access,gfx_postdraw_start_attempted;
static bool gfx_native_powergate_request_attempted;
static unsigned int cycle_requests,cycle_puts,cycle_gets,cycle_cpuwrites,cycle_starts,cycle_hellos,cycle_mapacks;
static unsigned int cycle_device_reads,cycle_unsafe_reads,cycle_diag_reads,cycle_coord_writes;
static u64 cycle_messages[300],cycle_metadata[300];static unsigned int cycle_count,cycle_pos;
static bool cycle_put_done,cycle_get_done;
static u32 cycle_control44=START|0x20,cycle_status48=0x6d;
static int pm_runtime_put_sync_suspend(struct fake_dev *d);
static int pm_runtime_resume_and_get(struct fake_dev *d);
static void writel(u32 value,void *p);
static int gfx_coord_owner_alias_check(void){return 0;}
'''

EXTRA_MOCK=r'''
static int pm_runtime_put_sync_suspend(struct fake_dev *d)
{
 assert(graph_io_lock==1&&gfx_postdraw_off_attempted&&!gfx_postdraw_device_access);
 assert(!held&&d->power.usage_count==1&&gfx_coord_owner_session.off_complete);
 assert(gfx_native_powergate_cpu_stopped&&cycle_requests==1&&cycle_cpuwrites==2);
 cycle_puts++;assert(cycle_puts==1);cycle_put_done=true;
 d->power.usage_count=0;d->active=false;d->suspended=true;d->power.runtime_status=2;
 if(is("off-accounting"))d->power.usage_count=1;
 if(is("off-put-error")){d->power.runtime_error=-EIO;return -EIO;}
 return 0;
}
static int pm_runtime_resume_and_get(struct fake_dev *d)
{
 assert(graph_io_lock==1&&!held&&d->power.usage_count==0&&cycle_put_done&&!gfx_postdraw_device_access);
 assert(gfx_postdraw_provider_off&&gfx_postdraw_accounting_ok&&gfx_postdraw_pm_get_attempted);
 cycle_gets++;assert(cycle_gets==1);
 if(is("on-get-error"))return -EIO;
 d->power.usage_count=1;d->active=true;d->suspended=false;d->power.runtime_status=0;
 cycle_get_done=true;cycle_control44=0;cycle_status48=is("pre-on-6d")?0x6d:0x6c;
 cycle_count=cycle_pos=0;
 if(is("on-accounting"))d->power.usage_count=2;
 if(is("on-identity"))owned[8]->pa^=0x4000;
 return 0;
}
static void writel(u32 value,void *p)
{
 assert(graph_io_lock==1&&held&&gfx_postdraw_device_access&&p==(char*)asc+0x44);
 if(!gfx_postdraw_start_attempted) {
  cycle_cpuwrites++;assert(cycle_cpuwrites<=2&&cycle_requests==1);
  assert(gfx_native_powergate_ack_observed&&gfx_native_powergate_idle_observed);
  if(!(is("clear10-drop")&&cycle_cpuwrites==1) && !(is("clear20-drop")&&cycle_cpuwrites==2))cycle_control44=value;
 } else {
  cycle_starts++;assert(cycle_starts==1&&cycle_get_done&&gfx_postdraw_coord_session.on_complete);
  if(is("start-drop"))return;
  cycle_control44=value;
  if(is("protocol-timeout"))return;
  cycle_messages[0]=0x00100000000c000cULL;cycle_metadata[0]=0;
  cycle_messages[1]=0x0080000000000003ULL;cycle_metadata[1]=0;
  cycle_messages[2]=0x0088000100000003ULL;cycle_metadata[2]=0;
  cycle_messages[3]=is("boot-wrong")?0x0070000000000002ULL:0x0070000000000020ULL;
  cycle_metadata[3]=0;cycle_count=4;
 }
}
'''

def harness(source):
 base.PREFIX=base.PREFIX.replace('#define GFX_COLD_RENDER_TRIAL 1','#define GFX_POSTDRAW_NATIVE_CYCLE_TRIAL 1').replace('static const unsigned int gfx_cold_current_epoch=1;','static unsigned int gfx_cold_current_epoch=1;')
 base.PREFIX=once(base.PREFIX,'static u32 readl(void *p);',EXTRA_PREFIX+'\nstatic u32 readl(void *p);')
 # PMGR observations are independently valid, including held0 after put.
 a=base.PREFIX.index('static int apple_pmgr_t6040_gfx_snapshot(')
 b=base.PREFIX.index('\n}\n',a)+3
 base.PREFIX=base.PREFIX[:a]+r'''
static int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o)
{
 physical_calls++;o->valid=APPLE_PMGR_GFX_VALID_BEFORE;o->domain_on=held;
 o->before=held?0x1f0003ff:0x0f000300;
 if(cycle_put_done&&!cycle_get_done) {
  if(is("off-physical-unknown"))o->valid=0;
  if(is("off-physical-busy"))o->before|=BIT(11);
  if(is("off-identity"))owned[9]->pa^=0x4000;
 }
 if(cycle_get_done&&is("on-physical-unknown"))o->valid=0;
 return 0;
}
'''+base.PREFIX[b:]
 base.MOCK=base.MOCK.replace('mem32(RECOVERY_TRACE_MASK)==0','mem32(RECOVERY_TRACE_MASK)==3')
 base.MOCK=once(base.MOCK,'{(void)ctx;assert(index==GFX_COORD_REQUEST_ENTRY);if(is("coord-request-error"))return -EIO;ptd=value;return 0;}',r'''{(void)ctx;assert(index==GFX_COORD_REQUEST_ENTRY);
 if(gfx_postdraw_cycle_intent) {
  cycle_coord_writes++;
  if((!cycle_get_done&&is("off-coordinate"))||(cycle_get_done&&is("on-coordinate")))return -EIO;
 }
 if(is("coord-request-error"))return -EIO;ptd=value;return 0;}''')
 base.MOCK=once(base.MOCK,'{(void)ctx;assert(index<3);if(!is("coord-vote-readback"))votes[index]=value;return 0;}',r'''{(void)ctx;assert(index<3);if(!is("coord-vote-readback"))votes[index]=value;
 if(cycle_get_done)cycle_status48=is("post-on-6e")?0x6e:0x6d;
 return 0;}''')
 base.MOCK=once(base.MOCK,'static u32 readl(void *p)\n{',r'''static u32 readl(void *p)
{
 if(gfx_postdraw_cycle_intent) {
  cycle_device_reads++;
  if(!held||!gfx_postdraw_device_access){cycle_unsafe_reads++;assert(false);}
  if(p==(char*)asc+0x44)return cycle_control44;
  if(p==(char*)asc+0x48)return cycle_requests&&!cycle_get_done&&is("native-idle-timeout")?0x6c:cycle_status48;
  if(p==(char*)mbox+0x110)return 0;
  if(p==(char*)mbox+0x114)return cycle_pos<cycle_count?0:EMPTY;
  assert(false);
 }
''')
 base.MOCK=once(base.MOCK,'static u64 readq(void *p)\n{',r'''static u64 readq(void *p)
{
 if(gfx_postdraw_cycle_intent) {
  assert(held&&gfx_postdraw_device_access&&cycle_pos<cycle_count);cycle_device_reads++;
  if(p==(char*)mbox+0x830)return cycle_messages[cycle_pos];
  assert(p==(char*)mbox+0x838);u64 value=cycle_metadata[cycle_pos++];
  if(!cycle_requests&&is("admission-deadline"))jiffies+=250;
  return value;
 }
''')
 base.MOCK=once(base.MOCK,'static void writeq(u64 v,void *p)\n{',r'''static void writeq(u64 v,void *p)
{
 if(gfx_postdraw_cycle_intent) {
  assert(held&&gfx_postdraw_device_access);
  if(p==(char*)mbox+0x800){tx_message=v;return;}
  assert(p==(char*)mbox+0x808&&v==0);messages_sent++;
  if(tx_message==0x0060000000000202ULL) {
   cycle_requests++;assert(cycle_requests==1&&gfx_native_powergate_request_attempted&&cycle_pos==cycle_count);
   if(is("no202-ack"))return;
   cycle_messages[cycle_count]=is("ack-wrong")?0x0070000000000020ULL:is("ack-one")?0x0070000000000201ULL:0x0070000000000202ULL;
   cycle_metadata[cycle_count]=is("ack-endpoint")?1:0;cycle_count++;return;
  }
  assert(cycle_starts==1&&cycle_get_done);
  if((tx_message>>52)==2){assert(tx_message==0x00200000000c000cULL);cycle_hellos++;}
  else {assert(tx_message==0x0080000000000001ULL||tx_message==0x0088000100000000ULL);cycle_mapacks++;}
  return;
 }
''')
 base.MOCK=once(base.MOCK,'static void inject(const char *row)\n{',r'''static void inject(const char *row)
{
 if(strstr(row,"m4rch gfx-postdraw-native-cycle: phase=intent ")) {
  if(is("cycle-intent-identity"))owned[5]->pa^=0x4000;
  if(is("draw-not-complete"))gfx_cold_complete=false;
 }
 if(strstr(row,"m4rch gfx-postdraw-native-cycle: phase=admission-ready ")&&is("pre202-identity"))root_word^=0x4000;
 if(strstr(row,"m4rch gfx-postdraw-native-cycle: phase=boot-running-observed ")&&is("protocol-identity"))owned[6]->pa^=0x4000;
 if(strstr(row,"m4rch gfx-cold-render: phase=control-ready ")&&is("trace-changed"))fw32(RECOVERY_TRACE_MASK,0);
''')
 setup=base.MAIN[:base.MAIN.index('int main(')]
 base.MAIN=setup+r'''
int main(int argc,char **argv)
{
 setvbuf(stdout,NULL,_IONBF,0);assert(argc==2);fault=argv[1];setup();
 int ret=gfx_coord_owner_begin_on();if(!ret){started=true;ret=actual_automatic_entry();}
 if(is("trace-changed")) {
  assert(!gfx_cold_complete&&gfx_cold_terminal_result<0&&draw_notifies==0);puts("PASS trace-changed maxrow=0");return 0;
 }
 assert(!ret&&gfx_cold_complete&&gfx_cold_sealed&&gfx_cold_software_stopped&&!receive_enabled);
 assert(!gfx_cold_trace_attempted&&mem32(RECOVERY_TRACE_MASK)==3&&control_notifies==1&&draw_notifies==1);
 assert(gfx_cold_observation_samples==6&&gfx_cold_identities_preserved);
 if(is("preexisting-ep0")) {cycle_messages[0]=0x0070000000000202ULL;cycle_metadata[0]=0;cycle_count=1;}
 if(is("admission-backlog")||is("admission-deadline")) {
  for(unsigned int i=0;i<70;i++){cycle_messages[i]=0x0042000000000000ULL;cycle_metadata[i]=32;}cycle_count=70;
 }
 const char command[]="postdraw-native-cycle 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n";
 mutex_lock(&graph_io_lock);
 if(is("missing-token"))ret=gfx_postdraw_command("postdraw-native-cycle",21);
 else if(is("bad-token"))ret=gfx_postdraw_command("postdraw-native-cycle G123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",86);
 else ret=gfx_postdraw_command(command,sizeof(command)-1);
 bool success=is("success")||is("ack-one")||is("admission-backlog")||is("duplicate")||is("row-bound");
 if(success) {
  assert(!ret&&gfx_postdraw_complete&&!gfx_postdraw_unknown&&cycle_requests==1&&cycle_puts==1&&cycle_gets==1);
  assert(cycle_cpuwrites==2&&cycle_starts==1&&cycle_hellos==1&&cycle_mapacks==2);
  assert(gfx_postdraw_provider_off&&gfx_postdraw_accounting_ok&&gfx_postdraw_coord_session.on_complete);
  assert(held&&consumer->dev.power.usage_count==1&&consumer->dev.active&&!consumer->dev.suspended);
  assert(gfx_postdraw_identities_preserved&&gfx_postdraw_boot_running_observed&&gfx_postdraw_map_seen==3);
 } else {
  assert(ret<0&&!gfx_postdraw_complete&&gfx_postdraw_unknown);
  if(!cycle_puts)assert(held&&cycle_gets==0);
  if(!gfx_postdraw_provider_off||!gfx_postdraw_accounting_ok)assert(cycle_gets==0);
 }
 unsigned int msg=messages_sent,reads=cycle_device_reads,puts=cycle_puts,gets=cycle_gets,requests=cycle_requests;
 assert(gfx_postdraw_command(command,sizeof(command)-1)==-EALREADY);
 assert(gfx_postdraw_diagnostic("sample")==0&&gfx_postdraw_diagnostic("gfx-snapshot")==0);
 assert(gfx_postdraw_diagnostic("gfx-powergate")==-EPERM&&gfx_postdraw_diagnostic("recover")==-EPERM);
 assert(msg==messages_sent&&reads==cycle_device_reads&&puts==cycle_puts&&gets==cycle_gets&&requests==cycle_requests);
 assert(!cycle_unsafe_reads&&!receive_enabled&&gfx_cold_retained_pages()==174&&installed&&device_context_retained);
 assert(root_notifies==1&&endpoint_starts==2&&control_notifies==1&&draw_notifies==1);
 if(is("row-bound")) {
  gfx_postdraw_pm_put_result=gfx_postdraw_pm_get_result=INT_MIN;
  gfx_postdraw_control=gfx_postdraw_status=gfx_postdraw_rx=gfx_postdraw_tx=UINT_MAX;
  gfx_postdraw_sample_jiffies=~0UL;gfx_postdraw_log("diagnostic-cached",INT_MIN);
 }
 mutex_unlock(&graph_io_lock);
 printf("PASS %s requests=%u puts=%u gets=%u starts=%u unsafe_reads=%u maxrow=%u\n",fault,cycle_requests,cycle_puts,cycle_gets,cycle_starts,cycle_unsafe_reads,maximum_log_row);
 return 0;
}
'''
 # Include PM mocks after production fields/helpers exist, before the actual
 # automatic entry. The command function itself remains production C.
 out=base.make_harness(source)
 at=out.index('static int actual_automatic_entry(')
 return out[:at]+EXTRA_MOCK+'\n'+out[at:]

CASES=['success','ack-one','admission-backlog','duplicate','row-bound','trace-changed',
 'missing-token','bad-token','draw-not-complete','cycle-intent-identity','pre202-identity',
 'preexisting-ep0','admission-deadline','no202-ack','ack-wrong','ack-endpoint',
 'native-idle-timeout','clear10-drop','clear20-drop','off-coordinate','off-put-error',
 'off-physical-unknown','off-physical-busy','off-accounting','off-identity',
 'on-get-error','on-accounting','on-identity','on-physical-unknown','on-coordinate',
 'pre-on-6d','post-on-6e','start-drop','protocol-timeout','boot-wrong','protocol-identity']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source,output=a.source.resolve(),a.output.resolve()
 if output.exists():raise ValueError('Distinct absent output required')
 receipt=source/'postdraw-native-cycle-owner-source-receipt.json';j=json.loads(receipt.read_text())
 assert j['profile']['version']==16
 for x in j['output_source_pins']:assert sha(source/x['name'])==x['sha256']
 for q,h in [(FROZEN,FROZEN_SHA),(NATIVE_Q,NATIVE_SHA)]:assert sha(q)==h and json.loads(q.read_text())['passed']
 output.parent.mkdir(parents=True,exist_ok=True);hp=output.with_suffix('.actual-owner.c');hp.write_text(harness(source))
 snapshot=output.with_suffix('.tester.py');snapshot.write_bytes(Path(__file__).read_bytes());fixtures=[];results=[];maximum=0
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 with tempfile.TemporaryDirectory(prefix='postdraw-c-q-') as td:
  binary=Path(td)/'owner';command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-unused-but-set-global','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(hp),'-o',str(binary)]
  c=subprocess.run(command,text=True,capture_output=True)
  if c.returncode:raise RuntimeError(c.stdout+'\n'+c.stderr)
  for case in CASES:
   x=subprocess.run([str(binary),case],text=True,capture_output=True,env=env)
   if x.returncode:
    output.with_suffix('.failure.json').write_text(json.dumps(dict(case=case,stdout=x.stdout,stderr=x.stderr),indent=2)+'\n');raise RuntimeError(case+'\n'+x.stdout+'\n'+x.stderr)
   f=output.with_suffix('.'+case+'.log');f.write_text('\n'.join(row for row in x.stdout.splitlines() if 'm4rch ' in row)+'\n')
   fixtures.append(dict(case=case,path=str(f),bytes=f.stat().st_size,sha256=sha(f)))
   last=x.stdout.splitlines()[-1];maximum=max(maximum,int(last.split('maxrow=')[1]));results.append(dict(case=case,returncode=0,stdout=last))
 pins=[dict(path=str(p),sha256=sha(p)) for p in [receipt,FROZEN,NATIVE_Q,BASE,hp,snapshot,Path(__file__).resolve()]]
 pins += [dict(path=str(source/x['name']),sha256=x['sha256']) for x in j['output_source_pins']]
 report=dict(schema='m4rch.gfx-postdraw-native-cycle.actual-C-qualification.v1',passed=True,hardware_access=False,kernel_build=False,
  source_path=str(source),source_receipt_sha256=sha(receipt),case_count=len(results),cases=results,compiler=command,
  sanitizers=['address','undefined'],maximum_new_log_row_bytes=maximum,actual_cold_control_draw=True,
  actual_postdraw_native_admission_ack_idle_cpu_stop=True,actual_paired_coordinate_OFF_ON=True,
  actual_PM_accounting_OFF_ON_guards=True,no_device_access_after_OFF_without_qualified_ON=True,
  maximum_native202=1,maximum_postdraw_pm_puts=1,maximum_retained_pm_gets=1,maximum_retained_starts=1,
  immutable_cold_identity_retained=True,capture_token_file_hash_verified_by_C=False,
  success_log_fixture=fixtures[0],cycle_success_log_fixture=fixtures[0],actual_log_fixtures=fixtures,input_pins=pins,
  frozen_unchanged_composition=[dict(path=str(FROZEN),sha256=FROZEN_SHA,rerun=False),dict(path=str(NATIVE_Q),sha256=NATIVE_SHA,rerun=False)],
  qualification='Actual production C using RAM PMGR/PM/MMIO/cache/physical services. Pointer/resource allocation services mocked. Host file durability/hash binding separate; token syntax alone is not fullcapture proof. No real firmware/hardware teardown, rejoin, rendering, application recovery, retirement or safe free established.')
 with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(output=str(output),sha256=sha(output),cases=len(results),maximum_log_row=maximum,fixture=fixtures[0])))
if __name__=='__main__':main()
