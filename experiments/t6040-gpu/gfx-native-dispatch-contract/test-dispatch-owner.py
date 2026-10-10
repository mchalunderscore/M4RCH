#!/usr/bin/env python3
"""Narrow actual-C checks of the v15 shared trace restore and its draw boundary.

Compose frozen v13 checks rather than repeat its56 cases. RAM services intercept
physical/PM/cache/MMIO; this establishes neither firmware nor hardware behavior.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_TEST=ROOT/'experiments/t6040-gpu/gfx-cold-render/test-cold-render-owner.py'
BASE_Q=ROOT/'out/gfx-cold-render/owner-qualification-v8.json'
BASE_Q_SHA='deea9356799207aba1d07c08c6858a2200abaf8ff3d5189d0ae401d9c89b0cf2'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text,old,new):
 if text.count(old)!=1:raise ValueError('Qualification hook changed: '+old[:100])
 return text.replace(old,new,1)


spec=importlib.util.spec_from_file_location('frozen_cold_tester',BASE_TEST)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.PREFIX=base.PREFIX.replace('#define GFX_COLD_RENDER_TRIAL 1','#define GFX_NATIVE_DISPATCH_CONTRACT_TRIAL 1')
base.PREFIX=once(base.PREFIX,'static unsigned int messages_sent,','static unsigned int trace_restore_writes,trace_zero_writes;\nstatic unsigned int messages_sent,')
base.MOCK=once(base.MOCK,' if(p==recovery_ptr(RECOVERY_TRACE_MASK)&&is("trace-drop"))fw32(RECOVERY_TRACE_MASK,3);',
 ''' if(p==recovery_ptr(RECOVERY_TRACE_MASK)) {
  if(gfx_dispatch_trace_write_attempted) {
   trace_restore_writes++;assert(trace_restore_writes==1);
   assert(gfx_cold_control_ready&&!gfx_cold_draw_intent&&!recovery_work_submitted);
   assert(control_notifies==1&&draw_notifies==0);
   assert(mem32(RECOVERY_CONTROL)==33&&mem32(RECOVERY_CONTROL+8)==33&&mem32(RECOVERY_CONTROL+16)==33);
   assert(gfx_dispatch_trace_intent&&gfx_dispatch_trace_written==3&&mem32(RECOVERY_TRACE_MASK)==3);
   if(is("trace-restore-drop"))fw32(RECOVERY_TRACE_MASK,0);
   if(is("trace-restore-identity"))owned[4]->pa^=0x4000;
  } else {
   trace_zero_writes++;assert(trace_zero_writes==1&&control_notifies==0&&draw_notifies==0);
   assert(mem32(RECOVERY_TRACE_MASK)==0);
  }
 }''')
base.MOCK=once(base.MOCK,'  assert(clean_records==2&&gfx_cold_producer_verified[0]&&gfx_cold_producer_verified[1]);',
 '''  assert(clean_records==2&&gfx_cold_producer_verified[0]&&gfx_cold_producer_verified[1]);
  assert(gfx_dispatch_trace_ready&&trace_restore_writes==1&&mem32(RECOVERY_TRACE_MASK)==3);''')
base.MOCK=once(base.MOCK,'static void inject(const char *row)\n{',
 '''static void inject(const char *row)
{
 if(strstr(row,"gfx-cold-render: phase=control-ready ")) {
  assert(mem32(RECOVERY_TRACE_MASK)==0&&trace_restore_writes==0&&draw_notifies==0);
  if(is("trace-admission-control"))fw32(RECOVERY_CONTROL+8,32);
  if(is("trace-admission-mask"))fw32(RECOVERY_TRACE_MASK,1);
  if(is("trace-admission-target"))owned[RENDER_FIRST_PAGE+20]->data[0]^=1;
 }
 if(strstr(row,"gfx-native-dispatch-trace: phase=intent ")) {
  if(is("trace-intent-identity"))owned[3]->pa^=0x4000;
  if(is("trace-intent-request"))fw32(RECOVERY_REQUEST+4,1);
  if(is("trace-intent-mask"))fw32(RECOVERY_TRACE_MASK,3);
 }
 if(strstr(row,"gfx-native-dispatch-trace: phase=write-intent ")) {
  if(is("trace-write-identity"))root_word^=0x4000;
  if(is("trace-write-mask"))fw32(RECOVERY_TRACE_MASK,1);
  if(is("trace-write-work"))fw32(recovery_work_cursors[0]+16,1);
 }
 if(strstr(row,"gfx-native-dispatch-trace: phase=readback ")) {
  if(is("trace-before-draw-mask"))fw32(RECOVERY_TRACE_MASK,0);
 }
''')
setup=base.MAIN[:base.MAIN.index('int main(')]
base.MAIN=setup+r'''
int main(int argc,char **argv)
{
 setvbuf(stdout,NULL,_IONBF,0);assert(argc==2);fault=argv[1];setup();
 assert(gfx_cold_startup_admission(2,true,false,false,false)==0);
 int ret=gfx_coord_owner_begin_on();if(!ret){started=true;ret=actual_automatic_entry();}
 bool success=is("success")||is("row-bound");
 if(success) {
  assert(!ret&&gfx_cold_complete&&gfx_dispatch_trace_ready);
  assert(trace_zero_writes==1&&trace_restore_writes==1);
  assert(gfx_dispatch_trace_before==0&&gfx_dispatch_trace_written==3&&gfx_dispatch_trace_after==3);
  assert(mem32(RECOVERY_TRACE_MASK)==3&&gfx_cold_trace_after==3);
  assert(control_notifies==1&&draw_notifies==1&&gfx_cold_observation_samples==6);
  assert(gfx_cold_identities_preserved&&held&&consumer->dev.power.usage_count==1);
 } else {
  assert(!gfx_cold_complete&&gfx_cold_sealed&&gfx_cold_software_stopped);
  if(!is("post-device-fault")&&!is("observe-clock-stalled"))assert(draw_notifies==0);
  if(strstr(fault,"trace-admission-")||strstr(fault,"trace-intent-")||strstr(fault,"trace-write-"))assert(trace_restore_writes==0);
  if(is("trace-restore-drop")||is("trace-restore-identity")||is("trace-before-draw-mask"))assert(trace_restore_writes==1);
 }
 assert(control_notifies==1&&root_notifies==1&&endpoint_starts==2);
 assert(trace_restore_writes<=1&&draw_notifies<=1);
 assert(gfx_cold_retained_pages()==174&&installed&&device_context_retained);
 assert(gfx_cold_software_stopped&&gfx_cold_sealed&&!gfx_cold_running&&!receive_enabled);
 unsigned int restores=trace_restore_writes,zeroes=trace_zero_writes,messages=messages_sent,used=receive_journal.used;
 int outcome=gfx_cold_terminal_result;const char *refusal=gfx_cold_refusal;
 mutex_lock(&graph_io_lock);assert(gfx_cold_run()==-EALREADY);
 if(gfx_dispatch_trace_intent)assert(gfx_dispatch_trace_restore()==-EALREADY);
 assert(gfx_cold_diagnostic("recover")==-EPERM&&gfx_cold_diagnostic("gfx-powergate")==-EPERM);
 assert(gfx_cold_diagnostic("sample")==0);mutex_unlock(&graph_io_lock);
 assert(trace_restore_writes==restores&&trace_zero_writes==zeroes&&messages_sent==messages&&receive_journal.used==used);
 assert(gfx_cold_terminal_result==outcome&&gfx_cold_refusal==refusal);
 if(is("row-bound")) {
  gfx_dispatch_trace_before=gfx_dispatch_trace_written=gfx_dispatch_trace_after=UINT32_MAX;
  gfx_cold_sample_index=gfx_cold_elapsed_ms=UINT32_MAX;gfx_dispatch_trace_result=INT32_MIN;
  gfx_dispatch_trace_log("retained-final");
 }
 printf("PASS %s restores=%u zeroes=%u control=%u draw=%u samples=%u retained=%u maxrow=%u\n",fault,restores,zeroes,control_notifies,draw_notifies,gfx_cold_observation_samples,gfx_cold_retained_pages(),maximum_log_row);
 return 0;
}
'''
CASES=['success','row-bound','trace-admission-control','trace-admission-mask','trace-admission-target',
 'trace-intent-identity','trace-intent-request','trace-intent-mask','trace-write-identity','trace-write-mask',
 'trace-write-work','trace-restore-drop','trace-restore-identity','trace-before-draw-mask',
 'post-device-fault','observe-clock-stalled']


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 source,output=a.source.resolve(),a.output.resolve()
 if output.exists() or output.with_suffix('.actual-owner.c').exists():raise ValueError('New qualification output required')
 receipt=source/'native-dispatch-contract-owner-source-receipt.json';r=json.loads(receipt.read_text())
 assert r['profile']['version']==15 and r['profile']['maximum_scheduler_request_writes']==0
 for x in r['output_source_pins']:assert sha(source/x['name'])==x['sha256']
 assert sha(BASE_Q)==BASE_Q_SHA and json.loads(BASE_Q.read_text())['passed']
 output.parent.mkdir(parents=True,exist_ok=True)
 harness=output.with_suffix('.actual-owner.c');harness.write_text(base.make_harness(source))
 snapshot=output.with_suffix('.tester.py');snapshot.write_bytes(Path(__file__).read_bytes())
 fixtures=[];results=[];maximum=0
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 with tempfile.TemporaryDirectory(prefix='native-dispatch-c-q-') as td:
  binary=Path(td)/'owner';command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror',
   '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-unused-but-set-global',
   '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(harness),'-o',str(binary)]
  c=subprocess.run(command,text=True,capture_output=True)
  if c.returncode:
   output.with_suffix('.failure.json').write_text(json.dumps(dict(stage='compile',stdout=c.stdout,stderr=c.stderr),indent=2)+'\n')
   raise RuntimeError(c.stdout+'\n'+c.stderr)
  for case in CASES:
   x=subprocess.run([str(binary),case],text=True,capture_output=True,env=env)
   if x.returncode:
    output.with_suffix('.failure.json').write_text(json.dumps(dict(stage='case',case=case,stdout=x.stdout,stderr=x.stderr),indent=2)+'\n')
    raise RuntimeError(case+'\n'+x.stdout+'\n'+x.stderr)
   fixture=output.with_suffix('.'+case+'.log');fixture.write_text('\n'.join(row for row in x.stdout.splitlines() if 'm4rch ' in row)+'\n')
   fixtures.append(dict(case=case,path=str(fixture),bytes=fixture.stat().st_size,sha256=sha(fixture)))
   last=x.stdout.splitlines()[-1];maximum=max(maximum,int(last.split('maxrow=')[1]));results.append(dict(case=case,returncode=0,stdout=last))
 pins=[dict(path=str(path),sha256=sha(path)) for path in [receipt,BASE_Q,BASE_TEST,harness,snapshot,Path(__file__).resolve()]]
 pins += [dict(path=str(source/x['name']),sha256=x['sha256']) for x in r['output_source_pins']]
 report=dict(schema='m4rch.gfx-native-dispatch-contract.actual-C-qualification.v1',passed=True,
  hardware_access=False,kernel_build=False,source_path=str(source),source_receipt_sha256=sha(receipt),
  case_count=len(results),cases=results,compiler=command,sanitizers=['address','undefined'],
  maximum_new_log_row_bytes=maximum,actual_cold_ap_root_control_draw=True,actual_trace_restore_and_stop=True,
  maximum_trace_restore_writes=1,maximum_scheduler_request_writes=0,no_extra_notification=True,
  trace_restore_after_control33_before_draw=True,trace3_retained_on_success=True,
  unknown_retains_backing=True,frozen_unchanged_composition=dict(path=str(BASE_Q),sha256=BASE_Q_SHA,case_count=56,rerun=False),
  success_log_fixture=fixtures[0],actual_log_fixtures=fixtures,input_pins=pins,
  qualification='Actual production C with RAM physical/PM/cache/MMIO services. Narrow trace guard/order/once/refusal/retention checks compose frozen v13. Firmware trace generation, real cache behavior, fetch, execution, completion and retirement unproved.')
 with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(path=str(output),sha256=sha(output),cases=len(results),maxrow=maximum,success_fixture=fixtures[0])))


if __name__=='__main__':main()
