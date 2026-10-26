#!/usr/bin/env python3
"""Exercise real wrapper admission and durable intent without hardware access."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
from gfx_poweroff_contract import CONTRACT, validate_receipt


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, KIT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


root = module('root_poweroff', 'run-root-poweroff.py')
resident = module('resident_poweroff', 'run-poweroff.py')
base = KIT.parent.parent.parent / 'out/gfx-native-reset-owner/candidate/asc-root-envelope/build-receipt.json'
receipt = json.loads(base.read_text())
del receipt['graph_recovery_trial']['gfx_reset_scope']
receipt['graph_recovery_trial']['gfx_power_off_scope'] = copy.deepcopy(CONTRACT)
receipt['kernel_gfx_power_off_api'] = receipt.pop('kernel_gfx_reset_api')
cases = []


def check(label, function, allowed):
    error = None
    try:
        function()
    except (ValueError, OSError, KeyboardInterrupt) as caught:
        error = caught
    assert (error is None) == allowed, (label, error, allowed)
    cases.append({'case': label, 'passed': True})


state = dict(submit_attempted=False, operation_failed=True, in_flight=None,
             resident_session_active=True, host_stop_requested=False)
check('valid-contract', lambda: validate_receipt(receipt), True)
for key in CONTRACT:
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial']['gfx_power_off_scope'][key] = None
    check('changed-contract-' + key, lambda c=changed: validate_receipt(c), False)
old = json.loads(base.read_text())
check('old-reset-owner-rejected', lambda: root.owner_parameters(old, graph=True), False)
check('old-reset-resident-rejected', lambda: resident.admit_command('sample', old, state), False)
check('actual-cold-parameters', lambda: root.owner_parameters(receipt, graph=True), True)
assert root.owner_parameters(receipt, graph=True) == ['run_gate=2', 'observe_ms=5000', 'resident_session=1']
for options in ({}, {'arena': True}, {'graph': True, 'arena': True}, {'graph': True, 'warm_restart': True}):
    check('invalid-startup-' + str(options), lambda o=options: root.owner_parameters(receipt, **o), False)
for name in ('control', 'recover', 'trace-off', 'submit', 'gfx-reset', 'warm-restart', 'unknown'):
    check('untyped-command-' + name, lambda n=name: resident.admit_command(n, receipt, state), False)
for name in resident.COMMANDS:
    check('before-stop-' + name, lambda n=name: resident.admit_command(n, receipt, state), name != 'gfx-poweroff')
stopped = dict(state, host_stop_requested=True)
for name in resident.COMMANDS:
    check('after-stop-' + name, lambda n=name: resident.admit_command(n, receipt, stopped), True)
for variation in ({'power_off_attempted': True}, {'in_flight': {'command': 'stop'}},
                  {'interrupted_operation': {'command': 'stop'}}):
    closed = dict(stopped, **variation)
    for name in resident.COMMANDS:
        check('sealed-' + str(variation) + '-' + name,
              lambda n=name, s=closed: resident.admit_command(n, receipt, s),
              name in ('sample', 'gfx-snapshot'))
for name in resident.COMMANDS:
    check('work-excludes-' + name, lambda n=name: resident.admit_command(n, receipt, dict(stopped, submit_attempted=True)), False)

real_open, real_write, real_close = resident.os.open, resident.os.write, resident.os.close
for failure in ('none', 'open', 'write', 'short', 'interrupt'):
    with tempfile.TemporaryDirectory(prefix='gfx-off-wrapper-') as directory:
        output = Path(directory)
        state_path = output / 'state.json'
        trial = copy.deepcopy(stopped)
        report = {'commands': [], 'validated_build_receipt': receipt}
        writes = []

        def fake_open(path, flags, *args):
            if Path(path) == resident.SYSFS / 'command':
                saved = json.loads(state_path.read_text())
                assert saved['power_off_attempted'] and saved['operation_failed']
                assert saved['in_flight']['command'] == 'gfx-poweroff'
                assert json.loads((output / 'attempt.json').read_text())['commands'][0]['stage'] == 'intent-recorded'
                if failure == 'open':
                    raise OSError('simulated open error')
                return 123456
            return real_open(path, flags, *args)

        def fake_write(fd, payload):
            if fd != 123456:
                return real_write(fd, payload)
            writes.append(payload)
            if failure == 'write':
                raise OSError('simulated write error')
            if failure == 'interrupt':
                raise KeyboardInterrupt('simulated interruption')
            return len(payload) - (failure == 'short')

        def fake_close(fd):
            if fd != 123456:
                return real_close(fd)

        with patch.object(resident.os, 'open', fake_open), patch.object(resident.os, 'write', fake_write), patch.object(resident.os, 'close', fake_close):
            check('durable-off-' + failure,
                  lambda: resident.command('gfx-poweroff', output, report, trial, state_path),
                  failure == 'none')
        assert len(writes) <= 1
        assert trial['power_off_attempted'] and trial['operation_failed'] and trial['in_flight'] is None
        check('no-second-off-' + failure,
              lambda: resident.admit_command('gfx-poweroff', receipt, trial), False)
        check('no-stop-after-off-' + failure,
              lambda: resident.admit_command('stop', receipt, trial), False)
        check('diagnostics-after-off-' + failure,
              lambda: resident.admit_command('sample', receipt, trial), True)

with tempfile.TemporaryDirectory(prefix='gfx-off-interrupted-') as directory:
    path = Path(directory) / 'state.json'
    interrupted = dict(stopped, in_flight={'command': 'gfx-poweroff'}, power_off_attempted=True)
    resident.seal_interrupted_operation(interrupted, path)
    assert interrupted['interrupted_operation'] == {'command': 'gfx-poweroff'}
    resident.admit_command('sample', receipt, interrupted)
    assert interrupted['in_flight'] and interrupted['operation_failed']
    check('interrupted-intent-never-erased', lambda: resident.admit_command('gfx-poweroff', receipt, interrupted), False)

files = [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in sorted(KIT.glob('*.py'))]
result = {'schema': 'm4rch.gfx-power-off-wrapper-qualification.v1',
          'hardware_access': False, 'qualification_complete': True,
          'case_count': len(cases), 'cases': cases, 'source_files': files,
          'qualification': 'Real Python admission and simulated sysfs intent/write handling; no actual PM, MMIO or firmware effect.'}
(KIT / 'wrapper-qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(str(len(cases)) + ' actual-wrapper admission and durable-intent cases passed; no hardware access.')
