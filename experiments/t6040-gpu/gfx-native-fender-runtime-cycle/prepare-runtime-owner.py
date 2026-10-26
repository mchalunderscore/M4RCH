#!/usr/bin/env python3
"""Prepare the distinct read-only runtime admission correction from frozen v18."""
from pathlib import Path
import argparse, hashlib, json

HERE = Path(__file__).resolve().parent
BASE_SHA = '45d2017114725882e7bec1bbbd60f2211888c3f5f5d7f3159174cdf0da2ce6a1'
HELPER_SHA = '4e25f120981774cef205020ea8d59683c42d549477ce174af427b7b3c61d8497'
OLD = 'GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL'
NEW = 'GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL'
RECEIPT = 'native-fender-runtime-cycle-owner-source-receipt.json'
SELECTED = dict(version=19, runtime_admission_after_verified_Fender=True,
 runtime_admission_named_actual_states=[0,4,15], gated_actual_requires_auto=True,
 runtime_admission_target=15, runtime_blocked_mask='0x80001c00',
 strict_before_Fender=True, strict_physical_OFF_unchanged=True,
 strict_fresh_ON_rejoin_unchanged=True, runtime_application_diagnostics=True,
 runtime_MMIO_writes=0, runtime_PM_writes=0)

def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t, a, b):
 if t.count(a) != 1: raise ValueError('Frozen insertion differs: '+a[:100])
 return t.replace(a,b,1)

def project_source(outputs):
 """Pure projection of original frozen-v18 path/bytes, including macro changes."""
 outputs = dict(outputs)
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile': outputs[n]=b.replace(OLD.encode(),NEW.encode())
 c=outputs['asc-graph-init.c'].decode()
 c=once(c,'#include "gfx-native-fender-enable.h"',
  '#include "gfx-native-fender-enable.h"\n#include "gfx-native-runtime-state.h"')
 c=once(c,'Experimental J614s native Fender enable transfer plus traced draw and native timeout NMI retained cycle',
  'Experimental J614s native Fender runtime admission plus traced draw and native timeout NMI retained cycle')
 outputs['asc-graph-init.c']=c.encode()
 cold=outputs['gfx-cold-render.h'].decode()
 declarations='''static bool gfx_native_runtime_active(const char *phase,u32 valid,bool domain_on,u32 word);
static bool gfx_runtime_application_guard(unsigned int count,unsigned int expected_trace,
 bool idle_required,bool idle_observed,bool live,u64 counter,u32 phase,u32 host_stop,
 u32 request_state,u32 request_flag,const u32 control[3],u32 trace);

'''
 cold=once(cold,'static bool gfx_cold_guard(unsigned int count,bool idle,unsigned int trace)',
  declarations+'static bool gfx_cold_guard(unsigned int count,bool idle,unsigned int trace)')
 cold=once(cold,' if(gfx_cold_snapshot("cold-guard",count,&physical) || !physical.domain_on ||\n    (physical.before&0x80001cffU)!=0xffU) return false;',
  ' if(gfx_cold_snapshot("cold-guard",count,&physical) ||\n    !gfx_native_runtime_active("cold-guard",physical.valid,physical.domain_on,physical.before)) return false;')
 cold=once(cold,''' return !gfx_cold_counter && !gfx_cold_phase && !gfx_cold_host_stop &&
  !gfx_cold_request_state && !gfx_cold_request_flag &&
  gfx_cold_control[0]==count && gfx_cold_control[1]==count && gfx_cold_control[2]==count &&
  gfx_cold_trace_after==trace && (!idle || recovery_idle()) && gfx_cold_live();''',
 ''' return gfx_runtime_application_guard(count,trace,idle,!idle||recovery_idle(),
  gfx_cold_live(),gfx_cold_counter,gfx_cold_phase,gfx_cold_host_stop,
  gfx_cold_request_state,gfx_cold_request_flag,gfx_cold_control,gfx_cold_trace_after);''')
 outputs['gfx-cold-render.h']=cold.encode()
 post=outputs['gfx-postdraw-native-nmi-cycle.h'].decode()
 post=once(post,' if(on) return o.domain_on && (o.before&0x80001cffU)==0xffU?0:-EBUSY;',
 ''' if(on && (!strcmp(phase,"admission-before") || !strcmp(phase,"before-off")))
  return gfx_native_runtime_active(phase,o.valid,o.domain_on,o.before)?0:-EBUSY;
 if(on) return o.domain_on && (o.before&0x80001cffU)==0xffU?0:-EBUSY;''')
 outputs['gfx-postdraw-native-nmi-cycle.h']=post.encode()
 helper=HERE/'gfx-native-runtime-state.h'
 if h(helper)!=HELPER_SHA: raise ValueError('Qualified runtime helper differs')
 outputs[helper.name]=helper.read_bytes()
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);previous=j.pop('native_fender_draw_cycle_trial')
  previous.update(SELECTED);j['native_fender_runtime_cycle_trial']=previous;j['cold_render_trial']['version']=19
  if n=='preparation.json': j['qualification']='Read-only native runtime admission after verified Fender enable, preserving strict pre-enable and physical OFF/fresh ON predicates; one draw/NMI retained cycle. No hardware result proved offline.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 return outputs

def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 if destination.exists() or source==destination or source in destination.parents: raise ValueError('Distinct absent destination required')
 receipt=source/'native-fender-draw-cycle-owner-source-receipt.json'
 if h(receipt)!=BASE_SHA: raise ValueError('Frozen v18 receipt differs')
 old=json.loads(receipt.read_text());before={r['name']:r['sha256'] for r in old['output_source_pins']}
 for n,d in before.items():
  if h(source/n)!=d: raise ValueError('Frozen source differs: '+n)
 outputs=project_source({n:(source/n).read_bytes() for n in before})
 profile=dict(old['profile']);profile.update(SELECTED);profile.update(family='gfx_native_fender_runtime_cycle_scope',version=19,compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items(): (destination/n).write_bytes(b)
 for n,d in before.items():
  if h(source/n)!=d: raise ValueError('Frozen source mutated: '+n)
 out=dict(schema='m4rch.native-fender-runtime-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),
  baseline_source_receipt=dict(path=str(receipt),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=h(Path(__file__))),
  input_source_pins=[dict(name=n,sha256=d) for n,d in before.items()],reused_helper_pins=old['reused_helper_pins'],
  output_source_pins=[dict(name=n,sha256=h(destination/n)) for n in outputs],
  changed_files=sorted(n for n in outputs if n in before and h(destination/n)!=before[n]),added_files=['gfx-native-runtime-state.h'],removed_files=[],profile=profile,
  hardware_actions=[],build_actions=[],qualification='Read-only dynamic auto-PM admission after native Fender complete, on the retained first epoch only. Application operands, strict OFF, fresh ON/rejoin and all lifetime constraints preserved. No forced clock, ACK or PMGR writes added.')
 with (destination/RECEIPT).open('x') as f: f.write(json.dumps(out,indent=2)+'\n')
 return out

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/RECEIPT),sha256=h(a.destination/RECEIPT),changed_files=j['changed_files'],profile=j['profile'])))
