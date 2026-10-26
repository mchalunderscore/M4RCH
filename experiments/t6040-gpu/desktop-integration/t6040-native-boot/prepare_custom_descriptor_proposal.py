#!/usr/bin/env python3
"""Compare frozen custom descriptors to qualified native bindings; write proposal only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def pin(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def fields(raw):
    names = ['physical', 'virtual', 'size', 'stride', 'relative', 'flags', 'trailing']
    return dict(zip(names, struct.unpack('<QQIIQII', raw)))


def prepare(prepared, staging, output):
    receipt_path = prepared / 'graph-receipt.json'
    arena_path = prepared / 'graph-before.bin'
    receipt = json.loads(receipt_path.read_text())
    original = arena_path.read_bytes()
    if pin(arena_path)['sha256'] != receipt['arena_sha256']:
        raise ValueError('Frozen custom arena and receipt differ')
    hardware = next(o for o in receipt['objects'] if o['name'] == 'hardware')
    hw = hardware['arena_offset']
    if hashlib.sha256(original[hw:hw + hardware['input_bytes']]).hexdigest() != hardware['input_sha256']:
        raise ValueError('Frozen hardware object and receipt differ')
    qualification_path = staging / 'qualification-v1/qualification.json'
    qualification = json.loads(qualification_path.read_text())
    if not qualification['complete'] or qualification['schema'] != 'm4rch.gravity-native-t6040-components.qualification.v3':
        raise ValueError('Qualified actual native v3 producer required')
    for item in qualification['inputs']:
        if pin(Path(item['path'])) != item:
            raise ValueError('Qualified input changed: ' + item['path'])
    evidence = ROOT / 'out/gpu-gravity-normal-boot-v3-source-evidence'
    flags_path = evidence / 'native-descriptor-flags.json'
    absent_path = evidence / 'native-slot27-absent.json'
    flags = json.loads(flags_path.read_text())['native_hardware_flags']
    absent = json.loads(absent_path.read_text())['hardware_descriptor']
    if absent != {'physical': 0, 'virtual': 0, 'size': 0, 'stride': 0, 'relative': 0, 'flags': 2}:
        raise ValueError('Native absence changed')
    projected = bytearray(original)
    rows = []
    for slot in [3, 22, 27, 39, 41]:
        relative = 0x640 + slot * 0x28
        offset = hw + relative
        before = original[offset:offset + 0x28]
        old = fields(before)
        if slot == 27:
            patch_offset = offset
            after_bytes = struct.pack('<QQIIQI', *(absent[name] for name in
                ['physical', 'virtual', 'size', 'stride', 'relative', 'flags']))
            scope = 'Replace the native serialized 36-byte prefix; retain trailing four bytes'
        else:
            patch_offset = offset + 0x20
            after_bytes = struct.pack('<I', flags[str(slot)])
            scope = 'Native descriptor flag projection only; retain all geometry and trailing bytes'
        before_bytes = original[patch_offset:patch_offset + len(after_bytes)]
        projected[patch_offset:patch_offset + len(after_bytes)] = after_bytes
        after = bytes(projected[offset:offset + 0x28])
        new = fields(after)
        if slot != 27 and any(old[key] != new[key] for key in old if key != 'flags'):
            raise ValueError('Flag-only projection changed geometry')
        if slot == 27 and any(new[key] != absent[key] for key in absent):
            raise ValueError('Canonical absent projection differs')
        rows.append({'slot': slot, 'hardware_relative_record_offset': hex(relative),
            'arena_record_offset': hex(offset), 'before': old, 'after': new,
            'before_record_hex': before.hex(), 'after_record_hex': after.hex(),
            'patch': {'arena_offset': hex(patch_offset), 'bytes': len(after_bytes),
                      'expected_before_hex': before_bytes.hex(), 'replacement_hex': after_bytes.hex()},
            'scope': scope})
    allowed = {int(row['patch']['arena_offset'], 16) + index
               for row in rows for index in range(row['patch']['bytes'])}
    changed = [index for index, (left, right) in enumerate(zip(original, projected)) if left != right]
    if len(projected) != len(original) or any(index not in allowed for index in changed):
        raise ValueError('Proposal changed bytes outside descriptor corrections')
    leaves = json.dumps(receipt['mmio_leaves'], sort_keys=True).encode()
    report = {'schema': 'm4rch.native-t6040-custom-descriptor-proposal.v1',
        'inputs': [pin(p) for p in [Path(__file__), receipt_path, arena_path,
            qualification_path, staging / 'source/linux/drivers/gpu/drm/asahi/g16_t6040.rs',
            flags_path, absent_path]],
        'hardware_object_arena_offset': hex(hw), 'hardware_gpu_va': hardware['gpu_va'],
        'rows': rows, 'changed_byte_count': len(changed), 'changed_arena_offsets': [hex(x) for x in changed],
        'proposed_arena_sha256': hashlib.sha256(projected).hexdigest(),
        'proposed_hardware_input_sha256': hashlib.sha256(projected[hw:hw + hardware['input_bytes']]).hexdigest(),
        'unchanged_mmio_leaves_sha256': hashlib.sha256(leaves).hexdigest(),
        'arena_bytes_unchanged': True, 'mappings_changed': False, 'backing_changed': False,
        'source_qualified_against_actual_v3_rust_producer': True,
        'hardware_actions': [], 'candidate_mutated': False, 'projected_arena_written': False,
        'limitations': ['Slot3 still has zero geometry in this custom arena; flag2 does not supply native MCC mappings.',
            'Slot27 existing donor PTE is retained but becomes unreferenced by this descriptor. No PTE removal or permission changes are proposed.',
            'Descriptor flags are independent of Linux PTE write permission.',
            'This is one offline correction proposal for a combined future execution trial; no runtime success is established.']}
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['prepared', 'staging', 'output']:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = prepare(args.prepared.resolve(), args.staging.resolve(), args.output.resolve())
    print(json.dumps({'rows': len(result['rows']), 'changed_byte_count': result['changed_byte_count'],
                      'candidate_mutated': False, 'hardware_actions': []}))
