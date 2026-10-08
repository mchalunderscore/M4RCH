#!/usr/bin/env python3
"""Offline GPUC003 receipt/arena check against the verified GPUC002 baseline.

This checks generated input, not installed PTEs, IRQ ownership or hardware safety.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

PAGE = 0x4000
ROOT = 0xfffffc2000100000
MMIO = ROOT + 0x100000
PLATFORM = {0: (0x502414000, 0xfffffc2001a00000),
            11: (0x5003d8000, 0xfffffc2001b18000)}


def number(value):
    return int(value, 0) if isinstance(value, str) else value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(baseline, receipt, arena):
    require(number(receipt['base']) == ROOT and number(receipt['mmio_virtual_base']) == MMIO,
            'Changed graph geometry')
    require(len(arena) == number(receipt['arena_bytes']) and len(arena) % PAGE == 0,
            'Arena size differs or is not page aligned')
    require(hashlib.sha256(arena).hexdigest() == receipt['arena_sha256'], 'Arena hash differs')
    require(number(baseline['base']) == ROOT and number(baseline['mmio_virtual_base']) == MMIO,
            'Unexpected baseline geometry')
    require(number(baseline['arena_bytes']) == len(arena), 'Changed object arena size')
    for key in ('static_map_sha256', 'voltage_adt_sha256', 'voltage_input_sha256'):
        require(receipt[key] == baseline[key], f'Changed baseline input: {key}')

    def leaves(data):
        result = {}
        previous = -1
        for leaf in data['mmio_leaves']:
            pa, va = number(leaf['physical']), number(leaf['gpu_va'])
            require(type(leaf['readonly']) is bool, 'Permission must be a JSON boolean')
            require(pa % PAGE == va % PAGE == 0, 'Unaligned device leaf')
            require(va > previous and va >> 25 == ROOT >> 25, 'Unsorted, duplicate or out-of-L2 VA')
            require(va >= ROOT + len(arena), 'Device leaf overlaps objects')
            result[va] = (pa, leaf['readonly'])
            previous = va
        return result

    old = leaves(baseline)
    expected = dict(old)
    for pa, va in PLATFORM.values():
        require(va not in expected and all(pa != p for p, _ in expected.values()),
                'Platform mapping aliases baseline')
        expected[va] = (pa, False)
    actual = leaves(receipt)
    require(actual == expected, 'Expected unchanged SGX leaves plus exactly two writable platform leaves')
    require(number(receipt['mapped_pages']) == len(arena) // PAGE + len(actual), 'Page count differs')
    descriptors = {}
    for row in receipt['mmio_descriptors']:
        slot = number(row['slot'])
        require(slot not in descriptors, 'Duplicate hardware descriptor slot')
        descriptors[slot] = row
    require(set(descriptors) == {number(r['slot']) for r in baseline['mmio_descriptors']} | set(PLATFORM),
            'Unexpected descriptor slots')
    for row in baseline['mmio_descriptors']:
        new = descriptors[number(row['slot'])]
        for key in ('physical', 'gpu_va', 'size', 'readonly'):
            require(new[key] == row[key], f'Changed baseline slot {row["slot"]}: {key}')
    hardware = [o for o in receipt['objects'] if o['name'] == 'hardware']
    require(len(hardware) == 1, 'Expected one hardware object')
    h = number(hardware[0]['arena_offset'])
    for slot, (pa, va) in PLATFORM.items():
        row = descriptors[slot]
        require((number(row['physical']), number(row['gpu_va']), number(row['size']), row['readonly'])
                == (pa, va, PAGE, False), f'Wrong platform descriptor {slot}')
        offset = h + 0x640 + slot * 40
        require(offset + 36 <= h + number(hardware[0]['input_bytes']), 'Descriptor exceeds hardware input')
        physical, address, size, range_size = struct.unpack_from('<QQII', arena, offset)
        require((physical, address, size, range_size) == (pa, va, PAGE, PAGE),
                f'Arena descriptor {slot} disagrees with receipt')
    require(len(receipt['objects']) == len(baseline['objects']), 'Changed object count')
    for obj, old_obj in zip(receipt['objects'], baseline['objects']):
        for key in ('name', 'arena_offset', 'gpu_va', 'input_bytes', 'reserved_bytes'):
            require(obj[key] == old_obj[key], f'Changed object geometry: {key}')
        start, length = number(obj['arena_offset']), number(obj['input_bytes'])
        require(0 <= start <= start + length <= len(arena), 'Object outside arena')
        require(hashlib.sha256(arena[start:start+length]).hexdigest() == obj['input_sha256'],
                f'Object hash differs: {obj["name"]}')
    return {'result': 'PASS', 'device_leaves': len(actual),
            'writable_leaves': sum(not ro for _, ro in actual.values()),
            'mapped_pages': receipt['mapped_pages'],
            'scope': 'Offline inputs only; native shadow walk, RAM exclusion and IRQ checks still required'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('receipt', type=Path)
    p.add_argument('arena', type=Path)
    a = p.parse_args()
    try:
        print(json.dumps(check(json.loads(a.baseline.read_text()), json.loads(a.receipt.read_text()),
                               a.arena.read_bytes()), indent=2))
    except (ValueError, KeyError, TypeError, struct.error) as error:
        p.exit(1, f'FAIL: {error}\n')
