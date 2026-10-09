#!/usr/bin/env python3
"""Prepare a distinct no-work PWRGATE source owner; never build or load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
EXPECTED={
 'asc-graph-init.c':'5e6156de5894c93b97b7ae43f2e6cf00df698e0e14c3c380e62c4432b049a29b',
 'recovery-cycle.h':'9971b319f7bbcc265ec6a9eca5b2f9bdf00e44a7c19eabce301eb48cc0debe71',
 'gfx-reset-scope.h':'4ad396fa170b694f7b7e00e37d7f88bbcd07b55ba44d767ee825a4cff8de7fff',
 'Makefile':'12508e7b773274cb8474d32fa33be952ef00eea09aa89390ad8061df4fe08d01',
 'gfx-coordinate-core.h':'b7a7376ab2a7e1b054e0338ce37efe035b85acaa6ba5072ed7231b6dcb245a95',
 'gfx-coordinate-owner.h':'9798b26320e2b0f9b270da9b598f21e909cf037e58070154a6818ac6156601b4',
 'native-status-owner-source-receipt.json':'5566c838e18f82335b4c8daded1d7e6a48d3b1729f9d7cc97bb4fb1b762b827b',
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def once(source,old,new):
 if source.count(old)!=1:raise ValueError('Frozen insertion changed: '+repr(old[:100]))
 return source.replace(old,new,1)

def transform_dispatcher(source):
 source=once(source,'static bool recovery_trace_off(void)',
                    'static bool __maybe_unused recovery_trace_off(void)')
 start=source.index('static ssize_t recovery_command_store(')
 end=source.index('static struct kobj_attribute recovery_command=',start)
 return source[:start]+'''#include "gfx-native-powergate.h"
static ssize_t recovery_command_store(struct kobject *kobj,struct kobj_attribute *attr,
 const char *buf,size_t count)
{
 int ret;
 mutex_lock(&graph_io_lock);
 ret=gfx_native_powergate_command(buf);
 mutex_unlock(&graph_io_lock);
 return ret?ret:count;
}
'''+source[end:]

def transform_scope(source):
 source=once(source,'static int gfx_reset_scope_stop(void)',
                    'static int __maybe_unused gfx_reset_scope_stop(void)')
 start=source.index('static int gfx_poweroff_attempt(void)')
 body=source[start:]
 if body.count('gfx_reset_scope_result("gfx-poweroff",ret)')!=3:
  raise ValueError('Frozen OFF result sites changed')
 return source[:start]+body.replace('gfx_reset_scope_result("gfx-poweroff",ret)',
                                  'gfx_reset_scope_result("gfx-powergate",ret)')

def transform_owner(source):
 old='''     if(recovered) pr_info("m4rch recovery-session: resident=1 control_ready=1 work_submitted=0 allocations_retained=1\\n");
     else pr_info("m4rch recovery-session: diagnostic=1 sealed=1 control_ready=0 work_submitted=0 allocations_retained=1; only sample/stop"
#ifdef GFX_RESET_SCOPE_TRIAL
      "/gfx-snapshot and one terminal gfx-poweroff after stop"
#endif
      " allowed\\n");'''
 new='''     if(recovered) pr_info("m4rch recovery-session: resident=1 control_ready=0 work_submitted=0 allocations_retained=1; only sample/gfx-snapshot and one terminal gfx-powergate allowed\\n");
     else pr_info("m4rch recovery-session: diagnostic=1 sealed=1 control_ready=0 work_submitted=0 allocations_retained=1; only sample/gfx-snapshot and one terminal gfx-powergate allowed\\n");
     pr_info("m4rch gfx-native-powergate-session: ready=1 initial_recovery_failed=%u initial_completed_cycles=%u startup_work_submitted=0\\n",!recovered,recovery_completed_total);'''
 source=once(source,old,new)
 source=once(source,' bool got = false, stopped = false, replied = false, epmap = false;\n'
                    ' bool ap_quiesced = false, iop_sleep = false, retired = false;',
                    ' bool got = false, replied = false, epmap = false;')
 source=once(source,'static void joined_output_sample(const char *phase)',
                    'static void __maybe_unused joined_output_sample(const char *phase)')
 source=once(source,'static int __init hello_init(void)\n{',
                    'static int __init hello_init(void)\n{\n'
                    ' /* Preserve the frozen detach helper without admitting or calling it. */\n'
                    ' (void)root_detach_after_shutdown;')
 start=source.index('retire_firmware:\n')
 end=source.index('fail:\n',start)
 source=source[:start]+'''retire_firmware:
 ;
 }
stop_firmware:
 return gfx_native_powergate_startup_retained("post-start-protocol-incomplete",-EIO);
'''+source[end:]
 source=once(source,
  '  gfx_coord_owner_log("later-startup-failure-retained",ret);\n  return 0;',
  '  return gfx_native_powergate_startup_retained("after-on-startup-failure",ret);')
 source=once(source,
  ' if (started) {gfx_coord_owner_pin();pr_err("m4rch ASC crashlog: started-state failure retained; reboot required\\n");return 0;}',
  ' if (started) return gfx_native_powergate_startup_retained("started-state-failure",ret);')
 return once(source,
  'MODULE_DESCRIPTION("Experimental J614s paired PMP/PMC retained no-work coordinator");',
  'MODULE_DESCRIPTION("Experimental J614s native PWRGATE retained no-work coordinator");')

def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:
  raise ValueError('Destination must be new and outside the frozen source')
 for name,pin in EXPECTED.items():
  if sha(source/name)!=pin:raise ValueError('Frozen input changed: '+name)
 old=json.loads((source/'native-status-owner-source-receipt.json').read_text())
 for row in old['output_source_pins']:
  if sha(source/row['name'])!=row['sha256']:raise ValueError('Frozen source pin changed: '+row['name'])
 files=sorted(p for p in source.iterdir() if p.is_file() and
              (p.suffix in ('.c','.h','.bin','.json') or p.name=='Makefile') and
              not p.name.endswith('.mod.c'))
 before={p.name:sha(p) for p in files}
 dispatcher=transform_dispatcher((source/'recovery-cycle.h').read_text())
 scope=transform_scope((source/'gfx-reset-scope.h').read_text())
 owner=transform_owner((source/'asc-graph-init.c').read_text())
 make=once((source/'Makefile').read_text(),
           'ccflags-y += -DGFX_COORDINATED_EXECUTION_TRIAL',
           'ccflags-y += -DGFX_NATIVE_POWERGATE_TRIAL')
 destination.mkdir(parents=True)
 for p in files:(destination/p.name).write_bytes(p.read_bytes())
 for name,data in [('recovery-cycle.h',dispatcher),('gfx-reset-scope.h',scope),
                   ('asc-graph-init.c',owner),('Makefile',make)]:
  (destination/name).write_text(data)
 (destination/'gfx-native-powergate.h').write_bytes((HERE/'gfx-native-powergate.h').read_bytes())
 after={p.name:sha(destination/p.name) for p in files}
 changed=sorted(n for n in before if before[n]!=after[n])
 if changed!=['Makefile','asc-graph-init.c','gfx-reset-scope.h','recovery-cycle.h']:
  raise ValueError('Unexpected source delta')
 after['gfx-native-powergate.h']=sha(destination/'gfx-native-powergate.h')
 if before!={p.name:sha(p) for p in files}:raise ValueError('Frozen input changed during preparation')
 receipt={'schema':'m4rch.gfx-native-powergate-owner-source.v1',
  'source':str(source),'destination':str(destination),
  'source_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
  'input_source_pins':[{'name':n,'sha256':v} for n,v in before.items()],
  'output_source_pins':[{'name':n,'sha256':v} for n,v in after.items()],
  'changed_files':changed,'added_files':['gfx-native-powergate.h'],
  'profile':{'compile_macro':'GFX_NATIVE_POWERGATE_TRIAL','work_publication_admitted':False,
   'typed_commands':['sample','gfx-snapshot','gfx-powergate'],
   'maximum_powergate_intents':1,'maximum_powergate_requests':1,
   'request':'0x0060000000000202','ack':'EP0 type nibble7 and low8=1 or2 after own request',
   'initial_admitted_states':['diagnostic0/1cycle phase2','healthy2cycles phase0'],
   'initial_recovery_cycle_attempt_unchanged':True,
   'maximum_ack_ms':2000,'maximum_ack_polls':2001,'maximum_rx_messages':64,
   'pre_stop_idle_polls':11,'fresh_cpu_stop_rmw_masks':['0x10','0x20'],
   'paired_off_only_after_ack_and_checked_cpu_stop':True,
   'unknown_ack_or_stop_result_keeps_pm_held':True,
   'terminal_intent_seals_all_other_commands':True,
   'post_on_startup_failure_retention_only':True,
   'post_on_startup_unknown_commands_admitted':[],
   'all174_backing_maps_consumer_module_retained':True,
   'restart_allowed':False,'dma_retirement_verified':False},
  'hardware_actions':[],'build_actions':[],
  'qualification':'Source preparation only; no native management ACK, teardown, recovery, render, DMA retirement or restart is established.'}
 with (destination/'powergate-owner-source-receipt.json').open('x') as f:
  json.dump(receipt,f,indent=2);f.write('\n')
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
 a=p.parse_args();r=prepare(a.source,a.destination)
 print(json.dumps({'receipt':str(a.destination/'powergate-owner-source-receipt.json'),
                   'changed_files':r['changed_files'],'added_files':r['added_files'],
                   'hardware_actions':[]}))
if __name__=='__main__':main()
