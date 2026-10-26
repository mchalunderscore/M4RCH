#!/usr/bin/env python3
"""ASan/UBSan fault replay of the actual new native PWRGATE header."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

PREAMBLE=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64; typedef uint32_t u32; typedef uint8_t u8;
#define BIT(n) (1U<<(n))
#define START BIT(4)
#define EMPTY BIT(17)
#define GFX_NATIVE_POWERGATE_TRIAL 1
#define GFX_NATIVE_STATUS_ZERO_TRIAL 1
#define GFX_RESET_SCOPE_PAGES 174U
#define RECOVERY_STATUS 0x100000U
#define RECOVERY_REQUEST 0x200000U
#define RECOVERY_CONTROL 0x300000U
#define RECOVERY_CONTROL_INITIAL 32U
#define RECOVERY_CONTROL_LAST 128U
#define RECEIVE_CAPACITY 65536U
#define READ_ONCE(v) (v)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof(*(a)))
struct { struct { struct { int usage_count,runtime_error; } power; } dev; } consumer_storage;
#define consumer (&consumer_storage)
static char asc_storage[0x1000],mbox_storage[0x1000];
static void *asc=asc_storage,*mbox=mbox_storage;
static bool held,backing,recovery_session_failed,recovery_work_submitted;
static bool receive_enabled,receive_crashed,gfx_poweroff_gate_consumed;
static bool gfx_reset_scope_host_stopped,gfx_poweroff_start_clear_attempted;
static bool gfx_reset_scope_sealed,idle_work;
static bool started,root_sent,device_context_retained;
static void *owned[174];static unsigned int pins;
static unsigned int recovery_completed_total;
static struct { unsigned int status,used; } receive_journal;
static int graph_io_lock,recovery_receive_work;
static unsigned long jiffies;
static unsigned int requests,qwrites,cpuwrites,pmputs,offcalls,cancels,operations;
static unsigned int diagnostic_calls;
static unsigned int control_reads_after10,rx_reads_after_ack,status_reads_after_ack;
static u32 control44,status48,phase,request_state,request_flag,host_stop;
static u32 controls[3]; static u64 counter;
static u64 rx_messages[70],rx_metadata[70]; static unsigned int rx_count,rx_pos;
static bool rx_admission_bad,rx_after_ack_bad,rx_before_cpu_pending,tx_full;
static bool rx_admission_pending,post_stop_nonidle;
static bool late_ack,no_ack,drop_clear10,drop_clear20,mutate_second,reassert_second;
static bool invalid_second,invalid_idle; static unsigned int idle_delay;
static int delegated_result;static bool delegated_consumes_pm;
static char logs[65536];static size_t log_used;
static void pr_info(const char *fmt,...)
{
 va_list ap;va_start(ap,fmt);
 int n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);
 assert(n>=0&&(size_t)n<sizeof(logs)-log_used);log_used+=(size_t)n;
}
static bool has_log(const char *s){return strstr(logs,s)!=NULL;}
static int atomic_read(const int *v){return *v;}
static bool sysfs_streq(const char *a,const char *b){return !strcmp(a,b);}
static unsigned long msecs_to_jiffies(unsigned int ms){return ms;}
static bool time_before(unsigned long a,unsigned long b){return (long)(a-b)<0;}
static void usleep_range(unsigned int lo,unsigned int hi)
{assert(lo==1000&&hi==1100);jiffies++;}
static void wmb(void){}
static void lockdep_assert_held(const int *lock){assert(lock==&graph_io_lock&&*lock==1);}
static void mutex_lock(int *lock){assert(*lock==0);*lock=1;}
static void mutex_unlock(int *lock){assert(*lock==1);*lock=0;}
static void gfx_coord_owner_pin(void){pins++;}
static void cancel_delayed_work(int *work)
{assert(work==&recovery_receive_work&&graph_io_lock==1&&recovery_session_failed);cancels++;}
static bool gfx_reset_scope_backing(void){return backing&&held;}
static bool recovery_idle(void){return idle_work;}
static u32 recovery_read32(unsigned int offset)
{
 if(offset==RECOVERY_STATUS+0x4900)return phase;
 if(offset==RECOVERY_STATUS+0x4910)return host_stop;
 if(offset==RECOVERY_REQUEST)return request_state;
 if(offset==RECOVERY_REQUEST+4)return request_flag;
 if(offset==RECOVERY_CONTROL)return controls[0];
 if(offset==RECOVERY_CONTROL+8)return controls[1];
 if(offset==RECOVERY_CONTROL+16)return controls[2];
 assert(false);return 0;
}
static u64 recovery_read64(unsigned int offset)
{assert(offset==RECOVERY_STATUS+0x48f0);return counter;}
static u32 readl(void *address);
static u64 readq(void *address);
static void writel(u32 value,void *address);
static void writeq(u64 value,void *address);
static bool receive_mailbox(u64 message,u64 metadata)
{
 if((metadata&0xff)==32&&message==0x0042000000000000ULL) {
  if(receive_journal.used==RECEIVE_CAPACITY){receive_journal.status=3;return false;}
  receive_journal.used++;return true;
 }
 if((metadata&0xff)==1)receive_crashed=true;
 receive_journal.status|=9;return false;
}
static int gfx_reset_scope_result(const char *command,int ret)
{assert(!strcmp(command,"gfx-powergate"));operations++;return ret;}
static int gfx_poweroff_sample(void){diagnostic_calls++;return 0;}
static int gfx_reset_scope_snapshot(void){diagnostic_calls++;return 0;}
static int gfx_poweroff_attempt(void);
'''

BODY=r'''
static u32 readl(void *address)
{
 if(address==(char*)asc+0x44) {
  if(gfx_native_powergate_clear10_attempted&&!gfx_native_powergate_clear20_attempted) {
   control_reads_after10++;
   if(control_reads_after10==2) {
    if(mutate_second)control44|=0x400;
    if(reassert_second)control44|=START;
    if(invalid_second)return ~0U;
   }
  }
  return control44;
 }
 if(address==(char*)asc+0x48) {
  if(gfx_native_powergate_clear20_attempted&&post_stop_nonidle)return 0x6c;
  if(gfx_native_powergate_ack_observed) {
   if(invalid_idle)return ~0U;
   status_reads_after_ack++;
   if(status_reads_after_ack<=idle_delay)return 0x6c;
  }
  return status48;
 }
 if(address==(char*)mbox+0x110)return tx_full?BIT(16):0;
 if(address==(char*)mbox+0x114) {
  if(!requests&&rx_admission_pending)return 0;
  if(!requests&&rx_admission_bad)return ~0U;
  if(gfx_native_powergate_ack_observed) {
   rx_reads_after_ack++;
   if(rx_after_ack_bad)return ~0U;
   if(rx_before_cpu_pending&&rx_reads_after_ack>=2)return 0;
  }
  if(requests&&!no_ack&&rx_pos<rx_count)return 0;
  return EMPTY;
 }
 assert(false);return 0;
}
static u64 readq(void *address)
{
 assert(rx_pos<rx_count);
 if(address==(char*)mbox+0x830)return rx_messages[rx_pos];
 assert(address==(char*)mbox+0x838);
 u64 value=rx_metadata[rx_pos++];
 if(late_ack)jiffies=2000;
 return value;
}
static void writeq(u64 value,void *address)
{
 assert(graph_io_lock==1&&gfx_native_powergate_intent&&gfx_reset_scope_sealed);
 assert(recovery_session_failed&&held&&(control44&START));qwrites++;
 if(address==(char*)mbox+0x800) {
  assert(value==GFX_NATIVE_POWERGATE_REQUEST&&requests==0);requests++;return;
 }
 assert(address==(char*)mbox+0x808&&value==0);
}
static void writel(u32 value,void *address)
{
 assert(address==(char*)asc+0x44&&gfx_native_powergate_ack_observed);
 assert(gfx_native_powergate_rx_empty_after_ack&&gfx_native_powergate_rx_empty_before_cpu);
 assert(gfx_native_powergate_idle_observed&&graph_io_lock==1&&held);
 assert(!(value&START));cpuwrites++;
 if(cpuwrites==1&&drop_clear10)return;
 if(cpuwrites==2&&drop_clear20)return;
 control44=value;
}
static int gfx_poweroff_attempt(void)
{
 assert(gfx_native_powergate_ack_observed&&gfx_native_powergate_cpu_stopped);
 assert(gfx_native_powergate_clear10_attempted&&gfx_native_powergate_clear20_attempted);
 assert(!(control44&0x30)&&gfx_reset_scope_host_stopped&&held);
 assert(!gfx_poweroff_gate_consumed&&cpuwrites==2);offcalls++;
 gfx_poweroff_gate_consumed=true;
 if(delegated_consumes_pm){held=false;pmputs++;}
 operations++;return delegated_result;
}
static void reset(void)
{
 held=backing=recovery_session_failed=receive_enabled=idle_work=true;
 started=root_sent=device_context_retained=true;pins=0;
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++)owned[i]=&owned[i];
 recovery_work_submitted=receive_crashed=gfx_poweroff_gate_consumed=false;
 gfx_reset_scope_host_stopped=gfx_poweroff_start_clear_attempted=gfx_reset_scope_sealed=false;
 recovery_completed_total=0;receive_journal.status=0;receive_journal.used=10;
 graph_io_lock=1;jiffies=0;requests=qwrites=cpuwrites=pmputs=offcalls=cancels=operations=0;
 diagnostic_calls=0;
 control_reads_after10=rx_reads_after_ack=status_reads_after_ack=0;
 control44=0x130;status48=0x4e;phase=2;request_state=0;request_flag=host_stop=1;
 controls[0]=controls[1]=controls[2]=32;counter=1;
 memset(rx_messages,0,sizeof(rx_messages));memset(rx_metadata,0,sizeof(rx_metadata));
 rx_count=1;rx_pos=0;rx_messages[0]=0x0070000000000002ULL;
 rx_admission_bad=rx_after_ack_bad=rx_before_cpu_pending=tx_full=false;
 rx_admission_pending=post_stop_nonidle=false;
 late_ack=no_ack=drop_clear10=drop_clear20=mutate_second=reassert_second=false;
 invalid_second=invalid_idle=false;idle_delay=0;
 delegated_result=0;delegated_consumes_pm=true;logs[0]=0;log_used=0;
 consumer_storage.dev.power.usage_count=1;consumer_storage.dev.power.runtime_error=0;
 gfx_native_powergate_intent=gfx_native_powergate_request_attempted=false;
 gfx_native_powergate_ack_observed=gfx_native_powergate_idle_observed=false;
 gfx_native_powergate_clear10_attempted=gfx_native_powergate_clear20_attempted=false;
 gfx_native_powergate_cpu_stopped=gfx_native_powergate_off_delegated=false;
 gfx_native_powergate_initial_recovery_failed=false;
 gfx_native_powergate_startup_unknown=false;
 gfx_native_powergate_rx_empty_after_ack=gfx_native_powergate_rx_empty_before_cpu=false;
 gfx_native_powergate_ack_message=gfx_native_powergate_ack_metadata=0;
 gfx_native_powergate_control_before=gfx_native_powergate_control_after10=0;
 gfx_native_powergate_control_after20=gfx_native_powergate_idle_status=0;
 gfx_native_powergate_ack_polls=gfx_native_powergate_rx_messages=0;
 gfx_native_powergate_idle_polls=0;
}
static unsigned int cases;
static void check(bool condition,const char *name)
{if(!condition){fprintf(stderr,"FAILED: %s\n%s",name,logs);abort();}cases++;puts(name);}
static void refused(int expected,const char *name,bool sent)
{
 int ret=gfx_native_powergate_command("gfx-powergate");
 check(ret==expected&&gfx_native_powergate_intent&&gfx_reset_scope_sealed&&
       recovery_session_failed&&held&&!cpuwrites&&!offcalls&&!pmputs&&
       requests==(sent?1U:0U)&&qwrites==(sent?2U:0U)&&operations==1,name);
 unsigned int saved_requests=requests,saved_writes=cpuwrites,saved_off=offcalls;
 assert(gfx_native_powergate_command("gfx-powergate")==-EALREADY);
 assert(requests==saved_requests&&cpuwrites==saved_writes&&offcalls==saved_off);
 assert(gfx_native_powergate_command("stop")==-EPERM);
 assert(gfx_native_powergate_command("gfx-poweroff")==-EPERM);
 assert(gfx_native_powergate_command("sample")==0);
 assert(gfx_native_powergate_command("gfx-snapshot")==0);
}
static void consumed_retry(void)
{
 unsigned int saved_requests=requests,saved_cpuwrites=cpuwrites,saved_pmputs=pmputs;
 assert(gfx_native_powergate_command("gfx-powergate")==-EALREADY);
 assert(gfx_native_powergate_command("stop")==-EPERM);
 assert(gfx_native_powergate_command("gfx-poweroff")==-EPERM);
 assert(requests==saved_requests&&cpuwrites==saved_cpuwrites&&pmputs==saved_pmputs);
}
int main(void)
{
 reset();assert(gfx_native_powergate_command("sample")==0);
 assert(gfx_native_powergate_command("gfx-snapshot")==0);
 check(diagnostic_calls==2&&!gfx_native_powergate_intent&&!requests&&!cpuwrites&&!offcalls,
       "admitted initial diagnostics never consume powergate intent");
 reset();assert(gfx_native_powergate_command("gfx-powergate")==0);
 check(requests==1&&qwrites==2&&cpuwrites==2&&offcalls==1&&pmputs==1&&!held&&
       control44==0x100&&gfx_native_powergate_cpu_stopped&&operations==1,"diagnostic success");
 assert(gfx_native_powergate_command("gfx-powergate")==-EALREADY&&offcalls==1&&pmputs==1);
 reset();recovery_session_failed=false;recovery_completed_total=2;phase=0;counter=2;
 request_flag=0;controls[0]=controls[1]=controls[2]=34;
 check(gfx_native_powergate_command("gfx-powergate")==0&&offcalls==1&&!held&&
       !gfx_native_powergate_initial_recovery_failed,"healthy initial2 success");
 reset();recovery_completed_total=1;counter=2;controls[0]=controls[1]=controls[2]=33;
 check(gfx_native_powergate_command("gfx-powergate")==0&&offcalls==1,"partial initial1 diagnostic success");
 const char *forbidden[]={"submit","recover","control","trace-off","stop","gfx-poweroff","gfx-reset","native-powergate"};
 for(unsigned int i=0;i<sizeof(forbidden)/sizeof(*forbidden);i++) {
  reset();assert(gfx_native_powergate_command(forbidden[i])==-EPERM);
  check(!gfx_native_powergate_intent&&!requests&&!cpuwrites&&!offcalls,"forbidden typed command");
 }
 reset();held=false;check(gfx_native_powergate_command("gfx-powergate")==-EBUSY&&
  !requests&&!cpuwrites&&!offcalls,"no held reference refusal");
 reset();consumer_storage.dev.power.usage_count=2;refused(-EBUSY,"shared usage refusal",false);
 reset();recovery_work_submitted=true;refused(-EBUSY,"work publication refusal",false);
 reset();receive_journal.used=RECEIVE_CAPACITY;refused(-EBUSY,"full journal refusal",false);
 reset();receive_journal.status=1;refused(-EBUSY,"sealed journal refusal",false);
 reset();phase=1;refused(-EBUSY,"unknown application phase refusal",false);
 reset();controls[0]=31;refused(-EBUSY,"unconsumed control refusal",false);
 reset();request_flag=0;refused(-EBUSY,"diagnostic flag mismatch refusal",false);
 reset();rx_admission_bad=true;refused(-EBUSY,"invalid RX admission refusal",false);
 reset();rx_admission_pending=true;refused(-EBUSY,"stale RX before request refused",false);
 reset();tx_full=true;refused(-EBUSY,"full TX admission refusal",false);
 reset();rx_messages[0]=0x0070000000000201ULL;
 check(gfx_native_powergate_command("gfx-powergate")==0&&requests==1&&offcalls==1&&
       (gfx_native_powergate_ack_message&0xff)==1,"native low8=1 ACK after sole202 accepted");
 assert(has_log("message=0x70000000000201"));
 reset();rx_messages[0]=0x0070000000000001ULL;
 check(gfx_native_powergate_command("gfx-powergate")==0&&requests==1&&offcalls==1&&
       gfx_native_powergate_ack_message==0x0070000000000001ULL,
       "native low16=1 ACK after sole202 accepted");
 reset();rx_messages[0]=0x0070000000000000ULL;refused(-EPROTO,"OFF ACK refused",true);
 reset();rx_messages[0]=0x0070000000000020ULL;refused(-EPROTO,"ON ACK refused",true);
 reset();rx_messages[0]=0x0080000000000002ULL;refused(-EPROTO,"wrong management type refused",true);
 reset();rx_metadata[0]=1;refused(-EIO,"crash endpoint refused",true);assert(receive_crashed);
 reset();rx_messages[0]=~0ULL;refused(-EIO,"invalid message refused",true);
 reset();rx_metadata[0]=~0ULL;refused(-EIO,"invalid metadata refused",true);
 reset();no_ack=true;refused(-ETIMEDOUT,"absent ACK deadline",true);
 assert(gfx_native_powergate_ack_polls==2000&&jiffies==2000);
 reset();late_ack=true;refused(-ETIMEDOUT,"ACK at deadline refused",true);
 assert(!gfx_native_powergate_ack_observed);
 reset();rx_count=2;rx_messages[1]=0x0042000000000000ULL;rx_metadata[1]=32;
 refused(-EBUSY,"ACK trailing frame refusal",true);assert(rx_pos==1);
 reset();rx_after_ack_bad=true;refused(-EIO,"invalid RX after ACK refused",true);
 reset();rx_before_cpu_pending=true;refused(-EBUSY,"late pending RX before CPU refused",true);
 reset();rx_count=2;rx_messages[0]=0x0042000000000000ULL;rx_metadata[0]=32;
 rx_messages[1]=0x0070000000000202ULL;
 check(gfx_native_powergate_command("gfx-powergate")==0&&receive_journal.used==11&&
       gfx_native_powergate_rx_messages==2&&pmputs==1,"qualified trace then low8 ACK accepted");
 reset();rx_count=65;
 for(unsigned int i=0;i<65;i++){rx_messages[i]=0x0042000000000000ULL;rx_metadata[i]=32;}
 refused(-EOVERFLOW,"bounded RX frame overflow",true);assert(rx_pos==64);
 reset();rx_count=2;receive_journal.used=RECEIVE_CAPACITY-1;
 rx_messages[0]=rx_messages[1]=0x0042000000000000ULL;rx_metadata[0]=rx_metadata[1]=32;
 refused(-EIO,"journal overflow during ACK wait",true);
 reset();status48=0x6c;refused(-ETIMEDOUT,"nonidle before CPU writes",true);
 assert(gfx_native_powergate_idle_polls==11);
 reset();idle_delay=10;
 check(gfx_native_powergate_command("gfx-powergate")==0&&gfx_native_powergate_idle_polls==11,
       "native tenth idle retry accepted");
 reset();invalid_idle=true;refused(-EIO,"invalid idle status refused",true);
 reset();drop_clear10=true;assert(gfx_native_powergate_command("gfx-powergate")==-EIO);
 check(cpuwrites==1&&!gfx_native_powergate_clear20_attempted&&!offcalls&&held,"clear10 readback failure retains PM");consumed_retry();
 reset();drop_clear20=true;assert(gfx_native_powergate_command("gfx-powergate")==-EIO);
 check(cpuwrites==2&&!offcalls&&held,"clear20 readback failure retains PM");consumed_retry();
 reset();post_stop_nonidle=true;assert(gfx_native_powergate_command("gfx-powergate")==-EIO);
 check(cpuwrites==2&&!offcalls&&held&&!gfx_native_powergate_cpu_stopped,
       "idle loss after clear20 retains PM");consumed_retry();
 reset();reassert_second=true;assert(gfx_native_powergate_command("gfx-powergate")==-EIO);
 check(cpuwrites==1&&!gfx_native_powergate_clear20_attempted&&!offcalls&&held,
       "START reassertion prevents second write");
 reset();invalid_second=true;assert(gfx_native_powergate_command("gfx-powergate")==-EIO);
 check(cpuwrites==1&&!offcalls&&held,"invalid freshsecond read retains PM");
 reset();mutate_second=true;assert(gfx_native_powergate_command("gfx-powergate")==0);
 check(control44==0x500&&cpuwrites==2&&pmputs==1,"freshsecond RMW preserves hardware changes");
 reset();delegated_result=-EAGAIN;delegated_consumes_pm=false;
 check(gfx_native_powergate_command("gfx-powergate")==-EAGAIN&&offcalls==1&&!pmputs&&held,
       "paired coordinator refusal retains PM");
 consumed_retry();
 reset();delegated_result=-EIO;
 check(gfx_native_powergate_command("gfx-powergate")==-EIO&&offcalls==1&&pmputs==1&&!held,
       "negative PMput is consumed once");
 consumed_retry();
 reset();delegated_result=-ETIMEDOUT;
 check(gfx_native_powergate_command("gfx-powergate")==-ETIMEDOUT&&offcalls==1&&pmputs==1&&!held,
       "physical OFF BUSY failure is consumed once");
 consumed_retry();
 reset();graph_io_lock=0;owned[173]=NULL;
 check(gfx_native_powergate_startup_retained("post-start-protocol-incomplete",-EIO)==0&&
       pins==1&&gfx_native_powergate_startup_unknown&&gfx_reset_scope_sealed&&held&&
       !requests&&!cpuwrites&&!offcalls&&!pmputs&&graph_io_lock==0&&
       has_log("pages_present=173")&&has_log("commands_allowed=0"),
       "unknown post-start startup retains exact resources");
 graph_io_lock=1;
 assert(gfx_native_powergate_command("gfx-powergate")==-EPERM);
 assert(gfx_native_powergate_command("sample")==-EPERM);
 assert(gfx_native_powergate_command("gfx-snapshot")==-EPERM);
 check(!gfx_native_powergate_intent&&!requests&&!cpuwrites&&!offcalls&&!diagnostic_calls,
       "unknown startup explicitly bars every command and callback");
 reset();graph_io_lock=0;
 check(startup_fallback_replay(false)==0&&pins==1&&held&&
       gfx_native_powergate_startup_unknown&&!requests&&!cpuwrites&&!offcalls&&!pmputs,
       "actual retire_firmware label retains without shutdown packets");
 reset();graph_io_lock=0;
 check(startup_fallback_replay(true)==0&&pins==1&&held&&
       gfx_native_powergate_startup_unknown&&!requests&&!cpuwrites&&!offcalls&&!pmputs,
       "actual stop_firmware label retains without CPU write");
 printf("CASES=%u\n",cases);return 0;
}
'''

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--prepared',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();prepared=a.prepared.resolve();header=HERE/'gfx-native-powergate.h'
 receipt=json.loads((prepared/'powergate-owner-source-receipt.json').read_text())
 for row in receipt['output_source_pins']:
  if sha(prepared/row['name'])!=row['sha256']:raise ValueError('Prepared source changed: '+row['name'])
 if (prepared/header.name).read_bytes()!=header.read_bytes():raise ValueError('Actual prepared header differs')
 frozen=Path(receipt['source']);old=json.loads((frozen/'native-status-owner-source-receipt.json').read_text())
 for row in old['output_source_pins']:
  if sha(frozen/row['name'])!=row['sha256']:raise ValueError('Frozen source changed')
 native=ROOT/'out/gfx-native-powergate/native-ranges.json'
 before={str(q):sha(q) for q in [header,HERE/'prepare-powergate-owner.py',Path(__file__),native,
                                prepared/'powergate-owner-source-receipt.json']}
 dispatcher=(prepared/'recovery-cycle.h').read_text()
 typed=dispatcher[dispatcher.index('static ssize_t recovery_command_store('):]
 if 'gfx_native_powergate_command(buf)' not in typed or any(s in typed for s in
       ['recovery_send(', 'recovery_write32(', 'gfx_reset_scope_stop(', 'gfx_poweroff_attempt(']):
  raise ValueError('Typed dispatcher is not the exclusive three-command profile')
 make=(prepared/'Makefile').read_text()
 if 'GFX_COORDINATED_EXECUTION_TRIAL' in make or 'GFX_NATIVE_POWERGATE_TRIAL' not in make:
  raise ValueError('Execution compile profile remains active')
 with tempfile.TemporaryDirectory(prefix='gfx-powergate-') as tmp:
  tmp=Path(tmp);source=tmp/'actual-header.c';binary=tmp/'actual-header'
  owner_source=(prepared/'asc-graph-init.c').read_text()
  fallback=owner_source[owner_source.index('retire_firmware:\n'):owner_source.index('fail:\n',owner_source.index('retire_firmware:\n'))]
  if any(s in fallback for s in ['power_ack(', 'writel(', 'root_release(', 'root_detach_after_shutdown(', 'cleanup(']):
   raise ValueError('Post-START startup fallback still controls hardware or releases backing')
  replay='static int startup_fallback_replay(bool direct_stop) {\n'
  replay+='if(direct_stop)goto stop_firmware;\nif(true){goto retire_firmware;\n'+fallback+'}\n'
  source.write_text(PREAMBLE+'\n#include "'+str(header)+'"\n'+replay+BODY)
  cc=os.environ.get('CC','cc')
  cmd=[cc,'-std=gnu11','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined',
       '-fno-omit-frame-pointer',str(source),'-o',str(binary)]
  build=subprocess.run(cmd,check=True,capture_output=True,text=True)
  run=subprocess.run([str(binary)],capture_output=True,text=True,
       env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1',
            'UBSAN_OPTIONS':'halt_on_error=1'})
  if run.returncode:raise AssertionError(run.stderr+run.stdout)
 cases=[s for s in run.stdout.splitlines() if not s.startswith('CASES=')]
 count=int(run.stdout.splitlines()[-1].split('=')[1]);assert count==len(cases)
 if before!={str(q):sha(q) for q in map(Path,before)}:raise ValueError('Qualification input changed')
 result={'schema':'m4rch.gfx-native-powergate-actual-c-qualification.v1',
  'actual_header':{'path':str(header),'sha256':sha(header)},'prepared_owner':str(prepared),
  'input_pins':[{'path':k,'sha256':v} for k,v in before.items()],
  'inputs':[{'path':k,'sha256':v} for k,v in before.items()],
  'passed':True,'hardware_access':False,'ASan_UBSan':True,'case_count':count,
  'compiler':cc,'sanitizers':['address','undefined'],'actual_c_cases':count,'cases':cases,
  'leak_sanitizer_enabled':False,'leak_sanitizer_reason':'Host ptrace restriction; harness allocates no heap backing.',
  'prepared_source_binding':True,'exclusive_typed_dispatcher_verified':True,
  'compiled_execution_profile_removed':True,'hardware_actions':[],
  'actual_post_start_fallback_replay_verified':True,
  'limitations':'New actual C header replay with mocked existing provider/receive helpers. Frozen core/adapter/OFF qualifications remain separate. No live native ACK, cessation, power collapse, recovery, rendering, restart or backing retirement is established.'}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'actual_c_cases':count,
                   'sanitizers':result['sanitizers'],'hardware_actions':[]}))
if __name__=='__main__':main()
