#!/usr/bin/env python3
"""Prepare a distinct automatic cold render owner; no build/load/hardware."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_RECEIPT_SHA='bf52cabe10ab41df883c22907a9a66d4ff338cebc93b3d82d66ea5e27004ffa1'
DESIGN_SHA='fefa394b1664d2855dbbc593cf053943e4ba7e1f064b9e1989c532f72c3aa8ac'
CHANGED=['Makefile','asc-graph-init.c','gfx-coordinate-owner.h','graph-receipt.json','preparation.json','recovery-cycle.h']
ADDED=['gfx-cold-ap.h','gfx-cold-render.h','gfx-cold-runtime.h','gfx-cold-startup.h']
REMOVED=['gfx-ap-repeat-cycle-coordinate.h','gfx-native-ap-repeat-cycle.h','gfx-native-powergate-drain.h','gfx-reset-scope.h','gfx-reset-startup.h']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def once(text,old,new):
 if text.count(old)!=1:raise ValueError('Frozen insertion changed: '+repr(old[:100]))
 return text.replace(old,new,1)

def owner_source(source):
 s=(source/'asc-graph-init.c').read_text()
 a=s.index('#ifdef GFX_RESET_SCOPE_TRIAL\n')
 b=s.index('#define ASC_BASE',a)
 s=s[:a]+'''#if !defined(GFX_COLD_RENDER_TRIAL) || !defined(GRAPH_RECOVERY_EXPERIMENT) || !defined(GRAPH_JOINED_INIT_EXPERIMENT) || defined(GRAPH_JOINED_WORK_EXPERIMENT)
#error Distinct cold render requires the joined idle graph and automatic work path
#endif
#include "gfx-cold-startup.h"
static unsigned int gfx_cold_sample_index,gfx_cold_elapsed_ms;
static unsigned long gfx_cold_sample_jiffies;
static bool gfx_cold_fault_valid;
static u64 gfx_cold_fault_info,gfx_cold_fault_addr;
'''+s[b:]
 s=once(s,'static int gfx_coord_owner_before_off(void);','')
 a=s.index('static unsigned int gfx_ap_repeat_current_epoch=1;')
 b=s.index('#ifdef GRAPH_RECOVERY_EXPERIMENT\nstatic bool power_ack',a)
 s=s[:a]+'static const unsigned int gfx_cold_current_epoch=1;\n#include "gfx-cold-ap.h"\n'+s[b:]
 s=once(s,'#include "gfx-ap-repeat-cycle-coordinate.h"','#include "gfx-cold-render.h"')
 s=s.replace('GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL','GFX_COLD_RENDER_TRIAL')
 s=s.replace('GFX_RETAINED_CYCLE_HOST_ON','GFX_COLD_AP_ON')
 s=s.replace('gfx_retained_cycle_cold_ap_log','gfx_cold_ap_log')
 s=s.replace('gfx_retained_cycle_ap_on_known','gfx_cold_ap_known')
 s=s.replace('gfx_retained_cycle_startup_retained','gfx_cold_startup_retained')
 s=once(s,' if(request==0xb && !cold_ap_on) return false;',' if(!cold_ap_on) return false;')
 s=once(s,'#ifdef GFX_RESET_SCOPE_TRIAL\n ret=gfx_reset_scope_startup_admission(run_gate,resident_session,\n  request_shutdown,warm_restart,release_on_shutdown);\n if(ret) return ret;\n#endif',' ret=gfx_cold_startup_admission(run_gate,resident_session,\n  request_shutdown,warm_restart,release_on_shutdown);\n if(ret) return ret;')
 a=s.index('  /* Publish one complete candidate batch; published pages remain pinned. */')
 b=s.index('\nretire_firmware:',a)
 s=s[:a]+'''  gfx_cold_apps_started=apps_started;
  /* Automatic once-only pipeline; module/PM/backing remain retained. */
  if(apps_started==3 && !(readl(mbox+0x110)&BIT(16)) && gfx_cold_ap_known()) {
   root_sent=true;receive_enabled=true;
   wmb();writeq(0x00810c2000100000ULL,mbox+0x800);writeq(32,mbox+0x808);
   pr_info("m4rch gfx-cold-render-root: phase=root-published message=0x00810c2000100000 endpoint=32 apps_started=3 work_submitted=0\\n");
   mutex_lock(&graph_io_lock);
   (void)gfx_cold_run();
   mutex_unlock(&graph_io_lock);
   return 0;
  }
'''+s[b:]
 s=once(s,'MODULE_DESCRIPTION("Experimental J614s bounded two retained AP ON skip PWRGATE management epochs no-work coordinator");','MODULE_DESCRIPTION("Experimental J614s automatic cold control and one retained TA/3D draw");')
 # Every fresh hardware/output row has its own sample/time provenance.
 for name in ['gpu-identity','ksm-status','ksm-detail','ksm-live','hw-completion-register','ksm-fault','joined-live-output','joined-hw-completion']:
  pattern=r'(pr_info\("m4rch '+re.escape(name)+r': phase=%s)([^"\n]*\\n",\s*)(phase,)'
  s,n=re.subn(pattern,lambda m:m[1]+' sample_index=%u elapsed_ms=%u sample_jiffies=%lu operand_samples_atomic=0'+m[2]+'phase,gfx_cold_sample_index,gfx_cold_elapsed_ms,gfx_cold_sample_jiffies,',s)
  if n!=1:raise ValueError('Sample row insertion changed '+name)
 s=once(s,' if(fault){\n  pr_info("m4rch ksm-fault:', ' gfx_cold_fault_valid=false;gfx_cold_fault_info=0;gfx_cold_fault_addr=0;\n if(fault){\n  gfx_cold_fault_info=readq(fault+0x18c0);gfx_cold_fault_addr=readq(fault+0x18c8);gfx_cold_fault_valid=true;\n  pr_info("m4rch ksm-fault:')
 s=once(s,'readq(fault+0x18c0),readq(fault+0x18c8));','gfx_cold_fault_info,gfx_cold_fault_addr);')
 # Read the same bound primary/PRC/engine operands in a healthy cold epoch.
 s=once(s,' iounmap(ksm);\n fault=ioremap', ''' iounmap(ksm);
 {
  void __iomem *primary=ioremap(0x288004000ULL,PAGE_SIZE);
  void __iomem *prc=ioremap(0x288d4c000ULL,PAGE_SIZE);
  void __iomem *engines=ioremap(0x288d44000ULL,PAGE_SIZE);
  if(primary) {
   pr_info("m4rch gfx-cold-render-primary: phase=%s sample_index=%u elapsed_ms=%u raw5960=%#llx raw5978=%#llx raw5970=%#llx operand_samples_atomic=0\\n",
    phase,gfx_cold_sample_index,gfx_cold_elapsed_ms,readq(primary+0x1960),readq(primary+0x1978),readq(primary+0x1970));
   iounmap(primary);
  }
  if(prc) {
   pr_info("m4rch gfx-cold-render-prc: phase=%s sample_index=%u elapsed_ms=%u rawd4c004=%#x rawd4c000=%#x operand_samples_atomic=0\\n",
    phase,gfx_cold_sample_index,gfx_cold_elapsed_ms,readl(prc+4),readl(prc));
   iounmap(prc);
  }
  if(engines) {
   pr_info("m4rch gfx-cold-render-engine: phase=%s sample_index=%u elapsed_ms=%u rawd44070=%#x operand_samples_atomic=0\\n",
    phase,gfx_cold_sample_index,gfx_cold_elapsed_ms,readl(engines+0x70));
   iounmap(engines);
  }
 }
 fault=ioremap''')
 return s

def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Destination must be distinct and new')
 old_path=source/'native-ap-repeat-cycle-owner-source-receipt.json'
 if sha(old_path)!=BASE_RECEIPT_SHA:raise ValueError('Frozen v12 receipt changed')
 old=json.loads(old_path.read_text());before={r['name']:r['sha256'] for r in old['output_source_pins']}
 for n,pin in before.items():
  if sha(source/n)!=pin:raise ValueError('Frozen v12 source changed '+n)
 before[old_path.name]=sha(old_path)
 design=ROOT/'docs/evidence/2026-10-10-gpu-desktop-critical-path-cold-render.json'
 if sha(design)!=DESIGN_SHA:raise ValueError('Cold render design changed')
 coord=(source/'gfx-coordinate-owner.h').read_text()
 a=coord.index('#if !defined(GFX_NATIVE_COORDINATED_SCOPE_TRIAL)');b=coord.index('#include <linux/of_address.h>',a)
 coord=coord[:a]+'''#if !defined(GFX_NATIVE_COORDINATED_SCOPE_TRIAL) || !defined(GFX_NATIVE_STATUS_ZERO_TRIAL) || !defined(GFX_COLD_RENDER_TRIAL)
#error Cold native STATUS0 coordination requires its distinct profile
#endif

'''+coord[b:]
 coord=coord[:coord.index('/* This is called with the existing OFF terminal gate')]
 coord=coord.replace('gfx_ap_repeat_current_epoch','gfx_cold_current_epoch').replace('gfx_poweroff_snapshot','gfx_cold_snapshot')
 changed={'Makefile':'''obj-m += asc-graph-init.o
ccflags-y += -DGRAPH_JOINED_INIT_EXPERIMENT -DGRAPH_RECOVERY_EXPERIMENT
ccflags-y += -DGFX_NATIVE_COORDINATED_SCOPE_TRIAL -DGFX_NATIVE_STATUS_ZERO_TRIAL
ccflags-y += -DGFX_COLD_RENDER_TRIAL
''','asc-graph-init.c':owner_source(source),'gfx-coordinate-owner.h':coord,'recovery-cycle.h':(HERE/'recovery-cycle.h').read_text()}
 for name in ['graph-receipt.json','preparation.json']:
  d=json.loads((source/name).read_text())
  if name=='graph-receipt.json':
   d['recovery_trial'].update(cycles=0,final_control_count=33,work_submitted=False,qualification='Retained cold transport/layout only. No class86, recovery phase writes or recovery cycle admission in the cold-render owner.')
   d['control_refresh']['extra_staged_record']=dict(index=32,arena_offset='0xb8800',bytes=64,opcode=22,sha256='9bafe1e1bba60370394a65ea3482db84eae9080636a6ca2a54b5fe69c5440fb0',host_producer_before=32,host_producer_after=33)
  else:d['qualification']='Distinct cold one-draw experiment; original authored render/job bytes and native initialization preserved. No live GPU execution, rendering, completion, DMA retirement or unload established.'
  d['cold_render_trial']=dict(version=13,startup_recovery_cycles=0,fresh_control_count=33,maximum_control_notifications=1,maximum_draw_notifications=1,automatic_submission=True,observation_ms=15000,trace_mask_before=3,trace_mask_after=0,retained_pages=174,pm_put_after_draw=False,off_after_draw=False)
  changed[name]=json.dumps(d,indent=2)+'\n'
 copied={n:pin for n,pin in before.items() if n not in REMOVED}
 destination.mkdir(parents=True)
 for n in copied:(destination/n).write_bytes((source/n).read_bytes())
 for n,data in changed.items():(destination/n).write_text(data)
 for n in ADDED:(destination/n).write_bytes((HERE/n).read_bytes())
 after={n:sha(destination/n) for n in copied};actual=sorted(n for n in copied if after[n]!=copied[n])
 if actual!=CHANGED:raise ValueError('Unexpected frozen-source delta '+repr(actual))
 after.update({n:sha(destination/n) for n in ADDED})
 for n,pin in before.items():
  if sha(source/n)!=pin:raise ValueError('Frozen source changed during preparation '+n)
 profile=dict(family='gfx_cold_render_scope',version=13,compile_macro='GFX_COLD_RENDER_TRIAL',
  typed_commands=['sample','gfx-snapshot'],automatic_startup=True,management_only=False,
  retained_pages=174,startup_recovery_cycles=0,recovery_phase_writes=0,maximum_cold_ap20_requests=1,
  maximum_control_notifications=1,maximum_draw_notifications=1,fresh_control_before=32,fresh_control_after=33,
  trace_mask_before=3,trace_mask_after=0,control_opcode=22,control_record_index=32,
  observation_ms=15000,observation_poll_max=15001,control_timeout_ms=5000,control_poll_max=5001,
  original_identity_capture_only=True,automatic_draw_once=True,preserved_ta_3d_recipe=True,
  outstanding_work_backing_retained=True,pm_reference_retained_after_draw=True,pm_put_after_draw=False,
  off_after_draw=False,asc_stop_after_draw=False,unload_allowed=False,warm_restart_allowed=False,
  firmware_cursor_reset_allowed=False,unknown_seals_mutations=True,diagnostics_after_stop_cached=True,
  delayed_worker_scheduled=False,synchronous_rx_during_pipeline=True,receive_journal_stopped_on_return=True,
  no_hardware_fetch_or_software_power38_admission_gate=True,
  sample_indices=[0,1,2,3,4,5],post_submit_sample_offsets_ms=[0,100,1000,5000,15000],
  sample_fields=['sample_index','elapsed_ms','sample_jiffies','operand_samples_atomic'],
  log_prefix='m4rch gfx-cold-render:',terminal_phase='retained-final',
  gpu_execution_verified=False,rendering_verified=False,retirement_verified=False)
 receipt=dict(schema='m4rch.gfx-cold-render-owner-source.v1',source=str(source),destination=str(destination),source_path=str(source),
  baseline_source_receipt={'path':str(old_path),'sha256':BASE_RECEIPT_SHA},
  design={'path':str(design),'sha256':DESIGN_SHA},source_preparer={'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
  input_source_pins=[{'name':n,'sha256':pin} for n,pin in before.items()],
  output_source_pins=[{'name':n,'sha256':pin} for n,pin in after.items()],
  changed_files=CHANGED,added_files=ADDED,removed_files=REMOVED,profile=profile,
  hardware_actions=[],build_actions=[],qualification='Source preparation only. Separate automatic cold control33 and one TA/3D draw; no recovery/terminal powergate path, no delayed worker, bounded synchronous raw diagnostics, all owned resources and PM retained.')
 with (destination/'cold-render-owner-source-receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 return receipt

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();r=prepare(a.source,a.destination)
 print(json.dumps({'receipt':str(a.destination/'cold-render-owner-source-receipt.json'),'changed_files':r['changed_files'],'added_files':r['added_files'],'hardware_actions':[]}))
