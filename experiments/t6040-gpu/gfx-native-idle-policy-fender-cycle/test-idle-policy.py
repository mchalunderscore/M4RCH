#!/usr/bin/env python3
"""Actual new C helper and exact v21 source projection, with RAM firmware actors."""
import argparse, hashlib, importlib.util, json, os, subprocess, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
PREFIX=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;typedef uint64_t u64;typedef uint8_t u8;
#define GFX_NATIVE_IDLE_POLICY_FENDER_CYCLE_TRIAL 1
#define GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL 1
#define APPLE_PMGR_GFX_VALID_BEFORE 1U
#define RECOVERY_STATUS 0x40000U
#define RECOVERY_REQUEST 0x24000U
#define RECOVERY_CONTROL 0xb4000U
#define RECOVERY_TRACE_MASK 0x3c000U
#define RECEIVE_CAPACITY 1024U
#define START 0x10U
#define EMPTY (1U<<16)
#define BIT(x) (1U<<(x))
#define READ_ONCE(x) (x)
static const char *which;
static bool is(const char *s){return !strcmp(which,s);}
static unsigned char ram[0x114000],asc_mem[0x2000],mbox_mem[0x1000],map0[0x4000],map1[0x4000];
static void *asc=asc_mem,*mbox=mbox_mem,*consumer=map0;
static void *gfx_gravity_preasc_consumer=map0,*gfx_gravity_preasc_asc=asc_mem,*gfx_gravity_preasc_mbox=mbox_mem;
static void *gfx_gravity_preasc_io[2]={map0,map1},*gfx_native_fender_enable_map=map1;
static bool gfx_gravity_preasc_region[2]={true,true};
static bool gfx_gravity_preasc_complete=true,gfx_gravity_preasc_unknown=false;
static bool gfx_postdraw_cycle_intent=true,gfx_postdraw_unknown=false,gfx_postdraw_off_attempted=false;
static bool gfx_postdraw_pm_put_attempted=false,gfx_postdraw_control_sealed=false;
static bool gfx_native_powergate_intent=true,gfx_native_powergate_admission_complete=true;
static bool gfx_native_powergate_request_attempted=false,gfx_postdraw_nmi_attempted=false;
static bool gfx_native_powergate_clear10_attempted=false,gfx_native_powergate_clear20_attempted=false;
static bool gfx_native_powergate_cpu_stopped=false,receive_enabled=true,receive_crashed=false;
static struct {u32 used,status;} receive_journal={0,0};
static bool gfx_cold_pipeline_intent=true,gfx_cold_complete=true,gfx_cold_sealed=true;
static bool gfx_cold_software_stopped=true,gfx_cold_running=false,gfx_cold_draw_intent=true;
static bool gfx_cold_draw_notify_sent=true,recovery_work_submitted=true;
static int gfx_cold_terminal_result=0;
static bool gfx_native_fender_enable_complete=true,gfx_native_fender_enable_unknown=false,gfx_native_fender_enable_attempted=true;
static bool gfx_native_fender_disable_intent=false,active_ok=true,held=true;
static u64 gfx_cold_counter;
static u32 gfx_cold_phase,gfx_cold_host_stop,gfx_cold_request_state,gfx_cold_request_flag;
static u32 gfx_cold_control[3],gfx_cold_trace_after=3;
static int graph_io_lock=1;
static unsigned long jiffies;
static unsigned int reads,hw_reads,pointer_reads,cleans,producer_writes,doorbell_words,barriers;
static unsigned int sleeps,mailbox_calls,counter_reads,snapshots,maxrow;
static bool notified,second_call,firmware_progressed;
struct apple_pmgr_gfx_reset_observation {u32 valid;bool domain_on;u32 before;};
static struct apple_pmgr_gfx_reset_observation physical={1,true,0x1f0003ff};
static void put(unsigned int o,u32 v){assert(o+4<=sizeof ram);memcpy(ram+o,&v,4);}
static u32 get(unsigned int o){u32 v;assert(o+4<=sizeof ram);memcpy(&v,ram+o,4);return v;}
static bool gfx_postdraw_active(void){return active_ok&&held;}
static void assert_lock(int *p){assert(p==&graph_io_lock&&*p==1);}
#define lockdep_assert_held assert_lock
static void row(const char *fmt,...){char b[1024];va_list ap;va_start(ap,fmt);int n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);
 assert(n>0&&n<512);if((unsigned int)n>maxrow)maxrow=n;fputs(b,second_call?stderr:stdout);}
#define pr_info row
static int gfx_cold_snapshot(const char *phase,unsigned int index,struct apple_pmgr_gfx_reset_observation *o){
 assert(!strcmp(phase,"idle-policy-before")&&!index&&graph_io_lock==1&&!snapshots&&!cleans&&!producer_writes&&!doorbell_words);
 snapshots++;*o=physical;
 row("m4rch gfx-cold-startup-physical: phase=%s index=%u result=0 valid=%#x domain_on=%u word=%#x operand_samples_atomic=0\n",phase,index,o->valid,o->domain_on,o->before);
 if(is("snapshot-ownership"))active_ok=false;
 if(is("snapshot-error"))return -EIO;if(is("snapshot-positive"))return 1;return 0;}
static void *recovery_ptr(unsigned int o){assert(o<sizeof ram);return ram+o;}
static void recovery_invalidate(void *p,size_t n){assert(p>= (void*)ram&&p+n<=(void*)(ram+sizeof ram));reads++;}
static void recovery_clean(void *p,size_t n){
 assert(graph_io_lock==1&&p==ram+0xb8840&&n==64&&!producer_writes&&!doorbell_words);cleans++;
 assert(cleans==1&&ram[0xb8840]==10&&ram[0xb8844]==1);
 for(unsigned i=0;i<64;i++)assert(ram[0xb8840+i]==(i==0?10:i==4?1:0));
 if(is("record-readback"))ram[0xb8848]=1;if(is("record-ownership"))active_ok=false;}
static u64 recovery_read64(unsigned int o){
 u64 v;assert(o+8<=sizeof ram);memcpy(&v,ram+o,8);pointer_reads++;
 if((is("pointer-initial")||(is("pointer-after-record")&&cleans)||(is("pointer-after-producer")&&producer_writes)||
     (is("pointer-after-notify")&&notified))&&o==0xa8)return v+8;
 return v;}
static u32 recovery_read32(unsigned int o){
 reads++;if(o==RECOVERY_STATUS+0xe438){counter_reads++;if(is("counter-prerecord")&&counter_reads==2)put(o,18);}
 return get(o);}
static void recovery_write32(unsigned int o,u32 v){
 assert(o==RECOVERY_CONTROL+16&&v==34&&cleans==1&&!producer_writes&&!doorbell_words&&graph_io_lock==1);
 producer_writes++;if(!is("producer-readback"))put(o,v);if(is("producer-ownership"))active_ok=false;}
static void gfx_cold_read_application(void){
 gfx_cold_control[0]=get(RECOVERY_CONTROL);gfx_cold_control[1]=get(RECOVERY_CONTROL+8);gfx_cold_control[2]=get(RECOVERY_CONTROL+16);}
static u32 readl(void *p){
 hw_reads++;assert(graph_io_lock==1);if(p==asc_mem+0x44)return is("start-clear")?0:START;
 if(p==asc_mem+0x48)return is("status-invalid")?UINT32_MAX:0x6c;
 if(p==mbox_mem+0x114)return notified&&(is("unknown-frame")||is("crash-frame")||is("invalid-frame")||is("valid-frame"))&&!mailbox_calls?0:EMPTY;
 if(p==mbox_mem+0x110)return producer_writes&&is("tx-full")?BIT(16):0;
 assert(0);return 0;}
static u64 readq(void *p){
 hw_reads++;assert(notified);if(p==mbox_mem+0x830)return is("invalid-frame")?UINT64_MAX:0x0042000000000000ULL;
 if(p==mbox_mem+0x838)return is("unknown-frame")?0:is("crash-frame")?1:32;
 assert(0);return 0;}
static bool receive_mailbox(u64 message,u64 metadata){
 assert(message==0x0042000000000000ULL&&metadata==32&&is("valid-frame"));mailbox_calls++;receive_journal.used++;return true;}
static void writeq(u64 value,void *p){
 assert(producer_writes==1&&get(RECOVERY_CONTROL+16)==34&&cleans==1&&barriers==1);
 assert(doorbell_words<2);if(!doorbell_words){assert(p==mbox_mem+0x800&&value==0x0084000000000000ULL);}
 else {assert(p==mbox_mem+0x808&&value==33);notified=true;put(RECOVERY_CONTROL+8,34);}
 doorbell_words++;}
static void wmb(void){assert(!barriers&&producer_writes==1&&!doorbell_words);barriers++;}
#define msecs_to_jiffies(x) (x)
#define jiffies_to_msecs(x) (x)
#define time_before(a,b) ((long)((a)-(b))<0)
static void usleep_range(unsigned int lo,unsigned int hi);
'''
SUFFIX=r'''
static void usleep_range(unsigned int lo,unsigned int hi){
 assert(lo==1000&&hi==2000&&notified&&doorbell_words==2);sleeps++;jiffies++;
 if(is("both-timeout")||is("processing-timeout"))return;
 if(is("late-processing")&&!gfx_idle_policy_processing_timeout)return;
 if(firmware_progressed)return;firmware_progressed=true;
 put(RECOVERY_CONTROL,34);put(RECOVERY_CONTROL+8,34);put(GFX_IDLE_POLICY_COUNTER,gfx_idle_policy_counter_before+1);
 if(!is("off-timeout")){put(GFX_IDLE_POLICY_STATUS+0x10,0);put(GFX_IDLE_POLICY_STATUS+0x18,0);put(GFX_IDLE_POLICY_STATUS+0x1c,8);}
 if(is("cursor-backward"))put(RECOVERY_CONTROL,32);
 if(is("cursor-ahead"))put(RECOVERY_CONTROL,35);
 if(is("prefetch-backward"))put(RECOVERY_CONTROL+8,32);
 if(is("prefetch-ahead"))put(RECOVERY_CONTROL+8,35);
 if(is("producer-changed"))put(RECOVERY_CONTROL+16,35);
 if(is("counter-missing"))put(GFX_IDLE_POLICY_COUNTER,gfx_idle_policy_counter_before);
 if(is("counter-jump"))put(GFX_IDLE_POLICY_COUNTER,gfx_idle_policy_counter_before+2);
 if(is("counter-backward"))put(GFX_IDLE_POLICY_COUNTER,gfx_idle_policy_counter_before-1);
 if(is("off-invalid"))put(GFX_IDLE_POLICY_STATUS+0x10,UINT32_MAX);
 if(is("ready-invalid"))put(GFX_IDLE_POLICY_STATUS+0x14,UINT32_MAX);
 if(is("generation-invalid"))put(GFX_IDLE_POLICY_STATUS+0x1c,UINT32_MAX);
 if(is("application-stop"))gfx_cold_host_stop=1;
 if(is("application-counter"))gfx_cold_counter=1;
 if(is("application-phase"))gfx_cold_phase=2;
 if(is("application-request"))gfx_cold_request_flag=1;
 if(is("record-terminal"))ram[GFX_IDLE_POLICY_RECORD+5]=1;
 if(is("poll-ownership"))active_ok=false;
 if(is("receive-journal"))receive_journal.status=1;
}
static void init(void){
 u64 v;
 v=GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_STATUS;memcpy(ram+0xa8,&v,8);
 v=GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_STATUS;memcpy(ram+0xb0,&v,8);
 for(unsigned i=0;i<3;i++){v=GFX_IDLE_POLICY_ARENA_BASE+RECOVERY_CONTROL+i*8;memcpy(ram+0x41a0+i*8,&v,8);put(RECOVERY_CONTROL+i*8,33);}
 v=GFX_IDLE_POLICY_ARENA_BASE+0xb8000;memcpy(ram+0x41b8,&v,8);
 ram[GFX_IDLE_POLICY_RECORD]=22;put(GFX_IDLE_POLICY_COUNTER,is("success-high-baseline")?0xabcdef00:17);
 put(GFX_IDLE_POLICY_STATUS+0x10,1);put(GFX_IDLE_POLICY_STATUS+0x14,1);put(GFX_IDLE_POLICY_STATUS+0x18,1);put(GFX_IDLE_POLICY_STATUS+0x1c,7);
 if(is("already-off")||is("processing-timeout"))put(GFX_IDLE_POLICY_STATUS+0x10,0);
 if(is("no-cycle"))gfx_postdraw_cycle_intent=false;
 if(is("cycle-unknown"))gfx_postdraw_unknown=true;
 if(is("inactive"))active_ok=false;if(is("not-held"))held=false;
 if(is("off-attempted"))gfx_postdraw_off_attempted=true;
 if(is("put-attempted"))gfx_postdraw_pm_put_attempted=true;
 if(is("sealed-control"))gfx_postdraw_control_sealed=true;
 if(is("no-admission"))gfx_native_powergate_admission_complete=false;
 if(is("202-already"))gfx_native_powergate_request_attempted=true;
 if(is("nmi-already"))gfx_postdraw_nmi_attempted=true;
 if(is("cpu-stopped"))gfx_native_powergate_cpu_stopped=true;
 if(is("receive-disabled"))receive_enabled=false;
 if(is("receive-crashed"))receive_crashed=true;
 if(is("journal-full"))receive_journal.used=RECEIVE_CAPACITY;
 if(is("draw-incomplete"))gfx_cold_complete=false;
 if(is("draw-not-sealed"))gfx_cold_sealed=false;
 if(is("draw-running"))gfx_cold_running=true;
 if(is("fender-enable-incomplete"))gfx_native_fender_enable_complete=false;
 if(is("fender-disable-already"))gfx_native_fender_disable_intent=true;
 if(is("preasc-incomplete"))gfx_gravity_preasc_complete=false;
 if(is("mapping-mismatch"))gfx_native_fender_enable_map=map0;
 if(is("region-unowned"))gfx_gravity_preasc_region[1]=false;
 if(is("consumer-mismatch"))gfx_gravity_preasc_consumer=map1;
 if(is("physical-domain-off"))physical.domain_on=false;
 if(is("physical-invalid"))physical.valid=0;
 if(is("physical-busy"))physical.before|=0x800;
 if(is("physical-gated"))physical.before=0x1400034f;
 if(is("baseline-cursor"))put(RECOVERY_CONTROL,32);
 if(is("baseline-producer"))put(RECOVERY_CONTROL+16,34);
 if(is("baseline-counter-invalid"))put(GFX_IDLE_POLICY_COUNTER,UINT32_MAX);
 if(is("baseline-off-invalid"))put(GFX_IDLE_POLICY_STATUS+0x10,UINT32_MAX);
 if(is("staged-opcode"))ram[GFX_IDLE_POLICY_RECORD]=10;
 if(is("staged-tail"))ram[GFX_IDLE_POLICY_RECORD+63]=1;
}
int main(int argc,char **argv){
 assert(argc==2);which=argv[1];init();bool before202=gfx_native_powergate_request_attempted,beforeoff=gfx_postdraw_off_attempted,beforeput=gfx_postdraw_pm_put_attempted;int ret=gfx_native_idle_policy_before_202();
 bool expected=is("success")||is("success-high-baseline")||is("physical-gated")||is("already-off")||
  is("processing-timeout")||is("off-timeout")||is("both-timeout")||is("late-processing")||is("valid-frame");
 if(expected){assert(ret==0&&gfx_idle_policy_complete&&!gfx_idle_policy_unknown&&gfx_idle_policy_continue_teardown);
  assert(cleans==1&&producer_writes==1&&doorbell_words==2&&barriers==1);
  assert(gfx_idle_policy_producer_verified&&gfx_idle_policy_notify_sent&&gfx_idle_policy_record_verified);
  assert(gfx_idle_policy_command_processed!=gfx_idle_policy_processing_timeout);
  assert(gfx_idle_policy_gpu_off_observed!=gfx_idle_policy_gpu_off_timeout);
  if(is("both-timeout")||is("processing-timeout")||is("late-processing"))assert(gfx_idle_policy_processing_timeout&&gfx_idle_policy_processing_polls==2001&&gfx_idle_policy_processing_elapsed_ms==2000);
  if(is("both-timeout")||is("off-timeout"))assert(gfx_idle_policy_gpu_off_timeout&&gfx_idle_policy_off_polls==2001&&gfx_idle_policy_off_elapsed_ms==2000);
  if(is("late-processing"))assert(!gfx_idle_policy_command_processed&&gfx_idle_policy_control[0]==34&&gfx_idle_policy_counter-gfx_idle_policy_counter_before==1);
  if(is("valid-frame"))assert(mailbox_calls==1&&gfx_idle_policy_messages==1);
 }else {assert(ret<0&&!gfx_idle_policy_complete&&gfx_idle_policy_unknown&&!gfx_idle_policy_continue_teardown);}
 assert(gfx_native_powergate_request_attempted==before202&&gfx_postdraw_off_attempted==beforeoff&&gfx_postdraw_pm_put_attempted==beforeput);
 assert(cleans<=1&&producer_writes<=1&&doorbell_words<=2);
 assert(gfx_idle_policy_processing_polls<=2001&&gfx_idle_policy_off_polls<=2001);
 assert(gfx_idle_policy_processing_elapsed_ms<=2000&&gfx_idle_policy_off_elapsed_ms<=2000);
 unsigned r=reads,h=hw_reads,p=pointer_reads,c=cleans,w=producer_writes,d=doorbell_words,b=barriers,s=sleeps,q=snapshots;
 second_call=true;assert(gfx_native_idle_policy_before_202()==-EALREADY);
 assert(r==reads&&h==hw_reads&&p==pointer_reads&&c==cleans&&w==producer_writes&&d==doorbell_words&&b==barriers&&s==sleeps&&q==snapshots);
 fprintf(stderr,"PASS %s result=%d clean=%u producer=%u notification_words=%u sleeps=%u processing_polls=%u off_polls=%u maxrow=%u\n",which,ret,cleans,producer_writes,doorbell_words,sleeps,gfx_idle_policy_processing_polls,gfx_idle_policy_off_polls,maxrow);
 return 0;
}
'''
CASES=['success','success-high-baseline','physical-gated','already-off','processing-timeout','off-timeout','both-timeout','late-processing','valid-frame',
 'no-cycle','cycle-unknown','inactive','not-held','off-attempted','put-attempted','sealed-control','no-admission','202-already','nmi-already','cpu-stopped','receive-disabled','receive-crashed','journal-full','draw-incomplete','draw-not-sealed','draw-running','fender-enable-incomplete','fender-disable-already','preasc-incomplete','mapping-mismatch','region-unowned','consumer-mismatch',
 'snapshot-error','snapshot-positive','snapshot-ownership','physical-domain-off','physical-invalid','physical-busy','pointer-initial','baseline-cursor','baseline-producer','baseline-counter-invalid','baseline-off-invalid','staged-opcode','staged-tail','counter-prerecord','record-readback','record-ownership','pointer-after-record','producer-readback','producer-ownership','pointer-after-producer','tx-full','pointer-after-notify','unknown-frame','crash-frame','invalid-frame','start-clear','status-invalid','cursor-backward','cursor-ahead','prefetch-backward','prefetch-ahead','producer-changed','counter-missing','counter-jump','counter-backward','off-invalid','ready-invalid','generation-invalid','application-stop','application-counter','application-phase','application-request','record-terminal','poll-ownership','receive-journal']
def load_preparer():
 spec=importlib.util.spec_from_file_location('idle_source_preparer',HERE/'prepare-idle-policy-owner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'out/gfx-native-descriptor-fender-cycle/prepared-owner-v1');p.add_argument('--prepared',type=Path,default=ROOT/'out/gfx-native-idle-policy-fender-cycle/prepared-owner-v1');p.add_argument('--output',type=Path,default=ROOT/'out/gfx-native-idle-policy-fender-cycle/idle-policy-qualification-v1.json');a=p.parse_args()
 out=a.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
 if out.exists() or a.prepared.exists():raise FileExistsError('New qualification and prepared source required')
 helper=HERE/'gfx-native-idle-policy.h';runtime=ROOT/'experiments/t6040-gpu/gfx-native-fender-runtime-cycle/gfx-native-runtime-state.h'
 if pin(runtime)['sha256']!='4e25f120981774cef205020ea8d59683c42d549477ce174af427b7b3c61d8497':raise ValueError('Frozen runtime helper differs')
 actual=out.with_suffix('.actual-helper.c');tester=out.with_suffix('.tester.py')
 actual.write_text(PREFIX+runtime.read_text()+helper.read_text()+SUFFIX);tester.write_bytes(Path(__file__).read_bytes())
 results=[]
 with tempfile.TemporaryDirectory(prefix='m4rch-idle-policy-') as tmp:
  binary=Path(tmp)/'actual-helper';command=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(actual),'-o',str(binary)]
  build=subprocess.run(command,capture_output=True,text=True)
  if build.returncode:out.with_suffix('.build-failed.log').write_text(build.stderr);raise RuntimeError(build.stderr)
  for case in CASES:
   r=subprocess.run([str(binary),case],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'});fixture=out.with_suffix('.'+case+'.log');fixture.write_text(r.stdout)
   if r.returncode:out.with_suffix('.'+case+'.failed.log').write_text(r.stderr);raise RuntimeError(case+': '+r.stderr)
   results.append(dict(case=case,returncode=r.returncode,result=r.stderr.strip(),fixture=pin(fixture)))
 prep=load_preparer();source=prep.prepare(a.source,a.prepared);sp=a.prepared/prep.RECEIPT
 old=json.loads((a.source/'native-descriptor-fender-cycle-owner-source-receipt.json').read_bytes());original={r['name']:(a.source/r['name']).read_bytes() for r in old['output_source_pins']};projected=prep.project_source(original)
 assert all((a.prepared/n).read_bytes()==b for n,b in projected.items())
 assert projected['graph-before.bin']==original['graph-before.bin']
 assert projected['graph-contract.h'].replace(prep.NEW.encode(),prep.OLD.encode())==original['graph-contract.h']
 post=projected['gfx-postdraw-native-nmi-cycle.h'];basepost=original['gfx-postdraw-native-nmi-cycle.h'].replace(prep.OLD.encode(),prep.NEW.encode())
 old_ack=basepost[basepost.index(b'static int gfx_native_powergate_ack(void)'):basepost.index(b'static void gfx_postdraw_nmi_log')]
 assert old_ack in post
 assert post.count(b'ret=gfx_native_idle_policy_before_202();')==1 and post.count(b'ret=gfx_native_powergate_ack();')==1
 assert post.index(b'if(!gfx_postdraw_draw_qualified())')<post.index(b'ret=gfx_native_idle_policy_before_202();')<post.index(b'gfx_postdraw_log("idle-policy-refresh-admission",0);')<post.index(b'ret=gfx_native_powergate_ack();')
 composed=[ROOT/'out/gfx-native-fender-off-cycle/fender-off-qualification-v1.json',ROOT/'out/gfx-native-fender-runtime-cycle/runtime-qualification-v1.json',ROOT/'out/gfx-native-descriptor-fender-cycle/descriptor-qualification-v1.json']
 report=dict(schema='m4rch.gfx-native-idle-policy.actual-C-qualification.v1',passed=True,case_count=len(CASES),cases=results,compiler=dict(command=command,returncode=build.returncode),helper_sha256=pin(helper)['sha256'],source_receipt_sha256=pin(sp)['sha256'],input_pins=[pin(p) for p in [helper,HERE/'prepare-idle-policy-owner.py',Path(__file__),runtime,actual,tester,sp,*[ROOT/n for n in prep.ABI_PINS],*composed]],success_log_fixture=results[0]['fixture'],clean_timeout_log_fixtures={c:next(r['fixture'] for r in results if r['case']==c) for c in ['processing-timeout','off-timeout','both-timeout','late-processing']},hardware_access=False,hardware_actions=[],kernel_build=False,maximum_record_cleans=1,maximum_producer_writes=1,maximum_mailbox_writes=2,maximum_control_notifications=1,caller_order_verified=True,unchanged_qualifications_repeated=False,source_projection=dict(all_outputs_rederived=True,graph_arena_unchanged=True,compiled_graph_bytes_unchanged=True,inherited_ACK_NMI_body_unchanged=True,sole_helper_before_fresh_admission_before_sole202=True),qualification='Actual production helper compiled unchanged with RAM/cache/transport fixtures and unchanged frozen runtime predicate under ASan/UBSan. Fresh high-counter delta, independent timeout paths, late completion, ownership/pointer/cursor/counter/frame failures and refused second call are exercised. Exact source projection and inheritedACK/NMI data checked; no real hardware timing, Apple execution or physicalOFF/work retirement proved.')
 out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,case_count=len(CASES),report=pin(out),source_receipt=pin(sp),helper=pin(helper),success_log_fixture=report['success_log_fixture'],clean_timeout_log_fixtures=report['clean_timeout_log_fixtures'])))
if __name__=='__main__':main()
