#!/usr/bin/env python3
"""Record native queue pointer ownership from the matched local Apple input.

This reads files only. Numeric source closures are saved without binary slices.
"""
import hashlib
import json
from pathlib import Path
import struct

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
AGX = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
EXPECTED = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
BASE = 0xfffffe0000000000


def pin(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    raw = AGX.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    segments, offset = [], 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        command, size = struct.unpack_from('<II', raw, offset)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', raw, offset + 24))
        offset += size

    def read(address, size):
        address += BASE
        offsets = [file_offset + address - vm for vm, _, file_offset, extent
                   in segments if vm <= address and address + size <= vm + extent]
        assert len(offsets) == 1
        return raw[offsets[0]:offsets[0] + size]

    spans = []
    for name, start, end in [
        ('timestamp_queue_object_creation', 0x898960c, 0x8989654),
        ('3d_channel_timestamp_argument', 0x898c97c, 0x898ca18),
        ('ta_channel_timestamp_argument', 0x898ca84, 0x898ca94),
        ('ta_channel_allocator_argument', 0x8a2e2e8, 0x8a2e398),
        ('channel_caller_argument_capture', 0x897fa50, 0x897fb00),
        ('channel_timestamp_argument_store', 0x8980004, 0x8980008),
        ('timestamp_queue_mapping', 0x8a23810, 0x8a238d4),
        ('timestamp_queue_reset_and_mode', 0x8a235a0, 0x8a23604),
        ('qos_id_capacity', 0x8a08bf4, 0x8a08c10),
        ('hardware_timestamp_mapping_argument', 0x89aa3dc, 0x89aa408),
        ('selected_gpu_to_firmware_identity', 0x89c8ff8, 0x89c9004),
        ('ksm_config_second_callback', 0x898714c, 0x898718c),
    ]:
        code = read(start, end - start)
        spans.append({'name': name, 'start': hex(start), 'end_exclusive': hex(end),
                      'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest()})

    virtual_targets = []
    for name, vtable, expected_target in [
        ('G16_3D', 0x7eaa560, 0x895a9dc),
        ('G16_SKSM_3D', 0x7eaa8e0, 0x895a9dc),
        ('G16_TA', 0x7eadc98, 0x8a1ecac),
        ('G16_SKSM_TA', 0x7eae018, 0x8a1ecac),
    ]:
        entry_address = vtable + 0x10 + 0x240
        entry = read(entry_address, 8)
        encoded = struct.unpack('<Q', entry)[0]
        target = 0x7004000 + (encoded & 0xffffffff)
        assert target == expected_target
        virtual_targets.append({'class': name, 'address_point': hex(vtable + 0x10),
                                'slot': '0x240', 'entry_address': hex(entry_address),
                                'entry_sha256': hashlib.sha256(entry).hexdigest(),
                                'target': hex(target)})

    timestamp_entry = read(0x7ea8668 + 0x10 + 0x2d8, 8)
    timestamp_target = 0x7004000 + (struct.unpack('<Q', timestamp_entry)[0] & 0xffffffff)
    assert timestamp_target == 0x89c8ff8
    assert read(timestamp_target, 12) == bytes.fromhex('5f2403d5e00301aac0035fd6')

    report = {
        'schema': 'm4rch.native-t6040-queue-bindings.v7',
        'offline_only': True,
        'source': pin(AGX), 'source_spans': spans,
        'channel_init_virtual_targets': virtual_targets,
        'bindings': {
            'state_00': {'host_source': 'channel+88', 'role': 'firmware queue cursor record',
                         'publication_pc': '0x898074c'},
            'state_08': {'host_source': 'channel+90', 'role': 'firmware command pointer ring',
                         'publication_pc': '0x8980acc'},
            'state_10': {'host_source': 'channel+98', 'role': 'firmware timestamp/notifier list',
                         'argument_capture_pc': '0x897fa78', 'argument_store_pc': '0x8980004',
                         'owner_chain': ['commandqueue+680', 'AGXTimeStampQueue+28',
                                         'channel_init_x5', 'channel+98', 'state+10'],
                         'firmware_alias_pc': '0x8a2384c', 'cpu_alias_pc': '0x8a238d0'},
            'state_9c': {'host_source': 'channel+f8',
                         'role': 'same command queue scheduler firmware slot used by config+4a',
                         'owner_chain': ['commandqueue+8b8', 'channel+f8', 'state+9c'],
                         'queue_load_pc': '0x897fac8', 'channel_store_pc': '0x897facc'},
        },
        'timestamp_list_reset': {
            'bytes': 24, 'offset_00_u64': 0, 'offset_08_u64': 'own firmware address',
            'offset_10_u32': 'one only when native host update mode is 2',
            'offset_14_u32': 0,
            'gravity_existing_jobs_encoder_matches': 'native update modes 0 and 1',
            'linux_initial_update_mode_policy': 0,
        },
        'qos_native_id_capacity': {'entries': 128, 'argument_pc': '0x8a08c04',
                                   'manager_init_call_pc': '0x8a08c08'},
        'hardware_timestamp_binding': {
            'hardware_offset': '0x28', 'gpu_va_argument': '0xfffffc2181400000',
            'selected_asc_vtable': '0x7ea8668', 'virtual_slot': '0x2d8',
            'entry_sha256': hashlib.sha256(timestamp_entry).hexdigest(),
            'target': hex(timestamp_target), 'conversion': 'identity',
            'store_pc': '0x89aa404',
            'role': 'owned timestamp mapping GPU/FW alias; not the QoS clock result',
        },
        'ksm_config_callback_66': {
            'object': 'descriptor+58', 'virtual_slot': '0x1e0',
            'call_pc': '0x8987184', 'store_pc': '0x8987188',
            'concrete_graphics_owner_semantics_resolved': False,
            'linux_experimental_policy': 0,
            'limitations': [
                'Generic config writer is not proof of its use by the concrete graphics caller.',
                'Selected CL/TA/3D descriptor initKSM overloads are no-op and getDataMaster returns255.',
                'Do not interpret callback66 as an engine, ASID or process ID without a source closure.',
            ],
        },
        'production_implication': [
            'Bind the existing owned 24-byte list to native state+10; do not invent a new job allocation role.',
            'Use the same owned scheduler slot for state+9c and configuration+4a.',
            'Native queue and ring pointers still require real allocation/mapping ownership.',
            'A host QoS lease alone does not implement native firmware QoS registration.',
        ],
        'composed_without_rerun': pin(ROOT / 'docs/evidence/2026-10-11-gravity-native-t6040-queue-v7.json'),
        'limitations': ['Static argument and ownership closure; no hardware, DMA or retirement proof.'],
        'hardware_actions': [],
    }
    destination = ROOT / 'docs/evidence/2026-10-11-gravity-native-queue-bindings-v7.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(pin(destination)))


if __name__ == '__main__':
    main()
