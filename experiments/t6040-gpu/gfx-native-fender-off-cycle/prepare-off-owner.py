#!/usr/bin/env python3
"""Prepare a distinct native Fender disable transfer from frozen v19."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
BASE_SHA='180beeda3cd323f9ae15d03dbec8dfd07daefe72aa2a3a35ceb13861cc2ef289'
HELPER_SHA='5d9d00b6bcb5e3d85a429833befa6a4bfcddaced32a79925e66eae469b962c77'
OLD='GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL';NEW='GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL'
RECEIPT='native-fender-off-cycle-owner-source-receipt.json'
SELECTED=dict(version=20,native_Fender_disable_calls=1,native_Fender_disable_offset='0xd06030',
 native_Fender_disable_policy='fresh-old-or-four',native_Fender_disable_after_CPU_stop_before_OFF=True,
 native_Fender_disable_after_coordinate_alias_before_OFF_seal=True,native_Fender_disable_transfer_hypothesis=True,
 native_Fender_disable_MMIO_writes=1,native_Fender_disable_PMGR_writes=0,native_Fender_disable_ACK_cleanup=False,
 native_Fender_disable_fresh_runtime_snapshot='fender-off-before',strict_physical_OFF_unchanged=True,
 strict_fresh_ON_rejoin_unchanged=True,native_poweroff_reproduced=False)
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t,a,b):
 if t.count(a)!=1:raise ValueError('Frozen insertion differs: '+a[:100])
 return t.replace(a,b,1)
def project_source(outputs):
 """Pure original-frozen-v19 relative-path/bytes projection; no writes."""
 outputs=dict(outputs)
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 c=outputs['asc-graph-init.c'].decode();c=once(c,'#include "gfx-native-runtime-state.h"','#include "gfx-native-runtime-state.h"\n#include "gfx-native-fender-disable.h"')
 c=once(c,'Experimental J614s native Fender runtime admission plus traced draw and native timeout NMI retained cycle','Experimental J614s native Fender disable before OFF plus traced draw and native timeout NMI retained cycle');outputs['asc-graph-init.c']=c.encode()
 post=outputs['gfx-postdraw-native-nmi-cycle.h'].decode();post=once(post,'static int gfx_postdraw_off(void)','static int gfx_native_fender_disable(void);\n\nstatic int gfx_postdraw_off(void)')
 hook=' ret=gfx_coord_owner_alias_check();if(ret) return gfx_postdraw_refuse("off-coordinate-alias",ret);'
 post=once(post,hook,hook+'\n ret=gfx_native_fender_disable();\n if(ret) return gfx_postdraw_refuse("off-native-fender-disable",ret);');outputs['gfx-postdraw-native-nmi-cycle.h']=post.encode()
 helper=HERE/'gfx-native-fender-disable.h'
 if h(helper)!=HELPER_SHA:raise ValueError('Qualified native disable helper differs')
 outputs[helper.name]=helper.read_bytes()
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);previous=j.pop('native_fender_runtime_cycle_trial');previous.update(SELECTED);j['native_fender_off_cycle_trial']=previous;j['cold_render_trial']['version']=20
  if n=='preparation.json':j['qualification']='One fresh native Fender disable RMW after stoppedCPU/freshRuntimeON and coordinate alias proof, before retained OFF sealing. Same draw/capture/NMI, strict physicalOFF/accounting and freshON. No hardware result proved offline.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 return outputs
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Distinct absent destination required')
 receipt=source/'native-fender-runtime-cycle-owner-source-receipt.json'
 if h(receipt)!=BASE_SHA:raise ValueError('Frozen v19 receipt differs')
 old=json.loads(receipt.read_text());before={r['name']:r['sha256'] for r in old['output_source_pins']}
 for n,d in before.items():
  if h(source/n)!=d:raise ValueError('Frozen source differs: '+n)
 outputs=project_source({n:(source/n).read_bytes() for n in before});profile=dict(old['profile']);profile.update(SELECTED);profile.update(family='gfx_native_fender_off_cycle_scope',version=20,compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,d in before.items():
  if h(source/n)!=d:raise ValueError('Frozen source mutated: '+n)
 out=dict(schema='m4rch.native-fender-off-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),baseline_source_receipt=dict(path=str(receipt),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=h(Path(__file__))),input_source_pins=[dict(name=n,sha256=d) for n,d in before.items()],reused_helper_pins=old['reused_helper_pins'],output_source_pins=[dict(name=n,sha256=h(destination/n)) for n in outputs],changed_files=sorted(n for n in outputs if n in before and h(destination/n)!=before[n]),added_files=['gfx-native-fender-disable.h'],removed_files=[],profile=profile,hardware_actions=[],build_actions=[],qualification='Native disable old|4 is experimentally transferred between verified CPUstop/coordinate alias and OFF sealing. The helper uses fresh runtimeON/GPUid/readback and retains all174 pages. Native poweroff, ACK cleanup, directkick and PMGR writes are not introduced. Draw/start/NMI/strictOFF/freshON are inherited.')
 with (destination/RECEIPT).open('x') as f:f.write(json.dumps(out,indent=2)+'\n')
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/RECEIPT),sha256=h(a.destination/RECEIPT),changed_files=j['changed_files'],profile=j['profile'])))
