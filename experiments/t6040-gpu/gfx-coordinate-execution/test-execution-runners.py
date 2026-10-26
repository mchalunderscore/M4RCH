#!/usr/bin/env python3
"""Exercise actual execution wrapper admission and durable intent in temp RAM."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from gfx_execution_contract import CONTRACT, validate_receipt
from gfx_coordinate_contract import validate_receipt as validate_idle

resident = runpy.run_path(str(HERE / 'run-execution.py'))
cold = runpy.run_path(str(HERE / 'run-root-execution.py'))
receipt = json.loads((ROOT / 'out/gfx-native-coordinate/candidate/asc-root-envelope/build-receipt.json').read_text())
assert hashlib.sha256((ROOT / 'out/gfx-native-coordinate/candidate/asc-root-envelope/build-receipt.json').read_bytes()).hexdigest() == '0afe3eed85958b124be56e7ed4c0f76595bf8271c016c44d47c4903ebe5a669c'
receipt['graph_recovery_trial'].pop('gfx_coordinated_power_off_scope')
receipt['graph_recovery_trial']['gfx_coordinated_execution_scope'] = copy.deepcopy(CONTRACT)
cases = []


def check(label, function, accepted):
    try:
        result = function()
        actual = result is not False
    except (ValueError, KeyError):
        actual = False
    assert actual == accepted, label
    cases.append({'case': label, 'passed': True})


def state(**changes):
    result = dict(submit_attempted=False, power_off_attempted=False,
                  operation_failed=False, in_flight=None, completed_idle_cycles=2,
                  trace_disabled=False, resident_session_active=True)
    result.update(changes)
    return result


check('distinct-contract', lambda: validate_receipt(receipt), True)
check('idle-wrapper-refuses-execution', lambda: validate_idle(receipt), False)
check('cold-parameters-unchanged', lambda: cold['owner_parameters'](receipt, graph=True) ==
      ['run_gate=2', 'observe_ms=5000', 'resident_session=1'], True)
for key in ('gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope'):
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial'][key] = {}
    check('mixed-' + key, lambda r=changed: validate_receipt(r), False)
for label, changes in [
    ('two-cycles', {}), ('three-cycles', {'completed_idle_cycles': 3}),
    ('trace-still-on', {'completed_idle_cycles': 4}),
    ('ready', {'completed_idle_cycles': 4, 'trace_disabled': True})]:
    check('submit-' + label, lambda c=changes: resident['admit_command']('submit', receipt, state(**c)), label == 'ready')
for command in resident['COMMANDS']:
    for label, changes in [('work', {'submit_attempted': True}),
                           ('off', {'power_off_attempted': True}),
                           ('unknown', {'interrupted_operation': {'command': 'recover'}}),
                           ('inflight', {'in_flight': {'command': 'recover'}})]:
        check(command + '-after-' + label,
              lambda c=command, s=changes: resident['admit_command'](c, receipt, state(**s)),
              command in ('sample', 'gfx-snapshot'))
for command in ('control', 'recover', 'trace-off', 'submit'):
    for label, changes in [('failed', {'operation_failed': True}),
                           ('stopped', {'host_stop_requested': True})]:
        check(command + '-' + label,
              lambda c=command, s=changes: resident['admit_command'](c, receipt, state(**s)), False)
check('off-no-stop', lambda: resident['admit_command']('gfx-poweroff', receipt, state()), False)
check('off-diagnostic-after-confirmed-stop', lambda: resident['admit_command']('gfx-poweroff', receipt,
      state(operation_failed=True, host_stop_requested=True)), True)
check('stop-repeat-refuses', lambda: resident['admit_command']('stop', receipt,
      state(host_stop_requested=True)), False)
for command in ('gfx-reset', 'restart', 'INIT', 'free'):
    check('unknown-' + command, lambda c=command: resident['admit_command'](c, receipt, state()), False)

# Execute the actual sysfs-write function with mocked syscalls. Every intent
# is read from its durable state file when the fake open/write is reached.
for name, initial, failure in [
    ('recover', state(), None), ('trace-off', state(completed_idle_cycles=4), None),
    ('submit', state(completed_idle_cycles=4, trace_disabled=True), None),
    ('submit', state(completed_idle_cycles=4, trace_disabled=True), 'open'),
    ('submit', state(completed_idle_cycles=4, trace_disabled=True), 'short'),
    ('submit', state(completed_idle_cycles=4, trace_disabled=True), 'interrupt'),
    ('gfx-poweroff', state(operation_failed=True, host_stop_requested=True), None),
    ('gfx-poweroff', state(operation_failed=True, host_stop_requested=True), 'open')]:
    with tempfile.TemporaryDirectory(prefix='gfx-execution-wrapper-') as directory:
        output = Path(directory)
        report = {'validated_build_receipt': receipt, 'commands': []}
        path = output / 'state.json'
        command = resident['command']
        calls = []
        real_open, real_write, real_close = resident['os'].open, resident['os'].write, resident['os'].close

        def fake_open(target, flags, *args):
            if Path(target) != resident['SYSFS'] / 'command':
                return real_open(target, flags, *args)
            saved = json.loads(path.read_text())
            assert saved['in_flight']['command'] == name
            assert name != 'submit' or saved['submit_attempted'] is True
            assert name != 'gfx-poweroff' or saved['power_off_attempted'] is True
            calls.append('open')
            if failure == 'open':
                raise OSError('mock open failure')
            return 123456

        def fake_write(fd, payload):
            if fd != 123456:
                return real_write(fd, payload)
            calls.append('write')
            if failure == 'interrupt':
                raise KeyboardInterrupt()
            return len(payload) - (1 if failure == 'short' else 0)

        def fake_close(fd):
            if fd != 123456:
                return real_close(fd)

        with patch.object(resident['os'], 'open', fake_open), patch.object(resident['os'], 'write', fake_write), patch.object(resident['os'], 'close', fake_close):
            try:
                command(name, output, report, initial, path)
                assert failure is None
            except (OSError, ValueError, KeyboardInterrupt):
                assert failure is not None
        assert calls.count('open') == 1 and calls.count('write') <= 1
        saved = json.loads(path.read_text())
        assert saved['in_flight'] is None
        if name == 'submit':
            assert saved['submit_attempted'] is True
        if name == 'gfx-poweroff':
            assert saved['power_off_attempted'] is True
        if failure:
            assert saved['operation_failed'] is True
        if name == 'recover' and not failure:
            assert saved['completed_idle_cycles'] == 4
        if name == 'trace-off' and not failure:
            assert saved['trace_disabled'] is True
        cases.append({'case': name + '-actual-intent-' + str(failure), 'passed': True})

for label, module in [('cold', cold), ('resident', resident)]:
    function = module['runner_source']
    compile(function(), str(module['BASE']), 'exec')
    check(label + '-nonunique-transform-refuses', lambda m=module: m['replace_once']('x x', 'x', 'y'), False)
    with tempfile.TemporaryDirectory(prefix='gfx-execution-base-') as directory:
        changed = Path(directory) / 'changed.py'
        changed.write_bytes(module['BASE'].read_bytes() + b'\n')
        old = function.__globals__['BASE']
        try:
            function.__globals__['BASE'] = changed
            check(label + '-base-change-refuses', function, False)
        finally:
            function.__globals__['BASE'] = old

result = {'schema': 'm4rch.gfx-coordinate-execution-wrapper-qualification.v1',
          'passed': True, 'case_count': len(cases), 'cases': cases,
          'inputs': [{'path': str((HERE / name).resolve()), 'sha256': hashlib.sha256((HERE / name).read_bytes()).hexdigest()}
                     for name in ['gfx_execution_contract.py', 'run-root-execution.py', 'run-execution.py', Path(__file__).name]],
          'hardware_access': False,
          'limitations': 'Actual admission/write functions with mocked sysfs. Cold-load guards inherit the frozen coordinated runner qualification; no new native startup, recovery, completion, retirement or rendering result.'}
if len(sys.argv) != 2:
    raise SystemExit('Usage: test-execution-runners.py NEW_OUTPUT_JSON')
with Path(sys.argv[1]).open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(f'{len(cases)} execution wrapper cases passed; no hardware access.')
