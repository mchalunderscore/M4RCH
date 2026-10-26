#!/usr/bin/env python3
"""RAM-only replay of the actual recovery helper, cycle counter and typed handler.

No module, sysfs, MMIO, mailbox or GPU actions. Kernel transport functions are
stubs; the actual C operation logic is extracted and compiled. This checks host
guards and lifetime, not firmware scheduling or private-cache coherence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

PREAMBLE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
#define pr_info(...) ((void)0)
#define GENMASK_ULL(h,l) ((~0ULL >> (63-(h))) & (~0ULL << (l)))
#define START 1U
struct kobject { int unused; };
struct kobj_attribute { int unused; };
static bool resident_session,recovery_resident,recovery_work_submitted;
static bool recovery_trace_disabled,recovery_session_failed;
static unsigned int recovery_completed_total,recovery_operation;
static unsigned int graph_io_lock,recovery_receive_work;
static struct { unsigned int used,status,doorbells; } receive_journal;
static bool receive_crashed;
static u8 ram[2*1024*1024],asc[256];
static bool idle_ok,control_ok,messages_ok,send_ok;
static unsigned int writes,mask_writes,job_writes,control_calls,publish_calls;
static unsigned int control_after_phase,control_after_request,control_after_flag;
static bool control_after_busy,control_after_mask;
static unsigned int wait_fail_at,wait_calls,send_calls,stops;
static u64 pending_token;
static void mutex_lock(void *p) {(void)p;}
static void mutex_unlock(void *p) {(void)p;}
static bool sysfs_streq(const char *a,const char *b) {return !strcmp(a,b);}
static bool power_ack(unsigned int a,unsigned int b,unsigned int c) {(void)a;(void)b;(void)c;return true;}
static void cancel_delayed_work(void *p) {(void)p;stops++;}
static u32 readl(void *p) {u32 value;memcpy(&value,p,4);return value;}
static void writel(u32 value,void *p) {memcpy(p,&value,4);}
static void ksm_status_sample(const char *p) {(void)p;}
static void joined_output_sample(const char *p) {(void)p;}
static void recovery_sample(unsigned int c,const char *p) {(void)c;(void)p;}
static void recovery_power_sample(const char *p) {(void)p;}
static void *recovery_ptr(unsigned int offset) {assert(offset<sizeof(ram));return ram+offset;}
static void recovery_invalidate(void *p,size_t n) {(void)p;(void)n;}
static u32 recovery_read32(unsigned int offset) {assert(offset+4<=sizeof(ram));return readl(ram+offset);}
static u64 recovery_read64(unsigned int offset) {u64 value;assert(offset+8<=sizeof(ram));memcpy(&value,ram+offset,8);return value;}
static void put32(unsigned int offset,u32 value) {assert(offset+4<=sizeof(ram));memcpy(ram+offset,&value,4);}
static void put64(unsigned int offset,u64 value) {assert(offset+8<=sizeof(ram));memcpy(ram+offset,&value,8);}
static void recovery_write32(unsigned int offset,u32 value) {
 writes++;
 if(offset==RECOVERY_TRACE_MASK) {assert(value==0);mask_writes++;}
 else if(offset==recovery_work_cursors[0]+16 || offset==recovery_work_cursors[1]+16) {
  assert(value==1);job_writes++;
 } else {assert(offset==RECOVERY_STATUS+0x4900 && (value==0 || value==2));}
 put32(offset,value);
}
static bool recovery_idle(void) {return idle_ok;}
static bool recovery_messages(void) {return messages_ok && !receive_journal.status && !receive_crashed;}
static bool recovery_send(u64 packet) {
 send_calls++;
 if((packet>>48)==0x86) pending_token=packet&GENMASK_ULL(43,0);
 return send_ok;
}
static bool recovery_wait(unsigned int phase,u64 counter) {
 wait_calls++;
 if(wait_calls==wait_fail_at) return false;
 assert(counter==pending_token+1);
 put32(RECOVERY_STATUS+0x4900,phase);put64(RECOVERY_STATUS+0x48f0,counter);
 return true;
}
static bool recovery_control(unsigned int count,bool publish) {
 control_calls++;
 if(publish) {
  publish_calls++;
  assert(count && count<=RECOVERY_CONTROL_LAST);
  assert(recovery_read32(RECOVERY_CONTROL)==count-1);
  assert(recovery_read32(RECOVERY_CONTROL+8)==count-1);
  assert(recovery_read32(RECOVERY_CONTROL+16)==count-1);
 }
 if(!control_ok || !recovery_messages()) return false;
 if(publish) {
  put32(RECOVERY_CONTROL,count);put32(RECOVERY_CONTROL+8,count);put32(RECOVERY_CONTROL+16,count);
  put32(RECOVERY_STATUS+0x4900,control_after_phase);
  put32(RECOVERY_REQUEST,control_after_request);put32(RECOVERY_REQUEST+4,control_after_flag);
  if(control_after_busy) idle_ok=false;
  if(control_after_mask) put32(RECOVERY_TRACE_MASK,3);
 }
 return true;
}
static void replay_cache_clean(void *a,void *b) {(void)a;(void)b;}
'''

REPLAY = r'''
static unsigned int cases;
static void cursors(unsigned int n) {
 put32(RECOVERY_CONTROL,n);put32(RECOVERY_CONTROL+8,n);put32(RECOVERY_CONTROL+16,n);
}
static void reset(void) {
 memset(ram,0,sizeof(ram));memset(asc,0,sizeof(asc));
 resident_session=recovery_resident=true;recovery_work_submitted=false;
 recovery_trace_disabled=recovery_session_failed=false;recovery_operation=0;
 recovery_completed_total=4;idle_ok=control_ok=messages_ok=send_ok=true;
 writes=mask_writes=job_writes=control_calls=publish_calls=wait_calls=send_calls=stops=0;
 control_after_phase=control_after_request=control_after_flag=wait_fail_at=0;
 control_after_busy=control_after_mask=receive_crashed=false;
 receive_journal.used=receive_journal.status=receive_journal.doorbells=0;
 cursors(RECOVERY_CONTROL_INITIAL+4);put32(RECOVERY_TRACE_MASK,3);
}
static ssize_t command(const char *text) {return recovery_command_store(NULL,NULL,text,strlen(text));}
static void untouched(void) {assert(!writes && !publish_calls && !recovery_trace_disabled && !job_writes);cases++;}
int main(void) {
 for(unsigned int n=0;n<4;n++) {reset();recovery_completed_total=n;assert(!recovery_trace_off());untouched();}
 reset();recovery_work_submitted=true;assert(!recovery_trace_off());untouched();
 reset();recovery_trace_disabled=true;assert(!recovery_trace_off());assert(!writes && !publish_calls);cases++;
 reset();idle_ok=false;assert(!recovery_trace_off());untouched();
 for(unsigned int n=0;n<3;n++) {reset();put32(n==0?RECOVERY_STATUS+0x4900:n==1?RECOVERY_REQUEST:RECOVERY_REQUEST+4,1);assert(!recovery_trace_off());untouched();}
 for(unsigned int n=0;n<3;n++) {reset();put32(RECOVERY_CONTROL+n*8,35);assert(!recovery_trace_off());untouched();}
 for(unsigned int n=0;n<RECOVERY_CONTROL_INITIAL+4;n++) {reset();cursors(n);assert(!recovery_trace_off());untouched();}
 for(unsigned int n=0;n<3;n++) {reset();put32(RECOVERY_TRACE_MASK,n==0?0:n==1?1:0xffffffffU);assert(!recovery_trace_off());untouched();}
 for(unsigned int n=0;n<3;n++) {reset();if(n==0) receive_journal.status=9;else if(n==1) receive_crashed=true;else messages_ok=false;assert(!recovery_trace_off());untouched();}
 for(unsigned int n=RECOVERY_CONTROL_LAST;n<RECOVERY_CONTROL_LAST+2;n++) {reset();cursors(n);assert(!recovery_trace_off());untouched();}
 reset();cursors(RECOVERY_CONTROL_LAST-1);assert(recovery_trace_off());
 assert(writes==1 && mask_writes==1 && !job_writes && publish_calls==1 && recovery_trace_disabled);
 assert(recovery_read32(RECOVERY_CONTROL)==RECOVERY_CONTROL_LAST && recovery_read32(RECOVERY_TRACE_MASK)==0);cases++;
 puts("PASS trace-off preconditions, fresh lower/upper cursor bounds, last staged control128 and exact mask0/one-control mutation");

 reset();assert(recovery_trace_off());assert(writes==1 && mask_writes==1 && publish_calls==1);
 assert(recovery_read32(RECOVERY_CONTROL)==37 && recovery_trace_disabled);cases++;
 reset();control_ok=false;assert(!recovery_trace_off());assert(writes==1 && publish_calls==1 && !recovery_trace_disabled);cases++;
 for(unsigned int n=0;n<5;n++) {reset();if(n==0)control_after_phase=1;else if(n==1)control_after_request=1;else if(n==2)control_after_flag=1;else if(n==3)control_after_busy=true;else control_after_mask=true;assert(!recovery_trace_off());assert(writes==1 && publish_calls==1 && !recovery_trace_disabled);cases++;}
 puts("PASS forced-copy failure and changed phase/request/idle/mask do not report trace disabled");

 reset();assert(command("submit")==-EBUSY);untouched();assert(!recovery_work_submitted && !recovery_session_failed);
 reset();recovery_session_failed=true;assert(command("trace-off")==-EIO);untouched();
 reset();recovery_resident=false;assert(command("trace-off")==-ENODEV);untouched();
 reset();recovery_completed_total=3;assert(command("trace-off")==-EIO);untouched();assert(recovery_session_failed);
 reset();control_ok=false;assert(command("trace-off")==-EIO);assert(recovery_session_failed && !recovery_trace_disabled && !recovery_work_submitted);cases++;
 unsigned int saved_writes=writes,saved_pubs=publish_calls;
 assert(command("submit")==-EIO && command("control")==-EIO && command("recover")==-EIO && command("trace-off")==-EIO);
 assert(writes==saved_writes && publish_calls==saved_pubs && !recovery_work_submitted);cases++;
 assert(command("sample")==6);assert(writes==saved_writes);assert(command("stop")==4 && !recovery_resident && stops==1);cases++;
 reset();assert(command("trace-off")==9 && recovery_trace_disabled);assert(command("submit")==6 && recovery_work_submitted);
 assert(job_writes==2 && writes==3 && publish_calls==1 && send_calls==1 && !recovery_session_failed);cases++;
 assert(!memcmp(ram+recovery_work_rings[0],recovery_work_records[0],24));
 assert(!memcmp(ram+recovery_work_rings[1],recovery_work_records[1],24));
 saved_writes=writes;saved_pubs=publish_calls;
 assert(command("submit")==-EALREADY && command("recover")==-EBUSY && command("control")==-EBUSY);
 assert(writes==saved_writes && publish_calls==saved_pubs);cases++;
 reset();assert(command("trace-off")==9);send_ok=false;assert(command("submit")==-EIO);
 assert(recovery_work_submitted && recovery_session_failed && job_writes==2);cases++;
 assert(command("submit")==-EIO && job_writes==2);cases++;
 puts("PASS typed trace-off sealing, submit gate, sample/stop after failure, immutable draw publication and failure quarantine");

 reset();recovery_completed_total=0;cursors(RECOVERY_CONTROL_INITIAL);
 assert(recovery_cycles() && recovery_completed_total==2 && recovery_read32(RECOVERY_CONTROL)==34);cases++;
 assert(recovery_cycles() && recovery_completed_total==4 && recovery_read32(RECOVERY_CONTROL)==36);cases++;
 for(unsigned int n=1;n<=4;n++) {reset();recovery_completed_total=0;cursors(32);wait_fail_at=n;assert(!recovery_cycles());assert(recovery_completed_total==(n<=2?0:1));cases++;}
 reset();recovery_completed_total=0;cursors(32);control_ok=false;assert(!recovery_cycles() && recovery_completed_total==0);cases++;
 for(unsigned int n=0;n<4;n++) {reset();recovery_completed_total=0;cursors(32);if(n==0)control_after_phase=1;else if(n==1)control_after_request=1;else if(n==2)control_after_flag=1;else control_after_busy=true;assert(!recovery_cycles() && recovery_completed_total==0);cases++;}
 reset();recovery_completed_total=0;cursors(32);recovery_work_submitted=true;assert(!recovery_cycles() && recovery_completed_total==0 && !writes && !send_calls);cases++;
 puts("PASS actual cycle-counter placement: accepted post-state plus fresh control consumption only");
 printf("RAM C replay cases: %u\n",cases);return 0;
}
'''


def extract(source, name):
    marker = ('static ssize_t ' if name == 'recovery_command_store' else 'static bool ') + name + '('
    start = source.index(marker)
    end = source.index('\n}\n', start) + 3
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'experiments/t6040-gpu/asc-graph-init/recovery-cycle.h')
    parser.add_argument('--contract', type=Path, default=ROOT / 'out/recovery-dispatch/prepared/recovery-contract.h')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    source = args.source.read_text()
    contract = args.contract.read_text()
    assert '#define RECOVERY_TRACE_INITIAL_MASK 3U' in contract
    functions = {name: extract(source, name) for name in ('recovery_cycles', 'recovery_trace_off', 'recovery_command_store')}
    clean = 'asm volatile("dc cvac, %0\\n\\tdc cvac, %1\\n\\tdsb sy" :: "r"(p),"r"(p+16) : "memory");'
    assert functions['recovery_command_store'].count(clean) == 1
    functions['recovery_command_store'] = functions['recovery_command_store'].replace(clean, 'replay_cache_clean(p,p+16);')
    # Generated structs need u8; transport stubs need the generated offsets.
    cut = PREAMBLE.index('static bool resident_session')
    program = PREAMBLE[:cut] + contract + PREAMBLE[cut:] + '\n'.join(functions.values()) + REPLAY
    with tempfile.TemporaryDirectory(prefix='m4rch-trace-off-replay-') as tmp:
        c = Path(tmp) / 'replay.c'
        executable = Path(tmp) / 'replay'
        c.write_text(program)
        subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Wno-unused-variable', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(c), '-o', str(executable)], check=True, capture_output=True, text=True)
        replay_env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
        result = subprocess.run([str(executable)], capture_output=True, text=True, env=replay_env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout, end='')
    if args.output:
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        report = dict(schema='m4rch-recovery-trace-off-c-replay-v1', hardware_access=False,
                      source=str(args.source), source_sha256=sha(args.source), contract=str(args.contract),
                      contract_sha256=sha(args.contract), test_sha256=sha(Path(__file__)),
                      functions=list(functions), output=result.stdout.splitlines(),
                      replacement='Only ARM cache-clean inline assembly replaced by no-op recorder; operation C extracted intact.',
                      qualification='Actual host helper/cycle/typed-handler logic with bounded RAM and stubbed transport. No GPU execution, scheduler, cache-coherence, notification-budget or backing-retirement proof.')
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
