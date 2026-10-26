#!/usr/bin/env python3
"""Read a named AGX PIO table from an extracted Mach-O; never access hardware.

The record layout/count must first be established from the matching driver's
getter and constructor. This reports CPU HAL resource IDs, not firmware slots.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def extract(data, count):
    if len(data) < 32 or struct.unpack_from('<I', data)[0] != 0xfeedfacf:
        raise ValueError('Expected little-endian 64-bit Mach-O')
    ncmds, sizeofcmds = struct.unpack_from('<II', data, 16)
    end = 32 + sizeofcmds
    if end > len(data) or count < 1 or count > 256:
        raise ValueError('Invalid command bounds or record count')
    segments, symbols = [], None
    pos = 32
    for _ in range(ncmds):
        if pos + 8 > end:
            raise ValueError('Truncated load command')
        cmd, size = struct.unpack_from('<II', data, pos)
        if size < 8 or pos + size > end:
            raise ValueError('Invalid load command')
        if cmd == 0x19:
            if size < 72:
                raise ValueError('Truncated segment')
            vmaddr, vmsize, offset, length = struct.unpack_from('<QQQQ', data, pos + 24)
            if offset + length > len(data):
                raise ValueError('Segment exceeds file')
            segments.append((vmaddr, vmsize, offset, length))
        elif cmd == 2:
            if size < 24:
                raise ValueError('Truncated symbol table command')
            symbols = struct.unpack_from('<IIII', data, pos + 8)
        pos += size
    if pos != end or symbols is None:
        raise ValueError('Missing symbols or inconsistent load commands')
    off, number, strings, stringsize = symbols
    if off + number * 16 > len(data) or strings + stringsize > len(data):
        raise ValueError('Symbol table exceeds file')
    matches = []
    for i in range(number):
        index, kind, _, _, value = struct.unpack_from('<IBBHQ', data, off + 16 * i)
        if index >= stringsize:
            raise ValueError('String index exceeds table')
        stop = data.find(b'\0', strings + index, strings + stringsize)
        if stop < 0:
            raise ValueError('Unterminated symbol')
        name = data[strings + index:stop].decode('utf-8', errors='replace')
        if name.endswith('AGFPIOGFXHALRelativeOffsetTableG16X') and kind & 0x0e == 0x0e:
            matches.append((name, value))
    if len(matches) != 1:
        raise ValueError('Expected exactly one G16X PIO table')
    name, address = matches[0]
    spans = [(offset + address - base) for base, _, offset, length in segments
             if base <= address and address + count * 32 <= base + length]
    if len(spans) != 1:
        raise ValueError('Table is not wholly inside one file-backed segment')
    start = spans[0]
    records = []
    for i in range(count):
        slot, relative, size, alternate, alternate_size, tail = struct.unpack_from(
            '<IIQIIQ', data, start + i * 32)
        records.append({'hal_resource_id': slot, 'relative_offset': hex(relative),
                        'length': hex(size), 'alternate_offset': hex(alternate),
                        'alternate_length': hex(alternate_size), 'unqualified_tail': hex(tail)})
    return {'macho_sha256': hashlib.sha256(data).hexdigest(), 'symbol': name,
            'table_vaddr': hex(address), 'record_bytes': 32, 'records': records,
            'scope': 'Static CPU HAL table; not firmware hardware records or validated MMIO addresses'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('macho', type=Path)
    parser.add_argument('--count', type=int, required=True,
                        help='Count verified from this driver table-length getter')
    args = parser.parse_args()
    print(json.dumps(extract(args.macho.read_bytes(), args.count), indent=2))


if __name__ == '__main__':
    main()
