#!/usr/bin/env python3
"""Replay actual distinct wrappers with intercepted native access and temp RAM."""
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
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT))
import gfx_native_status_contract as contract
from adt import parse
from linux_dt_contract import encoded_layout

EXECUTION_TEST = KIT / 'gfx-coordinate-execution/test-execution-runners.py'
EXECUTION_TEST_SHA = 'cb9e9a8c910872a643be8fdef14bc63f6647450fe46f8350ead3e5c86f110ae5'
COLD_TEST = KIT / 'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA = '7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT = REPO / 'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
ADT_SHA = '72f30734bb926e681fb1c759d03ad5230b2e21546f76aa7cf0a4fe190ccca0b2'
OBSERVED_LAYOUT = REPO / 'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
OBSERVED_LAYOUT_SHA = 'e2adc89815e82eba3b67b3d0b466d1c1d4a47ba94f7acbe18773403952de5759'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_one(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


raw = EXECUTION_TEST.read_bytes()
assert sha(raw) == EXECUTION_TEST_SHA
source = raw.decode()
source = source[:source.index("result = {'schema':")]
source = replace_one(source, 'from gfx_execution_contract import CONTRACT, validate_receipt',
                     'from gfx_native_status_contract import CONTRACT, validate_receipt')
source = replace_one(source, "'run-execution.py'", "'run-native-status.py'")
source = replace_one(source, "'run-root-execution.py'", "'run-root-native-status.py'")
source = source.replace("'gfx_coordinated_execution_scope'", "'gfx_native_status_execution_scope'")
source = replace_one(source,
    "for key in ('gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope'):",
    "for key in ('gfx_coordinated_execution_scope', 'gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope'):")
env = {'__name__': 'native_status_inherited_execution_test',
       '__file__': str(HERE / 'inherited-execution-test-context.py')}
exec(compile(source, str(EXECUTION_TEST), 'exec'), env)
cases = env['cases']
check = env['check']
receipt = env['receipt']
inherited_count = len(cases)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


root = module('native_status_actual_cold', HERE / 'run-root-native-status.py')
resident = module('native_status_actual_resident', HERE / 'run-native-status.py')
flow_results = []
for key in contract.CONTRACT:
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial'][contract.FAMILY_KEY][key] = None
    check('changed-distinct-contract-' + key,
          lambda item=changed: root.owner_parameters(item, graph=True), False)
for options in ({}, {'arena': True}, {'graph': True, 'arena': True},
                {'graph': True, 'warm_restart': True}):
    check('invalid-cold-parameters-' + str(options),
          lambda item=options: root.owner_parameters(receipt, **item), False)
for key in ('graph_submit_work', 'graph_power_retirement_probe', 'graph_release_on_shutdown'):
    changed = copy.deepcopy(receipt)
    changed[key] = True
    check('forbidden-cold-owner-flag-' + key,
          lambda item=changed: root.owner_parameters(item, graph=True), False)
adt_raw = ADT.read_bytes()
assert sha(adt_raw) == ADT_SHA
tree = parse(adt_raw)
pins = json.loads((KIT / 'gfx-native-coordinate-trial/adt-contract.json').read_text())
check('saved-all-twelve-adt-selection-pins', lambda: contract.qualify_adt(tree), True)
for pin in pins:
    for change in ('missing', 'length', 'byte'):
        changed = copy.deepcopy(tree)
        target = changed[pin['node']]
        saved = target[pin['name']]
        if change == 'missing':
            del target[pin['name']]
        elif change == 'length':
            target[pin['name']] = saved[:-1]
        else:
            target[pin['name']] = bytes([saved[0] ^ 1]) + saved[1:]
        check('adt-' + change + '-' + pin['node'] + '/' + pin['name'],
              lambda item=changed: contract.qualify_adt(item), False)

# Frozen execution/no-work wrappers must refuse the canonical new receipt.
for label, path in [('execution', 'gfx-coordinate-execution/run-root-execution.py'),
                    ('coordinate', 'gfx-native-coordinate-trial/run-root-coordinate.py')]:
    old = runpy.run_path(str(KIT / path))
    check('new-canonical-receipt-old-' + label + '-cold-refuses',
          lambda owner=old: owner['owner_parameters'](receipt, graph=True), False)
for label, path in [('execution', 'gfx-coordinate-execution/run-execution.py'),
                    ('coordinate', 'gfx-native-coordinate-trial/run-coordinate.py')]:
    old = runpy.run_path(str(KIT / path))
    state = dict(resident_session_active=True, completed_idle_cycles=4,
                 trace_disabled=True, submit_attempted=False, operation_failed=False,
                 power_off_attempted=False, in_flight=None)
    check('new-canonical-receipt-old-' + label + '-resident-refuses',
          lambda owner=old: owner['admit_command']('sample', receipt, state), False)

linux_fixture_directory = tempfile.TemporaryDirectory(prefix='native-status-of-layout-')
linux_base = Path(linux_fixture_directory.name)
layout_raw = OBSERVED_LAYOUT.read_bytes()
assert sha(layout_raw) == OBSERVED_LAYOUT_SHA
for item in json.loads(layout_raw):
    node = linux_base / item['node'].lstrip('/')
    node.mkdir(parents=True, exist_ok=True)
    for key, value in item['properties'].items():
        (node / key).write_bytes(bytes.fromhex(value))
assert encoded_layout(linux_base) == layout_raw
layout_report = contract.qualify_linux_dt(linux_base)
assert layout_report['flash_relocated'] is True
assert layout_report['exact_other_nodes'] == 311
assert layout_report['normalized_sha256'] == 'cd8aa099cda21fcd8dab8278d65145546b26311f2c8d67139fb83bf921371f8c'
cases.append({'case': 'actual-saved-relocated-layout-through-wrapper-helper', 'passed': True})
with tempfile.TemporaryDirectory(prefix='native-status-layout-bound-source-') as directory:
    changed = Path(directory)
    (changed / 'flash-layout-guard.py').write_bytes((HERE / 'flash-layout-guard.py').read_bytes() + b'\n')
    with patch.object(contract, 'HERE', changed):
        check('changed-flash-guard-sha-refuses', lambda: contract.qualify_linux_dt(linux_base), False)
    (changed / 'gfx-native-coordinate-trial').mkdir()
    (changed / 'gfx-native-coordinate-trial/linux-dt-contract.json').write_bytes(
        (KIT / 'gfx-native-coordinate-trial/linux-dt-contract.json').read_bytes() + b' ')
    with patch.object(contract, 'BASE_KIT', changed):
        check('changed-layout-baseline-sha-refuses', lambda: contract.qualify_linux_dt(linux_base), False)

# Reuse the exact full-main mock body qualified for the frozen coordinator;
# only update the fixture caller name and persist the returned layout report.
raw = COLD_TEST.read_bytes()
assert sha(raw) == COLD_TEST_SHA
cold_source = raw.decode()
start = cold_source.index('def elf_with_note(')
end = cold_source.index('ON_OBS = ', start)
helper_source = cold_source[start:end].replace("'run-coordinate.py'", "'run-native-status.py'")
exec(compile(helper_source, str(COLD_TEST), 'exec'), globals())
start = cold_source.index('def run_flow(')
end = cold_source.index("run_flow('retained'", start)
flow_source = cold_source[start:end]
flow_source = replace_one(flow_source, '            contract.qualify_linux_dt(linux_base)\n',
                         '            return contract.qualify_linux_dt(linux_base)\n')
flow_source = replace_one(flow_source,
    "            report = json.loads((output / 'attempt.json').read_text())\n",
    "            report = json.loads((output / 'attempt.json').read_text())\n            assert report['linux_dt_resource_layout'] == layout_report\n")
flow_source = flow_source.replace("'run-root-coordinate.py'", "'run-root-native-status.py'")
exec(compile(flow_source, str(COLD_TEST), 'exec'), globals())

MARKER = 'm4rch gfx-native-coordinate: startup-retained result='
RETAINED = MARKER + '-11 consumer=1 held=1 module_pinned=1 started=0 root_published=0 cleanup_attempted=0'
ON_OBS = 'm4rch gfx-coordinate-observation: enabled=1 result=0 request_attempted=1 request_acked=1 ack_samples=1 votes_attempted=3 votes_verified=3 request_before=0x100000000 request_written=0x100002000 ack_payload=0x100002000 ack_status=0x2 status_wait_events=0 ack_wait_events=0 ack_bypassed=0 status_payload=0x1 status_raw=0'
BYPASS_ZERO = ON_OBS.replace('request_acked=1', 'request_acked=0').replace('ack_samples=1', 'ack_samples=0').replace('ack_payload=0x100002000', 'ack_payload=0').replace('ack_status=0x2', 'ack_status=0').replace('ack_bypassed=0', 'ack_bypassed=1').replace('status_payload=0x1', 'status_payload=0')
BYPASS_PRIOR = BYPASS_ZERO.replace('ack_samples=0', 'ack_samples=3').replace('ack_payload=0 ', 'ack_payload=0x100000000 ').replace('ack_status=0 ', 'ack_status=0x2 ')
BYPASS_INVALID_RAW = BYPASS_PRIOR.replace('ack_payload=0x100000000', 'ack_payload=0x100002000').replace('ack_status=0x2', 'ack_status=0')
ON_OWNER = 'm4rch gfx-coordinate-owner: phase=post-active-on result=0 startup_retained=1 module_pinned=1 pmp_region=1 pmc_region=1 pmp_mapped=1 pmc_mapped=1 on_attempted=1 on_complete=1 off_attempted=0 off_complete=0 held=1 started=0 retirement_verified=0'
RESIDENT = 'm4rch recovery-session: resident=1 control_ready=1'
DIAGNOSTIC = 'm4rch recovery-session: diagnostic=1 sealed=1'
ROOT_PUBLISHED = 'G16S root sent to EP32'
MAPPED = str(receipt['graph_object_pages']) + ' object pages mapped'


def positive(obs=ON_OBS, marker=RESIDENT):
    return '\n'.join((obs, ON_OWNER, marker, ROOT_PUBLISHED, MAPPED)) + '\n'


POSITIVE = positive()
for label, obs in [('ack', ON_OBS), ('status0-no-ack', BYPASS_ZERO),
                   ('status0-prior-unmatched', BYPASS_PRIOR),
                   ('status0-prior-invalid-raw', BYPASS_INVALID_RAW)]:
    run_flow('qualified-resident-' + label, positive(obs), 'positive')
    run_flow('qualified-diagnostic-' + label, positive(obs, DIAGNOSTIC), 'positive')
run_flow('retained', RETAINED + '\n', 'startup-retained-before-firmware')
run_flow('retained-with-success-looking-records', RETAINED + '\n' + POSITIVE.replace(ROOT_PUBLISHED, '').replace(MAPPED, ''), 'startup-retained-before-firmware')
for label, log in [
    ('no-marker', ''),
    ('root-and-resident-only', RESIDENT + '\n' + ROOT_PUBLISHED + '\n'),
    ('missing-observation', POSITIVE.replace(ON_OBS, '')),
    ('missing-owner', POSITIVE.replace(ON_OWNER, '')),
    ('missing-resident', POSITIVE.replace(RESIDENT, '')),
    ('missing-root', POSITIVE.replace(ROOT_PUBLISHED, '')),
    ('missing-mapping', POSITIVE.replace(MAPPED, '')),
    ('duplicate-observation', POSITIVE + ON_OBS + '\n'),
    ('duplicate-owner', POSITIVE + ON_OWNER + '\n'),
    ('contradictory-ack', POSITIVE.replace('request_acked=1', 'request_acked=0')),
    ('partial-votes', POSITIVE.replace('votes_verified=3', 'votes_verified=2')),
    ('malformed-ack', POSITIVE.replace('request_acked=1', 'request_acked=1bad')),
    ('bypass-missing-latest-status', positive(BYPASS_ZERO.replace('status_payload=0', ''))),
    ('bypass-contradictory-acked', positive(BYPASS_ZERO.replace('request_acked=0', 'request_acked=1'))),
    ('bypass-prior-matched', positive(BYPASS_PRIOR.replace('ack_payload=0x100000000', 'ack_payload=0x100002000'))),
    ('bypass-unobserved-ack-word', positive(BYPASS_ZERO.replace('ack_status=0 ', 'ack_status=0x2 '))),
]:
    run_flow(label, log, 'startup-outcome-unqualified')
for label, log, options in [
    ('duplicate-retained', RETAINED + '\n' + RETAINED + '\n', {}),
    ('retained-started', RETAINED.replace('started=0', 'started=1') + '\n', {}),
    ('retained-mapped', RETAINED + '\n69 object pages mapped\n', {}),
    ('retained-root', RETAINED + '\n' + ROOT_PUBLISHED + '\n', {}),
    ('retained-note-mismatch', RETAINED + '\n', {'note': b'wrong-note'}),
    ('retained-no-reference', RETAINED + '\n', {'refcount': 0}),
    ('retained-insmod-failed', RETAINED + '\n', {'returncode': 1}),
    ('positive-note-mismatch', POSITIVE, {'note': b'wrong-note'}),
]:
    run_flow(label, log, failure=True, **options)
run_flow('positive-insmod-failed', POSITIVE, 'startup-outcome-unqualified', returncode=1)
run_flow('positive-no-ref', POSITIVE, 'startup-outcome-unqualified', refcount=0)
run_flow('module-absent-empty', '', 'cold-load-module-absent-unqualified', module_present=False)
run_flow('module-absent-success-looking', POSITIVE, 'cold-load-module-absent-unqualified', module_present=False)
run_flow('changed-linux-layout-before-any-sampler', '', failure=True, mutate_linux=True)
for pin in pins:
    def change_pin(saved_tree, p=pin):
        original = saved_tree[p['node']][p['name']]
        saved_tree[p['node']][p['name']] = bytes([original[0] ^ 1]) + original[1:]
    run_flow('adt-refusal-' + pin['name'], '', failure=True, mutate_adt=change_pin)

bound = [Path(__file__), HERE / 'gfx_native_status_contract.py',
         HERE / 'run-root-native-status.py', HERE / 'run-native-status.py',
         HERE / 'flash-layout-guard.py', EXECUTION_TEST, COLD_TEST,
         KIT / 'gfx-coordinate-execution/gfx_execution_contract.py',
         KIT / 'gfx-coordinate-execution/run-root-execution.py',
         KIT / 'gfx-coordinate-execution/run-execution.py',
         KIT / 'gfx-native-coordinate-trial/gfx_coordinate_contract.py',
         KIT / 'gfx-native-coordinate-trial/linux_dt_contract.py',
         KIT / 'gfx-native-coordinate-trial/linux-dt-contract.json',
         KIT / 'gfx-native-coordinate-trial/adt-contract.json', ADT, OBSERVED_LAYOUT]
result = {
    'schema': 'm4rch.gfx-native-status-wrapper-qualification.v1',
    'passed': True, 'hardware_access': False, 'case_count': len(cases),
    'inherited_execution_cases': inherited_count, 'actual_main_flow_count': len(flow_results),
    'cases': cases, 'actual_main_flows': flow_results,
    'transformed_execution_test_sha256': sha(source.encode()),
    'transformed_full_main_mock_sha256': sha(flow_source.encode()),
    'transformed_cold_runner_sha256': sha(root.runner_source().encode()),
    'transformed_resident_runner_sha256': sha(resident.runner_source().encode()),
    'inputs': [{'path': str(item.relative_to(REPO)), 'sha256': sha(item.read_bytes())} for item in bound],
    'flash_resource_report': layout_report,
    'limits': [
        'All native system access, insmod, MMIO samplers, graph sysfs and command writes were intercepted. No hardware result.',
        'Full-main fixture elides optional joined-owned and receive decoding; existing healthy receive worker remains a separate execution requirement.',
        'Software observation parsing does not prove native runtime mode, PMP/PMC readiness, causality, retirement, repeated recovery or rendered pixels.',
        'STATUS0 bypass is not acknowledged REQ and is not evidence of inactivity.',
        'Strict old wrappers are untouched; the canonical new family is refused by them.',
    ],
}
if len(sys.argv) != 2:
    raise SystemExit('Usage: test-native-status-runners.py NEW_OUTPUT_JSON')
destination = Path(sys.argv[1])
destination.parent.mkdir(parents=True, exist_ok=True)
with destination.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
linux_fixture_directory.cleanup()
print(f'{len(cases)} actual wrapper cases passed; {len(flow_results)} cold-main flows; no hardware.')
