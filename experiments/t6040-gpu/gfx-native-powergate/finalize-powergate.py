#!/usr/bin/env python3
"""Bind ONE separately built native PWRGATE candidate; no build/load/hardware."""
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
from gfx_native_powergate_contract import CONTRACT, FAMILY_KEY, validate_receipt
from gfx_reset_contract import require

BASE_RECEIPT_SHA = '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
BASE_PREPARATION_SHA = 'af522a6f563d2bdc194c0a30fc31dc3bc9d21fa872bad2557a29e483c6cacbf2'
CHANGED = ['Makefile', 'asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def check_qualification(path):
    q = json.loads(path.read_text())
    require(q.get('passed') is True and q.get('hardware_access') is False and q.get('case_count', 0) > 0,
            'Missing actual offline qualification: ' + str(path))
    rows = q.get('inputs', q.get('files', []))
    require(bool(rows), 'Qualification has no source binding')
    for row in rows:
        source = Path(row['path'])
        source = source if source.is_absolute() else ROOT / source
        require(sha(source) == row['sha256'], 'Qualification input changed: ' + str(source))
    return q


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('owner_qualification', type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    base = ROOT / 'out/gfx-coordinate-native-status/candidate'
    require(candidate != base and base not in candidate.parents, 'Frozen base must remain untouched')
    bpath = base / 'asc-root-envelope/build-receipt.json'
    bprep = base / 'native-status-preparation.json'
    require(sha(bpath) == BASE_RECEIPT_SHA and sha(bprep) == BASE_PREPARATION_SHA, 'Frozen baseline changed')
    old = json.loads(bpath.read_text())
    graph = candidate / 'asc-graph-init'
    for name, expected in old['artifact_sha256'].items():
        require(sha(base / name) == expected, 'Frozen artifact changed')
        if name != 'asc-graph-init/asc-graph-init.ko':
            require(sha(candidate / name) == expected, 'Non-owner artifact changed')
    for name, expected in old['graph_source_sha256'].items():
        require(sha(base / 'asc-graph-init' / name) == expected, 'Frozen source changed')
        if name not in CHANGED:
            require(sha(graph / name) == expected, 'Unplanned source change: ' + name)
    source_path = graph / 'powergate-owner-source-receipt.json'
    source = json.loads(source_path.read_text())
    require(source.get('schema') == 'm4rch.gfx-native-powergate-owner-source.v1' and
            source.get('hardware_actions') == [] and source.get('build_actions') == [] and
            source.get('changed_files') == CHANGED and source.get('added_files') == ['gfx-native-powergate.h'],
            'Unexpected powergate source transformation')
    require(source['profile']['typed_commands'] == ['sample', 'gfx-snapshot', 'gfx-powergate'] and
            source['profile']['work_publication_admitted'] is False and
            source['profile']['maximum_powergate_intents'] == 1, 'Unexpected powergate dispatcher profile')
    require(sha(Path(source['source_preparer']['path'])) == source['source_preparer']['sha256'], 'Preparer changed')
    for row in source['input_source_pins']:
        require(sha(base / 'asc-graph-init' / row['name']) == row['sha256'], 'Frozen preparer input changed')
    for row in source['output_source_pins']:
        require(sha(graph / row['name']) == row['sha256'], 'Prepared output changed')
    require(sha(graph / 'gfx-native-powergate.h') == sha(HERE / 'gfx-native-powergate.h'), 'Native header changed')
    for name, key in [('graph-before.bin', 'graph_fixture_sha256'), ('graph-receipt.json', 'graph_receipt_sha256')]:
        require(sha(graph / name) == old[key], 'Dormant graph fixture changed')
    require(sha(graph / 'backing.bin') == '35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3',
            'Immutable render backing changed')
    wrapper_path = ROOT / 'out/gfx-native-powergate/wrapper-qualification.json'
    wrapper = check_qualification(wrapper_path)
    owner = check_qualification(args.owner_qualification)
    required = {str((HERE / name).resolve()) for name in ['gfx-native-powergate.h', 'prepare-powergate-owner.py']}
    owner_paths = {str((ROOT / row['path']).resolve()) if not Path(row['path']).is_absolute() else str(Path(row['path']).resolve()) for row in owner.get('inputs', owner.get('files', []))}
    require(required <= owner_paths, 'Actual C/header/preparer qualification not bound')
    source_bindings = [row['sha256'] for row in owner.get('inputs', owner.get('files', []))
                       if Path(row['path']).name == 'powergate-owner-source-receipt.json']
    require(source_bindings == [sha(source_path)] and owner.get('prepared_source_binding') is True,
            'Qualified C dispatcher differs from candidate source receipt')
    require(owner.get('ASan_UBSan') is True, 'Actual C ASan/UBSan qualification missing')
    make = (graph / 'Makefile').read_text()
    require(all('-D' + flag in make for flag in ['GFX_NATIVE_POWERGATE_TRIAL', 'GFX_NATIVE_COORDINATED_SCOPE_TRIAL', 'GFX_NATIVE_STATUS_ZERO_TRIAL']) and
            'GFX_COORDINATED_EXECUTION_TRIAL' not in make and 'GFX_RESET_NATIVE_SEQUENCE_TRIAL' not in make,
            'Unexpected compiled profile')
    log = ROOT / 'out/gfx-native-powergate/owner-build.log'
    require('warning:' not in log.read_text() and 'error:' not in log.read_text(), 'Build diagnostics require review')
    module = graph / 'asc-graph-init.ko'
    vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
    require(vermagic.startswith(old['kernel_release'] + ' '), 'Owner vermagic mismatch')
    imports = subprocess.check_output(['llvm-nm', '-u', str(module)], text=True)
    require(all(name in imports for name in ['apple_pmgr_t6040_gfx_snapshot', '__pm_runtime_suspend', 'of_find_all_nodes']) and
            all(name not in imports for name in ['apple_pmgr_t6040_gfx_native_probe', 'apple_pmgr_t6040_gfx_checked_pulse']),
            'Unexpected owner imports')
    receipt = copy.deepcopy(old)
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    for name in receipt['graph_source_sha256']:
        receipt['graph_source_sha256'][name] = sha(graph / name)
    receipt['graph_source_sha256']['gfx-native-powergate.h'] = sha(graph / 'gfx-native-powergate.h')
    trial = receipt['graph_recovery_trial']
    trial.pop('gfx_native_status_execution_scope')
    trial[FAMILY_KEY] = CONTRACT
    require(validate_receipt(receipt), 'Final distinct powergate receipt invalid')
    output = candidate / 'asc-root-envelope/build-receipt.json'
    preparation_path = candidate / 'powergate-preparation.json'
    require(not output.exists() and not preparation_path.exists(), 'Finalization must never overwrite a candidate')
    files = [bpath, bprep, source_path, args.owner_qualification, wrapper_path, log, Path(__file__)] + [HERE / name for name in
        ['gfx_native_powergate_contract.py', 'run-root-powergate.py', 'run-powergate.py', 'preflight-fresh.py',
         'prepare-powergate-owner.py', 'gfx-native-powergate.h']]
    # Preserve and bind dormant render metadata; no execution command exists.
    analysis_inputs = json.loads(bprep.read_text())['analysis_input_pins']
    for row in analysis_inputs:
        require(sha(candidate / row['relative']) == row['sha256'], 'Dormant analysis metadata changed')
    prepared = {'schema': 'm4rch.gfx-native-powergate-preparation.v1', 'baseline_candidate': str(base),
        'baseline_receipt_sha256': BASE_RECEIPT_SHA, 'candidate': str(candidate),
        'owner_sha256': sha(module), 'vermagic': vermagic, 'inputs': [pin(p) for p in files],
        'actual_module_imports': imports.splitlines(), 'analysis_input_pins': analysis_inputs,
        'artifact_count': len(receipt['artifact_sha256']), 'owner_source_count': len(receipt['graph_source_sha256']),
        'changed_source_files': CHANGED, 'added_source_files': ['gfx-native-powergate.h'],
        'hardware_actions': [], 'module_loaded': False, 'kernel_rebuilt': False, 'boot_configuration_changed': False,
        'selected_next_hardware_candidate': True, 'hardware_preconditions_pending': True,
        'recovery_teardown_rendering_verified': False, 'commands': list(CONTRACT['commands']),
        'qualification': 'Fresh preflight then ONE cold no-work owner. Initial two recovery requests remain comparable. Only sample/gfx-snapshot and ONE combined gfx-powergate. Own management ACK and checked CPU stop precede paired OFF. Intent/errors retain all backing and seal every later destructive/publication operation. No retirement/restart/render proof.'}
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    prepared['candidate_receipt_sha256'] = sha(output)
    with preparation_path.open('x') as stream:
        json.dump(prepared, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'preparation': str(preparation_path), 'owner_sha256': sha(module),
                      'receipt_sha256': sha(output), 'hardware_actions': []}))


if __name__ == '__main__':
    main()
