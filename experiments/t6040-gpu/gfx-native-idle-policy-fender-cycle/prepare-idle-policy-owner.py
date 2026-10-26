#!/usr/bin/env python3
"""Prepare one idle-policy-before202 transfer from the frozen v21 owner."""
import argparse, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_SHA='d9c3abf1deff7d0a72c4229877598ec35b6c3a8fed7344b6ffca99b189b9c5f0'
HELPER_SHA='48b56d10cd312b09c9200637f0979ef91fdd50aa9b6475c5b1c6e80d919280cc'
OLD='GFX_NATIVE_DESCRIPTOR_FENDER_CYCLE_TRIAL';NEW='GFX_NATIVE_IDLE_POLICY_FENDER_CYCLE_TRIAL'
RECEIPT='native-idle-policy-fender-cycle-owner-source-receipt.json'
ABI_PINS={
 'docs/evidence/2026-10-11-gfx-native-gpu-idle-control-abi.json':'de39401219a145372264ed4bdf42bc7017f19ddc31c4384ba2de006217cde0b8',
 'docs/evidence/2026-10-11-gfx-native-firmware-off-object.json':'e1664b1fedc2bbb315aca5e226244cf908eda589d611549dcbb5fa3bb1049fd0'}
POLICY=dict(version=22,native_idle_policy_opcode=10,native_idle_policy_bool=1,
 native_idle_policy_bool_width=32,native_idle_policy_record_bytes=64,
 native_idle_policy_slot=33,native_idle_policy_producer=34,native_idle_policy_maximum_notifications=1,
 native_idle_policy_after_sealed_capture_before_202=True,native_idle_policy_caller_order_transfer_hypothesis=True,
 native_idle_policy_processing_timeout_ms=2000,native_idle_policy_firmware_off_timeout_ms=2000,
 native_idle_policy_processing_polls=2001,native_idle_policy_firmware_off_polls=2001,
 native_idle_policy_clean_timeout_continues_teardown=True,native_idle_policy_unsafe_failure_retains_unknown=True,
 native_idle_policy_independent_counter_offset='0xe438',native_idle_policy_firmware_off_object='status_a',
 native_idle_policy_firmware_off_word_offset='0x10',native_idle_policy_admission_refresh_before_sole_202=True,
 native_idle_policy_private_flag_writes=0,native_idle_policy_raw_reset_writes=0,
 strict_physical_OFF_unchanged=True,strict_fresh_ON_rejoin_unchanged=True,
 native_poweroff_reproduced=False,work_retirement_verified=False,selected_next_hardware_candidate=False)
def sha(b):return hashlib.sha256(b).hexdigest()
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=sha(b))
def require(ok,msg):
 if not ok:raise ValueError(msg)
def once(t,a,b):
 require(t.count(a)==1,'Frozen insertion differs: '+a[:100]);return t.replace(a,b,1)
def project_source(original):
 """Pure original-frozen-v21 path/bytes projection; no build or hardware."""
 outputs=dict(original)
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 helper=HERE/'gfx-native-idle-policy.h';require(pin(helper)['sha256']==HELPER_SHA,'Actual-C qualified helper differs')
 for n,h in ABI_PINS.items():require(pin(ROOT/n)['sha256']==h,'Frozen native ABI differs: '+n)
 c=outputs['asc-graph-init.c'].decode()
 c=once(c,'#include "gfx-native-fender-disable.h"','#include "gfx-native-fender-disable.h"\n#include "gfx-native-idle-policy.h"')
 c=once(c,'Experimental J614s native descriptor correction plus Fender draw and retained native NMI OFF cycle','Experimental J614s native idle-policy before202 plus descriptor Fender draw retained NMI OFF cycle')
 outputs['asc-graph-init.c']=c.encode()
 post=outputs['gfx-postdraw-native-nmi-cycle.h'].decode()
 post=once(post,'static int gfx_native_fender_disable(void);','static int gfx_native_fender_disable(void);\nstatic int gfx_native_idle_policy_before_202(void);')
 hook=' if(!gfx_postdraw_active()) return gfx_postdraw_refuse("pre202-ownership",-EBUSY);\n ret=gfx_native_powergate_ack();'
 post=once(post,hook,' if(!gfx_postdraw_active()) return gfx_postdraw_refuse("pre202-ownership",-EBUSY);\n ret=gfx_native_idle_policy_before_202();\n if(ret) return gfx_postdraw_refuse("idle-policy-before202",ret);\n /* New bounded policy observations consume the original250ms admission.\n  * Acquire fresh transport admission without replaying policy or202. */\n gfx_postdraw_log("idle-policy-refresh-admission",0);\n ret=gfx_native_powergate_admission_drain();\n if(ret) return gfx_postdraw_refuse("idle-policy-refresh-admission",ret);\n ret=gfx_native_powergate_ack();')
 outputs['gfx-postdraw-native-nmi-cycle.h']=post.encode();outputs[helper.name]=helper.read_bytes()
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);previous=j.pop('native_descriptor_fender_cycle_trial');previous.update(POLICY)
  j['native_idle_policy_fender_cycle_trial']=previous;j['cold_render_trial']['version']=22
  if n=='preparation.json':j['qualification']='One owned64B opcode0a/bool1 transfer before202; bounded independent processing and firmware-off observations. Clean timeout continues one inherited teardown; unsafe operands retainunknown. Native caller/order remain experimental. Actual C, source projection, host and real build are separate qualifications.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 require(outputs['graph-before.bin']==original['graph-before.bin'],'Arena changed')
 return outputs
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 require(not destination.exists() and source!=destination and source not in destination.parents,'Distinct absent destination required')
 receipt=source/'native-descriptor-fender-cycle-owner-source-receipt.json'
 require(pin(receipt)['sha256']==BASE_SHA,'Frozen v21 source receipt differs');old=json.loads(receipt.read_bytes());original={}
 for r in old['output_source_pins']:
  b=(source/r['name']).read_bytes();require(sha(b)==r['sha256'],'Frozen source differs: '+r['name']);original[r['name']]=b
 outputs=project_source(original);profile=dict(old['profile']);profile.update(POLICY);profile.update(family='gfx_native_idle_policy_fender_cycle_scope',compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,b in original.items():require((source/n).read_bytes()==b,'Frozen source mutated')
 result=dict(schema='m4rch.native-idle-policy-fender-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),baseline_source_receipt=pin(receipt),source_preparer=pin(Path(__file__)),helper_pin=pin(HERE/'gfx-native-idle-policy.h'),native_abi_pins=[pin(ROOT/n) for n in ABI_PINS],input_source_pins=old['output_source_pins'],reused_helper_pins=old['reused_helper_pins'],output_source_pins=[dict(name=n,sha256=sha(b)) for n,b in outputs.items()],changed_files=sorted(n for n in original if outputs[n]!=original[n]),added_files=['gfx-native-idle-policy.h'],removed_files=[],profile=profile,hardware_actions=[],build_actions=[],selected_next_hardware_candidate=False,qualification='One guarded slot33 opcode0a/bool1 publication with independent processing/off observations before sole202. Exact v21 arena/mappings/backing/shaders/174ownership/draw and native202/NMI/stop/Fender/coordinate/strictOFF/management-only rejoin are preserved. New source hook refreshes inherited admission after bounded waits; clean timeout continues while unsafe state seals retainedunknown.')
 with (destination/RECEIPT).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/RECEIPT),sha256=pin(a.destination/RECEIPT)['sha256'],changed_files=j['changed_files'],added_files=j['added_files'],selected_next_hardware_candidate=False)))
