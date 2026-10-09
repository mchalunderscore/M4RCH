#!/usr/bin/env python3
"""Prepare one native-init/recovery candidate while preserving the owned draw.

Offline only. Root work producers and all triangle bytes remain unchanged;
prepare-recovery-trial.py owns idle suppression and deferred publication.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

from firmware_text_contract import qualify
from owned_gpu_layout import validate
from adt import parse
from native_aux_power import prepare_auxiliary


HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
HOST_BASE = 0xfffffe0000000000
EPOCH_OFFSET = 0xf000
EPOCH_BYTES = 8
STATUS_NATIVE_BYTES = 0xe440


def sha(data):
    return hashlib.sha256(data).hexdigest()


def native_reader(raw):
    if sha(raw) != HOST_SHA:
        raise ValueError('Wrong pinned AGX353.14/25G83 host binary')
    segments = []
    position = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        command, length = struct.unpack_from('<II', raw, position)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', raw, position+24))
        position += length

    def read(offset, length):
        address = HOST_BASE+offset
        spans = [file_offset+address-va for va, _, file_offset, size in segments
                 if va <= address and address+length <= va+size]
        if len(spans) != 1:
            raise ValueError('Native range is not uniquely file backed')
        return raw[spans[0]:spans[0]+length]
    return read


def identity_counts(log):
    samples = re.findall(r'm4rch gpu-identity: phase=([a-z0-9-]+) raw_d04018=(0x[0-9a-f]+)', log)
    if [phase for phase, _ in samples] != ['before-root', 'after-publication', '1s', 'before-stop']:
        raise ValueError('Need the four serialized T6040 identification samples')
    values = [int(value, 16) for _, value in samples]
    if values != [0x01320311]*4:
        raise ValueError('ID differs from the reviewed T6040 recovery capture')
    value = values[0]
    counts = [((value >> high) & 15)*((value >> low) & 15)
              for high, low in ((16, 0), (20, 4), (24, 8))]
    masks = [min((1 << count)-1, 0xffffffff) for count in counts]
    assert counts == [2, 3, 3] and masks == [3, 7, 7]
    return samples, counts, masks


def prepare(source, macho, firmware_text, identity_log, recovery_audit, output, adt_path):
    native = native_reader(macho.read_bytes())
    text = firmware_text.read_bytes()
    firmware = qualify(text)
    epoch_audit_bytes = recovery_audit.read_bytes()
    epoch_audit = json.loads(epoch_audit_bytes)
    assert epoch_audit['schema'] == 'm4rch-recovery-temperature-epoch-audit-v1'
    assert epoch_audit['static_contract_verified'] is True
    assert epoch_audit['private_binary_sha256'] == HOST_SHA
    assert epoch_audit['firmware_text_identity']['normalized_sha256'] == firmware['normalized_sha256']
    # Restore the native GPC policy already used by Gravity's platform builder.
    # This candidate qualifies the board's absent no-gpc property only; explicit
    # overrides require a new reviewed policy rather than silently ignoring them.
    adt_bytes = adt_path.read_bytes()
    tree = parse(adt_bytes)
    assert int.from_bytes(tree['/device-tree/chosen']['chip-id'], 'little') == 0x6040
    assert '/device-tree/arm-io/sgx' in tree
    assert not any('no-gpc' in node for node in tree.values())
    gpc_spans = (
        ('host', 0x89aa388, 0x89aa3a4, '7ab0b5f24699a3078cab3b85b4d5a4504f4fc3ae7123f3361ac8f8124c72b902'),
        ('host', 0x89a1a68, 0x89a1b08, 'cae9982228cb68bbf890e2c3f03049f0456fbb0f93404a5bc11b1395332e3da0'),
        ('host', 0x89a18b4, 0x89a1910, 'd05b88563d662cac800728517f64715ec7f6cfa5e1ebc9fb7556a4beaa1d958f'),
        ('firmware', 0x2f304, 0x2f32c, '11570ef67c92f99160f4df7517c22757aedad9d8c567eb626573d4d734291ff0'),
        ('firmware', 0x2f3c8, 0x2f3d4, '3491929a3d492787659932a82685d83a98c9a1695967ab1d2d1039278989ad21'),
        ('firmware', 0xd364, 0xd428, '070e3e5b78c146e9738dc82c26e881b87d1330b5ee482ffcbc30eafccc6728b9'),
    )
    for kind, begin, end, expected in gpc_spans:
        data = native(begin, end-begin) if kind == 'host' else text[begin:end]
        assert sha(data) == expected, (kind, hex(begin))
    gpc_policy = dict(hardware_offset='0xea0', value=1, native_default_policy=2,
                      no_gpc_property='absent', absent_property_tristate=2,
                      adt_sha256=sha(adt_bytes), firmware_global='0x18fc78',
                      separate_f20_global='0x18fcc8',
                      gravity_reference='drivers/gpu/drm/asahi/g16_platform.rs: gpc defaults true; hardware ea0 stores self.gpc',
                      bound_spans=[dict(source=k, begin=hex(b), end=hex(e), sha256=h) for k,b,e,h in gpc_spans],
                      qualification='Native default probe policy with no no-gpc property. Zero ea0 skips physical GPC startup while setting software power fields; restoring one remains a live hardware hypothesis.')
    auxiliary_words, auxiliary_report = prepare_auxiliary(adt_bytes, native)
    # Full-file identities bind these exact producer/consumer sites. Constants
    # are read from the image, not borrowed from another M4 variant.
    host_checks = {
        0x89cd1b8: 0x3d83cd20,  # native vector -> hardware+f30
        0x89cd624: 0xfd000140,  # masks A/B -> hardware+254c/+2550
        0x89cd640: 0xb925550a,  # mask C -> hardware+2554
        0x89abb94: 0x910e8268,  # temperature epoch CPU field3a0
        0x89abb9c: 0x910ea268,  # mapped field3a8
        0x89abba8: 0xfd445900,  # native allocation extent constant
        0x89a7c98: 0x121a658c,  # shared suballocation alignment64
        0x89a7e20: 0x94b673e0,  # generic allocation block zeroing
        0x89cc55c: 0xf91da900,  # mapped epoch -> power+3b50
        0x89d0fa0: 0xf91da900,  # same pointer in configuration refresh
    }
    firmware_checks = {
        0x2f868: 0xb9141ea8, 0x2f874: 0xb91422a8, 0x2f880: 0xb91426a8,
        0xaa58: 0xb95426a8, 0xaac8: 0xf90b8913,
        0x33324: 0xb94f3908, 0x33328: 0x34000688,
        0x301a4: 0xf9451f68, 0x301a8: 0xb9400108,
    }
    for offset, instruction in host_checks.items():
        assert struct.unpack('<I', native(offset, 4))[0] == instruction, hex(offset)
    for offset, instruction in firmware_checks.items():
        assert struct.unpack_from('<I', text, offset)[0] == instruction, hex(offset)
    vector = native(0x712dd00, 16)
    assert struct.unpack('<4I', vector) == (0, 1, 1, 0)
    assert struct.unpack('<2i', native(0x712d8d0, 8)) == (-20, -24)
    assert struct.unpack('<2i', native(0x712d8d8, 8)) == (-4, -8)
    assert struct.unpack('<Q', native(0x712d8b0, 8))[0] == EPOCH_BYTES
    log_bytes = identity_log.read_bytes()
    samples, counts, masks = identity_counts(log_bytes.decode())

    layout = json.loads((source/'graph-receipt.json').read_text())
    prep = json.loads((source/'preparation.json').read_text())
    original = (source/'graph-before.bin').read_bytes()
    blob = bytearray(original)
    validate(blob, layout)
    assert sha(original) == layout['arena_sha256']
    assert prep['pages'] == 56 and prep['work_publication']['channels'] == [0, 1]
    assert prep['hardware_completion_trial']['owned_backing_pages'] == 4
    preserved_files = {name: sha((source/name).read_bytes())
                       for name in ('backing.bin', 'job-data.h', 'render-data.h')}
    assert preserved_files['backing.bin'] == prep['data_sha256']
    objects = {obj['name']: obj for obj in layout['objects']}
    for obj in objects.values():
        start = obj['arena_offset']
        assert sha(blob[start:start+obj['input_bytes']]) == obj['input_sha256'], obj['name']
    hardware = objects['hardware']['arena_offset']
    power = objects['power']['arena_offset']
    status = objects['status_b']
    # GPC startup schedules a timer that stores timestamps through slot32.
    # Matched stores d980/d984 and39ba8/39bac touch only its first16KiB page.
    descriptor = next(d for d in layout['mmio_descriptors'] if d['slot'] == 32)
    assert descriptor['physical'] == '0x288d60000' and descriptor['gpu_va'] == '0xfffffc2000f60000'
    assert descriptor['readonly'] and descriptor['size'] == '0x20000'
    descriptor.update(readonly=False, effective_writable_pages=['0x288d60000'],
                      role_qualification='Native timestamp stores d980/d984 and39ba8/39bac; only first page writable')
    leaf = next(x for x in layout['mmio_leaves'] if x['physical'] == 0x288d60000)
    assert leaf['readonly'] and leaf['gpu_va'] == 0xfffffc2000f60000
    leaf['readonly'] = False
    assert status['input_bytes'] <= STATUS_NATIVE_BYTES <= EPOCH_OFFSET
    assert EPOCH_OFFSET % 64 == 0 and EPOCH_OFFSET+EPOCH_BYTES <= status['reserved_bytes']
    # This is a separate suballocation in unused page-rounded allocation tail,
    # not a fabricated field in the native status_b structure.
    assert not any(blob[status['arena_offset']+STATUS_NATIVE_BYTES:
                        status['arena_offset']+EPOCH_OFFSET+EPOCH_BYTES])
    assert not any(blob[power+0x3118:power+0x5b78])
    assert struct.unpack_from('<Q', blob, power+0x3b58)[0] == 0
    assert struct.unpack_from('<I', blob, power+0x3b60)[0] == 0
    assert not any(edge['parent'] == 'power' and edge['byte_offset'] == 0x3b50
                   for edge in layout['pointers'])
    epoch_va = int(status['gpu_va'], 0)+EPOCH_OFFSET
    changes = []
    initializers = [
            ('hardware', 0x640+32*0x28+0x20, struct.pack('<I', 1)),
            ('hardware', 0xea0, struct.pack('<I', gpc_policy['value'])),
            ('hardware', 0xf30, vector),
            ('hardware', 0x254c, struct.pack('<3I', *masks)),
            ('power', 0x3b50, struct.pack('<Q', epoch_va))]
    initializers += [('hardware', offset, struct.pack('<I', value)) for offset, value in sorted(auxiliary_words.items())]
    for name, offset, payload in initializers:
        obj = objects[name]
        assert offset+len(payload) <= obj['input_bytes']
        start = obj['arena_offset']+offset
        old = bytes(blob[start:start+len(payload)])
        assert not any(old), (name, hex(offset))
        blob[start:start+len(payload)] = payload
        changes.append(dict(object=name, offset=hex(offset), before=old.hex(), after=payload.hex()))
    suballocation = dict(name='temperature_epoch', backing_object='status_b',
                         byte_offset=EPOCH_OFFSET, gpu_va=hex(epoch_va), bytes=EPOCH_BYTES,
                         alignment=64, native_backing_object_bytes=STATUS_NATIVE_BYTES,
                         initialization='fresh zero, from native shared allocator',
                         qualification='Separate retained host-owned epoch in unused allocation tail; disabled sensor mask/count fixture preserved.')
    layout.setdefault('owned_suballocations', []).append(suballocation)
    status['native_object_bytes'] = STATUS_NATIVE_BYTES
    status['input_bytes'] = EPOCH_OFFSET+EPOCH_BYTES
    layout['pointers'].append(dict(parent='power', byte_offset=0x3b50, target='status_b',
                                  target_byte_offset=EPOCH_OFFSET, width=8,
                                  encoded_gpu_va=hex(epoch_va), target_suballocation='temperature_epoch'))
    for obj in layout['objects']:
        start = obj['arena_offset']
        obj['input_sha256'] = sha(blob[start:start+obj['input_bytes']])
    layout['arena_sha256'] = sha(blob)
    validate(blob, layout)
    for i in range(13):
        for suffix in ('cursor', 'ring'):
            obj = objects[f'channel_{i}_{suffix}']
            start, size = obj['arena_offset'], obj['reserved_bytes']
            assert blob[start:start+size] == original[start:start+size]

    graph_prefix = (source/'graph-contract.h').read_text().split('static const u8 graph_bytes[')[0]
    old_leaf = '{ 0x288d60000ULL, 0xfffffc2000f60000ULL, 0 }'
    assert graph_prefix.count(old_leaf) == 1
    graph_prefix = graph_prefix.replace(old_leaf, '{ 0x288d60000ULL, 0xfffffc2000f60000ULL, 1 }')
    graph = graph_prefix+f'static const u8 graph_bytes[{len(blob)}]={{\n'
    graph += ''.join(f'[{i:#x}]={value:#x},\n' for i, value in enumerate(blob) if value)+'};\n'
    report = dict(
        schema='m4rch-native-init-recovery-v1', binary_sha256=HOST_SHA, firmware=firmware,
        source_arena_sha256=sha(original), generator_sha256=sha(Path(__file__).read_bytes()),
        temperature_epoch_audit_sha256=sha(epoch_audit_bytes), temperature_epoch_audit=epoch_audit,
        identity_log_sha256=sha(log_bytes), identity_samples=[dict(phase=p, raw_d04018=v) for p, v in samples],
        native_counts=counts, native_masks=masks, expected_primary_1710='0x1010',
        gpc_policy=gpc_policy,
        auxiliary_power=auxiliary_report,
        gpc_timestamp_mapping=dict(slot=32, physical='0x288d60000', gpu_va='0xfffffc2000f60000',
                                   writable_bytes=0x4000, descriptor_bytes=0x20000,
                                   firmware_stores=['0xd980','0xd984','0x39ba8','0x39bac'],
                                   qualification='First existing page only; remaining seven pages retain read-only PTEs'),
        changes=changes, temperature_epoch=suballocation,
        host_instruction_checks={hex(k): hex(v) for k, v in host_checks.items()},
        firmware_instruction_checks={hex(k): hex(v) for k, v in firmware_checks.items()},
        preserved_draw_files=preserved_files, original_root_channels_preserved=True,
        sensor_mask=0, sensor_count=0, graph_header_sha256=sha(graph.encode()),
        changed_graph_bytes=sum(a != b for a, b in zip(original, blob)),
        qualification='One integrated offline candidate: native defaults and retained temperature epoch. Original complete prepared draw, root work producers, and completion backing unchanged. Sensor calibration remains an explicit disabled fixture; recovery, DMA retirement, device execution and rendering remain unproved. Idle suppression belongs to the recovery preparer.')
    layout['native_init_recovery'] = report
    prep['native_init_recovery'] = report
    shutil.copytree(source, output)
    (output/'graph-before.bin').write_bytes(blob)
    (output/'graph-contract.h').write_text(graph)
    for name, value in (('preparation.json', prep), ('graph-receipt.json', layout),
                        ('native-init-recovery.json', report)):
        (output/name).write_text(json.dumps(value, indent=2)+'\n')
    assert all(sha((output/name).read_bytes()) == digest for name, digest in preserved_files.items())
    print(json.dumps(dict(changed_graph_bytes=report['changed_graph_bytes'], counts=counts,
                          masks=masks, temperature_epoch=hex(epoch_va),
                          root_channels_preserved=True, output=str(output)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'macho', 'firmware_text', 'identity_log', 'recovery_audit', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--adt', type=Path, required=True, help='Captured T6040 ADT to bind the native GPC default policy')
    args = parser.parse_args()
    prepare(args.source, args.macho, args.firmware_text, args.identity_log, args.recovery_audit, args.output, args.adt)
