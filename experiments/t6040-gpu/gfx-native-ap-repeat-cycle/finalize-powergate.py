#!/usr/bin/env python3
"""Bind a new built AP-retained owner, portable qualifications and frozen inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from gfx_native_ap_repeat_cycle_contract import CONTRACT,FAMILY_KEY,validate_receipt
from gfx_reset_contract import require
BASE=ROOT/'out/gfx-native-ap-retained-cycle/candidate'
FROZEN=ROOT/'out/gfx-native-ap-retained-cycle/prepared-owner-v2'
BASE_RECEIPT_SHA='a8a24d16dc8ea0f6836b7a03697c55a4a60954de01bc663c756a49574bb4efb9'
BASE_PREPARATION_SHA='89cb8e11c4ffeaa3865410d5a8550659bf340f986d6b626a354b1aeb83d67b9b'
FROZEN_SOURCE_RECEIPT_SHA='f8cc352fce19be8a959fdd6c4a386360cbea746934d5cfa09defa09222faf9d1'
FROZEN_C_QUALIFICATION_SHA='aa875ccdecb07b2944dee2066a53d955b613582929e6e232581dd4b4b096d334'
FROZEN_WRAPPER_QUALIFICATION_SHA='44a869162bbe382302b5f7dc78a77c084a9e90d4da1ff98051a072cf376c1686'
CHANGED=['Makefile','asc-graph-init.c','gfx-coordinate-owner.h','gfx-native-powergate-drain.h','gfx-reset-scope.h','recovery-cycle.h']
HEADERS=['gfx-native-ap-repeat-cycle.h','gfx-ap-repeat-cycle-coordinate.h']
REMOVED=['gfx-native-ap-retained-cycle.h','gfx-retained-power-cycle-coordinate.h']
SOURCE_RECEIPT='native-ap-repeat-cycle-owner-source-receipt.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pin(path):return {'path':str(path.resolve()),'sha256':sha(path),'bytes':path.stat().st_size}
def check_qualification(path):
 q=json.loads(path.read_text())
 require(q.get('passed') is True and q.get('hardware_access') is False and
  type(q.get('case_count')) is int and q['case_count']>0,'Missing actual offline qualification')
 rows=q.get('inputs',q.get('files',q.get('input_pins',[])));require(bool(rows),'Qualification has no source binding')
 for row in rows:
  p=Path(row['path']);p=p if p.is_absolute() else ROOT/p
  require(sha(p)==row['sha256'],'Qualification input changed: '+str(p))
 return q

def check_source_profile(source):
 require(source.get('schema')=='m4rch.gfx-native-ap-repeat-cycle-owner-source.v1' and
  source.get('hardware_actions')==[] and source.get('build_actions')==[] and
  source.get('changed_files')==CHANGED and source.get('changed_frozen_retained_files')==CHANGED and
  source.get('added_files')==HEADERS and source.get('removed_files')==REMOVED,
  'Unexpected AP-repeat source transformation')
 profile=source['profile']
 baseline=FROZEN/'native-ap-retained-cycle-owner-source-receipt.json'
 require(sha(baseline)==FROZEN_SOURCE_RECEIPT_SHA,'Frozen v11 source profile changed')
 expected=copy.deepcopy(json.loads(baseline.read_text())['profile'])
 expected.update(PROFILE_DELTA)
 require(profile==expected,'Unknown, missing or changed AP-repeat source policy')
 return True

PROFILE_DELTA={
 'compile_macro':'GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL','version':12,
 'typed_commands':CONTRACT['commands'],
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
 'transport_operands_cached_with_last_four_operand_guard_jiffies_and_nonatomic_label':True,
 'cold_ap_log_prefix':'m4rch gfx-native-ap-repeat-cold:',
 'second_log_row_prefixes':['m4rch gfx-native-ap-repeat-cycle'+s+':' for s in ('','-state','-transport','-management','-off','-on')],
 'third_log_row_prefixes':['m4rch gfx-native-ap-repeat-third'+s+':' for s in ('','-state','-transport','-management','-off','-on')],
 'third_log_row_count':6,'third_epoch':3,'second_epoch':2,
 'retained_coordinate_log_prefix':'m4rch gfx-native-ap-repeat-coordinate:',
 'third_physical_off_phase':'repeat-third-after-third-off',
 'runtime_pm_callback_wallclock_bound_claimed':False,
 'first_native_primary_and_progress_rows_bounded':True,
 'first_native_progress_log_prefix':'m4rch gfx-native-powergate-drain-progress:',
}

def check_owner_qualification(owner,source,source_path):
 maximum=owner.get('maximum_new_log_row_bytes')
 flags=('ASan_UBSan','actual_headers','actual_complete_E1_E2_E3_flow',
  'actual_first_powergate_and_scope_off','actual_second_and_third_coordinate_core',
  'actual_receive_worker','actual_cold_power_ack','actual_cold_root_publication_condition',
  'exact_second_state_byte_immutability_during_third','global_unknown_and_no_fourth_controls_exercised',
  'both_retained_own_low1_or_low2_ACK_exercised','post_put_faults_bound_to_own_epoch_put',
  'actual_complete_six_row_groups')
 require(owner.get('schema')=='m4rch.gfx-native-ap-repeat-cycle-c-qualification.v1' and
  all(owner.get(k) is True for k in flags) and
  owner.get('second_log_row_count')==6 and owner.get('third_log_row_count')==6 and
  type(maximum) is int and 1<=maximum<=511 and
  Path(owner.get('source_path','')).resolve()==Path(source['destination']).resolve() and
  owner.get('source_receipt_sha256')==sha(source_path),'Actual AP retained C qualification missing')
 rows=owner.get('successful_epoch_log_pins')
 require(isinstance(rows,list) and sorted(r.get('epoch') for r in rows)==[1,2,3],
  'Actual C-emitted retained epoch log binding missing')
 from gfx_native_ap_repeat_cycle_contract import qualify_retained_off_logs,qualify_first_off_logs
 for row in rows:
  path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
  require(sha(path)==row['sha256'] and path.stat().st_size==row['bytes'],
   'Actual retained epoch log changed')
  require(all(len(line.encode())+1<=511 for line in path.read_text().splitlines()),
   'Actual retained epoch row exceeds printk bound')
  if row['epoch']==1:qualify_first_off_logs(path.read_text())
  else:qualify_retained_off_logs(path.read_text(),row['epoch'])
 return True

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('candidate',type=Path);parser.add_argument('owner_qualification',type=Path)
 parser.add_argument('--wrapper-qualification',type=Path,required=True)
 args=parser.parse_args();candidate=args.candidate.resolve();graph=candidate/'asc-graph-init'
 require(candidate==ROOT/'out/gfx-native-ap-repeat-cycle/candidate','Distinct selected candidate required')
 bpath=BASE/'asc-root-envelope/build-receipt.json';bprep=BASE/'native-ap-retained-cycle-preparation.json'
 require(sha(bpath)==BASE_RECEIPT_SHA and sha(bprep)==BASE_PREPARATION_SHA,'Frozen baseline changed')
 old=json.loads(bpath.read_text())
 for name,expected in old['artifact_sha256'].items():
  require(sha(BASE/name)==expected,'Frozen artifact changed')
  if name!='asc-graph-init/asc-graph-init.ko':require(sha(candidate/name)==expected,'Non-owner artifact changed')
 for name,expected in old['graph_source_sha256'].items():
  require(sha(BASE/'asc-graph-init'/name)==expected,'Frozen owner source changed')
  if name not in CHANGED+REMOVED:require(sha(graph/name)==expected,'Unplanned owner source change')
 frozen_receipt=FROZEN/'native-ap-retained-cycle-owner-source-receipt.json'
 require(sha(frozen_receipt)==FROZEN_SOURCE_RECEIPT_SHA,'Frozen selected source receipt changed')
 source_path=graph/SOURCE_RECEIPT;source=json.loads(source_path.read_text());check_source_profile(source)
 require(Path(source['source_path']).resolve()==FROZEN.resolve(),'Unexpected frozen source')
 baseline=source['baseline_source_receipt']
 require(Path(baseline['path']).resolve()==frozen_receipt.resolve() and baseline['sha256']==FROZEN_SOURCE_RECEIPT_SHA,'Source baseline differs')
 require(sha(Path(source['source_preparer']['path']))==source['source_preparer']['sha256'],'Preparer changed')
 for row in source['input_source_pins']:
  require('/' not in row['name'] and sha(FROZEN/row['name'])==row['sha256'],'Frozen source input changed')
 for row in source['output_source_pins']:
  require('/' not in row['name'] and sha(graph/row['name'])==row['sha256'],'Prepared source changed')
 for header in HEADERS:require(sha(graph/header)==sha(HERE/header),'Selected header differs')
 require(all(not (graph/name).exists() for name in REMOVED),'Old HOST header selected')
 for name,key in [('graph-before.bin','graph_fixture_sha256'),('graph-receipt.json','graph_receipt_sha256')]:
  require(sha(graph/name)==old[key],'Dormant graph fixture changed')
 require(sha(graph/'backing.bin')=='35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3','Immutable backing changed')
 wrapper_path=args.wrapper_qualification.resolve()
 require(wrapper_path.parent==ROOT/'out/gfx-native-ap-repeat-cycle' and
  wrapper_path.name.startswith('wrapper-qualification-v') and wrapper_path.suffix=='.json',
  'Distinct versioned wrapper qualification required')
 wrapper=check_qualification(wrapper_path)
 require(wrapper['schema']=='m4rch.gfx-native-ap-repeat-cycle-wrapper-qualification.v1' and
  all(wrapper.get(k) is True for k in ('cold_ap_startup_proof_exercised',
   'actual_c_emitted_second_and_third_logs_qualified','actual_third_main_predecessor_raw_pins_exercised',
   'actual_earliest_refused_boot_guard_exercised')),'Wrong or incomplete wrapper qualification')
 owner=check_qualification(args.owner_qualification);check_owner_qualification(owner,source,source_path)
 owner_rows=owner.get('inputs',owner.get('files',owner.get('input_pins',[])))
 bound_paths={str((Path(r['path']) if Path(r['path']).is_absolute() else ROOT/r['path']).resolve()) for r in owner_rows}
 require({str((graph/n).resolve()) for n in HEADERS}<=bound_paths or
  {str((Path(source['destination'])/n).resolve()) for n in HEADERS}<=bound_paths,
  'Actual prepared C headers unbound')
 # The preparer itself is pinned by the source receipt and final preparation.
 require([r['sha256'] for r in owner_rows if Path(r['path']).name==SOURCE_RECEIPT]==[sha(source_path)],'Qualified dispatcher differs')
 frozen_c=ROOT/'out/gfx-native-ap-retained-cycle/owner-qualification-v2.json'
 frozen_wrapper=ROOT/'out/gfx-native-ap-retained-cycle/wrapper-qualification-v1.json'
 require(sha(frozen_c)==FROZEN_C_QUALIFICATION_SHA and sha(frozen_wrapper)==FROZEN_WRAPPER_QUALIFICATION_SHA,'Frozen qualifications changed')
 cq=check_qualification(frozen_c);pq=check_qualification(frozen_wrapper)
 require(cq['case_count']==122 and pq['case_count']==137,'Frozen composition differs')
 make=(graph/'Makefile').read_text()
 require(all('-D'+flag in make for flag in ('GFX_NATIVE_AP_REPEAT_CYCLE_TRIAL','GFX_NATIVE_POWERGATE_DRAIN_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL')) and
  all(flag not in make for flag in ('GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','GFX_NATIVE_RUNNING_CYCLE_TRIAL','GFX_NATIVE_IDLE_CYCLE_TRIAL','GFX_NATIVE_RETAINED_CYCLE_TRIAL','GFX_RETAINED_POWER_CYCLE_TRIAL','GFX_COORDINATED_EXECUTION_TRIAL','GFX_RESET_NATIVE_SEQUENCE_TRIAL')),'Unexpected compiled profile')
 log=ROOT/'out/gfx-native-ap-repeat-cycle/owner-build.log'
 require('warning:' not in log.read_text() and 'error:' not in log.read_text(),'Build diagnostics require review')
 module=graph/'asc-graph-init.ko'
 vermagic=subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()
 require(vermagic.startswith(old['kernel_release']+' '),'Owner vermagic differs')
 imports=subprocess.check_output(['llvm-nm','-u',str(module)],text=True)
 require(all(n in imports for n in ('apple_pmgr_t6040_gfx_snapshot','__pm_runtime_resume','__pm_runtime_suspend','of_find_all_nodes')) and
  all(n not in imports for n in ('apple_pmgr_t6040_gfx_native_probe','apple_pmgr_t6040_gfx_checked_pulse')),'Unexpected imports')
 receipt=copy.deepcopy(old);receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(module)
 for name in REMOVED:receipt['graph_source_sha256'].pop(name)
 for name in receipt['graph_source_sha256']:receipt['graph_source_sha256'][name]=sha(graph/name)
 for header in HEADERS:receipt['graph_source_sha256'][header]=sha(graph/header)
 trial=receipt['graph_recovery_trial'];trial.pop('gfx_native_ap_retained_cycle_scope');trial[FAMILY_KEY]=CONTRACT
 require(validate_receipt(receipt),'Final AP-retained receipt invalid')
 output=candidate/'asc-root-envelope/build-receipt.json';prep_path=candidate/'native-ap-repeat-cycle-preparation.json'
 require(not output.exists() and not prep_path.exists(),'Finalization never overwrites a candidate')
 basis=[ROOT/'docs/evidence/2026-10-10-gfx-native-ap-retained-cycle-repeatability-plan.json',
  ROOT/'docs/evidence/2026-10-10-gfx-native-ap-retained-cycle-live-outcome.json',
  ROOT/'docs/evidence/2026-10-10-gfx-native-ap-retained-cycle-live-native-boundary.json']
 for p,want in zip(basis,('a421ff9b9d92d21dc34cf49ae924b312d0fc62fb1f2759a28a6da30f6d039901',
  'c113b50b63b187b995a3a4226ba796c0cd7c2bbde586aba03a11d6a71c9b3f9b',
  '13f0e18aa8903c6ebbd6ea2fdd92c1b540265b79954dc5b128b814ea0370e024')):
  require(sha(p)==want,'Pinned repeatability/native basis changed')

 files=[bpath,bprep,source_path,args.owner_qualification,wrapper_path,frozen_c,frozen_wrapper,log,Path(__file__),*basis]+[HERE/n for n in
  ['ap_repeat_cycle_wrapper.py','gfx_native_ap_repeat_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','prepare-native-ap-repeat-cycle-owner.py',*HEADERS]]
 analysis=json.loads(bprep.read_text())['analysis_input_pins']
 for row in analysis:require(sha(candidate/row['relative'])==row['sha256'],'Dormant analysis metadata changed')
 prep={'schema':'m4rch.gfx-native-ap-repeat-cycle-preparation.v1','baseline_candidate':str(BASE),
  'baseline_receipt_sha256':BASE_RECEIPT_SHA,'candidate':str(candidate),'owner_sha256':sha(module),'vermagic':vermagic,
  'inputs':[pin(p) for p in files],'actual_module_imports':imports.splitlines(),'analysis_input_pins':analysis,
  'artifact_count':len(receipt['artifact_sha256']),'owner_source_count':len(receipt['graph_source_sha256']),
  'changed_source_files':CHANGED,'added_source_files':HEADERS,'removed_source_files':REMOVED,
  'qualification_composition':{'new_c_cases':owner['case_count'],'new_wrapper_cases':wrapper['case_count'],
   'frozen_v11_c_cases':122,'frozen_v11_wrapper_cases':137,'original_cases_repeated_by_finalizer':False},
  'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
  'selected_next_hardware_candidate':True,'hardware_preconditions_pending':True,'recovery_teardown_rendering_verified':False,
  'commands':CONTRACT['commands'],'refused_boots':list(__import__('gfx_native_ap_repeat_cycle_contract').REFUSED_BOOTS),
  'qualification':'One exact cold owned HOST B20 reply is carried through E1/E2/E3 management-only epochs. Each retained epoch owns a separate durable intent, PM reference, coordinator, protocol journal and captured proof. E3 rebuilds immutable E1 and exact E2 seven-input proof from its own operation delta before write; every uncertain/lost/mixed/duplicate history seals controls. Retained AP20 skips HOST ON without a new reply; each own202 uses low1/2 ACK, checked stop, paired OFF, PMput and strict physical OFF/accounting. No E4, B201/B0/INIT220/application/root/context/work/release. Hardware repeatability, application rejoin and retirement unverified.'}
 with output.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 prep['candidate_receipt_sha256']=sha(output)
 with prep_path.open('x') as f:json.dump(prep,f,indent=2);f.write('\n')
 print(json.dumps({'preparation':str(prep_path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))
if __name__=='__main__':main()
