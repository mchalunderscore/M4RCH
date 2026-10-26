#!/usr/bin/env python3
"""Bind a distinct built retained management-cycle owner; no build/load/GPU operation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from gfx_native_running_cycle_contract import CONTRACT, FAMILY_KEY, validate_receipt
from gfx_reset_contract import require

BASE_RECEIPT_SHA = '027b5dbf79e2cceecdb82823c5daba4bc5b7cdacb05cb7228b2b11cb5d6deeea'
BASE_PREPARATION_SHA = '2a8cc03ff760702d2d052fc8f047527cafa54a252e25d67e2aef664036b31d80'
FROZEN_SOURCE_RECEIPT_SHA = '313135beb0a845b461f07398a56072937c8e89f3771f161a30b6c1f13aaa7d5d'
FROZEN_C_QUALIFICATION_SHA = '5f1de50846c2b4b51488e37e103fa1277b17b20547f8a7c1390f288ec5b348f2'
FROZEN_WRAPPER_QUALIFICATION_SHA = '565b4bb2d72eb56f498f8450e3c8f57e27b3aa08460fee4404c9bcb390753a08'
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']
HEADERS = ['gfx-native-running-cycle.h']
REMOVED = ['gfx-native-idle-cycle.h']
SOURCE_RECEIPT = 'native-running-cycle-owner-source-receipt.json'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pin(path): return {'path':str(path.resolve()), 'sha256':sha(path)}


def check_qualification(path):
    q = json.loads(path.read_text())
    require(q.get('passed') is True and q.get('hardware_access') is False and
            q.get('case_count',0) > 0, 'Missing actual offline qualification: '+str(path))
    rows = q.get('inputs', q.get('files',[]))
    require(bool(rows), 'Qualification has no source binding')
    for row in rows:
        source = Path(row['path'])
        source = source if source.is_absolute() else ROOT/source
        require(sha(source) == row['sha256'], 'Qualification input changed: '+str(source))
    return q


def check_source_profile(source):
    require(source.get('schema') == 'm4rch.gfx-native-running-cycle-owner-source.v1' and
            source.get('hardware_actions') == [] and source.get('build_actions') == [] and
            source.get('changed_files') == CHANGED and
            source.get('changed_frozen_retained_files') == CHANGED and source.get('added_files') == HEADERS and
            source.get('removed_files') == REMOVED,
            'Unexpected retained-cycle source transformation')
    profile = source['profile']
    require(profile.get('typed_commands') == CONTRACT['commands'] and
            profile.get('work_publication_admitted') is False and
            profile.get('maximum_retained_cycle_intents') == 1,
            'Unexpected retained-cycle dispatcher profile')
    expected = {
        'version':CONTRACT['version'],
        'maximum_retained_cycle_starts':1,'maximum_retained_cycle_pm_gets':1,
        'maximum_retained_cycle_pm_puts':1,'maximum_retained_cycle_requests':1,
        'maximum_total_pm_puts':2,'maximum_total_powergate_requests':2,
        'maximum_protocol_records':CONTRACT['retained_cycle_maximum_protocol_records'],
        'maximum_protocol_polls':CONTRACT['retained_cycle_maximum_protocol_polls'],
        'nominal_protocol_timeout_ms':CONTRACT['retained_cycle_nominal_protocol_timeout_ms'],
        'pre_on_known_statuses':['0x6a','0x6c'],
        'post_on_known_statuses':['0x6a','0x6c','0x6d'],
        'status6d_requires_second_on_complete_and_second_ref':True,
        'pre_on_status6d_refused':True,'stage_specific_start_admission':True,
        'cold_reentry_start_clear':True,
        'exact_cold_reentry_status':None,
        'reentry_four_operands_before_and_after_second_paired_on':True,
        'reentry_four_operands_after_start_intent_log':True,
        'immediate_start_fresh_ctrl_rmw':True,'reentry_status6e_or48_refused':True,
        'reentry_tx_valid_and_available_required':True,
        'native_ordered_start_is_experimental_hypothesis':True,
        'maximum_log_row_bytes':CONTRACT['retained_cycle_maximum_log_row_bytes'],
        'complete_newline_structured_state_rows':True,
        'second_log_row_prefixes':['m4rch gfx-native-running-cycle:',
            'm4rch gfx-native-running-cycle-state:',
            'm4rch gfx-native-running-cycle-transport:',
            'm4rch gfx-native-running-cycle-management:',
            'm4rch gfx-native-running-cycle-off:','m4rch gfx-native-running-cycle-on:'],
        'exact_boot_running_message':'0x0070000000000020',
        'exact_host_on_message':'0x00b0000000000020',
        'boot_running_required_before_host_on':True,
        'boot_running_required_after_exact_final_map_ack':True,
        'host_on_fresh_four_operands_before_and_after_intent':True,
        'fresh_pm_identity_cpu_fifo_required_after_host_reply_before_second_202':True,
        'second_log_row_count':6,
        'host_on_reply_required_before_second_202':True,'maximum_host_on_requests':1,
        'maximum_host_on_polls':CONTRACT['retained_cycle_host_power_maximum_polls'],
        'nominal_host_on_timeout_ms':CONTRACT['retained_cycle_host_power_nominal_timeout_ms'],
        'running_host_on_is_experimental_protocol_hypothesis':True,
        'power20_never_shutdown_ack':True,'host_on_fresh_four_operands_after_intent':True,
        'host_on_reserved_reply_and_ack_capacity':CONTRACT['retained_cycle_host_power_reserved_journal_slots'],
        'fresh_rx_empty_required_before_start_and_second_request':True,
        'autonomous_hello_versions':CONTRACT['retained_cycle_autonomous_hello_versions'],
        'autonomous_endpoint_map_shape':CONTRACT['retained_cycle_autonomous_map_shape'],
        'retained_management_roundtrip_admitted':True,'transport_only':False,
        'separate_second_pm_reference':True,'separate_second_coordinator_epoch':True,
        'first_epoch_evidence_immutable':True,'host_protocol_journal_separate':True,
        'owned_page_pointer_and_pa_identity_required':174,
        'first_strict_physical_off_required_before_pm_get':True,
        'no_init220_request':True,'no_application_start':True,
        'no_application_root_publication':True,'no_context_reattach':True,
        'no_firmware_data_restore':True,'no_queue_or_counter_reset':True,
        'application_rejoin_verified':False,'application_rejoined':False,
        'second_intent_seals_all_controls':True}
    require(all(profile.get(key)==value for key,value in expected.items()),
            'Retained-cycle source profile operands differ')
    return True


def check_owner_qualification(owner,source,source_path):
    maximum=owner.get('maximum_new_log_row_bytes')
    require(owner.get('schema') == 'm4rch.gfx-native-running-cycle-c-qualification.v1' and
            owner.get('ASan_UBSan') is True and owner.get('actual_headers') is True and
            owner.get('actual_second_coordinate_core') is True and
            owner.get('actual_receive_worker') is True and
            owner.get('stage_specific_start_guards_exercised') is True and
            owner.get('actual_observed_6c_to_paired_on_to_6d_sequence_simulated') is True and
            owner.get('actual_running_host_on_before_202_replay') is True and
            owner.get('observed_boot_power20_sequence_simulated') is True and
            owner.get('actual_complete_six_row_groups') is True and
            owner.get('second_log_row_count') == 6 and
            owner.get('new_log_rows_bounded') is True and
            type(maximum) is int and 1 <= maximum <= CONTRACT['retained_cycle_maximum_log_row_bytes'] and
            Path(owner.get('source_path','')).resolve() == Path(source['destination']).resolve() and
            owner.get('source_receipt_sha256') == sha(source_path),
            'Actual native retained-cycle C/startup/log qualification missing')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('owner_qualification',type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    base = ROOT/'out/gfx-native-idle-cycle/candidate'
    frozen = ROOT/'out/gfx-native-idle-cycle/prepared-owner-v1'
    require(candidate != base and base not in candidate.parents and
            candidate != ROOT/'out/gfx-retained-power-cycle/candidate' and
            ROOT/'out/gfx-retained-power-cycle/candidate' not in candidate.parents and
            candidate != ROOT/'out/gfx-coordinate-native-status/candidate' and
            ROOT/'out/gfx-coordinate-native-status/candidate' not in candidate.parents and
            candidate != ROOT/'out/gfx-native-powergate-drain/candidate' and
            ROOT/'out/gfx-native-powergate-drain/candidate' not in candidate.parents and
            candidate != ROOT/'out/gfx-native-powergate/candidate' and
            ROOT/'out/gfx-native-powergate/candidate' not in candidate.parents,
            'Frozen candidates must remain untouched')
    bpath = base/'asc-root-envelope/build-receipt.json'
    bprep = base/'native-idle-cycle-preparation.json'
    require(sha(bpath) == BASE_RECEIPT_SHA and sha(bprep) == BASE_PREPARATION_SHA, 'Frozen comparison baseline changed')
    old = json.loads(bpath.read_text()); graph = candidate/'asc-graph-init'
    for name,expected in old['artifact_sha256'].items():
        require(sha(base/name) == expected,'Frozen artifact changed')
        if name != 'asc-graph-init/asc-graph-init.ko':
            require(sha(candidate/name) == expected,'Non-owner artifact changed')
    for name,expected in old['graph_source_sha256'].items():
        require(sha(base/'asc-graph-init'/name) == expected,'Frozen source changed')
        if name not in CHANGED+REMOVED: require(sha(graph/name) == expected,'Unplanned source change: '+name)
    source_path = graph/SOURCE_RECEIPT; source = json.loads(source_path.read_text())
    check_source_profile(source)
    require(Path(source['source_path']).resolve() == frozen.resolve(),'Unexpected frozen powergate source')
    baseline_source = source['baseline_source_receipt']
    require(Path(baseline_source['path']).resolve() == (frozen/'native-idle-cycle-owner-source-receipt.json').resolve() and
            baseline_source['sha256'] == FROZEN_SOURCE_RECEIPT_SHA and
            sha(Path(baseline_source['path'])) == FROZEN_SOURCE_RECEIPT_SHA,'Frozen powergate source receipt changed')
    require(sha(Path(source['source_preparer']['path'])) == source['source_preparer']['sha256'],'Preparer changed')
    for row in source['input_source_pins']:
        require('/' not in row['name'] and sha(frozen/row['name']) == row['sha256'],'Frozen preparer input changed')
    for row in source['output_source_pins']:
        require('/' not in row['name'] and sha(graph/row['name']) == row['sha256'],'Prepared output changed')
    for header in HEADERS:
        require(sha(graph/header) == sha(HERE/header),'Retained-cycle header changed')
    require(all(not (graph/name).exists() for name in REMOVED),'Unused prior retained core header must not be selected')
    require(not (graph/'gfx-native-powergate.h').exists() and not (graph/'powergate-owner-source-receipt.json').exists(),
            'Old unused powergate sources must not be selected')
    for name,key in [('graph-before.bin','graph_fixture_sha256'),('graph-receipt.json','graph_receipt_sha256')]:
        require(sha(graph/name) == old[key],'Dormant graph fixture changed')
    require(sha(graph/'backing.bin') == '35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3','Immutable render backing changed')
    wrapper_path = ROOT/'out/gfx-native-running-cycle/wrapper-qualification-final-v2.json'
    wrapper = check_qualification(wrapper_path)
    require(wrapper.get('schema') == 'm4rch.gfx-native-running-cycle-wrapper-qualification.v1', 'Wrong wrapper qualification family')
    owner = check_qualification(args.owner_qualification)
    check_owner_qualification(owner,source,source_path)
    rows = owner.get('inputs',owner.get('files',[]))
    owner_paths = {str((ROOT/row['path']).resolve()) if not Path(row['path']).is_absolute() else str(Path(row['path']).resolve()) for row in rows}
    require({str((HERE/name).resolve()) for name in tuple(HEADERS)+('prepare-native-running-cycle-owner.py',)} <= owner_paths,
            'Actual C/header/preparer qualification not bound')
    source_bindings = [row['sha256'] for row in rows if Path(row['path']).name == SOURCE_RECEIPT]
    require(source_bindings == [sha(source_path)],'Qualified C dispatcher differs from candidate source receipt')
    frozen_c = ROOT/'out/gfx-native-idle-cycle/owner-qualification-final-v1.json'
    frozen_wrapper = ROOT/'out/gfx-native-idle-cycle/wrapper-qualification-final-v2.json'
    require(sha(frozen_c) == FROZEN_C_QUALIFICATION_SHA and sha(frozen_wrapper) == FROZEN_WRAPPER_QUALIFICATION_SHA,'Frozen qualification changed')
    original_c = check_qualification(frozen_c); original_wrapper = check_qualification(frozen_wrapper)
    require(original_c.get('ASan_UBSan') is True and original_c['case_count'] == 135 and original_wrapper['case_count'] == 74,
            'Frozen qualification composition differs')
    make = (graph/'Makefile').read_text()
    require(all('-D'+flag in make for flag in ('GFX_NATIVE_RUNNING_CYCLE_TRIAL','GFX_NATIVE_POWERGATE_DRAIN_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL')) and
            all(flag not in make for flag in ('GFX_NATIVE_IDLE_CYCLE_TRIAL','GFX_NATIVE_RETAINED_CYCLE_TRIAL','GFX_RETAINED_POWER_CYCLE_TRIAL','GFX_NATIVE_POWERGATE_TRIAL','GFX_COORDINATED_EXECUTION_TRIAL','GFX_RESET_NATIVE_SEQUENCE_TRIAL')),
            'Unexpected compiled profile')
    log = ROOT/'out/gfx-native-running-cycle/owner-build.log'
    require('warning:' not in log.read_text() and 'error:' not in log.read_text(),'Build diagnostics require review')
    module = graph/'asc-graph-init.ko'
    vermagic = subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()
    require(vermagic.startswith(old['kernel_release']+' '),'Owner vermagic mismatch')
    imports = subprocess.check_output(['llvm-nm','-u',str(module)],text=True)
    require(all(name in imports for name in ('apple_pmgr_t6040_gfx_snapshot','__pm_runtime_resume','__pm_runtime_suspend','of_find_all_nodes')) and
            all(name not in imports for name in ('apple_pmgr_t6040_gfx_native_probe','apple_pmgr_t6040_gfx_checked_pulse')),
            'Unexpected owner imports')
    receipt = copy.deepcopy(old)
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    for name in REMOVED: receipt['graph_source_sha256'].pop(name)
    for name in receipt['graph_source_sha256']: receipt['graph_source_sha256'][name] = sha(graph/name)
    for header in HEADERS: receipt['graph_source_sha256'][header] = sha(graph/header)
    trial = receipt['graph_recovery_trial']; trial.pop('gfx_native_idle_cycle_scope'); trial[FAMILY_KEY] = CONTRACT
    require(validate_receipt(receipt),'Final distinct drain receipt invalid')
    output = candidate/'asc-root-envelope/build-receipt.json'; prep_path = candidate/'native-running-cycle-preparation.json'
    require(not output.exists() and not prep_path.exists(),'Finalization must never overwrite a candidate')
    files = [bpath,bprep,source_path,args.owner_qualification,wrapper_path,frozen_c,frozen_wrapper,log,Path(__file__)] + [HERE/name for name in
        ('running_cycle_wrapper.py','gfx_native_running_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','prepare-native-running-cycle-owner.py',*HEADERS)]
    analysis = json.loads(bprep.read_text())['analysis_input_pins']
    for row in analysis: require(sha(candidate/row['relative']) == row['sha256'],'Dormant analysis metadata changed')
    prep = {'schema':'m4rch.gfx-native-running-cycle-preparation.v1','baseline_candidate':str(base),'baseline_receipt_sha256':BASE_RECEIPT_SHA,
        'candidate':str(candidate),'owner_sha256':sha(module),'vermagic':vermagic,'inputs':[pin(p) for p in files],
        'actual_module_imports':imports.splitlines(),'analysis_input_pins':analysis,'artifact_count':len(receipt['artifact_sha256']),
        'owner_source_count':len(receipt['graph_source_sha256']),'changed_source_files':CHANGED,'added_source_files':HEADERS,'removed_source_files':REMOVED,
        'qualification_composition':{'new_c_cases':owner['case_count'],'new_wrapper_cases':wrapper['case_count'],
            'original_c_cases':135,'original_wrapper_cases':74,'original_cases_repeated_by_finalizer':False},
        'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
        'selected_next_hardware_candidate':True,'hardware_preconditions_pending':True,'recovery_teardown_rendering_verified':False,
        'commands':list(CONTRACT['commands']),'refused_boots':list(__import__('gfx_native_running_cycle_contract').REFUSED_BOOTS),
        'qualification':'Fresh cold no-work owner; ONE first successful native202/OFF capture then ONE sameconsumer retained-management roundtrip with fresh preON6a/6c guarded ACTIVE, separate pairedON then refreshed postON6a/6c/6d before oneSTART; exact6d additionally requires own secondONcomplete and held second reference. Exact autonomous BOOT7/20 must precede one own HOSTB20 and exact fresh B20 reply before second202; neither20 frame is shutdownACK. Separate PM reference and coordination epoch. No INIT220/root/context publication, app queue reset, work or release. Unknown outcomes seal every further power command. Full hardware roundtrip, application reuse and retirement remain unverified.'}
    with output.open('x') as f: json.dump(receipt,f,indent=2);f.write('\n')
    prep['candidate_receipt_sha256'] = sha(output)
    with prep_path.open('x') as f: json.dump(prep,f,indent=2);f.write('\n')
    print(json.dumps({'preparation':str(prep_path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))


if __name__ == '__main__': main()
