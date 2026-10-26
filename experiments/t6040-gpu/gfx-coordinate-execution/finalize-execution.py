#!/usr/bin/env python3
"""Bind separately built execution owner and unchanged draw; no hardware action."""
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
from gfx_execution_contract import CONTRACT, validate_receipt

BASE_RECEIPT_SHA = '0afe3eed85958b124be56e7ed4c0f76595bf8271c016c44d47c4903ebe5a669c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('candidate', type=Path)
    ap.add_argument('owner_qualification', type=Path)
    ap.add_argument('wrapper_qualification', type=Path)
    ap.add_argument('build_log', type=Path)
    args = ap.parse_args()
    candidate = args.candidate.resolve()
    baseline = ROOT / 'out/gfx-native-coordinate/candidate'
    base_path = baseline / 'asc-root-envelope/build-receipt.json'
    assert sha(base_path) == BASE_RECEIPT_SHA
    base = json.loads(base_path.read_text())
    graph = candidate / 'asc-graph-init'
    for name, expected in base['artifact_sha256'].items():
        assert sha(baseline / name) == expected
        if name != 'asc-graph-init/asc-graph-init.ko':
            assert sha(candidate / name) == expected, name
    for name, expected in base['graph_source_sha256'].items():
        assert sha(baseline / 'asc-graph-init' / name) == expected
        if name not in ('recovery-cycle.h', 'Makefile'):
            assert sha(graph / name) == expected, name
    for name, key in [('graph-before.bin', 'graph_fixture_sha256'),
                      ('graph-receipt.json', 'graph_receipt_sha256')]:
        assert sha(graph / name) == base[key]
    analysis_inputs = [
        ('asc-graph-init/preparation.json', 'c22c59c0735c84554f954f581f94978894a9c78e87b6ec06f8f7ba8c763580db'),
        ('analysis-inputs/target-receipt.json', 'c6008f792f60569d9ff186168c397a90b221586bd6f30cb6190647232441befa')]
    for name, expected in analysis_inputs:
        assert sha(candidate / name) == expected, name
    draw = json.loads((graph / 'preparation.json').read_text())
    assert draw['pages'] == 56 and draw['data_sha256'] == sha(graph / 'backing.bin')
    assert draw['target_receipt_sha256'] == analysis_inputs[1][1]
    analysis_tools = [
        ROOT / 'experiments/t6040-gpu/analyze-owned-work.py',
        ROOT / 'experiments/t6040-gpu/check-first-render-readback.py',
        HERE / 'analyze-execution.py']
    assert sha(analysis_tools[0]) == '3a3bb4447c02a60d161c156beca6709b25a710b6800dd0142138b036f976558f'
    assert sha(analysis_tools[1]) == 'e5fe5791767e205af97667a751783ce7ec00624330f3c2eeacd53dd70514afc6'
    for qpath in (args.owner_qualification, args.wrapper_qualification):
        q = json.loads(qpath.read_text())
        assert q['passed'] is True and q['hardware_access'] is False and q['case_count'] > 0
        for row in q['inputs']:
            assert sha(Path(row['path'])) == row['sha256'], row['path']
    source_receipt = graph / 'execution-owner-source-receipt.json'
    source = json.loads(source_receipt.read_text())
    assert source['hardware_actions'] == []
    for row in source['output_source_pins']:
        assert sha(graph / row['name']) == row['sha256'], row['name']
    make = (graph / 'Makefile').read_text()
    assert '-DGFX_COORDINATED_EXECUTION_TRIAL' in make
    assert '-DGFX_NATIVE_COORDINATED_SCOPE_TRIAL' in make
    assert 'GFX_RESET_NATIVE_SEQUENCE_TRIAL' not in make
    module = graph / 'asc-graph-init.ko'
    vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
    assert vermagic.startswith(base['kernel_release'] + ' ')
    imports = subprocess.check_output(['llvm-nm', '-u', str(module)], text=True)
    assert 'apple_pmgr_t6040_gfx_snapshot' in imports and '__pm_runtime_suspend' in imports
    assert 'of_find_all_nodes' in imports
    assert 'apple_pmgr_t6040_gfx_native_probe' not in imports
    assert 'apple_pmgr_t6040_gfx_checked_pulse' not in imports
    receipt = copy.deepcopy(base)
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    for name in receipt['graph_source_sha256']:
        receipt['graph_source_sha256'][name] = sha(graph / name)
    trial = receipt['graph_recovery_trial']
    trial.pop('gfx_coordinated_power_off_scope')
    trial['gfx_coordinated_execution_scope'] = CONTRACT
    assert validate_receipt(receipt)
    output = candidate / 'asc-root-envelope/build-receipt.json'
    assert not output.exists()
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    preparation = {
        'schema': 'm4rch.gfx-coordinate-execution-preparation.v1',
        'baseline_candidate': str(baseline), 'baseline_receipt_sha256': BASE_RECEIPT_SHA,
        'candidate': str(candidate), 'candidate_receipt_sha256': sha(output),
        'owner_sha256': sha(module), 'vermagic': vermagic,
        'inputs': [pin(path) for path in [base_path, source_receipt, args.owner_qualification,
                   args.wrapper_qualification, args.build_log, Path(__file__),
                   ROOT / 'docs/evidence/2026-10-09-gfx-native-coordinate-preparation.json'] +
                  [HERE / name for name in ['gfx_execution_contract.py', 'run-root-execution.py', 'run-execution.py']]],
        'actual_module_imports': imports.splitlines(),
        'artifact_count': len(receipt['artifact_sha256']),
        'owner_source_count': len(receipt['graph_source_sha256']),
        'analysis_input_pins': [{'relative': name, 'sha256': expected} for name, expected in analysis_inputs],
        'analysis_tool_pins': [pin(path) for path in analysis_tools],
        'graph_and_draw_unchanged': True, 'other_seven_helpers_unchanged': True,
        'frozen_idle_candidate_unchanged': True, 'hardware_actions': [],
        'module_loaded': False, 'kernel_rebuilt': False, 'boot_configuration_changed': False,
        'hardware_preconditions_pending': True,
        'selected_next_hardware_candidate': False,
        'recovery_teardown_rendering_verified': False,
        'qualification': 'Built contingency execution variant only. The frozen no-work coordinated trial remains next. Four actual idle recovery cycles and native trace-off are mandatory before the existing single draw; work intent closes OFF/STOP and new publication. No reset/restart/free/unload.'}
    prepared = candidate / 'execution-preparation.json'
    with prepared.open('x') as stream:
        json.dump(preparation, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'preparation': str(prepared), 'owner_sha256': sha(module),
                      'receipt_sha256': sha(output), 'hardware_actions': []}))


if __name__ == '__main__':
    main()
