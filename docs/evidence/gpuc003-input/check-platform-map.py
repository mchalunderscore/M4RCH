#!/usr/bin/env python3
"""Verify pinned 25G83 AGX constructor instructions; no hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SHA256 = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
# File offsets and raw AArch64 words from the matching extracted Mach-O.
WORDS = {
    0xa7dd4: 0x52880008, 0xa7de4: 0xd2880009,
    0xa7de8: 0xf2a04829, 0xa7dec: 0xf2c000a9,
    0xa7e04: 0xb9098a68, 0xa7e0c: 0xf903c669,
    0xa7ba4: 0xd2900019, 0xa7ba8: 0xf2a007b9,
    0xa7bac: 0xf2c000b9, 0xa7e50: 0xb937f268,
    0xa7e58: 0xf91afa79,
}


def verify(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Expected matching 25G83 AGXG16X 353.14 binary')
    for offset, word in WORDS.items():
        if struct.unpack_from('<I', data, offset)[0] != word:
            raise ValueError(f'Constructor instruction differs at {offset:#x}')
    return {'macho_sha256': SHA256, 'verified_instruction_words': len(WORDS),
            'resources': [
                {'slot': 0, 'name': 'GPCAICSWInt', 'physical': '0x502414000', 'extent': '0x4000'},
                {'slot': 11, 'name': 'PushTelemetryDashboardConfigSpace',
                 'physical': '0x5003d8000', 'extent': '0x4000'}],
            'scope': 'Static mapping provenance; not hardware access qualification'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('macho', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.macho.read_bytes()), indent=2))
