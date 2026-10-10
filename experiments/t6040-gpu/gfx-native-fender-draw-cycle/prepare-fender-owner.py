#!/usr/bin/env python3
"""Prepare a distinct native Fender enable transfer from the frozen v17 owner."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
BASE_SHA='d1f95e0cc08d13fbc46a457f715ccc0f439afd366da1eb78360716d99543b1a7'
OLD='GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL';NEW='GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL'
RECEIPT='native-fender-draw-cycle-owner-source-receipt.json'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t,a,b):
 if t.count(a)!=1:raise ValueError('Frozen insertion differs: '+a[:100])
 return t.replace(a,b,1)
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Distinct absent destination required')
 receipt=source/'postdraw-native-nmi-cycle-owner-source-receipt.json'
 if h(receipt)!=BASE_SHA:raise ValueError('Frozen v17 receipt differs')
 old=json.loads(receipt.read_text());before={x['name']:x['sha256'] for x in old['output_source_pins']}
 for n,d in before.items():
  if h(source/n)!=d:raise ValueError('Frozen source differs: '+n)
 outputs={n:(source/n).read_bytes() for n in before}
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 c=outputs['asc-graph-init.c'].decode()
 c=once(c,'#include "gfx-gravity-preasc.h"','#include "gfx-gravity-preasc.h"\n#include "gfx-native-fender-enable.h"')
 c=once(c,'Experimental J614s Gravity preASC plus traced draw and native timeout NMI retained cycle','Experimental J614s native Fender enable transfer plus traced draw and native timeout NMI retained cycle')
 outputs['asc-graph-init.c']=c.encode()
 cold=outputs['gfx-cold-render.h'].decode()
 cold=once(cold,'static int gfx_cold_run(void)','static int gfx_native_fender_enable(void);\n\nstatic int gfx_cold_run(void)')
 cold=once(cold,' ret=gfx_cold_fresh_control();if(ret)goto done;\n ret=gfx_cold_publish_draw();if(ret)goto done;',
  ' ret=gfx_cold_fresh_control();if(ret)goto done;\n ret=gfx_native_fender_enable();\n if(ret) {ret=gfx_cold_refuse("native-fender-enable",ret);goto done;}\n ret=gfx_cold_publish_draw();if(ret)goto done;')
 outputs['gfx-cold-render.h']=cold.encode()
 outputs['gfx-native-fender-enable.h']=(HERE/'gfx-native-fender-enable.h').read_bytes()
 selected=dict(version=18,native_Fender_enable_calls=1,native_Fender_enable_offset='0xd06030',
  native_Fender_enable_policy='fresh-old-and-not-six',after_fresh_control33_before_first_draw=True,
  explicit_transfer_hypothesis=True,native_addKicks_replayed=False,direct_SGX_kick_writes=False,
  scheduler_ACK_coverage_writes=False,teardown_register_cleanup=False,management_rejoin_replay=False)
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);previous=j.pop('postdraw_native_nmi_cycle_trial')
  previous.update(selected);j['native_fender_draw_cycle_trial']=previous;j['cold_render_trial']['version']=18
  if n=='preparation.json':j['qualification']='Distinct native Fender enable transfer before one firmware-mediated draw; NMI timeout fallback retained. No normal native kick, execution, physicalOFF or retirement proved.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 profile=dict(old['profile']);profile.update(selected);profile.update(family='gfx_native_fender_draw_cycle_scope',version=18,compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,d in before.items():
  if h(source/n)!=d:raise ValueError('Frozen source mutated: '+n)
 out=dict(schema='m4rch.native-fender-draw-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),
  baseline_source_receipt=dict(path=str(receipt),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=h(Path(__file__))),
  input_source_pins=[dict(name=n,sha256=d) for n,d in before.items()],reused_helper_pins=old['reused_helper_pins'],
  output_source_pins=[dict(name=n,sha256=h(destination/n)) for n in outputs],
  changed_files=sorted(n for n in outputs if n in before and h(destination/n)!=before[n]),added_files=['gfx-native-fender-enable.h'],removed_files=[],profile=profile,
  hardware_actions=[],build_actions=[],qualification='Exact native Fender enable operation is experimentally transferred to the firmware-mediated draw after control33. EP33 is not native addKicks. Native disable/control/count stores are not replayed. Strict physicalOFF/PM accounting still control restart. All174pages retained.')
 with (destination/RECEIPT).open('x') as f:f.write(json.dumps(out,indent=2)+'\n')
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/RECEIPT),sha256=h(a.destination/RECEIPT),changed_files=j['changed_files'],profile=j['profile'])))
