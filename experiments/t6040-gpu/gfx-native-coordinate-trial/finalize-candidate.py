#!/usr/bin/env python3
"""Bind already-built separate artifacts to qualified sources; no hardware."""
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
from gfx_coordinate_contract import CONTRACT, validate_receipt

BASE_RECEIPT_SHA = '8644ae827a06da50d9793199a7c780305cff85abb9c9e826cde41b967971f471'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {'path': str(path.resolve()), 'sha256': sha(path), 'bytes': path.stat().st_size}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', type=Path, default=ROOT / 'out/gfx-native-coordinate/candidate')
    ap.add_argument('--wrapper-qualification', required=True, type=Path)
    args = ap.parse_args()
    candidate = args.candidate.resolve()
    baseline = ROOT / 'out/gfx-poweroff-scope/candidate'
    old_path = baseline / 'asc-root-envelope/build-receipt.json'
    assert sha(old_path) == BASE_RECEIPT_SHA
    old = json.loads(old_path.read_text())
    receipt = copy.deepcopy(old)
    graph = candidate / 'asc-graph-init'
    final_path = candidate / 'asc-root-envelope/build-receipt.json'
    assert not final_path.exists(), 'Final receipt already exists; never overwrite'
    for name, expected in old['artifact_sha256'].items():
        assert sha(baseline / name) == expected, name
        if name != 'asc-graph-init/asc-graph-init.ko':
            assert sha(candidate / name) == expected, name
    for name, expected in old['graph_source_sha256'].items():
        assert sha(baseline / 'asc-graph-init' / name) == expected, name
    core = ROOT / 'experiments/t6040-gpu/gfx-native-coordinate/gfx-coordinate-core.h'
    adapter = ROOT / 'experiments/t6040-gpu/gfx-native-coordinate-owner/gfx-coordinate-owner.h'
    assert sha(graph / 'gfx-coordinate-core.h') == sha(core)
    assert sha(graph / 'gfx-coordinate-owner.h') == sha(adapter)
    core_q = ROOT / 'docs/evidence/2026-10-09-gfx-coordinate-core-qualification.json'
    adapter_q = ROOT / 'out/gfx-native-coordinate-owner/adapter-qualification.json'
    cq, aq = json.loads(core_q.read_text()), json.loads(adapter_q.read_text())
    assert cq['passed'] and cq['tests']['hardware_access'] is False
    assert cq['inputs'][0]['sha256'] == sha(core)
    assert aq['adapter_sha256'] == sha(adapter) and aq['core_sha256'] == sha(core)
    assert aq['ASan_UBSan'] and aq['hardware_actions'] == []
    for qual in (core_q, args.wrapper_qualification):
        data = json.loads(qual.read_text())
        if qual == core_q:
            assert data['passed'] is True
            pins = data['inputs']
        else:
            assert data['qualification_complete'] is True and data['hardware_access'] is False
            assert data['case_count'] > 0
            pins = data['source_files']
        for p in pins:
            path = Path(p['path'])
            path = path if path.is_absolute() else ROOT / path
            assert sha(path) == p['sha256'], str(path)
    native = ROOT / 'docs/evidence/2026-10-09-gfx-native-shutdown-coordination.json'
    assert sha(native) == CONTRACT['native_evidence_sha256']
    assert sha(HERE / 'adt-contract.json') == CONTRACT['native_adt_sha256']
    assert sha(HERE / 'linux-dt-contract.json') == CONTRACT['linux_dt_layout_sha256']
    for name, key in (('graph-before.bin', 'graph_fixture_sha256'),
                      ('graph-receipt.json', 'graph_receipt_sha256')):
        assert sha(graph / name) == old[key], name
    make = (graph / 'Makefile').read_text()
    assert '-DGFX_NATIVE_COORDINATED_SCOPE_TRIAL' in make
    assert 'GFX_RESET_NATIVE_SEQUENCE_TRIAL' not in make
    module = graph / 'asc-graph-init.ko'
    vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
    assert vermagic.startswith(old['kernel_release'] + ' ')
    imports = subprocess.check_output(['llvm-nm', '-u', str(module)], text=True)
    assert 'apple_pmgr_t6040_gfx_snapshot' in imports
    assert '__pm_runtime_suspend' in imports and 'of_find_all_nodes' in imports
    assert 'apple_pmgr_t6040_gfx_native_probe' not in imports
    assert 'apple_pmgr_t6040_gfx_checked_pulse' not in imports
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    for name in list(receipt['graph_source_sha256']) + ['gfx-coordinate-core.h', 'gfx-coordinate-owner.h']:
        receipt['graph_source_sha256'][name] = sha(graph / name)
    trial = receipt['graph_recovery_trial']
    trial.pop('gfx_power_off_scope')
    trial['gfx_coordinated_power_off_scope'] = CONTRACT
    receipt['hardware_trial_performed'] = False
    assert validate_receipt(receipt)
    final_path.write_text(json.dumps(receipt, indent=2) + '\n')
    sources = [HERE / name for name in ('gfx_coordinate_contract.py', 'run-root-coordinate.py',
                'run-coordinate.py', 'adt-contract.json', 'linux_dt_contract.py', 'linux-dt-contract.json')]
    owner_kit = ROOT / 'experiments/t6040-gpu/gfx-native-coordinate-owner'
    preparation = {
        'schema': 'm4rch.gfx-native-coordinate-candidate-preparation.v1',
        'baseline_candidate': str(baseline), 'baseline_receipt_sha256': BASE_RECEIPT_SHA,
        'candidate': str(candidate), 'owner_sha256': sha(module), 'vermagic': vermagic,
        'candidate_receipt_sha256': sha(final_path),
        'inputs': [pin(p) for p in [native, core_q, adapter_q, args.wrapper_qualification,
                   graph / 'coordinate-owner-source-receipt.json',
                   ROOT / 'out/gfx-native-coordinate/owner-build.log', Path(__file__),
                   owner_kit / 'test-owner.py', owner_kit / 'prepare-owner.py', adapter] + sources],
        'actual_module_imports': imports.splitlines(),
        'artifact_count': len(receipt['artifact_sha256']),
        'owner_source_count': len(receipt['graph_source_sha256']),
        'other_seven_helpers_unchanged': True, 'graph_and_backing_unchanged': True,
        'source_and_build_only': True, 'module_loaded': False, 'kernel_rebuilt': False,
        'current_owner_modified': False, 'boot_configuration_changed': False,
        'next_fresh_boot_candidate_prepared': True,
        'hardware_preconditions_pending': True,
        'teardown_or_restart_verified': False, 'backing_release_qualified': False,
        'experimental_policy': 'Paired mode2 PMP/PMC notifications. Runtime native policy and external writer exclusion remain unproved.'}
    output = candidate / 'coordinate-preparation.json'
    assert not output.exists()
    output.write_text(json.dumps(preparation, indent=2) + '\n')
    print(json.dumps({'preparation': str(output), 'receipt_sha256': sha(final_path),
                      'owner_sha256': sha(module), 'hardware_actions': []}))


if __name__ == '__main__':
    main()
