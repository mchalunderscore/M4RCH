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
from gfx_native_ap_retained_cycle_contract import CONTRACT,FAMILY_KEY,validate_receipt
from gfx_reset_contract import require
BASE=ROOT/'out/gfx-native-running-cycle/candidate'
FROZEN=ROOT/'out/gfx-native-running-cycle/prepared-owner-v2'
BASE_RECEIPT_SHA='32b2ff0c647eae38a4f74486dc4f85793fdbfe478d60ab96555eb290d4564c65'
BASE_PREPARATION_SHA='a2237389fa172c4f319c482df7ab9b58bbd551339ce690c8789ab2ae90a83303'
FROZEN_SOURCE_RECEIPT_SHA='d5ed3909257d659816e2c23cebe43f72308aa0677efa3660b5e76758b56ee36d'
FROZEN_C_QUALIFICATION_SHA='aaf2e76d651fbff245b169a500468b507a105cdbdb1d991b9469ea6c240fd50a'
FROZEN_WRAPPER_QUALIFICATION_SHA='bc0a8396c901708854a9036573e54ed52d72d6e21490933170078e3276716d60'
CHANGED=['Makefile','asc-graph-init.c','recovery-cycle.h']
HEADERS=['gfx-native-ap-retained-cycle.h']
REMOVED=['gfx-native-running-cycle.h']
SOURCE_RECEIPT='native-ap-retained-cycle-owner-source-receipt.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pin(path):return {'path':str(path.resolve()),'sha256':sha(path),'bytes':path.stat().st_size}
def check_qualification(path):
 q=json.loads(path.read_text())
 require(q.get('passed') is True and q.get('hardware_access') is False and
  type(q.get('case_count')) is int and q['case_count']>0,'Missing actual offline qualification')
 rows=q.get('inputs',q.get('files',[]));require(bool(rows),'Qualification has no source binding')
 for row in rows:
  p=Path(row['path']);p=p if p.is_absolute() else ROOT/p
  require(sha(p)==row['sha256'],'Qualification input changed: '+str(p))
 return q

def check_source_profile(source):
 require(source.get('schema')=='m4rch.gfx-native-ap-retained-cycle-owner-source.v1' and
  source.get('hardware_actions')==[] and source.get('build_actions')==[] and
  source.get('changed_files')==CHANGED and source.get('changed_frozen_retained_files')==CHANGED and
  source.get('added_files')==HEADERS and source.get('removed_files')==REMOVED,
  'Unexpected AP-retained source transformation')
 profile=source['profile']
 expected={
  'version':11,'compile_macro':'GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL',
  'typed_commands':CONTRACT['commands'],'work_publication_admitted':False,
  'maximum_retained_cycle_intents':1,'maximum_retained_cycle_starts':1,
  'maximum_retained_cycle_pm_gets':1,'maximum_retained_cycle_pm_puts':1,
  'maximum_retained_cycle_requests':1,'maximum_total_pm_puts':2,
  'maximum_total_powergate_requests':2,'maximum_protocol_records':16,
  'maximum_protocol_polls':4001,'nominal_protocol_timeout_ms':4000,
  'pre_on_known_statuses':['0x6a','0x6c'],'post_on_known_statuses':['0x6a','0x6c','0x6d'],
  'status6d_requires_second_on_complete_and_second_ref':True,'pre_on_status6d_refused':True,
  'stage_specific_start_admission':True,'reentry_four_operands_before_and_after_second_paired_on':True,
  'reentry_four_operands_after_start_intent_log':True,'immediate_start_fresh_ctrl_rmw':True,
  'maximum_log_row_bytes':511,'complete_newline_structured_state_rows':True,'second_log_row_count':6,
  'second_log_row_prefixes':['m4rch gfx-native-ap-retained-cycle:',
   'm4rch gfx-native-ap-retained-cycle-state:','m4rch gfx-native-ap-retained-cycle-transport:',
   'm4rch gfx-native-ap-retained-cycle-management:','m4rch gfx-native-ap-retained-cycle-off:',
   'm4rch gfx-native-ap-retained-cycle-on:'],
  'exact_boot_running_message':'0x0070000000000020',
  'boot_running_required_after_exact_final_map_ack':True,
  'power20_never_shutdown_ack':True,'owned_page_pointer_and_pa_identity_required':174,
  'first_strict_physical_off_required_before_pm_get':True,'first_epoch_evidence_immutable':True,
  'host_protocol_journal_separate':True,'fresh_rx_empty_required_before_start_and_second_request':True,
  'no_init220_request':True,'no_application_start':True,'no_application_root_publication':True,
  'no_context_reattach':True,'no_firmware_data_restore':True,'no_queue_or_counter_reset':True,
  'application_rejoin_verified':False,'second_intent_seals_all_controls':True,
 }
 require(all(profile.get(k)==v for k,v in expected.items()),'AP-retained source profile differs')
 # Cold ownership and retained skip fields are checked below, independently
 # from the native firmware state33 representation.
 retained={
  'cold_owned_ap_on_request':'0x00b0000000000020','cold_exact_ap_on_reply':'0x00b0000000000020',
  'cold_ap_state_wire':'0x20','maximum_cold_ap_polls':2001,'nominal_cold_ap_timeout_ms':2000,
  'cold_ap_on_exact_request_reply_required_before_root_publication':True,
  'cold_ap_on_fresh_rx_empty_tx_available_before_and_after_intent':True,
  'cold_ap_on_late_or_pending_reply_refused':True,'cold_ap_mirror_required_before_second_pm_get':True,
  'cold_ap_mirror_preserved_through_management_only_202':True,
  'retained_ap_unknown_state_refused':True,'second_host_on_requests_maximum':0,
  'second_host_on_fallback_forbidden':True,'retained_host_on_skip_intent_required':True,
  'retained_host_on_skip_requires_cold_exact_ap20_and_fresh_running':True,
  'retained_host_on_skip_fresh_gates_after_intent_log':True,
  'retained_host_on_skip_does_not_fabricate_fresh_reply':True,
  'second202_fresh_gates_after_intent_log':True,'retained_ap_skip_is_experimental_management_hypothesis':True,
  'second_ack_reserved_journal_slots':1,'no_ap_b201_or_b0':True,
  'cold_ap_log_prefix':'m4rch gfx-native-ap-retained-cold:','cold_ap_log_phases':['request','reply'],
 }
 require(all(profile.get(k)==v for k,v in retained.items()),'AP ownership or skip policy differs')
 forbidden=('host_on_reply_required_before_second_202','running_host_on_is_experimental_protocol_hypothesis',
  'host_on_fresh_four_operands_before_and_after_intent','fresh_pm_identity_cpu_fifo_required_after_host_reply_before_second_202',
  'maximum_host_on_polls','nominal_host_on_timeout_ms','host_on_fresh_four_operands_after_intent','host_on_reserved_reply_and_ack_capacity')
 require(not any(k in profile for k in forbidden),'Obsolete unconditional HOST policy remains')
 frozen_profile=json.loads((FROZEN/'native-running-cycle-owner-source-receipt.json').read_text())['profile']
 changed={'compile_macro','version','typed_commands','second_log_row_prefixes','second_powergate_admission'}
 for key,value in frozen_profile.items():
  if 'host_on' in key or 'host_reply' in key or key in changed:continue
  require(profile.get(key)==value,'Unchanged frozen source policy differs: '+key)
 expected_keys={key for key in frozen_profile if 'host_on' not in key and 'host_reply' not in key}|set(expected)|set(retained)
 require(set(profile)==expected_keys,'Unknown or missing AP retained source policy fields')
 return True

def check_owner_qualification(owner,source,source_path):
 maximum=owner.get('maximum_new_log_row_bytes')
 flags=('ASan_UBSan','actual_headers','actual_second_coordinate_core','actual_cold_power_ack',
  'actual_receive_worker','stage_specific_start_guards_exercised',
  'actual_observed_6c_to_paired_on_to_6d_sequence_simulated','actual_retained_ap20_skip_before202',
  'duplicate_B20_panics_in_firmware_model','actual_cold_root_publication_condition',
  'no_second_B20_path','post_skip_and_second202_intent_fresh_guards_exercised',
  'actual_complete_six_row_groups','new_log_rows_bounded')
 require(owner.get('schema')=='m4rch.gfx-native-ap-retained-cycle-c-qualification.v1' and
  all(owner.get(k) is True for k in flags) and owner.get('second_log_row_count')==6 and
  type(maximum) is int and 1<=maximum<=511 and
  Path(owner.get('source_path','')).resolve()==Path(source['destination']).resolve() and
  owner.get('source_receipt_sha256')==sha(source_path),'Actual AP retained C qualification missing')
 return True

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('candidate',type=Path);parser.add_argument('owner_qualification',type=Path)
 args=parser.parse_args();candidate=args.candidate.resolve();graph=candidate/'asc-graph-init'
 require(candidate==ROOT/'out/gfx-native-ap-retained-cycle/candidate','Distinct selected candidate required')
 bpath=BASE/'asc-root-envelope/build-receipt.json';bprep=BASE/'native-running-cycle-preparation.json'
 require(sha(bpath)==BASE_RECEIPT_SHA and sha(bprep)==BASE_PREPARATION_SHA,'Frozen baseline changed')
 old=json.loads(bpath.read_text())
 for name,expected in old['artifact_sha256'].items():
  require(sha(BASE/name)==expected,'Frozen artifact changed')
  if name!='asc-graph-init/asc-graph-init.ko':require(sha(candidate/name)==expected,'Non-owner artifact changed')
 for name,expected in old['graph_source_sha256'].items():
  require(sha(BASE/'asc-graph-init'/name)==expected,'Frozen owner source changed')
  if name not in CHANGED+REMOVED:require(sha(graph/name)==expected,'Unplanned owner source change')
 frozen_receipt=FROZEN/'native-running-cycle-owner-source-receipt.json'
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
 wrapper_path=ROOT/'out/gfx-native-ap-retained-cycle/wrapper-qualification-v1.json'
 wrapper=check_qualification(wrapper_path)
 require(wrapper['schema']=='m4rch.gfx-native-ap-retained-cycle-wrapper-qualification.v1' and
  wrapper.get('cold_ap_startup_proof_exercised') is True,'Wrong or incomplete wrapper qualification')
 owner=check_qualification(args.owner_qualification);check_owner_qualification(owner,source,source_path)
 owner_rows=owner.get('inputs',owner.get('files',[]))
 bound_paths={str((Path(r['path']) if Path(r['path']).is_absolute() else ROOT/r['path']).resolve()) for r in owner_rows}
 require({str((HERE/n).resolve()) for n in HEADERS+['prepare-native-ap-retained-cycle-owner.py']}<=bound_paths,'Actual C source qualification unbound')
 require([r['sha256'] for r in owner_rows if Path(r['path']).name==SOURCE_RECEIPT]==[sha(source_path)],'Qualified dispatcher differs')
 frozen_c=ROOT/'out/gfx-native-running-cycle/owner-qualification-final-v2.json'
 frozen_wrapper=ROOT/'out/gfx-native-running-cycle/wrapper-qualification-final-v2.json'
 require(sha(frozen_c)==FROZEN_C_QUALIFICATION_SHA and sha(frozen_wrapper)==FROZEN_WRAPPER_QUALIFICATION_SHA,'Frozen qualifications changed')
 cq=check_qualification(frozen_c);pq=check_qualification(frozen_wrapper)
 require(cq['case_count']==199 and pq['case_count']==102,'Frozen composition differs')
 make=(graph/'Makefile').read_text()
 require(all('-D'+flag in make for flag in ('GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','GFX_NATIVE_POWERGATE_DRAIN_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL')) and
  all(flag not in make for flag in ('GFX_NATIVE_RUNNING_CYCLE_TRIAL','GFX_NATIVE_IDLE_CYCLE_TRIAL','GFX_NATIVE_RETAINED_CYCLE_TRIAL','GFX_RETAINED_POWER_CYCLE_TRIAL','GFX_COORDINATED_EXECUTION_TRIAL','GFX_RESET_NATIVE_SEQUENCE_TRIAL')),'Unexpected compiled profile')
 log=ROOT/'out/gfx-native-ap-retained-cycle/owner-build.log'
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
 trial=receipt['graph_recovery_trial'];trial.pop('gfx_native_running_cycle_scope');trial[FAMILY_KEY]=CONTRACT
 require(validate_receipt(receipt),'Final AP-retained receipt invalid')
 output=candidate/'asc-root-envelope/build-receipt.json';prep_path=candidate/'native-ap-retained-cycle-preparation.json'
 require(not output.exists() and not prep_path.exists(),'Finalization never overwrites a candidate')
 basis=[ROOT/'docs/evidence/2026-10-10-gfx-native-running-cycle-crashlog-diagnosis.json',
  ROOT/'docs/evidence/2026-10-10-gfx-native-running-cycle-retained-ap-notification-native-boundary.json']
 for p,want in zip(basis,('b8b218602d959f21b6f945def61117d65019895814d35761a0d28bf796efb35d','7cbe46bf9f7d72806dec5835aba0ab21693c61cf3c0040901f1f7278c990f845')):
  require(sha(p)==want,'Native/actual diagnosis changed')
 files=[bpath,bprep,source_path,args.owner_qualification,wrapper_path,frozen_c,frozen_wrapper,log,Path(__file__),*basis]+[HERE/n for n in
  ['ap_retained_cycle_wrapper.py','gfx_native_ap_retained_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','prepare-native-ap-retained-cycle-owner.py',*HEADERS]]
 analysis=json.loads(bprep.read_text())['analysis_input_pins']
 for row in analysis:require(sha(candidate/row['relative'])==row['sha256'],'Dormant analysis metadata changed')
 prep={'schema':'m4rch.gfx-native-ap-retained-cycle-preparation.v1','baseline_candidate':str(BASE),
  'baseline_receipt_sha256':BASE_RECEIPT_SHA,'candidate':str(candidate),'owner_sha256':sha(module),'vermagic':vermagic,
  'inputs':[pin(p) for p in files],'actual_module_imports':imports.splitlines(),'analysis_input_pins':analysis,
  'artifact_count':len(receipt['artifact_sha256']),'owner_source_count':len(receipt['graph_source_sha256']),
  'changed_source_files':CHANGED,'added_source_files':HEADERS,'removed_source_files':REMOVED,
  'qualification_composition':{'new_c_cases':owner['case_count'],'new_wrapper_cases':wrapper['case_count'],
   'frozen_v10_c_cases':199,'frozen_v10_wrapper_cases':102,'original_cases_repeated_by_finalizer':False},
  'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
  'selected_next_hardware_candidate':True,'hardware_preconditions_pending':True,'recovery_teardown_rendering_verified':False,
  'commands':CONTRACT['commands'],'refused_boots':list(__import__('gfx_native_ap_retained_cycle_contract').REFUSED_BOOTS),
  'qualification':'One exact cold owned HOST B20 reply is carried through management-only first202/OFF. After separate PMget/ON/START/HELLO/maps/Running, fresh guarded retainedAP20 skips HOST ON without a new reply, then ONE own202 uses unchanged low1/2 ACK, checkedstop/pairedOFF/PMput/strictOFF gates. No B201/B0/INIT220/app/root/context/work/release. Nativeflags unbound; retained-state hypothesis; hardware roundtrip, application rejoin and retirement unverified.'}
 with output.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 prep['candidate_receipt_sha256']=sha(output)
 with prep_path.open('x') as f:json.dump(prep,f,indent=2);f.write('\n')
 print(json.dumps({'preparation':str(prep_path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))
if __name__=='__main__':main()
