#!/usr/bin/env python3
"""Pin the matched T6040 constructor's absent primary GMGIF resource; no MMIO."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
HOST_BASE = 0xfffffe0000000000
TABLE_SHA = 'bc4968f9b3b3b7b45474251e7fdb3cb649c929de0a0ae857aafb2235f0b3c8b5'
# Private instruction bytes stay outside this kit. These hashes bind the
# decoded operands below to the reviewed source and complete subclass bodies.
SPANS = [
    ('resource_pointer27', 0x89680fc, 0x8968138, 'da4b1dc474ec36dbba364abeab641cc745a07e2b81fac003b43b85844d27cac2'),
    ('zero_resource_array_and_flags_value', 0x896833c, 0x8968350, '185bb49902af3a48d27a2431367ebc8036d190c56c1f84fdd962c022ef9fa38e'),
    ('slot27_flags_and_payload_zero', 0x89683f8, 0x896840c, 'd73f6c37789c0d3e9ac99999624623709a1e908ac896ee7c6af14c872b864410'),
    ('native_primary_table_loop', 0x8968bb8, 0x8968c48, 'cc9cdc91ef88cb9aeba0aead10f52ec729a6d4baafa75b8f578321ee92773f42'),
    ('G16_inherited_constructor', 0x89d9b9c, 0x89d9e34, '5c27b21edfb0495295d80218a44b4464cbc5c7829a978a82bd101e96d58618fe'),
    ('T6040_inherited_constructor_and_overrides', 0x89ea464, 0x89ea9f0, '00c3048d5c14d5a283d445f0bc5c438f9b66c951e59359f210ba2e37d7f8bfd4'),
    ('native_hw_descriptor_producer', 0x89aa204, 0x89aa264, '14e76201114e4bf3ab2ce28838fbf61c948756833b15ddcd51ee7f48d21eca28'),
    ('native_primary_fw_mapping_zero_guard', 0x89cef40, 0x89cefac, '364c6f004312cb67bc5755bf306eac6302ccb75d0ea222350ce6ba07bf35ad0b'),
    ('T6040_primary_table_getters', 0x89e7e68, 0x89e7e84, 'c62b1f05f9ef84fc00ade8f7fd30959c264de9cfc8a9e900512f8c891f835dce'),
]


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def prepare(macho, symbols, pio_report, firmware_report, output):
    data = macho.read_bytes()
    if hashlib.sha256(data).hexdigest() != HOST_SHA:
        raise ValueError('Matched 25G83 AGX input required')
    segments, position = [], 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', data, position + 24))
        position += size

    def read(address, size):
        addresses = [off + HOST_BASE + address - va for va, _, off, length in segments
                     if va <= HOST_BASE + address and HOST_BASE + address + size <= va + length]
        if len(addresses) != 1:
            raise ValueError('Source span not uniquely backed')
        return data[addresses[0]:addresses[0] + size]

    spans = []
    for name, begin, end, expected in SPANS:
        actual = hashlib.sha256(read(begin, end - begin)).hexdigest()
        if actual != expected:
            raise ValueError('Matched source span differs: ' + name)
        spans.append({'name': name, 'start': hex(begin), 'end': hex(end),
                      'bytes': end - begin, 'sha256': actual})
    bzero = [s for s in json.loads(symbols.read_text())
             if s['name'] == '_bzero' and s['address'] == '0xfffffe000b744da0'
             and s['owner'] == 'com.apple.kernel']
    if len(bzero) != 1:
        raise ValueError('Matched kernel zeroing target not established')
    table = read(0x71305b8, 13 * 32)
    if hashlib.sha256(table).hexdigest() != TABLE_SHA:
        raise ValueError('Matched primary table differs')
    slots = [row[0] for row in struct.iter_unpack('<8I', table)]
    pio = json.loads(pio_report.read_text())
    if slots != [r['hal_resource_id'] for r in pio['records']] or 27 in slots:
        raise ValueError('Primary table absence or source cross-check differs')
    fw = json.loads(firmware_report.read_text())
    fwslot = [r for r in fw['slots'] if r['slot'] == 27]
    if not fw['zero_physical_skips_record'] or len(fwslot) != 1:
        raise ValueError('Existing qualified firmware copy evidence absent')
    slot = 27
    report = {
        'schema': 'm4rch.native-t6040-slot27-absent.v1', 'slot': slot,
        'name': fwslot[0]['name'], 'macho': pin(macho), 'source_spans': spans,
        'source_pins': [pin(symbols), pin(pio_report), pin(firmware_report)],
        'primary_table': {'address': '0x71305b8', 'bytes': len(table),
                          'sha256': TABLE_SHA, 'slots': slots, 'contains_slot27': False},
        'cpu_resource': {'base': hex(0x780 + slot * 0x438), 'record_stride': '0x438',
                         'flags': 2, 'instances': 0, 'physical': 0, 'extent': 0, 'relative': 0},
        'cpu_resource_producer': {
            'clear': {'address': '0x8968348', 'base': '0x780', 'bytes': '0xe1b0',
                      'target': '0xfffffe000b744da0', 'symbol': '_bzero'},
            'flags_store': {'address': '0x89683f8', 'object_offset': '0x7968', 'value': 2},
            'payload_clear': {'address': '0x8968408', 'object_offset': '0x796c', 'bytes': '0x214'},
            'inheritance_calls': [{'address': '0x89ea4ac', 'target': '0x89d9b9c'},
                                  {'address': '0x89d9bc8', 'target': '0x896731c'}],
            'subclass_review': 'Matched G16 and T6040 direct resource overrides do not populate slot 27.'},
        'hardware_descriptor': {'physical': 0, 'virtual': 0, 'size': 0, 'stride': 0,
                                'relative': 0, 'flags': 2},
        'hardware_descriptor_offset': hex(0x640 + slot * 0x28),
        'hardware_descriptor_producer': {'start': '0x89aa218', 'end': '0x89aa264',
                                        'record_stride': '0x28', 'record_count': 53,
                                        'size': 'CPU instances * CPU extent',
                                        'flags': 'CPU flags & 2', 'virtual_initialization': 0},
        'firmware_mapping': {'zero_physical_guard': '0x89cef70', 'slot27_skipped': True,
                             'firmware_cached_record': fwslot[0]['firmware_cached_record'],
                             'cached_copy_zero_physical_guard': '0x32f04',
                             'cached_copy_qualified_by_existing_report': True},
        'production_transfer': {'absent_primary_descriptor': True, 'mapping_pages': 0,
                                'donor_mapping_used': False, 'serialized_prefix_bytes': 36},
        'qualification': 'Bounded native constructor and hardware-descriptor producer binding. Flags 2 are retained even with zero geometry. This does not qualify all external callbacks or subsequent native lifetime changes, firmware permissions, full normal startup, submission or render.',
        'normal_startup_qualified': False, 'hardware_actions': [],
        'private_binary_or_instruction_bytes_exported': False,
    }
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['macho', 'symbols', 'pio_report', 'firmware_report', 'output']:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = prepare(*[getattr(args, name).resolve() for name in
                       ['macho', 'symbols', 'pio_report', 'firmware_report', 'output']])
    print(json.dumps({'slot': result['slot'], 'hardware_descriptor': result['hardware_descriptor'],
                      'source_spans': len(result['source_spans']), 'hardware_actions': []}))
