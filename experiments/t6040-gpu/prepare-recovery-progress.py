#!/usr/bin/env python3
"""Stage native idle defaults and one recovery trace bit; never touch hardware.

Preserve the RX recovery fixture, all mapping/lifetime rules and the deferred
immutable triangle. These are experimental initialization corrections plus a
progress observation, not a claim that the idle delays cause the stall.
"""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

from owned_gpu_layout import validate


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def prepare(source, policy_path, trace_path, output):
    policy = json.loads(policy_path.read_text())
    trace = json.loads(trace_path.read_text())
    layout = json.loads((source / 'graph-receipt.json').read_text())
    prep = json.loads((source / 'preparation.json').read_text())
    original = (source / 'graph-before.bin').read_bytes()
    validate(original, layout)
    assert sha(original) == layout['arena_sha256']
    assert prep['recovery_trial']['resident_session']
    assert prep['recovery_trial']['receive_service']['record_bytes'] == 72
    assert prep['pages'] == 56 and 'work_publication' not in prep
    assert policy['schema'] == 'm4rch-periodic-power-policy-audit-v1'
    assert trace['schema'] == 'm4rch-native-recovery-progress-trace-v1'
    # Evidence is numeric; the exact private driver remains an ignored input.
    expected_driver = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
    assert sha(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X').read_bytes()) == expected_driver
    assert policy['hardware_access'] is False
    assert policy['native_identity']['sha256'] == expected_driver
    assert trace['sources']['private_driver_sha256'] == expected_driver
    assert policy['firmware_text_identity']['normalized_sha256'] == '190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac'
    assert [(item['owned_object'], item['owned_offset'], item['milliseconds'])
            for item in policy['native_identity']['defaults']] == [
                ('region_c', '0x9b8', 2), ('region_c', '0x9bc', 40)]
    control = policy['force_snapshot_control']
    assert control['opcode'] == '0x16' and control['dispatch'] == '0x4b1c'
    assert control['records'] == 32
    assert control['cursor_before'] == [0, 0, 32] and control['cursor_after'] == [32, 32, 32]
    assert policy['emulation']['full_control22_differential_data_comparison'] is True
    assert [(item['gpu_delay_ms'], item['fender_delay_ms'], item['one_shot_enable_after'])
            for item in policy['emulation']['full_control22_mirror_cases']] == [(0, 0, 0), (2, 40, 0)]
    assert trace['native_mask']['minimum_candidate_write'] == dict(
        object='status_a', byte_offset=0, width=4, value=1, bit_index=0)
    assert trace['native_mask']['native_extent'] == 0x20
    assert trace['force_snapshot']['device_control_type'] == 22
    assert trace['owned_rx14_trace']['record_bytes'] == 72
    assert trace['owned_rx14_trace']['capacity'] == 512
    assert trace['owned_rx14_trace']['allowed_type'] == 5
    objects = {obj['name']: obj for obj in layout['objects']}
    status = objects['status_a']
    assert status['input_bytes'] >= 0x20
    assert struct.unpack_from('<Q', original, objects['root']['arena_offset'] + 0xa8)[0] == int(status['gpu_va'], 0)
    blob = bytearray(original)
    changes = []
    for name, offset, value in [('status_a', 0, 1), ('region_c', 0x9b8, 2), ('region_c', 0x9bc, 40)]:
        obj = objects[name]
        assert offset + 4 <= obj['input_bytes']
        at = obj['arena_offset'] + offset
        assert struct.unpack_from('<I', blob, at)[0] == 0
        struct.pack_into('<I', blob, at, value)
        changes.append(dict(object=name, offset=hex(offset), value=value, bytes=4))
    # Only the three reviewed u32 fields change. No command, pointer or PTE edit.
    allowed = {objects[item['object']]['arena_offset'] + int(item['offset'], 16) + i
               for item in changes for i in range(4)}
    assert all(i in allowed for i, (old, new) in enumerate(zip(original, blob)) if old != new)
    for obj in layout['objects']:
        at = obj['arena_offset']
        obj['input_sha256'] = sha(blob[at:at + obj['input_bytes']])
    layout['arena_sha256'] = sha(blob)
    validate(blob, layout)
    report = dict(schema='m4rch-recovery-progress-preparation-v1',
        source_arena_sha256=sha(original), arena_sha256=sha(blob),
        changes=changes, changed_bytes=sum(old != new for old, new in zip(original, blob)),
        policy_evidence_sha256=sha(policy_path.read_bytes()),
        trace_evidence_sha256=sha(trace_path.read_bytes()),
        private_driver_sha256=expected_driver,
        qualification='Native RegionC idle defaults plus native trace mask bit0. A type5 role4/event46 marker with matching arguments after the drained pre-ack prefix may support reaching firmware64c0 under recovery chronology, not a livePC or completed recovery. The prefix is not global producer quiescence. Idle-delay causality remains experimental. No hardware action, new work publication, allocation or mapping change.')
    layout['recovery_progress_trial'] = report
    prep['recovery_progress_trial'] = report
    prep['recovery_trial']['progress_trace'] = report
    layout['recovery_trial']['progress_trace'] = report
    preserved = {name: sha((source / name).read_bytes()) for name in (
        'backing.bin', 'job-data.h', 'render-data.h', 'recovery-contract.h')}
    report['preserved_sha256'] = preserved
    shutil.copytree(source, output)
    (output / 'graph-before.bin').write_bytes(blob)
    prefix = (source / 'graph-contract.h').read_text().split('static const u8 graph_bytes[')[0]
    values = ''.join(f'[{i:#x}]={value:#x},\n' for i, value in enumerate(blob) if value)
    (output / 'graph-contract.h').write_text(prefix + f'static const u8 graph_bytes[{len(blob)}]={{\n' + values + '};\n')
    for name, value in [('preparation.json', prep), ('graph-receipt.json', layout),
                        ('progress-preparation.json', report)]:
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    assert all(sha((output / name).read_bytes()) == digest for name, digest in preserved.items())
    print('Prepared three native fields; changed bytes:', report['changed_bytes'], '; no hardware action.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'policy', 'trace', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    prepare(args.source, args.policy, args.trace, args.output)
