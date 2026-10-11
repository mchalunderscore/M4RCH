#!/usr/bin/env python3
"""Prepare the native class1 assertion publication correction from frozen v22."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_SHA='0a928970fb1d5794bf55a4be334c0ff5f1c733bb899757a4dce45879b8acba1c'
OLD='GFX_NATIVE_IDLE_POLICY_FENDER_CYCLE_TRIAL';NEW='GFX_NATIVE_POWER_ASSERTION_FENDER_CYCLE_TRIAL'
RECEIPT='native-power-assertion-fender-cycle-owner-source-receipt.json'
HELPER_SHA='548fb903a0a12ade664b52759d41b0221831197f42656892b2d33f88fd9d8d9a'
BASE_HELPER_SHA='983a095fffb6785242174e93e229e7fac73293540150eb424078fc75ce0bc5b4'
HELPER_EDITS=[(739, b'', b'#define GFX_IDLE_POLICY_ASSERTION (0xc000U+0xe51U)\n#define GFX_IDLE_POLICY_REGION_C (0xc000U)\n'), (934, b'', b'static bool gfx_idle_policy_assertion_attempted,gfx_idle_policy_assertion_cleaned;\nstatic bool gfx_idle_policy_assertion_verified;\nstatic u32 gfx_idle_policy_assertion_before,gfx_idle_policy_assertion_requested,gfx_idle_policy_assertion;\n'), (3354, b'', b'/* Native field is packed and unaligned. Cache maintenance is inherited;\n * memcpy avoids an undefined aligned u32 access in the Linux C producer. */\nstatic u32 gfx_idle_policy_assertion_read(void)\n{\n u32 value;void *p=recovery_ptr(GFX_IDLE_POLICY_ASSERTION);\n recovery_invalidate(p,sizeof(value));memcpy(&value,p,sizeof(value));return value;\n}\n\n'), (6381, b'', b' pr_info("m4rch gfx-native-power-assertion: phase=%s root_offset=0x20 region_c_va=%#llx arena_offset=%#x field_offset=0xe51 bytes=4 unaligned=1 before=%u requested=%u current=%u consumed_baseline=%u consumed_current=%u attempted=%u cleaned=%u verified=%u dmbish=1 native_wrap_u32=1 near_wrap_supported=0 operand_samples_atomic=0\\n",\n  phase,(unsigned long long)(GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_REGION_C),\n  GFX_IDLE_POLICY_ASSERTION,gfx_idle_policy_assertion_before,gfx_idle_policy_assertion_requested,\n  gfx_idle_policy_assertion,gfx_idle_policy_counter_before,gfx_idle_policy_counter,\n  gfx_idle_policy_assertion_attempted,gfx_idle_policy_assertion_cleaned,gfx_idle_policy_assertion_verified);\n'), (6429, b' return recovery_read64(0xa8)==GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_STATUS &&\n', b' return recovery_read64(0x20)==GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_REGION_C &&\n  recovery_read64(0xa8)==GFX_IDLE_POLICY_ARENA_BASE+GFX_IDLE_POLICY_STATUS &&\n'), (8728, b'', b' gfx_idle_policy_assertion=gfx_idle_policy_assertion_read();\n'), (9149, b'', b' if(!gfx_idle_policy_assertion_attempted) {\n  /* Current trial retains old invalid-word rules; native wrap is understood\n   * but UINT_MAX/UINT_MAX-1 baselines are unsupported before any store. */\n  if(gfx_idle_policy_assertion>=~0U-1U ||\n     gfx_idle_policy_assertion!=gfx_idle_policy_counter) return -EPROTO;\n } else if(gfx_idle_policy_assertion!=gfx_idle_policy_assertion_requested) return -EPROTO;\n'), (11380, b'', b' gfx_idle_policy_assertion_before=gfx_idle_policy_assertion;\n gfx_idle_policy_assertion_requested=gfx_idle_policy_assertion_before+1U;\n'), (12568, b'', b' }\n /* Native 89a6a70..89a6b10: copy64, class1 assertion, DMBISH,\n  * producer. This new step never repairs or replays an ambiguous attempt. */\n gfx_idle_policy_assertion_attempted=true;\n memcpy(recovery_ptr(GFX_IDLE_POLICY_ASSERTION),&gfx_idle_policy_assertion_requested,sizeof(u32));\n /* recovery_clean supplies DMBISH before DC CVAC and DSB SY afterward. */\n recovery_clean(recovery_ptr(GFX_IDLE_POLICY_ASSERTION),sizeof(u32));\n gfx_idle_policy_assertion_cleaned=true;\n gfx_idle_policy_assertion=gfx_idle_policy_assertion_read();\n gfx_idle_policy_assertion_verified=gfx_idle_policy_assertion==gfx_idle_policy_assertion_requested;\n gfx_idle_policy_log("assertion-published","none",0);\n if(!gfx_idle_policy_assertion_verified) {ret=-EIO;condition="assertion-readback";goto refused;}\n ret=gfx_idle_policy_sample(false);if(ret) {condition="postassertion-operands";goto refused;}\n if(gfx_idle_policy_counter!=gfx_idle_policy_counter_before || !gfx_idle_policy_record_matches(command)) {\n  ret=-EPROTO;condition="postassertion-changed";goto refused;\n')]
POLICY=dict(version=23,native_power_assertion_class=1,native_power_assertion_region_c_root_offset='0x20',native_power_assertion_region_c_arena_offset='0xc000',native_power_assertion_field_offset='0xe51',native_power_assertion_width_bits=32,native_power_assertion_unaligned=True,native_power_assertion_maximum_writes=1,native_power_assertion_before_producer_after_record=True,native_power_assertion_cache_publication=True,native_power_assertion_baseline_equals_consumed=True,native_power_assertion_near_wrap_supported=False,native_power_assertion_native_u32_wrap_known=True,native_initial_control_opcode22_decimal_class=0,strict_physical_OFF_unchanged=True,work_retirement_verified=False,native_poweroff_reproduced=False,selected_next_hardware_candidate=False)
def sha(b):return hashlib.sha256(b).hexdigest()
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=sha(b))
def require(ok,msg):
 if not ok:raise ValueError(msg)
def helper_projection(original):
 b=original.replace(OLD.encode(),NEW.encode());require(sha(b)==BASE_HELPER_SHA,'Frozen v22 helper differs')
 parts=[];pos=0
 for offset,expected,replacement in HELPER_EDITS:
  require(offset>=pos and b[offset:offset+len(expected)]==expected,'Helper insertion guard differs')
  parts.extend([b[pos:offset],replacement]);pos=offset+len(expected)
 parts.append(b[pos:]);result=b''.join(parts)
 require(sha(result)==HELPER_SHA,'Qualified helper projection differs');return result
def project_source(original):
 outputs=dict(original)
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 helper=HERE/'gfx-native-idle-policy.h';b=helper_projection(original[helper.name])
 require(helper.read_bytes()==b,'Actual-C helper is not exact v22 guarded projection');outputs[helper.name]=b
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);previous=j.pop('native_idle_policy_fender_cycle_trial');previous.update(POLICY)
  j['native_power_assertion_fender_cycle_trial']=previous;j['cold_render_trial']['version']=23
  if n=='preparation.json':j['qualification']='Native class1 assertion publication after record and before producer; all v22 policy/timeouts and inherited teardown unchanged. Exact native publication order and counter identity are source-bound; caller/order transfer remains experimental.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 c=outputs['asc-graph-init.c'];old_title=b'Experimental J614s native idle-policy before202 plus descriptor Fender draw retained NMI OFF cycle';new_title=b'Experimental J614s native power-assertion idle-policy before202 plus descriptor Fender draw retained NMI OFF cycle'
 require(c.count(old_title)==1,'Frozen module description differs');outputs['asc-graph-init.c']=c.replace(old_title,new_title)
 require(outputs['graph-before.bin']==original['graph-before.bin'],'Arena changed');return outputs
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 require(not destination.exists() and source!=destination and source not in destination.parents,'Distinct absent destination required')
 receipt=source/'native-idle-policy-fender-cycle-owner-source-receipt.json'
 require(pin(receipt)['sha256']==BASE_SHA,'Frozen v22 source receipt differs');old=json.loads(receipt.read_bytes());original={}
 for r in old['output_source_pins']:
  b=(source/r['name']).read_bytes();require(sha(b)==r['sha256'],'Frozen source differs: '+r['name']);original[r['name']]=b
 outputs=project_source(original);profile=dict(old['profile']);profile.update(POLICY);profile.update(family='gfx_native_power_assertion_fender_cycle_scope',compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 result=dict(schema='m4rch.native-power-assertion-fender-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),baseline_source_receipt=pin(receipt),source_preparer=pin(Path(__file__)),helper_pin=pin(HERE/'gfx-native-idle-policy.h'),native_abi_pins=[pin(ROOT/'docs/evidence/2026-10-11-gfx-native-power-assertion-publication.json')],input_source_pins=old['output_source_pins'],reused_helper_pins=old['reused_helper_pins'],output_source_pins=[dict(name=n,sha256=sha(b)) for n,b in outputs.items()],changed_files=sorted(n for n in original if outputs[n]!=original[n]),added_files=[],removed_files=[],profile=profile,hardware_actions=[],build_actions=[],selected_next_hardware_candidate=False,qualification='One class1 host assertion after record cache publication and before producer/EP33. Exact v22 control record/timeout/unsafe policy, graph arena/compiled data, all174 ownership and draw/202/NMI/stop/Fender/coordinate/strictOFF/rejoin retained. Native pointer/u32/order source-bound; Linux cache mapping and before202 caller policy remain transfers.')
 for n,b in original.items():require((source/n).read_bytes()==b,'Frozen source mutated')
 (destination/RECEIPT).write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination);print(json.dumps(dict(receipt=pin(a.destination/RECEIPT),changed_files=j['changed_files'])))
