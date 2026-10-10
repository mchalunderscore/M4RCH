#!/usr/bin/env python3
"""Prepare distinct v17 from exact frozen v16. No builds or hardware actions."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_SHA='08383fcfe70b92f5562288f2ec60b01f7712d5e4f9cf40a7a728dce7e05ed1c5'
OLD='GFX_POSTDRAW_NATIVE_CYCLE_TRIAL';NEW='GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL'
RECEIPT='postdraw-native-nmi-cycle-owner-source-receipt.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(t,a,b):
 if t.count(a)!=1:raise ValueError('Frozen insertion changed: '+a[:100])
 return t.replace(a,b,1)
def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Distinct absent destination required')
 receipt=source/'postdraw-native-cycle-owner-source-receipt.json'
 if sha(receipt)!=BASE_SHA:raise ValueError('Frozen v16 source receipt differs')
 old=json.loads(receipt.read_text());before={p['name']:p['sha256'] for p in old['output_source_pins']}
 for n,h in before.items():
  if sha(source/n)!=h:raise ValueError('Frozen v16 source changed: '+n)
 outputs={n:(source/n).read_bytes() for n in before if n!='gfx-postdraw-native-cycle.h'}
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 h=outputs['gfx-cold-render.h'].decode()
 h=once(h,'#include "gfx-postdraw-native-cycle.h"','#include "gfx-postdraw-native-nmi-cycle.h"')
 outputs['gfx-cold-render.h']=h.encode()
 c=outputs['asc-graph-init.c'].decode()
 c=once(c,'#define ASC_BASE 0x28a600000ULL','#define ASC_BASE 0x28a600000ULL\n#define GFX_POSTDRAW_NMI_ASC_BYTES 0x2000U')
 # Every ASC reserve/map/release uses the new extent; mailbox remains separate.
 if c.count('ASC_BASE,0x1000')!=3:raise ValueError('Frozen ASC extent sites differ')
 c=c.replace('ASC_BASE,0x1000','ASC_BASE,GFX_POSTDRAW_NMI_ASC_BYTES')
 c=once(c,'goto fail;}asc_region=true;','goto fail;}asc_region=true;gfx_postdraw_nmi_asc_owned=true;')
 c=once(c,'#include "gfx-cold-render.h"','#include "gfx-cold-render.h"\n#include "gfx-gravity-preasc.h"')
 marker=' pr_info("m4rch ASC crashlog: cold control=%#x status=%#x; starting bounded poll\\n",control,status);'
 c=once(c,marker,' ret=gfx_gravity_preasc();\n if(ret) {\n  pr_err("m4rch gfx-gravity-preasc: startup-retained result=%d cleanup_attempted=0\\n",ret);\n  return 0; /* Native coordinate is pinned; retain owner/PM/resources. */\n }\n'+marker)
 c=c.replace('Experimental J614s one traced cold draw and one captured retained native management cycle','Experimental J614s Gravity preASC plus traced draw and native timeout NMI retained cycle')
 outputs['asc-graph-init.c']=c.encode()
 outputs['gfx-postdraw-native-nmi-cycle.h']=(HERE/'gfx-postdraw-native-nmi-cycle.h').read_bytes()
 outputs['gfx-gravity-preasc.h']=(HERE/'gfx-gravity-preasc.h').read_bytes()
 trial=dict(version=17,trace_mask_preserved=3,existing_opcode22_refreshes_trace=True,postdraw_command='postdraw-native-cycle <64 lowercase hex>',
  maximum_native202=1,maximum_native_nmi=1,nmi_only_after_clean_owned202_ACK_timeout=True,nmi_timeout_ms=250,nmi_poll_max=251,nmi_frame_max=256,
  nmi_ep0_message='0x00f0000000000000',nmi_fiq_writes=[['0x1004','0x10'],['0x1014','1']],asc_reserved_mapped_bytes=8192,
  crash_EP1_raw_only=True,crash_replies=0,crash_buffer_allocations=0,ack_inference_from_crash=False,
  maximum_pm_puts=1,maximum_retained_pm_gets=1,maximum_retained_starts=1,application_replay=False,root_replay=False,work_replay=False,
  second_B20=False,second_cycle=False,experimental_submitted_work_powergate=True,all_pages_maps_context_retained=True,
  gravity_preasc_before_first_start=True,gravity_preasc_calls=1,gravity_preasc_repeated_on_management_rejoin=False)
 for n in ('preparation.json','graph-receipt.json'):
  j=json.loads(outputs[n]);j.pop('postdraw_native_cycle_trial',None);j['postdraw_native_nmi_cycle_trial']=trial
  j['cold_render_trial'].update(version=17)
  if n=='preparation.json':j['qualification']='Distinct experimental Gravity preASC/traced draw and clean ACK-timeout firmware NMI retained management cycle; no retirement or application restart proved.'
  outputs[n]=(json.dumps(j,indent=2)+'\n').encode()
 profile=dict(old['profile']);profile.update(family='gfx_postdraw_native_nmi_cycle_scope',version=17,compile_macro=NEW,
  maximum_native_nmi=1,nmi_only_after_clean_owned202_ACK_timeout=True,nmi_timeout_ms=250,nmi_poll_max=251,nmi_frame_max=256,
  nmi_log_prefix='m4rch gfx-postdraw-native-nmi:',nmi_rx_log_prefix='m4rch gfx-postdraw-native-nmi-rx:',
  nmi_ep0_message='0x00f0000000000000',nmi_fiq_writes=[['0x1004','0x10'],['0x1014','1']],asc_reserved_mapped_bytes=8192,
  crash_EP1_raw_only=True,crash_replies=0,crash_buffer_allocations=0,ack_inference_from_crash=False,
  firmware_side_nmi_subset_only=True,macos_host_fatal_policy_reproduced=False,
  gravity_preasc_before_first_start=True,gravity_preasc_calls=1,gravity_preasc_repeated_on_management_rejoin=False)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,h in before.items():
  if sha(source/n)!=h:raise ValueError('Frozen v16 input mutated during preparation')
 report=dict(schema='m4rch.gfx-postdraw-native-nmi-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),
  baseline_source_receipt=dict(path=str(receipt),sha256=BASE_SHA),source_preparer=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__))),
  input_source_pins=[dict(name=n,sha256=h) for n,h in before.items()],reused_helper_pins=old['reused_helper_pins'],
  output_source_pins=[dict(name=n,sha256=sha(destination/n)) for n in outputs],
  changed_files=sorted(n for n in outputs if n in before and sha(destination/n)!=before[n]),
  added_files=['gfx-postdraw-native-nmi-cycle.h','gfx-gravity-preasc.h'],removed_files=['gfx-postdraw-native-cycle.h'],profile=profile,
  hardware_actions=[],build_actions=[],qualification='Source only. Native firmware NMI after submitted work is experimental; fresh idle, checked CPUstop, paired OFF/PMGR/accounting and management ON do not prove work retirement, rendering, application rejoin or safe free. All174 pages/maps retained. Gravity preASC affects initial cold startup only.')
 with (destination/RECEIPT).open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination)
 print(json.dumps(dict(receipt=str(a.destination/RECEIPT),changed_files=j['changed_files'],added_files=j['added_files'],profile=j['profile'])))
