#!/usr/bin/env python3
"""Actual new-family Python paths, synthetic logs and RAM; no native access."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT))
import gfx_native_powergate_contract as contract
from adt import parse
from linux_dt_contract import encoded_layout

BASE_RECEIPT = ROOT / 'out/gfx-coordinate-native-status/candidate/asc-root-envelope/build-receipt.json'
COLD_TEST = KIT / 'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA = '7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT = ROOT / 'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
OBSERVED_LAYOUT = ROOT / 'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def check(label, function, accepted):
    try:
        actual = function() is not False
    except (ValueError, KeyError, OSError):
        actual = False
    assert actual is accepted, label
    cases.append({'case': label, 'passed': True})


def replace_one(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


assert sha(BASE_RECEIPT.read_bytes()) == '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
receipt = json.loads(BASE_RECEIPT.read_text())
receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY] = copy.deepcopy(contract.CONTRACT)
root = module('powergate_actual_cold', HERE / 'run-root-powergate.py')
resident = module('powergate_actual_resident', HERE / 'run-powergate.py')
preflight = module('powergate_actual_preflight', HERE / 'preflight-fresh.py')
finalizer = module('powergate_actual_finalizer', HERE / 'finalize-powergate.py')
cases, flow_results = [], []
check('canonical-family', lambda: contract.validate_receipt(receipt), True)
check('cold-owner-parameters', lambda: root.owner_parameters(receipt, graph=True) ==
      ['run_gate=2', 'observe_ms=5000', 'resident_session=1'], True)
assert resident.COMMANDS == contract.COMMANDS == ('sample', 'gfx-snapshot', 'gfx-powergate')
for old_path, function in [('run-root-native-status.py', 'owner_parameters'), ('run-native-status.py', 'admit_command')]:
    old = runpy.run_path(str(KIT / 'gfx-coordinate-native-status' / old_path))
    check('old-native-status-refuses-' + function,
          (lambda: old[function](receipt, graph=True)) if function == 'owner_parameters' else
          (lambda: old[function]('sample', receipt, {})), False)
for family in ('gfx_native_status_execution_scope', 'gfx_coordinated_execution_scope', 'gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope'):
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial'][family] = {}
    check('mixed-family-' + family, lambda r=changed: contract.validate_receipt(r), False)
for flag in ('graph_submit_work', 'graph_power_retirement_probe', 'graph_release_on_shutdown'):
    changed = copy.deepcopy(receipt)
    changed[flag] = True
    check('forbidden-lifetime-' + flag, lambda r=changed: root.owner_parameters(r, graph=True), False)
for options in ({}, {'arena': True}, {'graph': True, 'warm_restart': True}):
    check('cold-mode-refusal-' + str(options), lambda p=options: root.owner_parameters(receipt, **p), False)
for label, value in [('missing', None), ('wrong-command', ['sample', 'gfx-snapshot', 'stop'])]:
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial'][contract.FAMILY_KEY]['commands'] = value
    check('changed-command-scope-' + label, lambda r=changed: contract.validate_receipt(r), False)


def state(**changes):
    value = dict(resident_session_active=True, powergate_ready=True,
                 operation_failed=True, powergate_attempted=False, submit_attempted=False,
                 in_flight=None, family=contract.FAMILY_KEY, operation_uncertain=False)
    value.update(changes)
    return value


for label, changes in [('diagnostic', {}), ('healthy', {'operation_failed': False}),
                       ('no-startup-proof', {'powergate_ready': False})]:
    check('powergate-' + label, lambda c=changes: resident.admit_command('gfx-powergate', receipt, state(**c)), label != 'no-startup-proof')
for field in ('powergate_attempted', 'submit_attempted', 'power_off_attempted', 'host_stop_requested',
              'gfx_reset_attempted', 'operation_uncertain', 'in_flight', 'interrupted_operation'):
    for name in contract.COMMANDS:
        check(name + '-after-' + field, lambda c=name, f=field:
              resident.admit_command(c, receipt, state(**{f: {'command': 'unknown'} if f in ('in_flight', 'interrupted_operation') else True})),
              name != 'gfx-powergate')
for name in ('stop', 'gfx-poweroff', 'control', 'recover', 'trace-off', 'submit', 'gfx-reset', 'restart', 'free', 'native-powergate'):
    check('no-old-command-' + name, lambda c=name: resident.admit_command(c, receipt, state()), False)

# Real save_json/fsync plus actual command(); open/write are intercepted.
for failure in (None, 'open', 'short', 'delivered-error', 'interrupt'):
    with tempfile.TemporaryDirectory(prefix='powergate-intent-') as directory:
        output = Path(directory)
        state_path = output / 'state.json'
        current = state()
        report = {'validated_build_receipt': receipt, 'commands': []}
        calls = []
        real_open, real_write, real_close = resident.os.open, resident.os.write, resident.os.close

        def fake_open(path, flags, *args):
            if Path(path) != resident.SYSFS / 'command':
                return real_open(path, flags, *args)
            saved = json.loads(state_path.read_text())
            attempt = json.loads((output / 'attempt.json').read_text())
            assert saved['powergate_attempted'] is True and saved['in_flight']['command'] == 'gfx-powergate'
            assert attempt['commands'][0]['stage'] == 'intent-recorded' and attempt['reboot_required'] is True
            calls.append('open')
            if failure == 'open':
                raise OSError('RAM-only open error')
            return 123456

        def fake_write(fd, payload):
            if fd != 123456:
                return real_write(fd, payload)
            assert payload == b'gfx-powergate\n'
            assert json.loads(state_path.read_text())['powergate_attempted'] is True
            calls.append('write')
            if failure == 'delivered-error':
                raise OSError('RAM-only possibly delivered write')
            if failure == 'interrupt':
                raise KeyboardInterrupt()
            return len(payload) - (failure == 'short')

        def fake_close(fd):
            if fd != 123456:
                real_close(fd)

        with patch.object(resident.os, 'open', fake_open), patch.object(resident.os, 'write', fake_write), patch.object(resident.os, 'close', fake_close):
            try:
                resident.command('gfx-powergate', output, report, current, state_path)
                assert failure is None
            except (OSError, ValueError, KeyboardInterrupt):
                assert failure is not None
        saved = json.loads(state_path.read_text())
        assert saved['powergate_attempted'] is True and saved['in_flight'] is None
        assert calls.count('open') == 1 and calls.count('write') <= 1
        assert bool(saved.get('operation_uncertain')) is (failure is not None)
        check('actual-intent-' + str(failure) + '-never-repeat', lambda: resident.admit_command('gfx-powergate', receipt, saved), False)
        for name in ('sample', 'gfx-snapshot'):
            check('actual-intent-' + str(failure) + '-' + name, lambda c=name: resident.admit_command(c, receipt, saved), True)
        cases.append({'case': 'actual-durable-intent-' + str(failure), 'passed': True, 'calls': calls})
with tempfile.TemporaryDirectory(prefix='powergate-unknown-') as directory:
    p = Path(directory) / 'state.json'
    current = state(in_flight={'command': 'gfx-powergate', 'operation_directory': 'unknown'})
    resident.seal_interrupted_operation(current, p)
    assert json.loads(p.read_text())['interrupted_operation'] == current['in_flight']
    check('sealed-unknown-never-powergate', lambda: resident.admit_command('gfx-powergate', receipt, current), False)

for label in ('terminal-complete', 'terminal-inflight', 'missing-attempt', 'malformed-attempt', 'wrong-receipt', 'complete-diagnostic'):
    with tempfile.TemporaryDirectory(prefix='powergate-history-') as directory:
        operations = Path(directory)
        child = operations / 'recorded-operation'
        child.mkdir()
        current = state(boot_id='offline-history')
        history = {'schema': 'm4rch.gfx-native-powergate-operation.v1', 'boot_id': 'offline-history',
                   'validated_build_receipt': receipt, 'requested_command': 'sample',
                   'commands': [{'command': 'sample'}], 'complete': True, 'capture_errors': []}
        if label.startswith('terminal'):
            history.update(requested_command='gfx-powergate', commands=[{'command': 'gfx-powergate', 'stage': 'intent-recorded'}],
                           complete=label == 'terminal-complete')
        if label == 'wrong-receipt':
            history['validated_build_receipt'] = {}
        if label != 'missing-attempt':
            (child / 'attempt.json').write_text('malformed' if label == 'malformed-attempt' else json.dumps(history))
        path = operations / 'state.json'
        resident.quarantine_operation_history(operations, receipt, current, path)
        check('lost-state-history-' + label, lambda: resident.admit_command('gfx-powergate', receipt, current), label == 'complete-diagnostic')
        for name in ('sample', 'gfx-snapshot'):
            check('lost-state-history-' + label + '-' + name, lambda c=name: resident.admit_command(c, receipt, current), True)
        if label != 'complete-diagnostic':
            saved = json.loads(path.read_text())
            assert saved['powergate_attempted'] if label.startswith('terminal') else saved['operation_uncertain']

for name, owner in [('cold', root), ('resident', resident)]:
    compile(owner.runner_source(), str(owner.BASE), 'exec')
    check(name + '-nonunique-insertion-refuses', lambda o=owner: o.replace_once('x x', 'x', 'y'), False)
    with tempfile.TemporaryDirectory(prefix='powergate-source-change-') as directory:
        path = Path(directory) / 'changed.py'
        path.write_bytes(owner.BASE.read_bytes() + b'\n')
        with patch.object(owner, 'BASE', path):
            check(name + '-frozen-base-change-refuses', owner.runner_source, False)

check('fresh-preflight-current-94cb-refuses', lambda: preflight.qualify_fresh_boot(contract.REFUSED_BOOT, ''), False)
check('fresh-preflight-new-boot-no-conflicts', lambda: preflight.qualify_fresh_boot('new-offline-boot', ''), True)
for name in ('asc_graph_init', 'asc_another', 'asahi_m4', 'resource_overlay', 'gfx_power_test', 'gpu_data_sample', 'm4rch_gpu_adt'):
    check('fresh-preflight-conflict-' + name, lambda n=name: preflight.qualify_fresh_boot('new-offline-boot', n + ' 0 1 - Live 0x0\n'), False)

# Source-bound full cold main replay; inherited fixture never reaches real system.
adt_raw = ADT.read_bytes()
assert sha(adt_raw) == '72f30734bb926e681fb1c759d03ad5230b2e21546f76aa7cf0a4fe190ccca0b2'
tree = parse(adt_raw)
pins = json.loads((KIT / 'gfx-native-coordinate-trial/adt-contract.json').read_text())
layout_directory = tempfile.TemporaryDirectory(prefix='powergate-linux-fixture-')
linux_base = Path(layout_directory.name)
layout_raw = OBSERVED_LAYOUT.read_bytes()
assert sha(layout_raw) == 'e2adc89815e82eba3b67b3d0b466d1c1d4a47ba94f7acbe18773403952de5759'
for row in json.loads(layout_raw):
    node = linux_base / row['node'].lstrip('/')
    node.mkdir(parents=True, exist_ok=True)
    for key, value in row['properties'].items():
        (node / key).write_bytes(bytes.fromhex(value))
assert encoded_layout(linux_base) == layout_raw
layout_report = contract.qualify_linux_dt(linux_base)
assert layout_report['flash_relocated'] is True and layout_report['exact_other_nodes'] == 311
cases.append({'case': 'actual-bounded-relocated-flash-through-bound-helper', 'passed': True})
raw = COLD_TEST.read_bytes()
assert sha(raw) == COLD_TEST_SHA
saved_test = raw.decode()
helper_source = saved_test[saved_test.index('def elf_with_note('):saved_test.index('ON_OBS = ')]
helper_source = helper_source.replace("'run-coordinate.py'", "'run-powergate.py'")
exec(compile(helper_source, str(COLD_TEST), 'exec'), globals())
flow_source = saved_test[saved_test.index('def run_flow('):saved_test.index("run_flow('retained'", saved_test.index('def run_flow('))]
flow_source = replace_one(flow_source, '            contract.qualify_linux_dt(linux_base)\n', '            return contract.qualify_linux_dt(linux_base)\n')
flow_source = flow_source.replace("'run-root-coordinate.py'", "'run-root-powergate.py'")
flow_source = replace_one(flow_source,
    "        boot = 'offline-' + label\n",
    "        boot = contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else 'offline-' + label\n")
flow_source = replace_one(flow_source,
    "        (graph / 'graph-receipt.json').write_bytes(layout)\n",
    "        (graph / 'graph-receipt.json').write_bytes(layout + (b'changed' if label == 'graph-receipt-pin-before-any-sampler' else b''))\n")
flow_source = replace_one(flow_source,
    "        if mutate_adt or mutate_linux:\n",
    "        if mutate_adt or mutate_linux or label in ('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler'):\n")
flow_source = replace_one(flow_source,
    "            if mutate_linux:\n                assert not any(row[0] == 'capture' for row in trace)\n",
    "            if mutate_linux or label in ('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler'):\n                assert not any(row[0] == 'capture' for row in trace)\n")
flow_source = replace_one(flow_source,
    "                assert report['resident_session_active'] or report['diagnostic_session_active']\n",
    "                assert report['resident_session_active'] is False and report['diagnostic_session_active'] is True\n"
    "                assert report['commands_admitted'] == list(contract.COMMANDS)\n"
    "                assert report['native_powergate_startup']['qualified'] is True\n"
    "                assert report['linux_dt_resource_layout'] == layout_report\n")
exec(compile(flow_source, str(COLD_TEST), 'exec'), globals())

ON_OBS = 'm4rch gfx-coordinate-observation: enabled=1 result=0 request_attempted=1 request_acked=0 ack_samples=0 votes_attempted=3 votes_verified=3 request_before=0 request_written=0x2000 ack_payload=0 ack_status=0 status_wait_events=0 ack_wait_events=0 ack_bypassed=1 status_payload=0 status_raw=0'
ON_ACK = ON_OBS.replace('request_acked=0', 'request_acked=1').replace('ack_samples=0', 'ack_samples=1').replace('ack_payload=0 ', 'ack_payload=0x2000 ').replace('ack_status=0 ', 'ack_status=0x2 ').replace('ack_bypassed=1', 'ack_bypassed=0').replace('status_payload=0 ', 'status_payload=1 ')
ON_OWNER = 'm4rch gfx-coordinate-owner: phase=post-active-on result=0 startup_retained=1 module_pinned=1 pmp_region=1 pmc_region=1 pmp_mapped=1 pmc_mapped=1 on_attempted=1 on_complete=1 off_attempted=0 off_complete=0 held=1 started=0 retirement_verified=0'
ROOT_PUBLISHED, MAPPED = 'G16S root sent to EP32', '69 object pages mapped'
RETAINED = 'm4rch gfx-native-coordinate: startup-retained result=-11 consumer=1 held=1 module_pinned=1 started=0 root_published=0 cleanup_attempted=0'
READY = 'm4rch gfx-native-powergate-session: ready=1 initial_recovery_failed=1 initial_completed_cycles=0 startup_work_submitted=0'
DIAGNOSTIC = 'm4rch recovery-session: diagnostic=1 sealed=1 control_ready=0 work_submitted=0 allocations_retained=1; only sample/gfx-snapshot and one terminal gfx-powergate allowed'
HEALTHY = 'm4rch recovery-session: resident=1 control_ready=0 work_submitted=0 allocations_retained=1; only sample/gfx-snapshot and one terminal gfx-powergate allowed'


def positive(obs=ON_OBS, cycles=0, failed=1):
    marker = READY.replace('initial_recovery_failed=1', 'initial_recovery_failed=' + str(failed)).replace('initial_completed_cycles=0', 'initial_completed_cycles=' + str(cycles))
    return '\n'.join([obs, ON_OWNER, DIAGNOSTIC if failed else HEALTHY, marker, ROOT_PUBLISHED, MAPPED]) + '\n'


POSITIVE = positive()
for label, log in [('diagnostic0-status0', POSITIVE), ('diagnostic1-status0', positive(cycles=1)),
                   ('healthy2-status0', positive(cycles=2, failed=0)), ('diagnostic0-ack', positive(obs=ON_ACK))]:
    run_flow(label, log, 'positive')
for label, log in [
    ('missing-ready', POSITIVE.replace(READY, '')), ('duplicate-ready', POSITIVE + READY + '\n'),
    ('missing-session', POSITIVE.replace(DIAGNOSTIC, '')), ('duplicate-session', POSITIVE + DIAGNOSTIC + '\n'),
    ('contradictory-ready-field', POSITIVE.replace(READY, READY + ' startup_work_submitted=1')),
    ('malformed-ready-field', POSITIVE.replace('initial_completed_cycles=0', 'initial_completed_cycles=0bad')),
    ('unexpected-ready-field', POSITIVE.replace(READY, READY + ' new=1')),
    ('wrong-ready', POSITIVE.replace('ready=1', 'ready=0')), ('work-published', POSITIVE.replace('startup_work_submitted=0', 'startup_work_submitted=1')),
    ('diagnostic-two-cycles', positive(cycles=2)), ('healthy-zero-cycles', positive(cycles=0, failed=0)),
    ('contradictory-session', POSITIVE.replace(DIAGNOSTIC, HEALTHY)),
    ('session-duplicate-field', POSITIVE.replace('control_ready=0', 'control_ready=0 control_ready=1')),
    ('missing-on', POSITIVE.replace(ON_OBS, '')), ('duplicate-on', POSITIVE + ON_OBS + '\n'),
    ('missing-owner', POSITIVE.replace(ON_OWNER, '')), ('missing-root', POSITIVE.replace(ROOT_PUBLISHED, '')),
    ('partial-votes', POSITIVE.replace('votes_verified=3', 'votes_verified=2')),
    ('status0-claimed-ack', POSITIVE.replace('request_acked=0', 'request_acked=1')),
    ('native-unknown-with-success-text', POSITIVE + 'm4rch gfx-native-powergate-startup-retained: phase=after-start result=-5 unknown=1 commands_allowed=0 started=1 root_published=1 context_retained=1 held=1 pages_present=174 pages_expected=174 allocations_released=0 restart_allowed=0 dma_retirement_verified=0\n'),
    ('native-malformed-unknown-with-success-text', POSITIVE + 'm4rch gfx-native-powergate-startup-retained: malformed fields\n'),
]:
    run_flow(label, log, 'startup-outcome-unqualified')
run_flow('retained-before-firmware', RETAINED + '\n', 'startup-retained-before-firmware')
run_flow('module-absent', '', 'cold-load-module-absent-unqualified', module_present=False)
run_flow('loaded-note-mismatch', POSITIVE, failure=True, note=b'changed')
run_flow('insmod-nonzero-success-text', POSITIVE, 'startup-outcome-unqualified', returncode=1)
run_flow('loaded-owner-zero-ref', POSITIVE, 'startup-outcome-unqualified', refcount=0)
run_flow('layout-change-before-any-sampler', '', failure=True, mutate_linux=True)
run_flow('current-94cb-before-any-sampler', '', failure=True)
run_flow('graph-receipt-pin-before-any-sampler', '', failure=True)
for pin in pins:
    def mutate_adt(saved, p=pin):
        value = saved[p['node']][p['name']]
        saved[p['node']][p['name']] = bytes([value[0] ^ 1]) + value[1:]
    run_flow('adt-selection-' + pin['name'], '', failure=True, mutate_adt=mutate_adt)

# Actual resident validate(), with exact ELF note + original cold proof and
# every non-whitelisted system path rejected. No fake validation callback.
with tempfile.TemporaryDirectory(prefix='powergate-resident-validation-') as directory:
    work = Path(directory)
    graph, build = work / 'asc-graph-init', work / 'asc-root-envelope'
    session = graph / 'boot-offline-resident'
    session.mkdir(parents=True)
    build.mkdir()
    fixture = copy.deepcopy(receipt)
    fixture['artifact_sha256'] = {'asc-graph-init/asc-graph-init.ko': sha(module_image)}
    fixture['graph_source_sha256'] = {'test-source.h': sha(b'bound source')}
    fixture['kernel_notes_sha256'] = sha(b'kernel-note')
    (graph / 'test-source.h').write_bytes(b'bound source')
    (graph / 'asc-graph-init.ko').write_bytes(module_image)
    (graph / 'graph-before.bin').write_bytes((ROOT / 'out/gfx-coordinate-native-status/candidate/asc-graph-init/graph-before.bin').read_bytes())
    (graph / 'graph-receipt.json').write_bytes((ROOT / 'out/gfx-coordinate-native-status/candidate/asc-graph-init/graph-receipt.json').read_bytes())
    (build / 'build-receipt.json').write_text(json.dumps(fixture))
    before = 'before\n'
    logs = before + POSITIVE
    (session / 'dmesg-before.log').write_text(before)
    (session / 'dmesg-after.log').write_text(logs)
    (session / 'text.bin').write_bytes(b'firmware-text-evidence')
    original = {'boot_id': 'offline-resident', 'diagnostic_session_active': True, 'resident_session_active': False,
        'load_returncode': 0, 'module_present': True, 'validated_build_receipt': fixture,
        'text_sha256': sha(b'firmware-text-evidence'), 'dmesg_after_sha256': sha(logs.encode()),
        'dmesg_before_sha256': sha(before.encode()),
        'root_published': True, 'mapping_or_publication_performed': True, 'commands_admitted': list(contract.COMMANDS)}
    original['native_powergate_startup'] = contract.qualify_powergate_startup(POSITIVE, original, 0, 1)
    (session / 'attempt.json').write_text(json.dumps(original))
    real_read_bytes, real_read_text = Path.read_bytes, Path.read_text
    real_exists, real_is_dir = Path.exists, Path.is_dir
    native_bytes = {'/sys/kernel/notes': b'kernel-note', str(resident.MODULE / 'notes/.note.gnu.build-id'): build_note}
    native_text = {str(resident.MODULE / 'refcnt'): '1', str(resident.MODULE / 'parameters/resident_session'): 'Y',
                   str(resident.MODULE / 'parameters/run_gate'): '2'}
    allowed_exists = {str(resident.SYSFS / p): True for p in ['command', 'objects', 'owned', 'notifications']}

    def read_bytes(path):
        if str(path).startswith(('/sys/', '/proc/')):
            assert str(path) in native_bytes, 'Forbidden resident native byte read'
            return native_bytes[str(path)]
        return real_read_bytes(path)

    def read_text(path, *args, **kwargs):
        if str(path).startswith(('/sys/', '/proc/')):
            assert str(path) in native_text, 'Forbidden resident native text read'
            return native_text[str(path)]
        return real_read_text(path, *args, **kwargs)

    def exists(path):
        if str(path).startswith(('/sys/', '/proc/')):
            assert str(path) in allowed_exists
            return allowed_exists[str(path)]
        return real_exists(path)

    def is_dir(path):
        if str(path).startswith(('/sys/', '/proc/')):
            assert path == resident.MODULE
            return True
        return real_is_dir(path)

    with patch.object(Path, 'read_bytes', read_bytes), patch.object(Path, 'read_text', read_text), patch.object(Path, 'exists', exists), patch.object(Path, 'is_dir', is_dir), patch.object(resident.os, 'uname', lambda: SimpleNamespace(release=fixture['kernel_release'])):
        check('actual-resident-validate-positive', lambda: resident.validate(work, 'offline-resident'), True)
        for key, value in [('boot_id', 'other'), ('load_returncode', 1), ('module_present', False),
                           ('commands_admitted', ['sample', 'gfx-snapshot', 'stop']), ('native_powergate_startup', None),
                           ('dmesg_after_sha256', '0' * 64), ('dmesg_before_sha256', '0' * 64), ('text_sha256', '0' * 64)]:
            changed = dict(original, **{key: value})
            (session / 'attempt.json').write_text(json.dumps(changed))
            check('actual-resident-attempt-change-' + key, lambda: resident.validate(work, 'offline-resident'), False)
        (session / 'attempt.json').write_text(json.dumps(original))
        for key in native_bytes:
            saved = native_bytes[key]
            native_bytes[key] = b'changed'
            check('actual-resident-native-note-change-' + key, lambda: resident.validate(work, 'offline-resident'), False)
            native_bytes[key] = saved
        for key, bad in [(str(resident.MODULE / 'refcnt'), '0'), (str(resident.MODULE / 'parameters/run_gate'), '1'),
                         (str(resident.MODULE / 'parameters/resident_session'), 'N')]:
            saved = native_text[key]
            native_text[key] = bad
            check('actual-resident-native-parameter-change-' + key, lambda: resident.validate(work, 'offline-resident'), False)
            native_text[key] = saved
        for name in ('command', 'objects', 'owned', 'notifications'):
            allowed_exists[str(resident.SYSFS / name)] = False
            check('actual-resident-missing-interface-' + name, lambda: resident.validate(work, 'offline-resident'), False)
            allowed_exists[str(resident.SYSFS / name)] = True
        for path in [graph / 'test-source.h', graph / 'graph-before.bin', graph / 'graph-receipt.json']:
            saved = path.read_bytes()
            path.write_bytes(saved + b'x')
            check('actual-resident-pin-change-' + path.name, lambda: resident.validate(work, 'offline-resident'), False)
            path.write_bytes(saved)

        native_text['/proc/sys/kernel/random/boot_id'] = 'offline-resident'
        allowed_exists[str(resident.MODULE)] = True
        operations = session / 'resident-operations'
        native_command_calls = []
        real_open, real_write, real_close = resident.os.open, resident.os.write, resident.os.close

        def main_open(path, flags, *args):
            if Path(path) != resident.SYSFS / 'command':
                return real_open(path, flags, *args)
            saved = json.loads((operations / 'state.json').read_text())
            assert saved['in_flight']['command'] in contract.COMMANDS
            if saved['in_flight']['command'] == 'gfx-powergate':
                assert saved['powergate_attempted'] is True
            native_command_calls.append('open')
            return 123456

        def main_write(fd, data):
            if fd != 123456:
                return real_write(fd, data)
            native_command_calls.append(data.decode().strip())
            return len(data)

        def main_close(fd):
            if fd != 123456:
                real_close(fd)

        capture_mode = 'success'

        def main_capture(destination, observed_receipt, report):
            assert observed_receipt == fixture
            if capture_mode == 'error':
                report['capture_errors'].append('RAM-only missing capture')
            return {'notifications': {'status_flags': 1 if capture_mode == 'journal-error' else 0},
                    'objects': {'bytes': 69 * 0x4000}, 'owned': {'bytes': 174 * 0x4000}}

        with patch.object(resident.os, 'geteuid', lambda: 0), patch.object(resident.os, 'open', main_open), patch.object(resident.os, 'write', main_write), patch.object(resident.os, 'close', main_close), patch.object(resident.subprocess, 'check_output', lambda *args, **kw: 'RAM-only log'), patch.object(resident, 'capture', main_capture), contextlib.redirect_stdout(io.StringIO()):
            # First management operation succeeds as a host syscall only; no
            # synthetic management ACK or physical success is claimed.
            with patch.object(resident.sys, 'argv', ['run-powergate.py', str(work), 'gfx-powergate']):
                resident.main()
            stored = json.loads((operations / 'state.json').read_text())
            assert stored['powergate_attempted'] is True and stored['family'] == contract.FAMILY_KEY
            cases.append({'case': 'actual-resident-main-powergate-durable-terminal', 'passed': True})
            before_calls = len(native_command_calls)
            with patch.object(resident.sys, 'argv', ['run-powergate.py', str(work), 'gfx-powergate']):
                check('actual-resident-main-repeat-before-open-refused', resident.main, False)
            assert len(native_command_calls) == before_calls
            with patch.object(resident.sys, 'argv', ['run-powergate.py', str(work), 'gfx-snapshot']):
                resident.main()
            cases.append({'case': 'actual-resident-main-post-intent-diagnostics', 'passed': True})
            # Loss of state cannot erase the command report. A later sample
            # rebuilds only a quarantined state and leaves the attempt sealed.
            (operations / 'state.json').unlink()
            with patch.object(resident.sys, 'argv', ['run-powergate.py', str(work), 'sample']):
                resident.main()
            assert json.loads((operations / 'state.json').read_text())['powergate_attempted'] is True
            cases.append({'case': 'actual-resident-main-missing-state-preserves-terminal-history', 'passed': True})
            for mode in ('error', 'journal-error'):
                capture_mode = mode
                with patch.object(resident.sys, 'argv', ['run-powergate.py', str(work), 'sample']):
                    if mode == 'error':
                        check('actual-resident-main-capture-failure-refused', resident.main, False)
                    else:
                        resident.main()
                assert json.loads((operations / 'state.json').read_text())['operation_uncertain'] is True
                cases.append({'case': 'actual-resident-main-' + mode + '-seals-management', 'passed': True})

# Actual candidate metadata and qualification readers reject changed pins.
with tempfile.TemporaryDirectory(prefix='powergate-metadata-') as directory:
    work = Path(directory)
    (work / 'asc-root-envelope').mkdir()
    (work / 'asc-graph-init').mkdir()
    (work / 'artifact').write_bytes(b'artifact')
    (work / 'asc-graph-init/test.h').write_bytes(b'source')
    (work / 'asc-graph-init/graph-before.bin').write_bytes(b'graph')
    (work / 'asc-graph-init/graph-receipt.json').write_bytes(b'layout')
    fixture = copy.deepcopy(receipt)
    fixture['artifact_sha256'] = {'asc-graph-init/asc-graph-init.ko': sha(b'artifact')}
    (work / 'asc-graph-init/asc-graph-init.ko').write_bytes(b'artifact')
    fixture['graph_source_sha256'] = {'test.h': sha(b'source')}
    fixture['graph_fixture_sha256'], fixture['graph_receipt_sha256'] = sha(b'graph'), sha(b'layout')
    rpath = work / 'asc-root-envelope/build-receipt.json'
    rpath.write_text(json.dumps(fixture))
    prep = {'schema': 'm4rch.gfx-native-powergate-preparation.v1', 'candidate_receipt_sha256': sha(rpath.read_bytes()),
        'selected_next_hardware_candidate': True, 'hardware_actions': [], 'owner_sha256': sha(b'artifact'),
        'inputs': [{'path': str(work / 'artifact'), 'sha256': sha(b'artifact')}], 'analysis_input_pins': []}
    (work / 'powergate-preparation.json').write_text(json.dumps(prep))
    check('actual-preflight-candidate-positive', lambda: preflight.validate_candidate(work), True)
    for path in [work / 'artifact', work / 'asc-graph-init/test.h', work / 'asc-graph-init/graph-before.bin', work / 'asc-graph-init/graph-receipt.json', work / 'asc-graph-init/asc-graph-init.ko']:
        saved = path.read_bytes()
        path.write_bytes(saved + b'x')
        check('actual-preflight-pin-change-' + path.name, lambda: preflight.validate_candidate(work), False)
        path.write_bytes(saved)
    qpath = work / 'qualification.json'
    q = {'passed': True, 'hardware_access': False, 'case_count': 1, 'inputs': prep['inputs']}
    qpath.write_text(json.dumps(q))
    check('actual-finalizer-bound-qualification-positive', lambda: finalizer.check_qualification(qpath), True)
    for key, value in [('passed', False), ('hardware_access', True), ('case_count', 0), ('inputs', [])]:
        qpath.write_text(json.dumps(dict(q, **{key: value})))
        check('actual-finalizer-qualification-refusal-' + key, lambda: finalizer.check_qualification(qpath), False)
    qpath.write_text(json.dumps(q))
    (work / 'artifact').write_bytes(b'changed')
    check('actual-finalizer-qualification-source-change', lambda: finalizer.check_qualification(qpath), False)

bound = [Path(__file__), HERE / 'gfx_native_powergate_contract.py', HERE / 'run-root-powergate.py',
         HERE / 'run-powergate.py', HERE / 'preflight-fresh.py', HERE / 'finalize-powergate.py',
         KIT / 'gfx-coordinate-native-status/gfx_native_status_contract.py',
         KIT / 'gfx-coordinate-native-status/run-root-native-status.py', KIT / 'gfx-coordinate-native-status/run-native-status.py',
         KIT / 'gfx-coordinate-native-status/flash-layout-guard.py',
         KIT / 'gfx-native-coordinate-trial/gfx_coordinate_contract.py',
         KIT / 'gfx-native-coordinate-trial/linux_dt_contract.py', KIT / 'gfx-native-coordinate-trial/adt-contract.json',
         KIT / 'gfx-native-coordinate-trial/linux-dt-contract.json', COLD_TEST, BASE_RECEIPT, ADT, OBSERVED_LAYOUT,
         HERE / 'gfx-native-powergate.h', HERE / 'prepare-powergate-owner.py',
         ROOT / 'out/gfx-native-powergate/prepared-owner-v5/powergate-owner-source-receipt.json',
         ROOT / 'out/gfx-native-powergate/owner-qualification-final-v5.json']
result = {'schema': 'm4rch.gfx-native-powergate-wrapper-qualification.v1', 'passed': True,
    'hardware_access': False, 'case_count': len(cases), 'cases': cases, 'actual_main_flow_count': len(flow_results),
    'actual_main_flows': flow_results, 'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p.read_bytes())} for p in bound],
    'transformed_cold_runner_sha256': sha(root.runner_source().encode()),
    'transformed_resident_runner_sha256': sha(resident.runner_source().encode()),
    'transformed_cold_mock_sha256': sha(flow_source.encode()), 'flash_resource_report': layout_report,
    'limits': ['All system paths, subprocess and sysfs writes intercepted; no GPU operation or actual ACK.',
               'The full cold fixture elides optional owned/journal decoding; exact startup admission is exercised.',
               'No powergate success, native policy equivalence, DMA retirement, safe restart or rendering proof.',
               'Candidate finalizer subprocess/build-import checks await the actual separately built module.']}
if len(sys.argv) != 2:
    raise SystemExit('Usage: test-powergate-runners.py NEW_OUTPUT_JSON')
output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
with output.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
layout_directory.cleanup()
print(f'{len(cases)} actual wrapper cases passed; {len(flow_results)} cold-main flows; no hardware.')
