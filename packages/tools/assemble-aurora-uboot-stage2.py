#!/usr/bin/env python3
"""Assemble a J614s stage 2 using the booted loader and a built package."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import zlib

BASE_HASH = '6a824dd6177a3b895331fa5e32431b7612e7038a5bbc470bfc498956cf7f0d9b'
PREFIX_HASH = 'fe9571af510cec542852e88a21928be29a855c66b2937fc3938a6cdedb3fc501'
DTB_HASH = 'e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8'
OLD_UBOOT_HASH = 'b25192d5f2f4c07f49ee0cc6f15d2c9ec5199cf201cc608c1a651c249ba0b018'
PACKAGE_HASH = 'd499e5ae234a7016c00ffc724e63cfad7334b6aa15e28fa88c06e311eac49c2f'
MEMBER = 'usr/lib/asahi-boot/u-boot-nodtb.bin'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_uboot(data: bytes) -> bool:
    if len(data) < 64 or data[56:60] != b'ARM\x64':
        return False
    offset, extent = struct.unpack_from('<QQ', data, 8)
    return offset == 0 and len(data) <= extent <= 32 * 1024 * 1024


def assemble(base_path: Path, dtb_path: Path, package_path: Path, output: Path) -> dict:
    base, dtb, package = base_path.read_bytes(), dtb_path.read_bytes(), package_path.read_bytes()
    if digest(base) != BASE_HASH or digest(dtb) != DTB_HASH or digest(package) != PACKAGE_HASH:
        raise ValueError('base stage 2, device tree or built package differs from the checked inputs')
    if len(dtb) < 40 or struct.unpack_from('>II', dtb) != (0xd00dfeed, len(dtb)):
        raise ValueError('invalid device tree header')
    if base.count(dtb) != 1:
        raise ValueError('expected one occurrence of the known board device tree')
    offset = base.index(dtb)
    prefix = base[:offset]
    if len(prefix) % 16384 or digest(prefix) != PREFIX_HASH:
        raise ValueError('unexpected stage-2 loader prefix')
    decoder = zlib.decompressobj(31)
    old_uboot = decoder.decompress(base[offset + len(dtb):]) + decoder.flush()
    if not decoder.eof or decoder.unused_data or digest(old_uboot) != OLD_UBOOT_HASH:
        raise ValueError('old U-Boot payload differs from the booted input')
    with tarfile.open(fileobj=io.BytesIO(package), mode='r:xz') as archive:
        entries = [member for member in archive.getmembers() if member.name.lstrip('./') == MEMBER]
        if len(entries) != 1 or not entries[0].isfile():
            raise ValueError('package must contain one regular U-Boot image')
        new_uboot = archive.extractfile(entries[0]).read()
    if not valid_uboot(old_uboot) or not valid_uboot(new_uboot):
        raise ValueError('invalid ARM64 U-Boot header')
    candidate = prefix + dtb + gzip.compress(new_uboot, compresslevel=9, mtime=0)
    receipt = {
        'base_stage2_sha256': digest(base), 'm1n1_prefix_sha256': digest(prefix),
        'dtb_sha256': digest(dtb), 'old_uboot_sha256': digest(old_uboot),
        'package_sha256': digest(package), 'new_uboot_sha256': digest(new_uboot),
        'candidate_sha256': digest(candidate), 'boot_verified': False,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / 'boot.bin.before').write_bytes(base)
    (output / 'boot.bin.candidate').write_bytes(candidate)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assemble(args.base, args.dtb, args.package, args.output)
    except (OSError, ValueError, tarfile.TarError, zlib.error) as error:
        parser.exit(1, f'assembly refused: {error}\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
