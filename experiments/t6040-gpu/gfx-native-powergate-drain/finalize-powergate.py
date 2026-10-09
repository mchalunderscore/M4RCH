#!/usr/bin/env python3
"""Bind a distinct built admission-drain owner; no build/load/GPU operation."""
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
from gfx_native_powergate_drain_contract import CONTRACT, FAMILY_KEY, validate_receipt
from gfx_reset_contract import require

BASE_RECEIPT_SHA = '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
BASE_PREPARATION_SHA = 'af522a6f563d2bdc194c0a30fc31dc3bc9d21fa872bad2557a29e483c6cacbf2'
FROZEN_SOURCE_RECEIPT_SHA = '29aedde66ac1a15ef0ea180d79dcb2470a1fb638fbaf3750c15afd4a52a2a2f7'
FROZEN_C_QUALIFICATION_SHA = 'dc07f9c1b37de7ba4aa7ccfb5328af89b16dabc64e7e95bd7c3c04ad1256e914'
FROZEN_WRAPPER_QUALIFICATION_SHA = 'd0f27bceb4ccc535b1126ca895b66ac9536d8c0a24dde43623db6c2d9c4515ab'
CHANGED = ['Makefile', 'asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h']
HEADER = 'gfx-native-powergate-drain.h'
SOURCE_RECEIPT = 'powergate-drain-owner-source-receipt.json'


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
    require(source.get('schema') == 'm4rch.gfx-native-powergate-drain-owner-source.v1' and
            source.get('hardware_actions') == [] and source.get('build_actions') == [] and
            source.get('changed_files') == CHANGED and source.get('added_files') == [HEADER],
            'Unexpected admission-drain source transformation')
    profile = source['profile']
    require(profile.get('typed_commands') == ['sample','gfx-snapshot','gfx-powergate'] and
            profile.get('work_publication_admitted') is False and
            profile.get('maximum_powergate_intents') == 1, 'Unexpected dispatcher profile')
    for key in ('bounded_admission_drain','nominal_admission_deadline_ms','maximum_admission_wait_polls',
                'maximum_admission_rx_messages','maximum_successful_admission_rx_messages',
                'qualified_admission_endpoint32_only','stale_ep0_refused','precise_admission_operands_logged'):
        require(profile.get(key) == CONTRACT[key], 'Unbound admission-drain operand: '+key)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('owner_qualification',type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    base = ROOT/'out/gfx-coordinate-native-status/candidate'
    frozen = ROOT/'out/gfx-native-powergate/prepared-owner-v5'
    require(candidate != base and base not in candidate.parents and
            candidate != ROOT/'out/gfx-native-powergate/candidate' and
            ROOT/'out/gfx-native-powergate/candidate' not in candidate.parents,
            'Frozen candidates must remain untouched')
    bpath = base/'asc-root-envelope/build-receipt.json'
    bprep = base/'native-status-preparation.json'
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
    require(Path(baseline_source['path']).resolve() == (frozen/'powergate-owner-source-receipt.json').resolve() and
            baseline_source['sha256'] == FROZEN_SOURCE_RECEIPT_SHA and
            sha(Path(baseline_source['path'])) == FROZEN_SOURCE_RECEIPT_SHA,'Frozen powergate source receipt changed')
    require(sha(Path(source['source_preparer']['path'])) == source['source_preparer']['sha256'],'Preparer changed')
    for row in source['input_source_pins']:
        require('/' not in row['name'] and sha(frozen/row['name']) == row['sha256'],'Frozen preparer input changed')
    for row in source['output_source_pins']:
        require('/' not in row['name'] and sha(graph/row['name']) == row['sha256'],'Prepared output changed')
    require(sha(graph/HEADER) == sha(HERE/HEADER),'Admission header changed')
    require(not (graph/'gfx-native-powergate.h').exists() and not (graph/'powergate-owner-source-receipt.json').exists(),
            'Old unused powergate sources must not be selected')
    for name,key in [('graph-before.bin','graph_fixture_sha256'),('graph-receipt.json','graph_receipt_sha256')]:
        require(sha(graph/name) == old[key],'Dormant graph fixture changed')
    require(sha(graph/'backing.bin') == '35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3','Immutable render backing changed')
    wrapper_path = ROOT/'out/gfx-native-powergate-drain/wrapper-qualification.json'
    wrapper = check_qualification(wrapper_path)
    require(wrapper.get('schema') == 'm4rch.gfx-native-powergate-drain-wrapper-qualification.v1', 'Wrong wrapper qualification family')
    owner = check_qualification(args.owner_qualification)
    require(owner.get('schema') == 'm4rch.gfx-native-powergate-drain-actual-c-qualification.v1' and
            owner.get('ASan_UBSan') is True and owner.get('prepared_source_binding') is True and
            owner.get('actual_post_start_fallback_replay_verified') is True,'Actual drain C/startup qualification missing')
    rows = owner.get('inputs',owner.get('files',[]))
    owner_paths = {str((ROOT/row['path']).resolve()) if not Path(row['path']).is_absolute() else str(Path(row['path']).resolve()) for row in rows}
    require({str((HERE/name).resolve()) for name in (HEADER,'prepare-powergate-drain-owner.py')} <= owner_paths,
            'Actual C/header/preparer qualification not bound')
    source_bindings = [row['sha256'] for row in rows if Path(row['path']).name == SOURCE_RECEIPT]
    require(source_bindings == [sha(source_path)],'Qualified C dispatcher differs from candidate source receipt')
    frozen_c = ROOT/'out/gfx-native-powergate/owner-qualification-final-v5.json'
    frozen_wrapper = ROOT/'out/gfx-native-powergate/wrapper-qualification.json'
    require(sha(frozen_c) == FROZEN_C_QUALIFICATION_SHA and sha(frozen_wrapper) == FROZEN_WRAPPER_QUALIFICATION_SHA,'Frozen qualification changed')
    original_c = check_qualification(frozen_c); original_wrapper = check_qualification(frozen_wrapper)
    require(original_c.get('ASan_UBSan') is True and original_c['case_count'] == 55 and original_wrapper['case_count'] == 196,
            'Frozen qualification composition differs')
    make = (graph/'Makefile').read_text()
    require(all('-D'+flag in make for flag in ('GFX_NATIVE_POWERGATE_DRAIN_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL')) and
            all(flag not in make for flag in ('GFX_NATIVE_POWERGATE_TRIAL','GFX_COORDINATED_EXECUTION_TRIAL','GFX_RESET_NATIVE_SEQUENCE_TRIAL')),
            'Unexpected compiled profile')
    log = ROOT/'out/gfx-native-powergate-drain/owner-build.log'
    require('warning:' not in log.read_text() and 'error:' not in log.read_text(),'Build diagnostics require review')
    module = graph/'asc-graph-init.ko'
    vermagic = subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()
    require(vermagic.startswith(old['kernel_release']+' '),'Owner vermagic mismatch')
    imports = subprocess.check_output(['llvm-nm','-u',str(module)],text=True)
    require(all(name in imports for name in ('apple_pmgr_t6040_gfx_snapshot','__pm_runtime_suspend','of_find_all_nodes')) and
            all(name not in imports for name in ('apple_pmgr_t6040_gfx_native_probe','apple_pmgr_t6040_gfx_checked_pulse')),
            'Unexpected owner imports')
    receipt = copy.deepcopy(old)
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    for name in receipt['graph_source_sha256']: receipt['graph_source_sha256'][name] = sha(graph/name)
    receipt['graph_source_sha256'][HEADER] = sha(graph/HEADER)
    trial = receipt['graph_recovery_trial']; trial.pop('gfx_native_status_execution_scope'); trial[FAMILY_KEY] = CONTRACT
    require(validate_receipt(receipt),'Final distinct drain receipt invalid')
    output = candidate/'asc-root-envelope/build-receipt.json'; prep_path = candidate/'powergate-drain-preparation.json'
    require(not output.exists() and not prep_path.exists(),'Finalization must never overwrite a candidate')
    files = [bpath,bprep,source_path,args.owner_qualification,wrapper_path,frozen_c,frozen_wrapper,log,Path(__file__)] + [HERE/name for name in
        ('frozen_wrapper.py','gfx_native_powergate_drain_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','prepare-powergate-drain-owner.py',HEADER)]
    analysis = json.loads(bprep.read_text())['analysis_input_pins']
    for row in analysis: require(sha(candidate/row['relative']) == row['sha256'],'Dormant analysis metadata changed')
    prep = {'schema':'m4rch.gfx-native-powergate-drain-preparation.v1','baseline_candidate':str(base),'baseline_receipt_sha256':BASE_RECEIPT_SHA,
        'candidate':str(candidate),'owner_sha256':sha(module),'vermagic':vermagic,'inputs':[pin(p) for p in files],
        'actual_module_imports':imports.splitlines(),'analysis_input_pins':analysis,'artifact_count':len(receipt['artifact_sha256']),
        'owner_source_count':len(receipt['graph_source_sha256']),'changed_source_files':CHANGED,'added_source_files':[HEADER],
        'qualification_composition':{'new_c_cases':owner['case_count'],'new_wrapper_cases':wrapper['case_count'],
            'original_c_cases':55,'original_wrapper_cases':196,'original_cases_repeated_by_finalizer':False},
        'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
        'selected_next_hardware_candidate':True,'hardware_preconditions_pending':True,'recovery_teardown_rendering_verified':False,
        'commands':list(CONTRACT['commands']),'refused_boots':['94cb4163-fc21-43ec-9489-07c54e549885','d841b8bf-bf1f-4499-9508-caf275909695'],
        'qualification':'Fresh preflight and ONE cold no-work owner. Bounded qualified EP32 admission drain, fresh RX-empty, own202 ACK and checked CPU stop precede pairedOFF. Nominal11ms jiffy deadline can exceed wall-time under scheduling/finite service; wait polls and frames are separately bounded. All backing retained, terminal intent never retried, no restart/retirement/render proof.'}
    with output.open('x') as f: json.dump(receipt,f,indent=2);f.write('\n')
    prep['candidate_receipt_sha256'] = sha(output)
    with prep_path.open('x') as f: json.dump(prep,f,indent=2);f.write('\n')
    print(json.dumps({'preparation':str(prep_path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))


if __name__ == '__main__': main()
