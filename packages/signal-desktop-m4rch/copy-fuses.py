#!/usr/bin/env python3
"""Preserve the packaged Signal Electron fuses when replacing its runtime."""
import sys
from pathlib import Path

sentinel = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'
original = Path(sys.argv[1]).read_bytes()
target = Path(sys.argv[2])
replacement = bytearray(target.read_bytes())

def wire(data):
    if data.count(sentinel) != 1:
        raise ValueError('Expected exactly one Electron fuse sentinel')
    start = data.index(sentinel) + len(sentinel)
    version, length = data[start:start + 2]
    if version != 1 or length != 9:
        raise ValueError(f'Unexpected Electron fuse layout: {version}, {length}')
    return start + 2, length

old_start, old_length = wire(original)
new_start, new_length = wire(replacement)
assert old_length == new_length
fuses = original[old_start:old_start + old_length]
if any(fuse not in b'01r' for fuse in fuses):
    raise ValueError('Invalid Electron fuse value')
replacement[new_start:new_start + new_length] = fuses
target.write_bytes(replacement)
