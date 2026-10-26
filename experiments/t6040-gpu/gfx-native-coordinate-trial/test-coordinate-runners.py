#!/usr/bin/env python3
"""Qualify actual paired wrappers with RAM/temp-file mocks; never native access."""
import contextlib
import copy
import hashlib
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
REPO = KIT.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT))
import gfx_coordinate_contract as contract
from adt import parse
from linux_dt_contract import encoded_layout

OLD_QUALIFIER = KIT / 'gfx-poweroff-trial/test-runners.py'
OLD_QUALIFIER_SHA = '726d0707f61e23ab37addba2f9b028a1d39c0760e713947e3d458c968dfb0c29'
ADT = REPO / 'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
ADT_SHA = '72f30734bb926e681fb1c759d03ad5230b2e21546f76aa7cf0a4fe190ccca0b2'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def transformed_qualifier():
    raw = OLD_QUALIFIER.read_bytes()
    assert sha(raw) == OLD_QUALIFIER_SHA, 'Frozen inherited qualifier changed'
    source = raw.decode()
    replacements = [
        ('from gfx_poweroff_contract import CONTRACT, validate_receipt',
         'from gfx_coordinate_contract import CONTRACT, validate_receipt'),
        ("'run-root-poweroff.py'", "'run-root-coordinate.py'"),
        ("'run-poweroff.py'", "'run-coordinate.py'"),
    ]
    for old, new in replacements:
        assert source.count(old) == 1
        source = source.replace(old, new, 1)
    source = source.replace("'gfx_power_off_scope'", "'gfx_coordinated_power_off_scope'")
    # Preserve all actual tests, but aggregate their result into our receipt.
    tail = "files = [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}"
    assert source.count(tail) == 1
    return source[:source.index(tail)]


inherited_source = transformed_qualifier()
environment = {'__name__': 'paired_wrapper_qualification', '__file__': str(HERE / 'inherited-test-context.py')}
exec(compile(inherited_source, str(OLD_QUALIFIER), 'exec'), environment)
root = environment['root']
resident = environment['resident']
receipt = environment['receipt']
cases = environment['cases']
check = environment['check']
inherited_count = len(cases)
flow_results = []

# Compilation is of the actual generated code, with no modification of a runner.
for label, module in [('cold', root), ('resident', resident)]:
    compile(module.runner_source(), str(module.BASE), 'exec')
    cases.append({'case': label + '-actual-transformed-code-compiles', 'passed': True})
    with tempfile.TemporaryDirectory(prefix='coordinate-base-pin-') as directory:
        changed = Path(directory) / 'base.py'
        changed.write_bytes(module.BASE.read_bytes() + b'\n# changed\n')
        with patch.object(module, 'BASE', changed):
            check(label + '-changed-base-sha-refuses', module.runner_source, False)
check('cold-nonunique-transform-point-refuses', lambda: root.replace_once('x x', 'x', 'y'), False)
check('cold-missing-transform-point-refuses', lambda: root.replace_once('z', 'x', 'y'), False)

# Both old wrappers are loaded as definitions only; family isolation is symmetric.
old_root = runpy.run_path(str(KIT / 'gfx-poweroff-trial/run-root-poweroff.py'))
old_resident = runpy.run_path(str(KIT / 'gfx-poweroff-trial/run-poweroff.py'))
old_receipt = copy.deepcopy(receipt)
old_receipt['graph_recovery_trial'].pop('gfx_coordinated_power_off_scope')
old_receipt['graph_recovery_trial']['gfx_power_off_scope'] = copy.deepcopy(contract.BASE_CONTRACT)
state = dict(resident_session_active=True, host_stop_requested=True,
             submit_attempted=False, operation_failed=False, in_flight=None)
for name, item in [('old', old_receipt), ('absent', dict(receipt, graph_recovery_trial={}))]:
    check(name + '-receipt-new-cold-refuses', lambda r=item: root.owner_parameters(r, graph=True), False)
    check(name + '-receipt-new-resident-refuses', lambda r=item: resident.admit_command('sample', r, state), False)
check('new-receipt-old-cold-refuses', lambda: old_root['owner_parameters'](receipt, graph=True), False)
check('new-receipt-old-resident-refuses', lambda: old_resident['admit_command']('sample', receipt, state), False)
for name, value in [('gfx_power_off_scope', contract.BASE_CONTRACT),
                    ('gfx_reset_scope', {})]:
    mixed = copy.deepcopy(receipt)
    mixed['graph_recovery_trial'][name] = value
    check('mixed-' + name + '-new-cold-refuses', lambda r=mixed: root.owner_parameters(r, graph=True), False)
    check('mixed-' + name + '-new-resident-refuses', lambda r=mixed: resident.admit_command('sample', r, state), False)
mixed_legacy = copy.deepcopy(receipt)
mixed_legacy['graph_recovery_trial']['gfx_power_off_scope'] = copy.deepcopy(contract.BASE_CONTRACT)
# Historical code ignores this future key. This is an observed limit, not an
# admission offered by either paired wrapper or by the canonical new receipt.
check('observed-limit-frozen-legacy-cold-accepts-hand-mixed-scope',
      lambda: old_root['owner_parameters'](mixed_legacy, graph=True), True)
check('observed-limit-frozen-legacy-resident-accepts-hand-mixed-scope',
      lambda: old_resident['admit_command']('sample', mixed_legacy, state), True)
for key in ('graph_submit_work', 'graph_power_retirement_probe', 'graph_release_on_shutdown'):
    changed = copy.deepcopy(receipt)
    changed[key] = True
    check('forbidden-owner-flag-' + key, lambda r=changed: root.owner_parameters(r, graph=True), False)
for key, value in [('resident_session', False)]:
    changed = copy.deepcopy(receipt)
    changed['graph_recovery_trial'][key] = value
    check('missing-retained-owner-' + key, lambda r=changed: root.owner_parameters(r, graph=True), False)
assert root.owner_parameters(receipt, graph=True) == ['run_gate=2', 'observe_ms=5000', 'resident_session=1']
cases.append({'case': 'owner-parameters-exact-gate-and-resident-no-extra-flags', 'passed': True})

adt_raw = ADT.read_bytes()
assert sha(adt_raw) == ADT_SHA
tree = parse(adt_raw)
check('all-twelve-saved-adt-pins-qualify', lambda: contract.qualify_adt(tree), True)
pins = json.loads((HERE / 'adt-contract.json').read_text())
assert len(pins) == 12
for pin in pins:
    label = pin['node'] + '/' + pin['name']
    for change in ('byte', 'missing', 'length'):
        modified = copy.deepcopy(tree)
        node = modified[pin['node']]
        if change == 'missing':
            del node[pin['name']]
        elif change == 'length':
            node[pin['name']] = node[pin['name']][:-1]
        else:
            value = bytearray(node[pin['name']])
            value[0] ^= 1
            node[pin['name']] = bytes(value)
        check('adt-' + change + '-refuses-' + label,
              lambda t=modified: contract.qualify_adt(t), False)
with tempfile.TemporaryDirectory(prefix='coordinate-adt-contract-') as directory:
    changed = Path(directory)
    (changed / 'adt-contract.json').write_bytes((HERE / 'adt-contract.json').read_bytes() + b' ')
    with patch.object(contract, 'HERE', changed):
        check('changed-adt-contract-sha-refuses', lambda: contract.qualify_adt(tree), False)

linux_fixture_directory = tempfile.TemporaryDirectory(prefix='coordinate-of-layout-')
linux_base = Path(linux_fixture_directory.name)
linux_layout_raw = (HERE / 'linux-dt-contract.json').read_bytes()
linux_layout = json.loads(linux_layout_raw)
assert len(linux_layout) == 312
for node in linux_layout:
    directory = linux_base / node['node'].lstrip('/')
    directory.mkdir(parents=True, exist_ok=True)
    for key, value in node['properties'].items():
        (directory / key).write_bytes(bytes.fromhex(value))
assert encoded_layout(linux_base) == linux_layout_raw
check('exact-312-node-linux-of-layout-qualifies', lambda: contract.qualify_linux_dt(linux_base), True)
for key in ('#address-cells', '#size-cells', 'reg', 'ranges', 'compatible', 'status', 'device_type'):
    selected = next(node for node in linux_layout if key in node['properties'])
    filename = linux_base / selected['node'].lstrip('/') / key
    saved = filename.read_bytes()
    for mutation in ('changed', 'missing'):
        try:
            if mutation == 'missing':
                filename.unlink()
            else:
                filename.write_bytes(bytes([saved[0] ^ 1]) + saved[1:] if saved else b'\0\0\0\0')
            check('linux-layout-' + mutation + '-' + key,
                  lambda: contract.qualify_linux_dt(linux_base), False)
        finally:
            filename.write_bytes(saved)
for key, value in [('dma-ranges', struct.pack('>QQQ', 0, 0, 0x1000)),
                   ('assigned-addresses', struct.pack('>QQ', 0x5003c0000, 0x1000)),
                   ('device_type', b'pci\0')]:
    filename = linux_base / key
    try:
        filename.write_bytes(value)
        check('linux-layout-new-' + key, lambda: contract.qualify_linux_dt(linux_base), False)
    finally:
        filename.unlink()
alias = linux_base / 'coordinate-unexpected-alias@5003c0000'
alias.mkdir()
(alias / 'reg').write_bytes(struct.pack('>QQ', 0x5003c0000, 0x30000))
(alias / 'status').write_bytes(b'okay\0')
check('linux-layout-new-available-pmp-alias', lambda: contract.qualify_linux_dt(linux_base), False)
(alias / 'reg').unlink()
(alias / 'status').unlink()
alias.rmdir()
for key, value in [('reg', b'\0'), ('ranges', b'\0'), ('dma-ranges', b'\0'),
                   ('assigned-addresses', b'\0'), ('#address-cells', b'\0'),
                   ('#size-cells', struct.pack('>I', 5))]:
    filename = linux_base / key
    saved = filename.read_bytes() if filename.exists() else None
    try:
        filename.write_bytes(value)
        check('linux-layout-malformed-' + key, lambda: contract.qualify_linux_dt(linux_base), False)
    finally:
        if saved is None:
            filename.unlink()
        else:
            filename.write_bytes(saved)
with tempfile.TemporaryDirectory(prefix='coordinate-of-pin-') as directory:
    pinned = Path(directory)
    (pinned / 'linux-dt-contract.json').write_bytes(linux_layout_raw + b' ')
    with patch.object(contract, 'HERE', pinned):
        check('linux-layout-contract-hash-refuses', lambda: contract.qualify_linux_dt(linux_base), False)
# Non-resource properties are explicitly outside the normalized layout.
(linux_base / 'unrelated-test-property').write_bytes(b'offline-only')
check('linux-layout-unselected-property-has-no-resource-effect', lambda: contract.qualify_linux_dt(linux_base), True)
(linux_base / 'unrelated-test-property').unlink()

MARKER = 'm4rch gfx-native-coordinate: startup-retained result='
RETAINED = MARKER + '-11 consumer=1 held=1 module_pinned=1 started=0 root_published=0 cleanup_attempted=0'
clean_report = {'root_published': False, 'mapping_or_publication_performed': False}
check('retained-startup-qualified', lambda: contract.qualify_startup_retention([RETAINED], 0, 1, clean_report), True)
qualified = contract.qualify_startup_retention([RETAINED], 0, 1, clean_report)
assert qualified['own_pm_reference_retained'] and qualified['startup_before_firmware_verified']
assert not qualified['backing_release_qualified'] and not qualified['restart_qualified']
assert qualified['reboot_required'] and qualified['startup_coordination_result'] == -11
for label, lines, returncode, refcount, report in [
    ('missing-record', [], 0, 1, clean_report),
    ('two-records', [RETAINED, RETAINED], 0, 1, clean_report),
    ('failed-insmod', [RETAINED], 1, 1, clean_report),
    ('zero-reference', [RETAINED], 0, 0, clean_report),
    ('negative-reference', [RETAINED], 0, -1, clean_report),
    ('root-published', [RETAINED], 0, 1, dict(clean_report, root_published=True)),
    ('mapping-performed', [RETAINED], 0, 1, dict(clean_report, mapping_or_publication_performed=True)),
    ('missing-result', [RETAINED.replace('result=-11 ', '')], 0, 1, clean_report),
    ('zero-result', [RETAINED.replace('result=-11', 'result=0')], 0, 1, clean_report),
    ('positive-result', [RETAINED.replace('result=-11', 'result=1')], 0, 1, clean_report),
]:
    check('retention-' + label, lambda l=lines, r=returncode, f=refcount, p=report:
          contract.qualify_startup_retention(l, r, f, p), False)
for key, value in [('consumer', '1'), ('held', '1'), ('module_pinned', '1'),
                   ('started', '0'), ('root_published', '0'), ('cleanup_attempted', '0')]:
    for mutation in ('missing', 'wrong'):
        bad = RETAINED.replace(key + '=' + value,
                               '' if mutation == 'missing' else key + '=' + ('0' if value == '1' else '1'))
        check('retention-' + mutation + '-' + key,
              lambda b=bad: contract.qualify_startup_retention([b], 0, 1, clean_report), False)
for label, bad in [
    ('duplicate-contradictory', RETAINED + ' started=1 started=0'),
    ('duplicate-equal', RETAINED + ' started=0'),
    ('partial-hex-token', RETAINED.replace('started=0', 'started=0x1')),
    ('partial-decimal-token', RETAINED.replace('started=0', 'started=0bad')),
]:
    check('retention-' + label, lambda b=bad:
          contract.qualify_startup_retention([b], 0, 1, clean_report), False)
for key in ('root_published', 'mapping_or_publication_performed'):
    absent_report = dict(clean_report)
    absent_report.pop(key)
    check('retention-missing-report-' + key, lambda r=absent_report:
          contract.qualify_startup_retention([RETAINED], 0, 1, r), False)
    for value in (None, 0, '', 'false'):
        bad_report = dict(clean_report, **{key: value})
        check('retention-nonboolean-report-' + key + '-' + repr(value), lambda r=bad_report:
              contract.qualify_startup_retention([RETAINED], 0, 1, r), False)


def elf_with_note(note=b'\x04\0\0\0\x08\0\0\0\x03\0\0\0GNU\0PAIRNOTE'):
    names = b'\0.shstrtab\0.note.gnu.build-id\0'
    table = 64
    name_offset = table + 3 * 64
    note_offset = name_offset + len(names)
    blob = bytearray(note_offset + len(note))
    blob[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<Q', blob, 40, table)
    struct.pack_into('<HHH', blob, 58, 64, 3, 1)
    struct.pack_into('<IIQQQQIIQQ', blob, table + 64, 1, 3, 0, 0, name_offset, len(names), 0, 0, 1, 0)
    struct.pack_into('<IIQQQQIIQQ', blob, table + 128, 11, 7, 0, 0, note_offset, len(note), 0, 0, 4, 0)
    blob[name_offset:note_offset] = names
    blob[note_offset:] = note
    return bytes(blob), note


module_image, build_note = elf_with_note()
note_reader = runpy.run_path(str(HERE / 'run-coordinate.py'))['module_build_note']
assert note_reader(module_image) == build_note
cases.append({'case': 'thin-resident-run-path-exposes-actual-gnu-note-reader', 'passed': True})
check('module-note-truncated-header-refuses', lambda: note_reader(module_image[:8]), False)
check('module-note-truncated-section-refuses', lambda: note_reader(module_image[:100]), False)
check('module-note-missing-refuses', lambda: note_reader(module_image.replace(b'.note.gnu.build-id', b'.note.not.build-id')), False)

ON_OBS = 'm4rch gfx-coordinate-observation: enabled=1 result=0 request_attempted=1 request_acked=1 ack_samples=1 votes_attempted=3 votes_verified=3 request_before=0x100000000 request_written=0x100002000 ack_payload=0x100002000 ack_status=0x2 status_wait_events=0 ack_wait_events=0'
ON_OWNER = 'm4rch gfx-coordinate-owner: phase=post-active-on result=0 startup_retained=1 module_pinned=1 pmp_region=1 pmc_region=1 pmp_mapped=1 pmc_mapped=1 on_attempted=1 on_complete=1 off_attempted=0 off_complete=0 held=1 started=0 retirement_verified=0'
RESIDENT = 'm4rch recovery-session: resident=1 control_ready=1'
DIAGNOSTIC = 'm4rch recovery-session: diagnostic=1 sealed=1'
ROOT_PUBLISHED = 'G16S root sent to EP32'
MAPPED = str(receipt['graph_object_pages']) + ' object pages mapped'
POSITIVE = '\n'.join((ON_OBS, ON_OWNER, RESIDENT, ROOT_PUBLISHED, MAPPED)) + '\n'


def graph_check(label, observations, owners, *, allowed=False, returncode=0,
                refcount=1, report=None):
    if report is None:
        report = {'root_published': True, 'mapping_or_publication_performed': True}
    assert contract.qualify_graph_startup(observations, owners, returncode, refcount, report) is allowed, label
    cases.append({'case': 'graph-startup-' + label, 'passed': True})


graph_check('canonical-actual-adapter-fields', [ON_OBS], [ON_OWNER], allowed=True)
for label, observations, owners in [
    ('missing-observation', [], [ON_OWNER]), ('duplicate-observation', [ON_OBS, ON_OBS], [ON_OWNER]),
    ('missing-owner', [ON_OBS], []), ('duplicate-owner', [ON_OBS], [ON_OWNER, ON_OWNER]),
    ('failed-plus-successful-observation', [ON_OBS, ON_OBS.replace('result=0', 'result=-5')], [ON_OWNER]),
    ('duplicate-ack-field', [ON_OBS + ' request_acked=0'], [ON_OWNER]),
    ('duplicate-owner-field', [ON_OBS], [ON_OWNER + ' on_complete=0']),
    ('malformed-ack-token', [ON_OBS.replace('request_acked=1', 'request_acked=1junk')], [ON_OWNER]),
    ('raw-ack-wrong-bit', [ON_OBS.replace('ack_status=0x2', 'ack_status=0x40000000000000')], [ON_OWNER]),
    ('zero-ack-status', [ON_OBS.replace('ack_status=0x2', 'ack_status=0')], [ON_OWNER]),
    ('wrong-ack-target', [ON_OBS.replace('ack_payload=0x100002000', 'ack_payload=0x100000000')], [ON_OWNER]),
    ('wrong-request-target', [ON_OBS.replace('request_written=0x100002000', 'request_written=0x100000000')], [ON_OWNER]),
    ('zero-ack-samples', [ON_OBS.replace('ack_samples=1', 'ack_samples=0')], [ON_OWNER]),
    ('excess-ack-samples', [ON_OBS.replace('ack_samples=1', 'ack_samples=15002')], [ON_OWNER]),
]:
    graph_check(label, observations, owners)
for field, value in [('request_before', '0x100000000'), ('request_written', '0x100002000'), ('ack_payload', '0x100002000'),
                      ('ack_status', '0x2')]:
    for bad in ('-1', '0xffffffffffffffff', '0x1ffffffffffffffff'):
        graph_check('invalid-u64-' + field + '-' + bad,
                    [ON_OBS.replace(field + '=' + value, field + '=' + bad)], [ON_OWNER])
for record_name, record, marker in [('observation', ON_OBS, 'm4rch gfx-coordinate-observation: '),
                                     ('owner', ON_OWNER, 'm4rch gfx-coordinate-owner: ')]:
    fields = record[len(marker):].split()
    for field in fields:
        key, value = field.split('=', 1)
        required = (record_name == 'observation' and key in ('enabled', 'result', 'request_attempted',
                    'request_acked', 'votes_attempted', 'votes_verified', 'ack_samples',
                    'request_before', 'request_written', 'ack_payload', 'ack_status')) or record_name == 'owner'
        if required:
            bad = record.replace(field, '')
            graph_check('missing-' + record_name + '-' + key,
                        [bad if record_name == 'observation' else ON_OBS],
                        [bad if record_name == 'owner' else ON_OWNER])
for key in ('root_published', 'mapping_or_publication_performed'):
    for value in (None, False, 0, 'true'):
        bad = {'root_published': True, 'mapping_or_publication_performed': True, key: value}
        graph_check('bad-report-' + key + '-' + repr(value), [ON_OBS], [ON_OWNER], report=bad)


def run_flow(label, log, expected_stage=None, *, returncode=0, refcount=1,
             note=build_note, failure=False, mutate_adt=None, mutate_linux=False,
             module_present=True):
    """Execute actual transformed main with all external access intercepted.

    Fixture keeps full receipt lifetime/contract but elides optional receive/owned
    decoding, which is inherited code outside this startup-gating qualification.
    A graph object existence check is permitted only for a positive path.
    """
    with tempfile.TemporaryDirectory(prefix='coordinate-cold-flow-') as directory:
        work = Path(directory)
        build = work / 'asc-root-envelope'
        graph = work / 'asc-graph-init'
        build.mkdir()
        graph.mkdir()
        fixture = copy.deepcopy(receipt)
        fixture['graph_source_sha256'] = {}
        fixture['artifact_sha256'] = {'asc-graph-init/asc-graph-init.ko': sha(module_image)}
        fixture['kernel_notes_sha256'] = sha(b'fixture-kernel-note')
        fixture['joined_context_init'] = False
        fixture['graph_recovery_trial']['receive_service'] = False
        layout = b'{"objects": []}\n'
        objects = b'fixture-objects'
        fixture['graph_fixture_sha256'] = sha(objects)
        fixture['graph_receipt_sha256'] = sha(layout)
        (build / 'build-receipt.json').write_text(json.dumps(fixture))
        (graph / 'graph-receipt.json').write_bytes(layout)
        (graph / 'graph-before.bin').write_bytes(objects)
        (graph / 'asc-graph-init.ko').write_bytes(module_image)
        boot = 'offline-' + label
        output = graph / ('boot-' + boot)
        trace = []
        cold = False
        dmesg_calls = 0
        saved_tree = copy.deepcopy(tree)
        if mutate_adt:
            mutate_adt(saved_tree)
        text = bytearray(0x5b800)
        for offset, word in {0x2f250: 0xf9400109, 0x2f264: 0xeb0a013f,
                             0x2f268: 0x54003d61, 0x2f2b4: 0xb9402d29,
                             0x2f2b8: 0x34003b49, 0x2fa2c: 0x94004f40}.items():
            struct.pack_into('<I', text, offset, word)
        text[0x5b768:0x5b768+len(b'Host-mapped FW allocations are disabled')] = b'Host-mapped FW allocations are disabled'
        original_read_bytes, original_read_text = Path.read_bytes, Path.read_text
        original_exists = Path.exists

        def system_path(path):
            return str(path).startswith(('/sys/', '/proc/'))

        def read_bytes(path):
            if system_path(path):
                trace.append(('read-bytes', str(path), cold))
                if str(path) == '/sys/kernel/notes':
                    return b'fixture-kernel-note'
                if str(path) == '/sys/module/asc_graph_init/notes/.note.gnu.build-id':
                    return note
                raise AssertionError('Forbidden native/graph byte read: ' + str(path))
            return original_read_bytes(path)

        def read_text(path, *args, **kwargs):
            if system_path(path):
                trace.append(('read-text', str(path), cold))
                values = {'/proc/modules': '', '/proc/sys/kernel/random/boot_id': boot,
                          '/proc/interrupts': 'fixture-interrupts',
                          '/sys/module/asc_graph_init/refcnt': str(refcount)}
                assert str(path) in values, 'Forbidden native/graph text read: ' + str(path)
                return values[str(path)]
            return original_read_text(path, *args, **kwargs)

        def exists(path):
            if system_path(path):
                trace.append(('exists', str(path), cold))
                if str(path) == '/sys/module/asc_graph_init':
                    return module_present
                if str(path) == '/sys/kernel/m4rch_gpu_graph_trial/objects':
                    assert expected_stage == 'positive', 'Graph access before startup qualification'
                    return False
                raise AssertionError('Unexpected native existence check: ' + str(path))
            return original_exists(path)

        def capture(module, sysfile, destination, name):
            trace.append(('capture', str(destination.name), cold))
            assert not cold, 'Powered sampler after cold insmod'
            if destination.name == 'boot.adt':
                data = adt_raw
            elif destination.name == 'pagetables.bin':
                data = bytes(0x40000)
            elif destination.name == 'text.bin':
                data = bytes(text)
            elif destination.name == 'data-before.bin':
                data = b'fixture-before'
            else:
                raise AssertionError('Unexpected capture: ' + str(destination))
            destination.write_bytes(data)
            return data

        def execute(command, **kwargs):
            nonlocal cold
            trace.append(('subprocess', command, cold))
            assert not cold, 'Cleanup/retry after cold insmod'
            assert command in (['insmod', str(graph / 'asc-graph-init.ko'), 'run_gate=1'],
                               ['rmmod', 'asc_graph_init'],
                               ['insmod', str(graph / 'asc-graph-init.ko'), 'run_gate=2', 'observe_ms=5000', 'resident_session=1'])
            if command[-1] == 'resident_session=1':
                intent = json.loads((output / 'attempt.json').read_text())
                assert intent['stage'] == 'cold-load-intent'
                assert intent['selected_module'] == str(graph / 'asc-graph-init.ko')
                assert intent['cold_parameters'] == command[2:]
                assert trace[-2][0] == 'sync', 'Intent must be synced immediately before insmod'
                cold = True
                return SimpleNamespace(returncode=returncode, stdout='', stderr='fixture-cold')
            return SimpleNamespace(returncode=0, stdout='', stderr='')

        def check_output(command, **kwargs):
            nonlocal dmesg_calls
            assert command == ['dmesg', '--color=never']
            dmesg_calls += 1
            trace.append(('dmesg', dmesg_calls, cold))
            assert dmesg_calls <= 2
            return 'fixture-before\n' + (log if dmesg_calls == 2 else '')

        def sync():
            trace.append(('sync', None, cold))

        def qualify_linux():
            trace.append(('qualify-linux-dt', 'temporary-312-node-fixture', cold))
            assert not any(row[0] in ('capture', 'subprocess') for row in trace)
            contract.qualify_linux_dt(linux_base)

        import owned_gpu_layout
        error = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(root.sys, 'argv', ['run-root-coordinate.py', str(work), '--run', '--graph']))
            stack.enter_context(patch.object(root.os, 'geteuid', lambda: 0))
            stack.enter_context(patch.object(root.os, 'uname', lambda: SimpleNamespace(release=fixture['kernel_release'])))
            stack.enter_context(patch.object(root.os, 'sync', sync))
            stack.enter_context(patch.object(root, 'parse', lambda raw: saved_tree))
            stack.enter_context(patch.object(root, 'qualify', lambda raw: {'fixture': True}))
            stack.enter_context(patch.object(root, 'qualify_linux_dt', qualify_linux))
            stack.enter_context(patch.object(root, 'capture', capture))
            stack.enter_context(patch.object(owned_gpu_layout, 'validate', lambda *args: None))
            stack.enter_context(patch.object(root.subprocess, 'run', execute))
            stack.enter_context(patch.object(root.subprocess, 'check_output', check_output))
            stack.enter_context(patch.object(Path, 'read_bytes', read_bytes))
            stack.enter_context(patch.object(Path, 'read_text', read_text))
            stack.enter_context(patch.object(Path, 'exists', exists))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            linux_changed = linux_base / 'status'
            if mutate_linux:
                linux_changed.write_bytes(b'disabled\0')
            try:
                root.main()
            except ValueError as caught:
                error = str(caught)
            finally:
                if mutate_linux:
                    linux_changed.unlink()
        assert bool(error) == failure, (label, error)
        if mutate_adt or mutate_linux:
            assert not cold and not any(row[0] == 'subprocess' for row in trace)
            if mutate_linux:
                assert not any(row[0] == 'capture' for row in trace)
            report = None
        else:
            assert cold
            report = json.loads((output / 'attempt.json').read_text())
            if failure:
                assert report['stage'] == 'cold-load-intent'
            elif expected_stage == 'positive':
                assert report['resident_session_active'] or report['diagnostic_session_active']
                assert report['root_published']
            else:
                assert report['stage'] == expected_stage, (label, report)
                assert report['commands_admitted'] == [] and report['unloaded'] is False
                assert not report['resident_session_active'] and not report['diagnostic_session_active']
                assert report['reboot_required']
        after = [row for row in trace if row[-1] is True]
        assert not any(row[0] in ('capture', 'subprocess') for row in after)
        graph_accesses = [row for row in after if '/sys/kernel/m4rch_gpu_graph_trial/' in str(row[1])]
        assert bool(graph_accesses) == (expected_stage == 'positive')
        def durable_trace(value):
            if isinstance(value, str):
                return value.replace(str(work), '<temporary-build-fixture>')
            if isinstance(value, (tuple, list)):
                return [durable_trace(item) for item in value]
            return value
        flow_results.append({'case': label, 'stage': report.get('stage') if report else None,
                             'error': error, 'durable_cold_intent_before_insmod': cold,
                             'post_cold_graph_access_count': len(graph_accesses),
                             'post_cold_sampler_or_cleanup_count': 0,
                             'trace': durable_trace(trace)})
        cases.append({'case': 'actual-main-' + label, 'passed': True})


run_flow('retained', RETAINED + '\n', 'startup-retained-before-firmware')
run_flow('retained-with-success-records', RETAINED + '\n' + POSITIVE.replace(ROOT_PUBLISHED, '').replace(MAPPED, ''),
         'startup-retained-before-firmware')
for label, log in [
    ('no-marker', ''),
    ('root-and-resident-only', RESIDENT + '\n' + ROOT_PUBLISHED + '\n'),
    ('missing-observation', POSITIVE.replace(ON_OBS, '')),
    ('missing-owner', POSITIVE.replace(ON_OWNER, '')),
    ('missing-resident', POSITIVE.replace(RESIDENT, '')),
    ('missing-root-publication', POSITIVE.replace(ROOT_PUBLISHED, '')),
    ('missing-mapping-publication', POSITIVE.replace(MAPPED, '')),
    ('two-on-observations', POSITIVE + ON_OBS + '\n'),
    ('two-on-owner-records', POSITIVE + ON_OWNER + '\n'),
    ('failed-request-ack', POSITIVE.replace('request_acked=1', 'request_acked=0')),
    ('partial-votes', POSITIVE.replace('votes_verified=3', 'votes_verified=2')),
    ('wrong-owner-phase', POSITIVE.replace('phase=post-active-on', 'phase=pre-active-on')),
    ('incomplete-on', POSITIVE.replace('on_complete=1', 'on_complete=0')),
    ('contradictory-on-observation', POSITIVE.replace(ON_OBS, ON_OBS + ' request_acked=0')),
    ('contradictory-on-owner', POSITIVE.replace(ON_OWNER, ON_OWNER + ' on_complete=0')),
    ('malformed-on-field', POSITIVE.replace('request_acked=1', 'request_acked=1bad')),
    ('failed-plus-successful-on-observations', POSITIVE + ON_OBS.replace('result=0', 'result=-5') + '\n'),
]:
    run_flow(label, log, 'startup-outcome-unqualified')
for label, log, kwargs in [
    ('retained-duplicate-record', RETAINED + '\n' + RETAINED + '\n', {}),
    ('retained-started', RETAINED.replace('started=0', 'started=1') + '\n', {}),
    ('retained-mapped', RETAINED + '\n69 object pages mapped\n', {}),
    ('retained-root-published', RETAINED + '\n' + ROOT_PUBLISHED + '\n', {}),
    ('retained-note-mismatch', RETAINED + '\n', {'note': b'wrong-note'}),
    ('retained-no-reference', RETAINED + '\n', {'refcount': 0}),
    ('retained-failed-insmod', RETAINED + '\n', {'returncode': 1}),
    ('retained-malformed-numeric', RETAINED.replace('started=0', 'started=0x1') + '\n', {}),
    ('retained-duplicate-field', RETAINED + ' started=1 started=0\n', {}),
    ('success-records-note-mismatch', POSITIVE, {'note': b'wrong-note'}),
]:
    run_flow(label, log, failure=True, **kwargs)
run_flow('qualified-resident', POSITIVE, 'positive')
run_flow('qualified-diagnostic', POSITIVE.replace(RESIDENT, DIAGNOSTIC), 'positive')
run_flow('success-records-with-failed-insmod', POSITIVE, 'startup-outcome-unqualified', returncode=1)
run_flow('success-records-with-no-reference', POSITIVE, 'startup-outcome-unqualified', refcount=0)
run_flow('module-absent-empty-outcome', '', 'cold-load-module-absent-unqualified', module_present=False)
run_flow('module-absent-success-looking-outcome', POSITIVE, 'cold-load-module-absent-unqualified', module_present=False)
run_flow('module-absent-failed-insmod', '', 'cold-load-module-absent-unqualified', module_present=False, returncode=1)
run_flow('changed-linux-layout-before-any-helper', '', failure=True, mutate_linux=True)
for pin in pins:
    def change_pin(saved_tree, p=pin):
        original = saved_tree[p['node']][p['name']]
        saved_tree[p['node']][p['name']] = bytes([original[0] ^ 1]) + original[1:]
    run_flow('adt-refusal-' + pin['name'], '', failure=True, mutate_adt=change_pin)

bound = [Path(__file__), HERE / 'gfx_coordinate_contract.py', HERE / 'adt-contract.json',
         HERE / 'linux_dt_contract.py', HERE / 'linux-dt-contract.json',
         HERE / 'run-coordinate.py', HERE / 'run-root-coordinate.py',
         OLD_QUALIFIER, root.BASE, resident.BASE,
         KIT / 'gfx-poweroff-trial/gfx_poweroff_contract.py',
         KIT / 'gfx_reset_contract.py', ADT]
source_files = [{'path': str(p.relative_to(REPO)), 'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                for p in bound]
result = {
    'schema': 'm4rch.gfx-paired-coordinate-wrapper-qualification.v1',
    'hardware_access': False, 'qualification_complete': True,
    'inherited_case_count': inherited_count, 'case_count': len(cases), 'cases': cases,
    'transformed_inherited_qualifier_sha256': sha(inherited_source.encode()),
    'transformed_cold_runner_sha256': sha(root.runner_source().encode()),
    'transformed_resident_runner_sha256': sha(resident.runner_source().encode()),
    'source_files': source_files, 'actual_main_flow_cases': flow_results,
    'qualification': 'Actual generated Python admission, durable intent and early startup control flow; all external accesses intercepted. No native PM/MMIO/firmware/module activity.',
    'limits': [
        'Synthetic ELF note and minimal temporary build fixture are not the future hardware candidate or loaded image.',
        'Main fixture preserves admission/lifetime contract but elides optional receive-service and joined-owned snapshot decoding; these inherited decoder branches are not requalified here.',
        'Malformed known retention records can raise after synced cold intent; tested rejection preserves the owner without graph reads, samplers, cleanup or retry.',
        'Log records are software-reported startup evidence, not hardware PMP/PMC policy equivalence, DMA retirement, OFF success or restart safety.',
        'Canonical new receipts omit the old scope and are refused by frozen legacy wrappers. Historical legacy validators ignore the future scope key and can accept a deliberately hand-mixed receipt; paired wrappers reject every tested mixed receipt.',
    ],
}
destination = REPO / 'out/gfx-native-coordinate/wrapper-qualification.json'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + '\n')
print(f'{len(cases)} actual paired-wrapper cases passed ({inherited_count} inherited); no hardware access.')
print(destination)
linux_fixture_directory.cleanup()
