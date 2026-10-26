#!/usr/bin/env python3
"""Bind the inherited T6040 counter resource to matched private constructor spans."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
HOST_BASE = 0xfffffe0000000000


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def prepare(macho, output):
    data = macho.read_bytes()
    if hashlib.sha256(data).hexdigest() != HOST_SHA:
        raise ValueError('Matched 25G83 AGX input required')
    segments = []
    position = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', data, position + 24))
        position += size

    def read(address, size):
        addresses = [off + HOST_BASE + address - va for va, _, off, length in segments
                     if va <= HOST_BASE + address and HOST_BASE + address + size <= va + length]
        if len(addresses) != 1:
            raise ValueError('Constructor span not uniquely backed')
        return data[addresses[0]:addresses[0] + size]

    # Keep private instruction bytes out of this kit. Bind decoded numeric
    # operands to the exact matched image and reviewed constructor span hashes.
    spans = []
    for name, begin, end, expected_hash in [
        ('T6040_base_constructor_call', 0x89ea488, 0x89ea4b0,
         '5c60024e3e575a075ca2469c479d442852a5c332aef0d7eed2bfc6cb859b9561'),
        ('counter_resource_size_count_base', 0x89d9d60, 0x89d9de8,
         '0d70645f75a83911ad306386817714a21edfbac28a8df12f50368a353afeb27b')]:
        actual_hash = hashlib.sha256(read(begin, end - begin)).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError('Matched producer span differs: ' + name)
        spans.append({'name': name, 'start': hex(begin), 'end': hex(end),
            'bytes': end - begin, 'sha256': actual_hash})
    report = {'schema': 'm4rch.native-t6040-counter-resource.v1', 'macho': pin(macho),
        'spans': spans, 'slot': 41, 'resource_offset': '0xb478',
        'physical': '0x288e1f800', 'size': 0x4000, 'instances': 1,
        'size_source': 'round_down(page_bytes + 0x49b, page_bytes), with page_bytes=0x4000',
        'physical_source': 'primary SGX base + 0xe1f000 + 0x800',
        'inheritance': 'T6040 configureDevice calls matched G16 configureDevice before its overrides.',
        'experimental_descriptor_flags': 1,
        'experimental_page_permissions': [{'physical': '0x288e1c000', 'writable': True,
            'source': 'saved native counter store/readback and existing slot40 alias'},
            {'physical': '0x288e20000', 'writable': False,
             'source': 'unchanged second-page experimental read-only selection'}],
        'native_permission_translation_complete': False, 'hardware_actions': [],
        'qualification': 'Exact inherited native counter geometry. Captured first-page writes support the explicit experiment permission; native firmware flags/PTE policy and full normal boot remain unproved.'}
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('macho', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = prepare(args.macho.resolve(), args.output.resolve())
    print(json.dumps({'slot': report['slot'], 'size': report['size'], 'source_spans': len(report['spans'])}))
