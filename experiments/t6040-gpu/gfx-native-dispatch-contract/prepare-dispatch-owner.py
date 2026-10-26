#!/usr/bin/env python3
"""Prepare a distinct v15 cold draw with native config and retained trace.

Build, live loading and hardware actions belong to the root coordinator.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE_SHA='2ebd9dbe52a5e0be4de5793d9c3c6ee454ead602569e52ed16e5260e3a4cfec7'
RECIPE_SHA='2f66948af31aa7803f6298a97d8eba4412590b9e72e6876a64c3383886731ee8'
OLD='GFX_COLD_RENDER_TRIAL'
NEW='GFX_NATIVE_DISPATCH_CONTRACT_TRIAL'
ADDED=['gfx-dispatch-trace.h']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text,before,after):
 if text.count(before)!=1:raise ValueError('Frozen insertion changed: '+before[:100])
 return text.replace(before,after,1)


def prepare(source,recipe,destination):
 source,recipe,destination=source.resolve(),recipe.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:
  raise ValueError('New distinct destination required')
 base=source/'cold-render-owner-source-receipt.json'
 if sha(base)!=BASE_SHA:raise ValueError('Selected v13 source receipt changed')
 old=json.loads(base.read_text());pins={p['name']:p['sha256'] for p in old['output_source_pins']}
 for name,h in pins.items():
  if sha(source/name)!=h:raise ValueError('Frozen v13 source differs: '+name)
 recipe_path=recipe/'receipt.json'
 if sha(recipe_path)!=RECIPE_SHA:raise ValueError('Selected four-byte recipe receipt changed')
 rr=json.loads(recipe_path.read_text())
 if not rr['prepared'] or rr['hardware_actions'] or rr['recipe']['changed_byte_count']!=4:
  raise ValueError('Invalid recipe qualification')
 for p in rr['inputs']+rr['outputs']:
  f=Path(p['path'])
  if f.stat().st_size!=p['bytes'] or sha(f)!=p['sha256']:raise ValueError('Recipe closure differs: '+str(f))
 recipe_graph=recipe/'graph';outputs={name:(source/name).read_bytes() for name in pins}
 for p in rr['outputs']:
  name=Path(p['path']).name
  if name not in outputs:raise ValueError('Recipe file absent from selected v13 owner: '+name)
  if name not in ('backing.bin','render-data.h','preparation.json','graph-receipt.json') and sha(source/name)!=p['sha256']:
   raise ValueError('Unrelated graph artifact differs from selected v13: '+name)
  outputs[name]=(recipe_graph/name).read_bytes()
 for name,raw in list(outputs.items()):
  if name.endswith(('.c','.h')) or name=='Makefile':outputs[name]=raw.replace(OLD.encode(),NEW.encode())
 header=outputs['gfx-cold-render.h'].decode()
 header=once(header,'static const char *gfx_cold_refusal="none";',
  'static const char *gfx_cold_refusal="none";\n'
  'static bool gfx_dispatch_trace_intent,gfx_dispatch_trace_write_attempted,gfx_dispatch_trace_ready;\n'
  'static unsigned int gfx_dispatch_trace_before,gfx_dispatch_trace_written,gfx_dispatch_trace_after;\n'
  'static int gfx_dispatch_trace_result;\n'
  'static const char *gfx_dispatch_trace_refusal="none";')
 header=once(header,'static int gfx_cold_sample(', '#include "gfx-dispatch-trace.h"\n\nstatic int gfx_cold_sample(')
 header=once(header,' if(gfx_cold_draw_intent || !gfx_cold_control_ready ||\n    !gfx_cold_guard(33,true,0)',
  ' if(gfx_cold_draw_intent || !gfx_cold_control_ready || !gfx_dispatch_trace_ready ||\n    !gfx_cold_guard(33,true,gfx_dispatch_expected_trace())')
 header=once(header,' if(!gfx_cold_guard(33,true,0) || !gfx_cold_immutable_backing())\n  return gfx_cold_refuse("draw-intent-recheck",-EBUSY);',
  ' if(!gfx_cold_guard(33,true,gfx_dispatch_expected_trace()) || !gfx_cold_immutable_backing())\n  return gfx_cold_refuse("draw-intent-recheck",-EBUSY);')
 header=once(header,' ret=gfx_cold_publish_draw();if(ret)goto done;',
  ' ret=gfx_dispatch_trace_restore();\n if(ret) {ret=gfx_cold_refuse("dispatch-trace",ret);goto done;}\n ret=gfx_cold_publish_draw();if(ret)goto done;')
 header=once(header,' gfx_cold_log("retained-final",result);',
  ' gfx_dispatch_trace_log("retained-final");\n gfx_cold_log("retained-final",result);')
 header=once(header,' gfx_cold_log("diagnostic-cached",gfx_cold_terminal_result);return 0;',
  ' gfx_dispatch_trace_log("diagnostic-cached");\n gfx_cold_log("diagnostic-cached",gfx_cold_terminal_result);return 0;')
 outputs['gfx-cold-render.h']=header.encode()
 c=outputs['asc-graph-init.c'].decode().replace('Experimental J614s automatic cold control and one retained TA/3D draw',
  'Experimental J614s one cold draw with native config getter bindings and retained dispatch trace')
 outputs['asc-graph-init.c']=c.encode()
 trial=dict(version=15,native_config_getters_coherent=True,config_recipe_changed_bytes=4,
  trace_before_control=3,trace_after_control=0,trace_before_draw=3,trace_retained_after_draw=3,
  maximum_trace_restore_writes=1,trace_restore_after_control_cursors=[33,33,33],
  trace_restore_before_first_draw_sample=True,extra_notifications=0,scheduler_request_writes=0,
  retained_pages=174,pm_put_after_draw=False,off_after_draw=False)
 for name in ('graph-receipt.json','preparation.json'):
  d=json.loads(outputs[name]);d.pop('cold_render_pause_release_trial',None)
  d['native_dispatch_contract_trial']=trial
  d['cold_render_trial'].update(version=15,trace_mask_after=3)
  if name=='preparation.json':d['qualification']='Distinct native config getter coherent cold draw with trace restored after fresh control33; all resources retained, no scheduler-request intervention or GPU execution proved.'
  outputs[name]=(json.dumps(d,indent=2)+'\n').encode()
 outputs['gfx-dispatch-trace.h']=(HERE/'gfx-dispatch-trace.h').read_bytes()
 profile=dict(old['profile']);profile.update(family='gfx_native_dispatch_contract_scope',version=15,compile_macro=NEW,
  trace_mask_after=3,trace_mask_after_control=0,trace_mask_before_draw=3,trace_mask_retained_after_draw=3,
  maximum_trace_restore_writes=1,trace_restore_after_fresh_control=True,trace_restore_before_draw=True,
  trace_restore_log_prefix='m4rch gfx-native-dispatch-trace:',maximum_scheduler_request_writes=0,
  native_config_getter_changed_bytes=4,no_extra_notification_for_trace=True,
  native_reason_mutex_owned=False,native_reason_lifecycle_reproduced=False)
 destination.mkdir(parents=True)
 for name,raw in outputs.items():(destination/name).write_bytes(raw)
 for name,h in pins.items():
  if sha(source/name)!=h:raise ValueError('Frozen v13 source mutated during preparation')
 receipt=dict(schema='m4rch.gfx-native-dispatch-contract-owner-source.v1',source=str(source),destination=str(destination),source_path=str(source),
  baseline_source_receipt=dict(path=str(base),sha256=BASE_SHA),
  recipe_receipt=dict(path=str(recipe_path),sha256=RECIPE_SHA),
  source_preparer=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__))),
  input_source_pins=[dict(name=n,sha256=h) for n,h in pins.items()]+[dict(name=base.name,sha256=BASE_SHA)],
  recipe_source_pins=rr['inputs']+rr['outputs'],
  output_source_pins=[dict(name=n,sha256=sha(destination/n)) for n in outputs],
  changed_files=sorted(n for n in pins if sha(destination/n)!=pins[n]),added_files=ADDED,removed_files=[],
  profile=profile,hardware_actions=[],build_actions=[],
  qualification='Source only; distinct cold ON/AP/root/control33/one draw retains allocations and PM. One shared trace-mask restore0→3 after ready33; no MMIO/scheduler-request intervention, OFF, retry, wake or retirement claim.')
 with (destination/'native-dispatch-contract-owner-source-receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 return receipt


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--recipe',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
 r=prepare(a.source,a.recipe,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/'native-dispatch-contract-owner-source-receipt.json'),changed=r['changed_files'],added=ADDED,profile=r['profile'])))
