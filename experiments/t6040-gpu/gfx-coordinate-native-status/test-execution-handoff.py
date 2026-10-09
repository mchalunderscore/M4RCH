#!/usr/bin/env python3
"""Actual offline analyzer handoff on explicitly synthetic saved captures.

Uses immutable new-candidate bytes and RAM snapshots made by the actual
resident capture function with every native access intercepted. No execution
or renderer success is inferred from CPU-written test pixels/cursors.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CANDIDATE = REPO / 'out/gfx-coordinate-native-status/candidate'
ANALYZER = HERE / 'analyze-execution.py'
ANALYZER_SHA = '4e74885c8b11cea96e12581225e5f78fae8b554b8d1b573d1753d0b5f596d541'
RECEIPT_SHA = '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
TEXT = REPO / 'out/owned-hw-completions/live-candidate/asc-graph-init/boot-520da35a-487e-4575-97b3-af12afa2936c/text.bin'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
resident = runpy.run_path(str(HERE / 'run-native-status.py'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        raise ValueError('Never overwrite qualification')
    assert digest(ANALYZER) == ANALYZER_SHA
    receipt_path = CANDIDATE / 'asc-root-envelope/build-receipt.json'
    assert digest(receipt_path) == RECEIPT_SHA
    receipt = json.loads(receipt_path.read_text())
    prepared = json.loads((CANDIDATE / 'native-status-preparation.json').read_text())
    layout = json.loads((CANDIDATE / 'asc-graph-init/graph-receipt.json').read_text())
    metadata = json.loads((CANDIDATE / 'asc-graph-init/preparation.json').read_text())
    target_receipt = json.loads((CANDIDATE / 'analysis-inputs/target-receipt.json').read_text())
    before = (CANDIDATE / 'asc-graph-init/backing.bin').read_bytes()
    graph_before = (CANDIDATE / 'asc-graph-init/graph-before.bin').read_bytes()
    assert metadata['pages'] == 56 and receipt['joined_owned_pages'] == 174
    assert digest(CANDIDATE / 'asc-graph-init/backing.bin') == metadata['data_sha256']
    assert target_receipt['target']['bytes'] == 16384
    assert before[20 * 16384:21 * 16384] == bytes([165]) * 16384
    bound = {receipt_path, CANDIDATE / 'native-status-preparation.json', ANALYZER,
             HERE / 'run-native-status.py', HERE / 'gfx_native_status_contract.py', TEXT,
             Path(__file__)}
    bound.update(CANDIDATE / key for key in receipt['artifact_sha256'])
    bound.update(CANDIDATE / 'asc-graph-init' / key for key in receipt['graph_source_sha256'])
    bound.update(CANDIDATE / pin['relative'] for pin in prepared['analysis_input_pins'])
    bound.update(Path(pin['path']) for pin in prepared['analysis_tool_pins'])
    bound.add(HERE.parent / 'firmware_text_contract.py')
    bound.add(HERE.parent / 'decode-receive-journal.py')
    before_pins = {path: digest(path) for path in bound}
    destination.mkdir(parents=True)
    cases = []
    journal = runpy.run_path(str(HERE.parent / 'decode-receive-journal.py'))
    header = journal['HEADER'].pack(journal['MAGIC'], journal['VERSION'],
        journal['ENTRY'].size, journal['CAPACITY'], 0, 0, 0, 0, 0, 0, 0, 0)
    notifications = header + bytes(journal['CAPACITY'] * journal['ENTRY'].size)
    frozen_text = TEXT.read_bytes()

    def pixels(mode):
        output = bytearray(before[20 * 16384:21 * 16384])
        if mode == 'outside-samples-only':
            output[4 * (7 + 7 * 64)] ^= 1
        if mode in ('references-only', 'wrong-reference', 'background-and-references'):
            background = bytes(round(max(0, min(1, value)) * 255)
                               for value in target_receipt['background_candidate']['float_rgba'])
            if mode == 'background-and-references':
                output[:] = background * (64 * 64)
            for sample in target_receipt['interior_reference_samples']:
                offset = sample['linear_offset']
                output[offset:offset + 4] = bytes(sample['rgba8_nearest'])
            for x, y in ((0, 0), (63, 0), (0, 63), (63, 63)):
                offset = y * 256 + x * 4
                output[offset:offset + 4] = background
            if mode == 'wrong-reference':
                output[target_receipt['interior_reference_samples'][0]['linear_offset']] ^= 0x40
        return bytes(output)

    def make_capture(path, mode, progress=False):
        graph = bytearray(graph_before)
        backing = bytearray(before)
        target = pixels(mode)
        backing[20 * 16384:21 * 16384] = target
        if progress:
            base = int(layout['base'], 0)
            for channel in (0, 1, 12):
                for index, address in enumerate(layout['empty_channel_fixture'][channel]['cursors']):
                    struct.pack_into('<I', graph, int(address, 0) - base, channel + index + 1)
            for index in range(2):
                offset = (48 + index * 2) * 16384
                struct.pack_into('<I', backing, offset + 0x100, index + 2)
                struct.pack_into('<I', backing, offset + 0x130, index + 3)
                struct.pack_into('<I', backing, offset + 0x140, index + 4)
            backing[47 * 16384:47 * 16384 + 3] = b'CPU'
        owned = bytearray(receipt['joined_owned_pages'] * 16384)
        owned[112 * 16384:168 * 16384] = backing
        log = ('SYNTHETIC CPU FIXTURE; NOT A GPU TRIAL\n'
               'm4rch recovery-cycle: prepared_triangle_published=1 notification_sent=1\n')
        report = {'schema': 'm4rch-resident-operation-v1',
                  'synthetic_fixture': True, 'boot_id': 'SYNTHETIC-CPU-NO-HARDWARE',
                  'requested_command': 'submit', 'validated_build_receipt': receipt,
                  'commands': [{'command': 'submit', 'stage': 'returned', 'result': 'success'}],
                  'capture_errors': [], 'resident_session_active': True,
                  'reboot_required': False, 'allocations_retained': True,
                  'snapshots_atomic': False, 'submit_attempted': True,
                  'power_off_attempted': False, 'completed_idle_cycles': 4,
                  'trace_disabled': True, 'complete': True,
                  'qualification': 'CPU-authored RAM fixture. No new native execution or rendered pixels.'}
        expected = {str(resident['SYSFS'] / 'objects'): bytes(graph),
                    str(resident['SYSFS'] / 'owned'): bytes(owned),
                    str(resident['SYSFS'] / 'notifications'): notifications}
        original = Path.read_bytes
        reads = []

        def read(path):
            text = str(path)
            if text.startswith(('/sys/', '/proc/')):
                assert text in expected, 'Unintercepted native access: ' + text
                reads.append(text)
                return expected[text]
            return original(path)

        def dmesg(command, **kwargs):
            assert command == ['dmesg', '--color=never']
            return log

        with patch.object(Path, 'read_bytes', read), \
             patch.object(resident['subprocess'], 'check_output', dmesg):
            report['final_capture'] = resident['capture'](path, receipt, report)
        assert report['capture_errors'] == []
        assert len(reads) == 3
        (path / 'text.bin').write_bytes(frozen_text)
        save(path / 'attempt.json', report)
        return report, target, bytes(backing[47 * 16384:48 * 16384])

    def invoke(label, candidate, capture, allowed):
        output = destination / label
        result = subprocess.run([sys.executable, str(ANALYZER), str(candidate),
                                 str(capture), str(output)], capture_output=True, text=True)
        assert (result.returncode == 0) == allowed, (label, result.stderr)
        entry = {'case': label, 'passed': True, 'analysis_returncode': result.returncode,
                 'synthetic_capture': True, 'hardware_access': False}
        if allowed:
            summary = json.loads((output / 'summary.json').read_text())
            work = json.loads((output / 'work/result.json').read_text())
            samples = json.loads((output / 'target-samples.json').read_text())
            assert summary['gpu_execution_verified'] is False
            assert summary['retirement_verified'] is False
            assert summary['boot_id'] == 'SYNTHETIC-CPU-NO-HARDWARE'
            assert digest(output / 'work/target-after.bin') == work['target_sha256']
            assert digest(output / 'work/target-after.bin') == samples.get('target_sha256', work['target_sha256'])
            assert work['firmware_scheduler']['available'] is False
            entry.update(target_changed_bytes=summary['target_changed_bytes'],
                         completion_changed_bytes=summary['completion_changed_bytes'],
                         sample_pass=samples['passed'], gpu_execution_verified=False,
                         retirement_verified=False)
        else:
            assert not (output / 'summary.json').exists()
            entry['refusal_last_line'] = result.stderr.strip().splitlines()[-1]
        cases.append(entry)
        return output

    with tempfile.TemporaryDirectory(prefix='gfx-execution-handoff-RAM-') as directory:
        ram = Path(directory)
        for mode in ('sentinel', 'outside-samples-only', 'references-only',
                     'wrong-reference', 'background-and-references'):
            capture = ram / mode
            report, target, completion = make_capture(capture, mode, progress=mode == 'references-only')
            output = invoke('synthetic-' + mode, CANDIDATE, capture, True)
            summary = json.loads((output / 'summary.json').read_text())
            assert summary['eight_target_reference_samples_passed'] == (mode in ('references-only', 'background-and-references'))
            assert (output / 'work/target-after.bin').read_bytes() == target
            assert (output / 'work/completion-after.bin').read_bytes() == completion
            assert summary['target_changed_bytes'] == sum(a != b for a, b in zip(before[20 * 16384:21 * 16384], target))
            if mode == 'references-only':
                work = json.loads((output / 'work/result.json').read_text())
                assert work['queues'][0]['completed_cursor'] == 2
                assert work['queues'][1]['completed_cursor'] == 3
                assert summary['completion_changed_bytes'] == 3
                assert [item['channel'] for item in work['root_channels']] == [0, 1, 12]
                assert work['root_channels'][2]['cursors'] == [13, 14, 15]
        capture = ram / 'bound-capture'
        report, _, _ = make_capture(capture, 'references-only', progress=True)
        for filename in ('objects-after.bin', 'owned-after.bin', 'dmesg-after.log'):
            path = capture / filename
            original = path.read_bytes()
            path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            invoke('refuse-changed-' + filename, CANDIDATE, capture, False)
            path.write_bytes(original)
        for key, value in [('submit_attempted', False), ('validated_build_receipt', {})]:
            changed = copy.deepcopy(report)
            changed[key] = value
            save(capture / 'attempt.json', changed)
            invoke('refuse-report-' + key, CANDIDATE, capture, False)
        save(capture / 'attempt.json', report)
        # Mutations occur only in a RAM clone, never the frozen candidate.
        clone = ram / 'candidate-clone'
        shutil.copytree(CANDIDATE, clone)
        for relative in ('asc-graph-init/asc-graph-init.ko',
                         'asc-graph-init/recovery-cycle.h',
                         'asc-graph-init/backing.bin',
                         'asc-graph-init/preparation.json',
                         'analysis-inputs/target-receipt.json'):
            path = clone / relative
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            invoke('refuse-pin-' + path.name, clone, capture, False)
            path.write_bytes(original)
        # Record a concrete current binding gap rather than claiming refusal.
        path = clone / 'asc-graph-init/graph-receipt.json'
        original = path.read_bytes()
        changed = json.loads(original)
        changed['empty_channel_fixture'][0]['cursors'][0] = changed['empty_channel_fixture'][0]['cursors'][1]
        save(path, changed)
        assert digest(path) != receipt['graph_receipt_sha256']
        output = invoke('observed-unbound-graph-receipt-changes-cursor', clone, capture, True)
        work = json.loads((output / 'work/result.json').read_text())
        assert work['root_channels'][0]['cursors'] == [2, 2, 3]
        cases[-1].update(expected_refusal_missing=True,
                         root_cursor_changed_by_unbound_layout=True,
                         original_root_cursors=[1, 2, 3], altered_root_cursors=[2, 2, 3])
        path.write_bytes(original)
        path = clone / 'asc-graph-init/graph-before.bin'
        original = path.read_bytes()
        path.write_bytes(original + b'\n')
        output = invoke('observed-unbound-graph-before-not-consumed', clone, capture, True)
        cases[-1].update(expected_refusal_missing=True,
                         consumed_by_downstream_analyzer=False)
        path.write_bytes(original)
        path = clone / 'native-status-preparation.json'
        original = path.read_bytes()
        for field in ('analysis_input_pins', 'analysis_tool_pins'):
            changed = json.loads(original)
            changed[field][0]['sha256'] = '0' * 64
            save(path, changed)
            invoke('refuse-altered-' + field, clone, capture, False)
        path.write_bytes(original)
        output = destination / 'refuse-existing-output'
        output.mkdir()
        (output / 'keep').write_text('saved output')
        invoke('refuse-existing-output', CANDIDATE, capture, False)
        assert (output / 'keep').read_text() == 'saved output'
        # A sample subdirectory has captures but no operation-level report.
        sample = ram / 'sample-01s'
        shutil.copytree(capture, sample)
        (sample / 'attempt.json').unlink()
        invoke('scope-sample-directory-needs-parent-report', CANDIDATE, sample, False)
    assert before_pins == {path: digest(path) for path in bound}, 'Immutable input changed'
    result = {'schema': 'm4rch.gfx-native-status-execution-handoff-qualification.v1',
              'passed': True, 'hardware_access': False, 'case_count': len(cases),
              'synthetic_capture': True, 'new_execution_observed': False,
              'all_candidate_pins_enforced': False,
              'blocking_findings': ['Frozen analyzer omits graph_receipt_sha256 check; changed in-bounds cursor address is accepted and changes reported root cursors.'],
              'cases': cases,
              'inputs': [{'path': str(path.relative_to(REPO)), 'sha256': value}
                         for path, value in sorted(before_pins.items())],
              'capture_schema_source': 'Actual native-status resident capture() with intercepted sysfs/dmesg',
              'owned_layout': {'joined_pages': 174, 'render_first': 112, 'backing_pages': 56,
                               'target_owned_page': 132, 'completion_owned_page': 159},
              'output_handoff': 'work/target-after.bin to target-samples.json; work/result.json to summary.json',
              'limits': [
                  'Every pixel/cursor/completion change is CPU-authored synthetic data; no GPU/render result.',
                  'Only operation final_capture is directly analyzable. Timed sample directories need their parent report and a separate explicit selection helper.',
                  'Eight passing target references do not establish other pixels, execution, receive/event/stamp completion, synchronization or retirement.',
                  'Receive journal is preserved by capture() but the pinned analyzer does not join or validate it; independent journal review remains required.',
                  'Optional firmware DATA is absent in actual resident captures; scheduler DATA analysis remains unavailable.',
                  'graph-before.bin is not consumed and is not separately checked by the frozen offline wrapper. graph-receipt.json is consumed but its expected receipt hash is not checked.',
                  'live_* decoded log arrays are boot log history without dmesg-before subtraction; typed samples do not make those values fresh after submit.',
              ]}
    save(destination / 'qualification.json', result)
    print(json.dumps({'passed': True, 'case_count': len(cases), 'hardware_access': False,
                      'synthetic_capture': True, 'receipt': str(destination / 'qualification.json')}))


if __name__ == '__main__':
    main()
