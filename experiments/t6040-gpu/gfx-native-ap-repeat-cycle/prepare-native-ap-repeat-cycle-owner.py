#!/usr/bin/env python3
"""Prepare a distinct bounded E1/E2/E3 retained management owner; never build/load."""
import argparse
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_RECEIPT_SHA='f8cc352fce19be8a959fdd6c4a386360cbea746934d5cfa09defa09222faf9d1'
CHANGED=['Makefile','asc-graph-init.c','gfx-coordinate-owner.h','gfx-native-powergate-drain.h','gfx-reset-scope.h','recovery-cycle.h']
ADDED=['gfx-native-ap-repeat-cycle.h','gfx-ap-repeat-cycle-coordinate.h']
REMOVED=['gfx-native-ap-retained-cycle.h','gfx-retained-power-cycle-coordinate.h']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def once(text,old,new):
 if text.count(old)!=1:raise ValueError('Frozen insertion changed: '+repr(old[:100]))
 return text.replace(old,new,1)
def epoch_logs(text,prefixes):
 import re
 for prefix in prefixes:
  # Keep existing fields and behavior; add the currently owned epoch to the record.
  pattern=r'((?:pr_info|pr_err)\("m4rch '+re.escape(prefix)+r': )([^"\n]*\\n",\n)(\s*)'
  text,n=re.subn(pattern,lambda m:m[1]+'epoch=%u '+m[2]+m[3]+'gfx_ap_repeat_current_epoch,',text)
  if not n:raise ValueError('Missing epoch log '+prefix)
 return text

def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:raise ValueError('Destination must be new outside frozen source')
 old_path=source/'native-ap-retained-cycle-owner-source-receipt.json'
 if sha(old_path)!=BASE_RECEIPT_SHA:raise ValueError('Frozen v11 receipt changed')
 old=json.loads(old_path.read_text());before={r['name']:r['sha256'] for r in old['output_source_pins']}
 for n,p in before.items():
  if sha(source/n)!=p:raise ValueError('Frozen v11 source changed '+n)
 before[old_path.name]=sha(old_path);copied={n:p for n,p in before.items() if n not in REMOVED}
 make=once((source/'Makefile').read_text(),'-DGFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','-DGFX_NATIVE_AP_REPEAT_CYCLE_TRIAL')
 owner=(source/'asc-graph-init.c').read_text().replace('GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL')
 owner=once(owner,'#ifdef GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL\nstatic bool gfx_ap_cold_request_attempted','static unsigned int gfx_ap_repeat_current_epoch=1;\nstatic bool gfx_ap_repeat_unknown;\n#ifdef GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL\nstatic bool gfx_ap_cold_request_attempted')
 owner=once(owner,'#include "gfx-retained-power-cycle-coordinate.h"','#include "gfx-ap-repeat-cycle-coordinate.h"')
 owner=once(owner,'m4rch gfx-native-ap-retained-cycle-session:','m4rch gfx-native-ap-repeat-cycle-session:')
 owner=once(owner,'m4rch gfx-native-ap-repeat-cycle-session: ready=1','m4rch gfx-native-ap-repeat-cycle-session: epoch=1 ready=1')
 owner=once(owner,'native retained AP ON skip PWRGATE transport management no-work coordinator','bounded two retained AP ON skip PWRGATE management epochs no-work coordinator')
 dispatcher=(source/'recovery-cycle.h').read_text()
 dispatcher=once(dispatcher,'static bool gfx_retained_cycle_intent;','static bool gfx_retained_cycle_intent, gfx_ap_repeat_third_intent;')
 dispatcher=dispatcher.replace('!gfx_retained_cycle_intent','!gfx_retained_cycle_intent && !gfx_ap_repeat_third_intent && !gfx_ap_repeat_unknown')
 dispatcher=once(dispatcher,'#include "gfx-native-ap-retained-cycle.h"','#include "gfx-native-ap-repeat-cycle.h"')
 reset=epoch_logs((source/'gfx-reset-scope.h').read_text(),['gfx-poweroff-pm','gfx-poweroff-dram','gfx-poweroff-asc','gfx-poweroff-result','gfx-poweroff-snapshot','gfx-poweroff-word','gfx-poweroff-stop'])
 native=(source/'gfx-native-powergate-drain.h').read_text()
 import re
 native=re.sub(r'(m4rch gfx-native-powergate-drain(?:-admission|-rx|-startup-retained)?:) ',r'\1 epoch=1 ',native)
 # Bound the inherited E1 row as well: move progress counters to a complete
 # second row, leaving every first-OFF admission field in the primary record.
 native=once(native,' initial_recovery_failed=%u initial_completed_cycles=%u','')
 native=once(native,' ack_polls=%u rx_messages=%u','')
 native=once(native,' idle_polls=%u','')
 native=once(native,' control_before=%#x','')
 native=once(native,'  phase,result,gfx_native_powergate_intent,gfx_native_powergate_initial_recovery_failed,\n  recovery_completed_total,gfx_native_powergate_request_attempted,','  phase,result,gfx_native_powergate_intent,gfx_native_powergate_request_attempted,')
 native=once(native,'  (unsigned long long)gfx_native_powergate_ack_metadata,gfx_native_powergate_ack_polls,\n  gfx_native_powergate_rx_messages,gfx_native_powergate_rx_empty_after_ack,','  (unsigned long long)gfx_native_powergate_ack_metadata,gfx_native_powergate_rx_empty_after_ack,')
 native=once(native,'  gfx_native_powergate_idle_polls,gfx_native_powergate_idle_status,','  gfx_native_powergate_idle_status,')
 native=once(native,'  gfx_native_powergate_clear10_attempted,gfx_native_powergate_control_before,','  gfx_native_powergate_clear10_attempted,')
 native=once(native,'  gfx_native_powergate_off_delegated,held,GFX_RESET_SCOPE_PAGES);','  gfx_native_powergate_off_delegated,held,GFX_RESET_SCOPE_PAGES);\n pr_info("m4rch gfx-native-powergate-drain-progress: epoch=1 phase=%s initial_recovery_failed=%u initial_completed_cycles=%u ack_polls=%u rx_messages=%u idle_polls=%u control_before=%#x\\n",\n  phase,gfx_native_powergate_initial_recovery_failed,recovery_completed_total,\n  gfx_native_powergate_ack_polls,gfx_native_powergate_rx_messages,\n  gfx_native_powergate_idle_polls,gfx_native_powergate_control_before);')
 coord=epoch_logs((source/'gfx-coordinate-owner.h').read_text(),['gfx-coordinate-resource','gfx-coordinate-event','gfx-coordinate-observation','gfx-coordinate-owner'])
 destination.mkdir(parents=True)
 for n in copied:(destination/n).write_bytes((source/n).read_bytes())
 for n,data in [('Makefile',make),('asc-graph-init.c',owner),('recovery-cycle.h',dispatcher),('gfx-reset-scope.h',reset),('gfx-coordinate-owner.h',coord),('gfx-native-powergate-drain.h',native)]: (destination/n).write_text(data)
 for n in ADDED:(destination/n).write_bytes((HERE/n).read_bytes())
 after={n:sha(destination/n) for n in copied}
 changed=sorted(n for n in copied if after[n]!=copied[n])
 if changed!=CHANGED:raise ValueError('Unexpected baseline delta '+repr(changed))
 after.update({n:sha(destination/n) for n in ADDED})
 for n,p in before.items():
  if sha(source/n)!=p:raise ValueError('Frozen input changed during preparation '+n)
 profile=dict(old['profile'])
 profile.update({'compile_macro':'GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL','version':12,
  'typed_commands':['sample','gfx-snapshot','gfx-powergate','gfx-native-ap-repeat-cycle','gfx-native-ap-repeat-third'],
  'maximum_retained_cycle_intents':2,'maximum_retained_cycle_starts':2,'maximum_retained_cycle_pm_gets':2,
  'maximum_retained_cycle_pm_puts':2,'maximum_retained_cycle_requests':2,'maximum_total_pm_puts':3,'maximum_total_powergate_requests':3,
  'maximum_per_retained_epoch_intents':1,'maximum_per_retained_epoch_starts':1,'maximum_per_retained_epoch_pm_gets':1,
  'maximum_per_retained_epoch_pm_puts':1,'maximum_per_retained_epoch_requests':1,
  'second_intent_seals_all_controls':False,'second_success_admits_only_third_control':True,'third_intent_seals_all_controls':True,
  'all_negative_controls_including_duplicates_seal_remaining_controls':True,'unknown_allows_only_safe_diagnostics':True,
  'original_first_epoch_identity_capture_only':True,'first_and_second_epoch_evidence_immutable_through_third':True,
  'third_separate_state_coordinator_reference_journal_deadlines_intent':True,
  'third_requires_second_terminal_result_zero_and_refusal_none':True,
  'third_requires_second_own_ack_journal_checked_cpu_stop_paired_off_put_strict_physical_off_accounting':True,
  'third_requires_fresh_current_off_accounting_original_identity_and_cold_ap20':True,
  'third_host_on_requests_maximum':0,'third_host_on_fallback_forbidden':True,
  'application_rollcall_reply_bitmap':0,'management_only':True,'fourth_epoch_admitted':False,
  'explicit_epoch_on_state_rx_tx_coordinate_pmgr':True,
  'first_native_primary_and_progress_rows_bounded':True,'first_native_progress_log_prefix':'m4rch gfx-native-powergate-drain-progress:',
  'transport_operands_cached_with_last_four_operand_guard_jiffies_and_nonatomic_label':True,
  'cold_ap_log_prefix':'m4rch gfx-native-ap-repeat-cold:',
  'second_log_row_prefixes':['m4rch gfx-native-ap-repeat-cycle'+x+':' for x in ['','-state','-transport','-management','-off','-on']],
  'third_log_row_prefixes':['m4rch gfx-native-ap-repeat-third'+x+':' for x in ['','-state','-transport','-management','-off','-on']],
  'third_log_row_count':6,'third_epoch':3,'second_epoch':2,
  'retained_coordinate_log_prefix':'m4rch gfx-native-ap-repeat-coordinate:',
  'third_physical_off_phase':'repeat-third-after-third-off',
  'runtime_pm_callback_wallclock_bound_claimed':False,
 })
 receipt={'schema':'m4rch.gfx-native-ap-repeat-cycle-owner-source.v1','source':str(source),'destination':str(destination),'source_path':str(source),
  'baseline_source_receipt':{'path':str(old_path),'sha256':BASE_RECEIPT_SHA},'frozen_retained_receipt':{'path':str(old_path),'sha256':BASE_RECEIPT_SHA},
  'source_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
  'input_source_pins':[{'name':n,'sha256':p} for n,p in before.items()],
  'output_source_pins':[{'name':n,'sha256':p} for n,p in after.items()],
  'added_files':ADDED,'removed_files':REMOVED,'changed_files':CHANGED,'changed_frozen_retained_files':changed,
  'profile':profile,'hardware_actions':[],'build_actions':[],
  'qualification':'Source preparation only. E2 preserves v11 protocol with explicit epoch logs and negative-result seal. E3 has separate fixed state and requires clean E2 own ACK/checked stop/paired OFF/oneput/strict OFF/accounting plus original E1 identities. Neither retained epoch sends B20 or enables applications; no E4, DMA retirement, rendering or unload claim.'}
 with (destination/'native-ap-repeat-cycle-owner-source-receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();r=prepare(a.source,a.destination)
 print(json.dumps({'receipt':str(a.destination/'native-ap-repeat-cycle-owner-source-receipt.json'),'changed_files':r['changed_files'],'added_files':r['added_files'],'hardware_actions':[]}))
