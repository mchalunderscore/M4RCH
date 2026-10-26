#!/usr/bin/env python3
"""Prepare a new v14 source only; never build/load or alter frozen v13."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_SHA='2ebd9dbe52a5e0be4de5793d9c3c6ee454ead602569e52ed16e5260e3a4cfec7'
OLD='GFX_COLD_RENDER_TRIAL'
NEW='GFX_COLD_RENDER_PAUSE_RELEASE_TRIAL'
ADDED=['gfx-cold-pause-state.h','gfx-cold-pause-release.h']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Frozen insertion changed: '+a[:100])
 return s.replace(a,b,1)
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('New distinct destination required')
 base=source/'cold-render-owner-source-receipt.json'
 if sha(base)!=BASE_SHA:raise ValueError('Selected v13 receipt changed')
 old=json.loads(base.read_text());pins={x['name']:x['sha256'] for x in old['output_source_pins']}
 for name,h in pins.items():
  if sha(source/name)!=h:raise ValueError('Frozen source differs: '+name)
 before=dict(pins);before[base.name]=BASE_SHA
 outputs={name:(source/name).read_bytes() for name in pins}
 for name,raw in list(outputs.items()):
  if name.endswith(('.c','.h')) or name=='Makefile':outputs[name]=raw.replace(OLD.encode(),NEW.encode())
 s=outputs['asc-graph-init.c'].decode()
 s=once(s,'static u64 gfx_cold_fault_info,gfx_cold_fault_addr;','static u64 gfx_cold_fault_info,gfx_cold_fault_addr;\n#include "gfx-cold-pause-state.h"')
 s=once(s,' /* Matched TEXT reads21038/21040', ''' gfx_pause_sample.ksm_valid=true;
 gfx_pause_sample.enabled0=readq(ksm+0x1038);gfx_pause_sample.enabled1=readq(ksm+0x1040);
 gfx_pause_sample.request=readq(ksm+0x11c8);gfx_pause_sample.ack=readq(ksm+0x11d0);
 /* Matched TEXT reads21038/21040''')
 s=once(s,'readq(ksm+0x1038),readq(ksm+0x1040),readq(ksm+0x11c8));','gfx_pause_sample.enabled0,gfx_pause_sample.enabled1,gfx_pause_sample.request);')
 s=once(s,'readq(ksm+0x11d0));','gfx_pause_sample.ack);')
 s=once(s,'  for(q=0;q<4;q++)\n   pr_info(','''  for(q=0;q<4;q++) {
   gfx_pause_sample.config[q]=readq(ksm+0x1148+q*8);
   gfx_pause_sample.status[q]=readq(ksm+0x1168+q*8);
   pr_info(''')
 s=once(s,'readq(ksm+0x1148+q*8),readq(ksm+0x1168+q*8));','gfx_pause_sample.config[q],gfx_pause_sample.status[q]);\n  }')
 s=once(s,'  gfx_cold_fault_info=readq(fault+0x18c0);gfx_cold_fault_addr=readq(fault+0x18c8);gfx_cold_fault_valid=true;','  gfx_cold_fault_info=readq(fault+0x18c0);gfx_cold_fault_addr=readq(fault+0x18c8);gfx_cold_fault_valid=true;\n  gfx_pause_sample.fault_valid=true;gfx_pause_sample.fault_info=gfx_cold_fault_info;gfx_pause_sample.fault_addr=gfx_cold_fault_addr;')
 s=once(s,' pr_info("m4rch joined-live-output:', ' memcpy(gfx_pause_sample.changed,counts,sizeof(counts));gfx_pause_sample.output_valid=true;\n pr_info("m4rch joined-live-output:')
 s=s.replace('Experimental J614s automatic cold control and one retained TA/3D draw','Experimental J614s one cold draw and once native-formula scheduling bit0 release')
 outputs['asc-graph-init.c']=s.encode()
 s=outputs['gfx-cold-render.h'].decode()
 s=once(s,'static int gfx_cold_sample(', '#include "gfx-cold-pause-release.h"\n\nstatic int gfx_cold_sample(')
 s=once(s,' gfx_cold_sample_index=index;',' memset(&gfx_pause_sample,0,sizeof(gfx_pause_sample));\n gfx_cold_sample_index=index;')
 s=once(s,' if(!gfx_cold_fault_valid) return -ENODATA;',' gfx_cold_pause_watch();\n if(!gfx_cold_fault_valid) return -ENODATA;')
 s=once(s,'   next++;','   if(next==1) {\n    ret=gfx_cold_pause_release();\n    if(ret) return gfx_cold_refuse("pause-release",ret);\n   }\n   next++;')
 s=once(s,' gfx_cold_log("retained-final",result);',' gfx_pause_log("retained-final");\n gfx_cold_log("retained-final",result);')
 outputs['gfx-cold-render.h']=s.encode()
 for name in ['graph-receipt.json','preparation.json']:
  d=json.loads(outputs[name]);d['cold_render_pause_release_trial']=dict(version=14,maximum_request_writes=1,request_before=3,request_after=2,request_formula='old_request & ~1',expected_ack_lowbit=0,intervention_after_sample_index=2,no_ack_write=True,no_extra_notification=True,preserve_bit1=True,retained_pages=174)
  outputs[name]=(json.dumps(d,indent=2)+'\n').encode()
 for name in ADDED:outputs[name]=(HERE/name).read_bytes()
 profile=dict(old['profile']);profile.update(family='gfx_cold_render_pause_release_scope',version=14,compile_macro=NEW,maximum_scheduler_request_writes=1,scheduler_request_offset='0x211c8',scheduler_ack_offset='0x211d0',scheduler_request_before=3,scheduler_request_after=2,scheduler_request_formula='last_fresh_request & ~1ULL',scheduler_expected_ack_lowbit=0,scheduler_release_sample_index=2,scheduler_release_min_elapsed_ms=100,scheduler_release_timeout_ms=100,scheduler_release_poll_max=101,scheduler_ack_writes=0,scheduler_preserve_bit1=True,scheduler_other_bits_preserved=True,scheduler_observe_firmware_rewrite=True,scheduler_requires_no_output_completion_progress=True,scheduler_requires_own_work_consumption=True,native_reason_mutex_owned=False,native_reason_lifecycle_reproduced=False,scheduler_log_prefix='m4rch gfx-cold-pause-release:')
 destination.mkdir(parents=True)
 for name,raw in outputs.items():(destination/name).write_bytes(raw)
 changed=sorted(name for name in pins if sha(destination/name)!=pins[name])
 for name,h in before.items():
  if sha(source/name)!=h:raise ValueError('Frozen source mutated')
 receipt=dict(schema='m4rch.gfx-cold-render-pause-release-owner-source.v1',source=str(source),destination=str(destination),source_path=str(source),baseline_source_receipt=dict(path=str(base),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__))),input_source_pins=[dict(name=n,sha256=h) for n,h in before.items()],output_source_pins=[dict(name=n,sha256=sha(destination/n)) for n in outputs],changed_files=changed,added_files=ADDED,removed_files=[],profile=profile,hardware_actions=[],build_actions=[],qualification='Distinct fresh cold draw plus one native-formula request-bit0 intervention. Firmware reason/mutex ownership is not reproduced; bit1 acknowledgement wait remains separate. No execution, rendering or retirement proved.')
 with (destination/'cold-render-pause-release-owner-source-receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();r=prepare(a.source,a.destination);print(json.dumps(dict(receipt=str(a.destination/'cold-render-pause-release-owner-source-receipt.json'),changed=r['changed_files'],added=ADDED)))
