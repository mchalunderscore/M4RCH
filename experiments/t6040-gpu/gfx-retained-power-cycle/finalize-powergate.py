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
from gfx_retained_power_cycle_contract import CONTRACT, FAMILY_KEY, validate_receipt
from gfx_reset_contract import require

BASE_RECEIPT_SHA = '393049662c9966922fda7f66cbfa1c762efc2f0840492042b581e96271a7b6a5'
BASE_PREPARATION_SHA = 'f0fbf1090d73aad478f5b06a76a2f3900d672834c83a4201e0d01103e03fd923'
FROZEN_SOURCE_RECEIPT_SHA = 'e55cf8f6bf8a5b8d979a567412cada0b1df38b5d7750183a34e448a38d9c39c1'
FROZEN_C_QUALIFICATION_SHA = '041aed9b5ef9fc08bc9344477b835c56359133dcbaf5e79eb1ea40ff19c48e5f'
FROZEN_WRAPPER_QUALIFICATION_SHA = 'af990df129fdb30dcf93c5a5d66fc78f688af9fb43399d37324d63bff1ac24ca'
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']
HEADERS = ['gfx-retained-power-cycle.h','gfx-retained-power-cycle-coordinate.h']
SOURCE_RECEIPT = 'retained-power-cycle-owner-source-receipt.json'


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
    require(source.get('schema') == 'm4rch.gfx-retained-power-cycle-owner-source.v1' and
            source.get('hardware_actions') == [] and source.get('build_actions') == [] and
            source.get('changed_files') == ['Makefile','asc-graph-init.c','gfx-reset-scope.h','recovery-cycle.h'] and
            source.get('changed_frozen_drain_files') == CHANGED and source.get('added_files') == HEADERS,
            'Unexpected retained-cycle source transformation')
    profile = source['profile']
    require(profile.get('typed_commands') == CONTRACT['commands'] and
            profile.get('work_publication_admitted') is False and
            profile.get('maximum_retained_cycle_intents') == 1,
            'Unexpected retained-cycle dispatcher profile')
    expected = {
        'maximum_retained_cycle_starts':1,'maximum_retained_cycle_pm_gets':1,
        'maximum_retained_cycle_pm_puts':1,'maximum_retained_cycle_requests':1,
        'maximum_total_pm_puts':2,'maximum_total_powergate_requests':2,
        'maximum_protocol_records':CONTRACT['retained_cycle_maximum_protocol_records'],
        'maximum_protocol_polls':CONTRACT['retained_cycle_maximum_protocol_polls'],
        'nominal_protocol_timeout_ms':CONTRACT['retained_cycle_nominal_protocol_timeout_ms'],
        'exact_cold_reentry_status':'0x6a','cold_reentry_start_clear':True,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('owner_qualification',type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    base = ROOT/'out/gfx-native-powergate-drain/candidate'
    frozen = ROOT/'out/gfx-native-powergate-drain/prepared-owner-v2'
    require(candidate != base and base not in candidate.parents and
            candidate != ROOT/'out/gfx-coordinate-native-status/candidate' and
            ROOT/'out/gfx-coordinate-native-status/candidate' not in candidate.parents and
            candidate != ROOT/'out/gfx-native-powergate/candidate' and
            ROOT/'out/gfx-native-powergate/candidate' not in candidate.parents,
            'Frozen candidates must remain untouched')
    bpath = base/'asc-root-envelope/build-receipt.json'
    bprep = base/'powergate-drain-preparation.json'
    require(sha(bpath) == BASE_RECEIPT_SHA and sha(bprep) == BASE_PREPARATION_SHA, 'Frozen comparison baseline changed')
    old = json.loads(bpath.read_text()); graph = candidate/'asc-graph-init'
    for name,expected in old['artifact_sha256'].items():
        require(sha(base/name) == expected,'Frozen artifact changed')
        if name != 'asc-graph-init/asc-graph-init.ko':
            require(sha(candidate/name) == expected,'Non-owner artifact changed')
    for name,expected in old['graph_source_sha256'].items():
        require(sha(base/'asc-graph-init'/name) == expected,'Frozen source changed')
        if name not in CHANGED: require(sha(graph/name) == expected,'Unplanned source change: '+name)
    source_path = graph/SOURCE_RECEIPT; source = json.loads(source_path.read_text())
    check_source_profile(source)
    require(Path(source['source_path']).resolve() == frozen.resolve(),'Unexpected frozen powergate source')
    baseline_source = source['baseline_source_receipt']
    require(Path(baseline_source['path']).resolve() == (frozen/'powergate-drain-owner-source-receipt.json').resolve() and
            baseline_source['sha256'] == FROZEN_SOURCE_RECEIPT_SHA and
            sha(Path(baseline_source['path'])) == FROZEN_SOURCE_RECEIPT_SHA,'Frozen powergate source receipt changed')
    require(sha(Path(source['source_preparer']['path'])) == source['source_preparer']['sha256'],'Preparer changed')
    for row in source['input_source_pins']:
        require('/' not in row['name'] and sha(frozen/row['name']) == row['sha256'],'Frozen preparer input changed')
    for row in source['output_source_pins']:
        require('/' not in row['name'] and sha(graph/row['name']) == row['sha256'],'Prepared output changed')
    for header in HEADERS:
        require(sha(graph/header) == sha(HERE/header),'Retained-cycle header changed')
    require(not (graph/'gfx-native-powergate.h').exists() and not (graph/'powergate-owner-source-receipt.json').exists(),
            'Old unused powergate sources must not be selected')
    for name,key in [('graph-before.bin','graph_fixture_sha256'),('graph-receipt.json','graph_receipt_sha256')]:
        require(sha(graph/name) == old[key],'Dormant graph fixture changed')
    require(sha(graph/'backing.bin') == '35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3','Immutable render backing changed')
    wrapper_path = ROOT/'out/gfx-retained-power-cycle/wrapper-qualification-final-v3.json'
    wrapper = check_qualification(wrapper_path)
    require(wrapper.get('schema') == 'm4rch.gfx-retained-power-cycle-wrapper-qualification.v1', 'Wrong wrapper qualification family')
    owner = check_qualification(args.owner_qualification)
    require(owner.get('schema') == 'm4rch.gfx-retained-power-cycle-c-qualification.v1' and
            owner.get('ASan_UBSan') is True and owner.get('actual_headers') is True and
            owner.get('actual_second_coordinate_core') is True and
            owner.get('actual_receive_worker') is True and
            Path(owner.get('source_path','')).resolve() == Path(source['destination']).resolve() and
            owner.get('source_receipt_sha256') == sha(source_path),'Actual drain C/startup qualification missing')
    rows = owner.get('inputs',owner.get('files',[]))
    owner_paths = {str((ROOT/row['path']).resolve()) if not Path(row['path']).is_absolute() else str(Path(row['path']).resolve()) for row in rows}
    require({str((HERE/name).resolve()) for name in tuple(HEADERS)+('prepare-retained-cycle-owner.py',)} <= owner_paths,
            'Actual C/header/preparer qualification not bound')
    source_bindings = [row['sha256'] for row in rows if Path(row['path']).name == SOURCE_RECEIPT]
    require(source_bindings == [sha(source_path)],'Qualified C dispatcher differs from candidate source receipt')
    frozen_c = ROOT/'out/gfx-native-powergate-drain/owner-qualification-final-v2.json'
    frozen_wrapper = ROOT/'out/gfx-native-powergate-drain/wrapper-qualification.json'
    require(sha(frozen_c) == FROZEN_C_QUALIFICATION_SHA and sha(frozen_wrapper) == FROZEN_WRAPPER_QUALIFICATION_SHA,'Frozen qualification changed')
    original_c = check_qualification(frozen_c); original_wrapper = check_qualification(frozen_wrapper)
    require(original_c.get('ASan_UBSan') is True and original_c['case_count'] == 85 and original_wrapper['case_count'] == 94,
            'Frozen qualification composition differs')
    make = (graph/'Makefile').read_text()
    require(all('-D'+flag in make for flag in ('GFX_RETAINED_POWER_CYCLE_TRIAL','GFX_NATIVE_POWERGATE_DRAIN_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL')) and
            all(flag not in make for flag in ('GFX_NATIVE_POWERGATE_TRIAL','GFX_COORDINATED_EXECUTION_TRIAL','GFX_RESET_NATIVE_SEQUENCE_TRIAL')),
            'Unexpected compiled profile')
    log = ROOT/'out/gfx-retained-power-cycle/owner-build.log'
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
    for name in receipt['graph_source_sha256']: receipt['graph_source_sha256'][name] = sha(graph/name)
    for header in HEADERS: receipt['graph_source_sha256'][header] = sha(graph/header)
    trial = receipt['graph_recovery_trial']; trial.pop('gfx_native_powergate_drain_scope'); trial[FAMILY_KEY] = CONTRACT
    require(validate_receipt(receipt),'Final distinct drain receipt invalid')
    output = candidate/'asc-root-envelope/build-receipt.json'; prep_path = candidate/'retained-power-cycle-preparation.json'
    require(not output.exists() and not prep_path.exists(),'Finalization must never overwrite a candidate')
    files = [bpath,bprep,source_path,args.owner_qualification,wrapper_path,frozen_c,frozen_wrapper,log,Path(__file__)] + [HERE/name for name in
        ('retained_wrapper.py','gfx_retained_power_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','prepare-retained-cycle-owner.py',*HEADERS)]
    analysis = json.loads(bprep.read_text())['analysis_input_pins']
    for row in analysis: require(sha(candidate/row['relative']) == row['sha256'],'Dormant analysis metadata changed')
    prep = {'schema':'m4rch.gfx-retained-power-cycle-preparation.v1','baseline_candidate':str(base),'baseline_receipt_sha256':BASE_RECEIPT_SHA,
        'candidate':str(candidate),'owner_sha256':sha(module),'vermagic':vermagic,'inputs':[pin(p) for p in files],
        'actual_module_imports':imports.splitlines(),'analysis_input_pins':analysis,'artifact_count':len(receipt['artifact_sha256']),
        'owner_source_count':len(receipt['graph_source_sha256']),'changed_source_files':CHANGED,'added_source_files':HEADERS,
        'qualification_composition':{'new_c_cases':owner['case_count'],'new_wrapper_cases':wrapper['case_count'],
            'original_c_cases':85,'original_wrapper_cases':94,'original_cases_repeated_by_finalizer':False},
        'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
        'selected_next_hardware_candidate':True,'hardware_preconditions_pending':True,'recovery_teardown_rendering_verified':False,
        'commands':list(CONTRACT['commands']),'refused_boots':list(__import__('gfx_retained_power_cycle_contract').REFUSED_BOOTS),
        'qualification':'Fresh cold no-work owner; ONE first successful native202/OFF capture then ONE sameconsumer retained-management roundtrip with separate PM reference and coordination epoch. No INIT220/root/context publication, app queue reset, work or release. Unknown outcomes seal every further power command. Full hardware roundtrip, application reuse and retirement remain unverified.'}
    with output.open('x') as f: json.dump(receipt,f,indent=2);f.write('\n')
    prep['candidate_receipt_sha256'] = sha(output)
    with prep_path.open('x') as f: json.dump(prep,f,indent=2);f.write('\n')
    print(json.dumps({'preparation':str(prep_path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))


if __name__ == '__main__': main()
