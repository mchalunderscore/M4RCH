#!/usr/bin/env python3
"""Prepare v16 from frozen v15; hardware/builds remain root-coordinator work."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_SHA='e8783d245414dfcffffbbb62d17b6cbf93ec91479c901ae78f0ff21d538203e4'
REPEAT_SHA='21f4903013d2db05fd0ab3ad5de8c92a15fdcda4d20c48fd85f6ca847b562b0b'
OLD='GFX_NATIVE_DISPATCH_CONTRACT_TRIAL';NEW='GFX_POSTDRAW_NATIVE_CYCLE_TRIAL'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t,a,b):
 if t.count(a)!=1:raise ValueError('Frozen insertion changed: '+a[:100])
 return t.replace(a,b,1)
def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Distinct absent destination required')
 receipt=source/'native-dispatch-contract-owner-source-receipt.json'
 if sha(receipt)!=BASE_SHA:raise ValueError('Frozen v15 source receipt differs')
 old=json.loads(receipt.read_text());before={p['name']:p['sha256'] for p in old['output_source_pins']}
 for n,h in before.items():
  if sha(source/n)!=h:raise ValueError('Frozen v15 source changed: '+n)
 repeat=ROOT/'out/gfx-native-ap-repeat-cycle/prepared-owner-v1'
 rr=repeat/'native-ap-repeat-cycle-owner-source-receipt.json'
 if sha(rr)!=REPEAT_SHA:raise ValueError('Frozen v12 receipt differs')
 rj=json.loads(rr.read_text())
 for p in rj['output_source_pins']:
  if sha(repeat/p['name'])!=p['sha256']:raise ValueError('Frozen v12 helper differs: '+p['name'])
 outputs={n:(source/n).read_bytes() for n in before if n!='gfx-dispatch-trace.h'}
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 h=outputs['gfx-cold-render.h'].decode()
 a=h.index('static bool gfx_dispatch_trace_intent,');b=h.index('\n\nstatic unsigned int gfx_cold_retained_pages(',a);h=h[:a]+h[b:]
 h=once(h,' gfx_cold_trace_attempted=true;recovery_write32(RECOVERY_TRACE_MASK,0);\n if(recovery_read32(RECOVERY_TRACE_MASK)) return gfx_cold_refuse("trace-mask-readback",-EIO);',' /* Preserve trace3; this existing opcode22 refreshes firmware cached18eecc. */\n if(recovery_read32(RECOVERY_TRACE_MASK)!=3) return gfx_cold_refuse("trace-mask-readback",-EIO);')
 h=once(h,' if(!gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())',' if(!gfx_cold_guard(33,true,3) || !gfx_cold_immutable_backing())')
 h=h.replace(' || !gfx_dispatch_trace_ready','').replace('gfx_dispatch_expected_trace()','3U')
 h=once(h,'#include "gfx-dispatch-trace.h"\n\n','')
 h=once(h,' ret=gfx_dispatch_trace_restore();\n if(ret) {ret=gfx_cold_refuse("dispatch-trace",ret);goto done;}\n','')
 h=once(h,' gfx_dispatch_trace_log("retained-final");\n','')
 h=once(h,' gfx_dispatch_trace_log("diagnostic-cached");\n','')
 h=once(h,'static int gfx_cold_diagnostic(const char *command)\n{','static int gfx_cold_diagnostic(const char *command)\n{\n if(gfx_postdraw_cycle_intent) return gfx_postdraw_diagnostic(command);')
 # The cycle is separate from immutable draw state; its header follows the
 # actual cold functions but precedes the command implementation.
 h=once(h,'static int gfx_cold_diagnostic(const char *command)\n{','#include "gfx-postdraw-native-cycle.h"\n\nstatic int gfx_cold_diagnostic(const char *command)\n{')
 h=h.replace(' * scheduled, no submitted-work OFF/PM put or firmware stop is attempted.',' * scheduled. A separate token-bearing command may perform one experimental\n * retained postdraw native management cycle after the host saves full captures.')
 outputs['gfx-cold-render.h']=h.encode()
 c=outputs['asc-graph-init.c'].decode()
 c=once(c,'static const unsigned int gfx_cold_current_epoch=1;','static unsigned int gfx_cold_current_epoch=1;')
 c=c.replace('Experimental J614s one cold draw with native config getter bindings and retained dispatch trace','Experimental J614s one traced cold draw and one captured retained native management cycle')
 outputs['asc-graph-init.c']=c.encode()
 dispatcher=outputs['recovery-cycle.h'].decode()
 dispatcher=once(dispatcher,'static int gfx_cold_diagnostic(const char *command);','static int gfx_cold_diagnostic(const char *command);\nstatic int gfx_postdraw_command(const char *buf,size_t count);')
 dispatcher=once(dispatcher,' mutex_lock(&graph_io_lock);ret=gfx_cold_diagnostic(buf);mutex_unlock(&graph_io_lock);',' mutex_lock(&graph_io_lock);\n if(count>=21 && !memcmp(buf,"postdraw-native-cycle",21)) ret=gfx_postdraw_command(buf,count);\n else ret=gfx_cold_diagnostic(buf);\n mutex_unlock(&graph_io_lock);')
 outputs['recovery-cycle.h']=dispatcher.encode()
 outputs['gfx-postdraw-native-cycle.h']=(HERE/'gfx-postdraw-native-cycle.h').read_bytes()
 trial=dict(version=16,trace_mask_preserved=3,trace_restore_writes=0,existing_opcode22_refreshes_trace=True,
  postdraw_command='postdraw-native-cycle <64 lowercase hex>',capture_token_host_verified_only=True,
  maximum_native202=1,maximum_pm_puts=1,maximum_retained_pm_gets=1,maximum_retained_starts=1,
  application_replay=False,root_replay=False,work_replay=False,second_B20=False,second_cycle=False,
  experimental_submitted_work_powergate=True,all_pages_maps_context_retained=True)
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);j.pop('native_dispatch_contract_trial',None);j['postdraw_native_cycle_trial']=trial
  j['cold_render_trial'].update(version=16,trace_mask_after=3)
  if n=='preparation.json':j['qualification']='Distinct traced cold draw plus a separate immutable-capture-token experimental submitted-work native management cycle. No retirement, rendering or application restart proved.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 profile=dict(old['profile']);profile.update(family='gfx_postdraw_native_cycle_scope',version=16,compile_macro=NEW,
  typed_commands=['sample','gfx-snapshot','postdraw-native-cycle <capture-token>'],trace_mask_after_control=3,
  maximum_trace_restore_writes=0,trace_restore_after_fresh_control=False,trace_restore_before_draw=False,
  trace_restore_log_prefix=None,trace_mask_preserved_through_control33=True,
  maximum_native202=1,maximum_postdraw_cycle_intents=1,maximum_postdraw_pm_puts=1,
  maximum_retained_pm_gets=1,maximum_retained_starts=1,capture_before_cycle_required_by_host=True,
  capture_token_syntax_checked_by_C=True,capture_token_file_hash_verified_by_C=False,
  experimental_submitted_work_powergate=True,second_B20_requests=0,root_republications=0,
  application_restarts=0,work_replays=0,postdraw_management_rejoin_only=True,
  postdraw_log_prefix='m4rch gfx-postdraw-native-cycle:',postdraw_command='postdraw-native-cycle',
  resources_retained_after_OFF=True,post_OFF_device_reads_require_fresh_qualified_ON=True)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,h0 in before.items():
  if sha(source/n)!=h0:raise ValueError('Frozen v15 input mutated during preparation')
 closure=[dict(path=str(rr),sha256=sha(rr))]+[dict(path=str(repeat/n),sha256=sha(repeat/n)) for n in ['gfx-native-powergate-drain.h','gfx-native-ap-repeat-cycle.h','gfx-reset-scope.h','gfx-ap-repeat-cycle-coordinate.h']]
 report=dict(schema='m4rch.gfx-postdraw-native-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),
  baseline_source_receipt=dict(path=str(receipt),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__))),
  input_source_pins=[dict(name=n,sha256=h0) for n,h0 in before.items()],reused_helper_pins=closure,
  output_source_pins=[dict(name=n,sha256=sha(destination/n)) for n in outputs],
  changed_files=sorted(n for n in outputs if n in before and sha(destination/n)!=before[n]),
  added_files=['gfx-postdraw-native-cycle.h'],removed_files=['gfx-dispatch-trace.h'],profile=profile,
  hardware_actions=[],build_actions=[],qualification='Source only. Firmware/native abort after submitted work is experimental; ACK, CPU idle, paired OFF/PMGR/accounting and management rejoin do not prove rendering, hardware retirement, application rejoin, reusable draw state or safe free.')
 with (destination/'postdraw-native-cycle-owner-source-receipt.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/'postdraw-native-cycle-owner-source-receipt.json'),changed_files=j['changed_files'],added_files=j['added_files'],profile=j['profile'])))
