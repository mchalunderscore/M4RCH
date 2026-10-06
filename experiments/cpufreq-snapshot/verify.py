#!/usr/bin/env python3
"""Verify the exact running diagnostic kernel and installed package generation."""
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess


def build_id(notes):
    offset = 0
    while offset + 12 <= len(notes):
        namesz, descsz, kind = struct.unpack_from('<III', notes, offset)
        offset += 12
        name = notes[offset:offset+namesz]; offset += (namesz+3)&~3
        desc = notes[offset:offset+descsz]; offset += (descsz+3)&~3
        if name == b'GNU\0' and kind == 3 and len(desc) == descsz:
            return desc.hex()
    raise ValueError('GNU kernel build ID absent')


def main():
    kit = Path(__file__).resolve().parent
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=kit, check=True)
    receipt = json.loads((kit/'build.json').read_text())
    if platform.machine() != 'aarch64' or platform.release() != receipt['kernel_release']:
        raise ValueError('Different architecture or kernel release')
    if b'apple,j614s\0' not in Path('/proc/device-tree/compatible').read_bytes():
        raise ValueError('Different board; do not bypass the guard')
    if build_id(Path('/sys/kernel/notes').read_bytes()) != receipt['kernel_build_id']:
        raise ValueError('Different running build; boot the staged diagnostic first')
    provenance = json.loads(Path('/usr/share/doc/linux-m4rch/build-provenance.json').read_text())
    if (provenance['modules_sha256'] != receipt['modules_sha256'] or
            provenance['compressed_image_sha256'] != receipt['compressed_image_sha256']):
        raise ValueError('Install this kit\'s matching packages before capturing')
    print('Exact diagnostic build and installed package generation accepted.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
