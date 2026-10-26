#!/usr/bin/env python3
import gzip
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from prepare import PROJECT, OUTPUT, WORK, PIN, sha, run

sys.path.insert(0, str(PROJECT / 'sdboot'))
from loader import pack, validate_uboot_config


def main():
    source = PROJECT / 'out/aurora-loader/loader/m1n1.bin'
    # Keep the exact native-working Aurora second-stage m1n1; its runtime
    # firmware-buffer reservations already cover inherited stage-1 allocations.
    native = json.loads((PROJECT / 'out/aurora-loader/manifest.json').read_text())
    if sha(source) != native['files']['loader/m1n1.bin']['sha256']:
        raise ValueError('Native-working second-stage m1n1 differs')
    prefix, control, uboot = source.read_bytes(), (OUTPUT / 'control.dtb').read_bytes(), (WORK / 'uboot/u-boot-nodtb.bin').read_bytes()
    pack(prefix, control, uboot)
    validate_uboot_config(WORK / 'uboot/.config', WORK / 'uboot/drivers/serial/Makefile', internal=True)
    if b'2026.07-AUBS001' not in uboot or b'AUBS001: missing Aurora J614s control tree' not in uboot:
        raise ValueError('Missing stage-2 identity')
    first = (OUTPUT / 'stage1.bin').read_bytes()
    magic = b'AURORA-S1-CFG01\0'
    if len(first) % 16384 or not first.endswith(b'STACKBOT') or first.count(magic) != 1:
        raise ValueError('Invalid first-stage image boundary/config')
    offset = first.index(magic) + len(magic)
    body = first[offset:offset + 240]
    version, window, esp, path = struct.unpack('<II40s192s', body)
    crc, = struct.unpack_from('<I', first, offset + 240)
    if version != 1 or window != 0 or esp.rstrip(b'\0') != b'5fdb35c6-3a66-416d-8358-6555fd99fcc5' or path.rstrip(b'\0') != b';boot.bin' or zlib.crc32(body) != crc:
        raise ValueError('First-stage target/CRC differs')
    if b'nvme.adopt=live-rtkit-v1' not in first or b'AUBS001-stage1' not in first:
        raise ValueError('Missing live-session handoff')
    compressed = gzip.compress(uboot, compresslevel=9, mtime=0)
    assert gzip.decompress(compressed) == uboot
    payload = prefix + control + compressed
    if len(first) < ((len(payload) + 16384 + 16383) // 16384) * 16384:
        raise ValueError('First-stage image has insufficient room for stage 2 and variables')
    (OUTPUT / 'boot.bin').write_bytes(payload)
    sources = {'m1n1': PIN, 'uboot': '7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c',
               'linux_dts': '420a1c8f5492daeaa59ffba565aac610f5218d27'}
    for name in ['stage1', 'uboot']:
        tree = WORK / name
        patch = subprocess.check_output(['git', '-C', str(tree), 'diff', '--binary', 'HEAD'])
        for f in run('git', '-C', str(tree), 'ls-files', '--others', '--exclude-standard').splitlines():
            r = subprocess.run(['git', 'diff', '--no-index', '--binary', '--', '/dev/null', f], cwd=tree, stdout=subprocess.PIPE)
            if r.returncode != 1: raise ValueError('Cannot export ' + f)
            patch += r.stdout
        (OUTPUT / (name + '.patch')).write_bytes(patch)
    profile = {'test': 'AUBS001', 'revision': 1, 'sources': sources, 'wallace_source_inputs': [],
               'stage1_target': 'boot.bin on ESP 5fdb35c6-3a66-416d-8358-6555fd99fcc5',
               'stage1_requires_recovery_enrollment': True, 'native_boot_tested': False,
               'kernel_initramfs_mesa_changed': False, 'speakers_enabled': False,
               'retained_local_integration': 'J614s adaptation and live firmware/board handoff',
               'stage2_m1n1_native_sha256': sha(source)}
    profile['chainload_image_room_bytes'] = len(first) - len(payload)
    (OUTPUT / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    names = ['stage1.bin', 'boot.bin', 'control.dtb', 'profile.json', 'control-provenance.json', 'stage1.patch', 'uboot.patch']
    (OUTPUT / 'manifest.json').write_text(json.dumps({'test': 'AUBS001', 'files': {n: {'bytes': (OUTPUT / n).stat().st_size, 'sha256': sha(OUTPUT / n)} for n in names}}, indent=2) + '\n')
    print(json.dumps({'test': 'AUBS001', 'stage1_sha256': sha(OUTPUT / 'stage1.bin'), 'boot_sha256': sha(OUTPUT / 'boot.bin'), 'wallace_source_inputs': []}))


if __name__ == '__main__':
    main()
