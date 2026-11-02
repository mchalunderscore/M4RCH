#!/usr/bin/env python3
"""Build an Aura trial with the already-booted DTB and U-Boot payload."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'cache/uboot-aurora-20261101/stage2/boot.bin.candidate'
EXPECTED = {
    'booted': 'e36106dc730a691e7016a7b43588cd3f9f4046400affdf54e4506591b3fbde9f',
    'old_prefix': 'fe9571af510cec542852e88a21928be29a855c66b2937fc3938a6cdedb3fc501',
    'aura': '25660ee854c384c5395f0c81adec030bf0c3adcb5ecde97cdf64671ab5815026',
    'dtb': 'e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8',
    'uboot': '410658b62acd693560175317456d36fee83eb8ae3e5a9f6e03d7bb2149f7cf8d',
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def checked(path, name):
    data = path.read_bytes()
    if digest(data) != EXPECTED[name]:
        raise ValueError(f'{name} does not match its verified build')
    return data

def main():
    out = ROOT / 'cache/aura-stage2-assembly-20261101'
    if out.exists():
        raise ValueError(f'{out} already exists; preserve it and inspect it first')
    booted = checked(BASE, 'booted')
    aura = checked(Path('/usr/lib/asahi-boot/m1n1.bin'), 'aura')
    dtb = checked(Path('/usr/lib/asahi-boot/apple-j614s.dtb'), 'dtb')
    uboot = checked(Path('/usr/lib/asahi-boot/u-boot-nodtb.bin'), 'uboot')
    if len(aura) % 16384 or struct.unpack_from('>II', dtb) != (0xd00dfeed, len(dtb)):
        raise ValueError('unexpected Aura alignment or invalid DTB')
    if booted.count(dtb) != 1:
        raise ValueError('booted loader must contain exactly one matching DTB')
    offset = booted.index(dtb)
    if digest(booted[:offset]) != EXPECTED['old_prefix']:
        raise ValueError('booted m1n1 prefix differs')
    compressed = booted[offset + len(dtb):]
    decoder = zlib.decompressobj(31)
    decoded = decoder.decompress(compressed) + decoder.flush()
    if not decoder.eof or decoder.unused_data or decoded != uboot:
        raise ValueError('booted U-Boot payload differs or has trailing data')
    candidate = aura + dtb + compressed
    if gzip.decompress(candidate[len(aura) + len(dtb):]) != uboot:
        raise ValueError('candidate payload verification failed')
    out.mkdir(parents=True)
    (out / 'boot.bin.candidate').write_bytes(candidate)
    (out / 'receipt.json').write_text(json.dumps({
        'booted_sha256': digest(booted), 'aura_sha256': digest(aura),
        'dtb_sha256': digest(dtb), 'uboot_sha256': digest(uboot),
        'candidate_sha256': digest(candidate), 'boot_verified': False,
    }, indent=2) + '\n')
    print((out / 'receipt.json').read_text())

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zlib.error) as exc:
        sys.exit(f'refused: {exc}')
