#!/usr/bin/env python3
"""Exercise actual v14 C through cold AP/root/draw/release/retention in RAM.

Hardware, physical/cache and allocation services are intercepted. Frozen v13
qualifications compose unchanged checks; this executes new intervention edges.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess,tempfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_TEST=ROOT/'experiments/t6040-gpu/gfx-cold-render/test-cold-render-owner.py'
BASE_Q=ROOT/'out/gfx-cold-render/owner-qualification-v8.json'
BASE_Q_SHA='deea9356799207aba1d07c08c6858a2200abaf8ff3d5189d0ae401d9c89b0cf2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Qualification hook changed: '+a[:80])
 return s.replace(a,b,1)
spec=importlib.util.spec_from_file_location('frozen_cold_tester',BASE_TEST);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.PREFIX=base.PREFIX.replace('#define GFX_COLD_RENDER_TRIAL 1','#define GFX_COLD_RENDER_PAUSE_RELEASE_TRIAL 1\n#include "gfx-cold-pause-state.h"')
base.PREFIX=once(base.PREFIX,'static unsigned int messages_sent,','static unsigned int scheduler_writes;\nstatic bool scheduler_state_installed;\nstatic unsigned int messages_sent,')
base.PREFIX=once(base.PREFIX,'if(!is("observe-clock-stalled")||!draw_pending)jiffies++;','if(!is("ack-clock-stalled")||!scheduler_writes)jiffies++;')
base.PREFIX=once(base.PREFIX,'if(base==0x288020000ULL)return ', 'if(base==0x288020000ULL && gfx_cold_sample_index==2 && is("sample-ksm-missing"))return NULL;\n if(base==0x288020000ULL)return ')
base.PREFIX=once(base.PREFIX,'if(base==0x28800c000ULL)return ', 'if(base==0x28800c000ULL && gfx_cold_sample_index==2 && is("sample-fault-missing"))return NULL;\n if(base==0x28800c000ULL)return ')
base.PREFIX=once(base.PREFIX,' if(is("physical-busy"))',' if(gfx_cold_sample_index==2 && is("release-physical-busy"))o->before|=BIT(11);\n if(is("physical-busy"))')
base.MOCK=once(base.MOCK,'static u64 ptd;','static void reg64(unsigned int offset,u64 value){memcpy(ksm_memory+offset,&value,8);}\nstatic u64 ptd;')
base.MOCK=once(base.MOCK,' if(p==(char*)mbox+0x800){', ''' if(p==ksm_memory+0x11c8) {
  u64 before;memcpy(&before,p,8);assert(before==3&&v==(before&~1ULL));
  scheduler_writes++;assert(scheduler_writes==1);memcpy(p,&v,8);
  if(is("write-dropped")||is("readback-reasserted"))reg64(0x11c8,3);
  if(is("readback-otherbits"))reg64(0x11c8,6);
  if(is("readback-invalid"))reg64(0x11c8,~0ULL);
  if(is("ack-invalid"))reg64(0x11d0,~0ULL);
  if(is("ack-timeout")||is("ack-clock-stalled")||is("ack-delay"))reg64(0x11d0,3);
  if(is("ack-zero"))reg64(0x11d0,0);
  return;
 }
 if(p==(char*)mbox+0x800){''')
base.MOCK=once(base.MOCK,' firmware_step++;',''' firmware_step++;
 if(draw_pending && !scheduler_state_installed && jiffies>=gfx_cold_observe_start+100) {
  scheduler_state_installed=true;
  reg64(0x1038,3);reg64(0x1040,0);reg64(0x11c8,3);reg64(0x11d0,2);
  for(unsigned int i=0;i<2;i++){fw32(recovery_work_cursors[i],1);fw32(recovery_work_cursors[i]+8,1);}
  if(is("request-zero"))reg64(0x11c8,0);
  if(is("request-one"))reg64(0x11c8,1);
  if(is("request-two"))reg64(0x11c8,2);
  if(is("request-otherbits"))reg64(0x11c8,7);
  if(is("request-invalid"))reg64(0x11c8,~0ULL);
  if(is("ack-zero-eligibility"))reg64(0x11d0,0);
  if(is("ack-three-eligibility"))reg64(0x11d0,3);
  if(is("enable-zero"))reg64(0x1038,0);
  if(is("enable-extra"))reg64(0x1040,1);
  if(is("config-changed"))reg64(0x1148,1);
  if(is("completion-status"))reg64(0x1168,1);
  if(is("work-not-consumed"))fw32(recovery_work_cursors[1]+8,0);
  if(is("target-progress"))owned[RENDER_FIRST_PAGE+20]->data[0]^=1;
  if(is("software-progress"))owned[RENDER_FIRST_PAGE+47]->data[0]=1;
  if(is("hardware-progress"))owned[RENDER_FIRST_PAGE+RENDER_HW_COMPLETION_FIRST+3]->data[0]=1;
  if(is("sample-fault")){u64 value=7;memcpy(fault_memory+0x18c0,&value,8);}
 }
 if(scheduler_writes && is("ack-delay") && jiffies>=gfx_cold_observe_start+105)reg64(0x11d0,2);
 if(scheduler_writes && jiffies>=gfx_cold_observe_start+1000) {
  if(is("later-reasserted"))reg64(0x11c8,3);
  if(is("later-otherbits"))reg64(0x11c8,4);
 }
''')
base.MOCK=once(base.MOCK,'static void inject(const char *row)\n{','''static void inject(const char *row)
{
 if(strstr(row,"gfx-cold-pause-release: phase=intent ")) {
  if(is("pause-intent-request"))reg64(0x11c8,7);
  if(is("pause-intent-config"))reg64(0x1150,1);
  if(is("pause-intent-fault")){u64 value=1;memcpy(fault_memory+0x18c0,&value,8);}
  if(is("pause-intent-identity"))owned[4]->pa^=0x4000;
 }
 if(strstr(row,"gfx-cold-pause-release: phase=write-intent ")) {
  if(is("last-request"))reg64(0x11c8,7);
  if(is("last-ownership"))held=false;
 }
 if(strstr(row,"gfx-cold-pause-release: phase=readback ")&&is("poll-ownership"))consumer->dev.power.runtime_error=-EIO;
''')
# The original setup preserves exact source graph/job/backing and four queue VAs.
setup=base.MAIN[:base.MAIN.index('int main(')]
setup=once(setup,' consumer_storage.dev=', ''' for(unsigned int i=0;i<4;i++)reg64(0x1148+i*8,BIT_ULL(54)|render_vas[RENDER_HW_COMPLETION_FIRST+i]|1ULL);
 consumer_storage.dev=''')
base.MAIN=setup+r'''
int main(int argc,char **argv)
{
 setvbuf(stdout,NULL,_IONBF,0);assert(argc==2);fault=argv[1];setup();
 assert(gfx_cold_startup_admission(2,true,false,false,false)==0);
 int ret=gfx_coord_owner_begin_on();if(!ret){started=true;ret=actual_automatic_entry();}
 bool success=is("success")||is("ack-delay")||is("ack-zero")||is("later-reasserted")||is("later-otherbits")||is("row-bound");
 if(success) {
  assert(!ret&&gfx_cold_complete&&gfx_pause_complete&&gfx_pause_write_issued);
  assert(gfx_pause_before==3&&gfx_pause_written==2&&gfx_pause_polls<=GFX_PAUSE_POLLS);
  assert(scheduler_writes==1&&gfx_cold_observation_samples==6);
  if(is("later-reasserted"))assert(gfx_pause_rewritten&&gfx_pause_reasserted);
  else if(is("later-otherbits"))assert(gfx_pause_rewritten&&!gfx_pause_reasserted);
  else assert(!gfx_pause_rewritten&&!gfx_pause_reasserted);
 } else assert(!gfx_cold_complete);
 assert(control_notifies==1&&draw_notifies==1&&root_notifies==1&&endpoint_starts==2);
 assert(gfx_cold_software_stopped&&gfx_cold_sealed&&!gfx_cold_running&&!receive_enabled);
 assert(gfx_cold_retained_pages()==174&&installed&&device_context_retained);
 assert(scheduler_writes<=1);
 if(strstr(fault,"readback-")||is("write-dropped")||(strstr(fault,"ack-")&&!strstr(fault,"eligibility"))||is("poll-ownership"))assert(scheduler_writes==1);
 if(strstr(fault,"request-")||strstr(fault,"eligibility")||strstr(fault,"enable-")||strstr(fault,"config-")||strstr(fault,"progress")||strstr(fault,"intent-")||strstr(fault,"last-")||strstr(fault,"sample-")||is("work-not-consumed")||is("completion-status")||is("release-physical-busy"))assert(scheduler_writes==0);
 if(!is("last-ownership"))assert(held);
 if(!is("poll-ownership"))assert(!consumer->dev.power.runtime_error);
 unsigned int writes=scheduler_writes,messages=messages_sent,used=receive_journal.used;
 int result=gfx_cold_terminal_result;const char *refusal=gfx_cold_refusal;
 mutex_lock(&graph_io_lock);assert(gfx_cold_run()==-EALREADY);
 if(gfx_pause_intent)assert(gfx_cold_pause_release()==-EALREADY);
 assert(gfx_cold_diagnostic("recover")==-EPERM&&gfx_cold_diagnostic("gfx-powergate")==-EPERM);
 assert(gfx_cold_diagnostic("sample")==0);mutex_unlock(&graph_io_lock);
 assert(scheduler_writes==writes&&messages_sent==messages&&receive_journal.used==used);
 assert(gfx_cold_terminal_result==result&&gfx_cold_refusal==refusal);
 if(is("row-bound")) {
  gfx_pause_before=gfx_pause_written=gfx_pause_after=gfx_pause_ack=UINT64_MAX;
  gfx_pause_polls=gfx_cold_sample_index=gfx_cold_elapsed_ms=UINT32_MAX;
  gfx_pause_result=INT32_MIN;gfx_pause_log("retained-final");
 }
 printf("PASS %s writes=%u control=%u draw=%u samples=%u retained=%u maxrow=%u\n",fault,scheduler_writes,control_notifies,draw_notifies,gfx_cold_observation_samples,gfx_cold_retained_pages(),maximum_log_row);
 return 0;
}
'''
CASES=['success','ack-delay','ack-zero','later-reasserted','later-otherbits','row-bound','request-zero','request-one','request-two','request-otherbits','request-invalid','ack-zero-eligibility','ack-three-eligibility','enable-zero','enable-extra','config-changed','completion-status','work-not-consumed','target-progress','software-progress','hardware-progress','sample-fault','sample-fault-missing','sample-ksm-missing','release-physical-busy','pause-intent-request','pause-intent-config','pause-intent-fault','pause-intent-identity','last-request','last-ownership','write-dropped','readback-reasserted','readback-otherbits','readback-invalid','ack-invalid','ack-timeout','ack-clock-stalled','poll-ownership']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
 if output.exists() or output.with_suffix('.actual-owner.c').exists():raise ValueError('New qualification output required')
 receipt=source/'cold-render-pause-release-owner-source-receipt.json';r=json.loads(receipt.read_text());assert r['profile']['version']==14
 for x in r['output_source_pins']:assert sha(source/x['name'])==x['sha256']
 assert sha(BASE_Q)==BASE_Q_SHA
 output.parent.mkdir(parents=True,exist_ok=True);harness=output.with_suffix('.actual-owner.c');harness.write_text(base.make_harness(source));tester=output.with_suffix('.tester.py');tester.write_bytes(Path(__file__).read_bytes())
 fixtures=[];results=[];maxrow=0;env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
 with tempfile.TemporaryDirectory(prefix='cold-pause-c-q-') as td:
  binary=Path(td)/'owner';command=['clang','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-unused-but-set-global','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(source),str(harness),'-o',str(binary)]
  c=subprocess.run(command,text=True,capture_output=True)
  if c.returncode:
   output.with_suffix('.failure.json').write_text(json.dumps(dict(stage='compile',stdout=c.stdout,stderr=c.stderr),indent=2)+'\n');raise RuntimeError(c.stdout+'\n'+c.stderr)
  for case in CASES:
   x=subprocess.run([str(binary),case],text=True,capture_output=True,env=env)
   if x.returncode:
    output.with_suffix('.failure.json').write_text(json.dumps(dict(stage='case',case=case,stdout=x.stdout,stderr=x.stderr),indent=2)+'\n');raise RuntimeError(case+'\n'+x.stdout+'\n'+x.stderr)
   raw='\n'.join(row for row in x.stdout.splitlines() if 'm4rch ' in row)+'\n';path=output.with_suffix('.'+case+'.log');path.write_text(raw)
   fixtures.append(dict(case=case,path=str(path),sha256=sha(path),bytes=path.stat().st_size));last=x.stdout.splitlines()[-1];maxrow=max(maxrow,int(last.split('maxrow=')[1]));results.append(dict(case=case,returncode=0,stdout=last))
 pins=[dict(path=str(p),sha256=sha(p)) for p in [receipt,BASE_Q,BASE_TEST,harness,tester,Path(__file__).resolve()]]+[dict(path=str(source/x['name']),sha256=x['sha256']) for x in r['output_source_pins']]
 report=dict(schema='m4rch.gfx-cold-render-pause-release.actual-C-qualification.v1',passed=True,hardware_access=False,kernel_build=False,source_path=str(source),source_receipt_sha256=sha(receipt),case_count=len(results),cases=results,compiler=command,sanitizers=['address','undefined'],maximum_new_log_row_bytes=maxrow,actual_cold_ap_root_control_draw=True,actual_intervention_and_stop=True,maximum_mmio_request_writes=1,no_ack_or_bit1_write=True,unknown_retains_backing=True,frozen_unchanged_composition=dict(path=str(BASE_Q),sha256=BASE_Q_SHA,case_count=56,rerun=False),success_log_fixture=fixtures[0],actual_log_fixtures=fixtures,input_pins=pins,qualification='Actual production C pipeline and bit0 intervention with RAM MMIO/PM/cache/page services; unchanged v13 checks composed. Firmware mutex/reason ownership and actual hardware behavior are unproved.')
 with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(dict(path=str(output),sha256=sha(output),cases=len(results),maxrow=maxrow,success_fixture=fixtures[0])))
if __name__=='__main__':main()
