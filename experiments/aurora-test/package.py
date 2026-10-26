#!/usr/bin/env python3
"""Package the compiled test with the existing NVMe initramfs's root contract."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile

PROJECT = Path(__file__).resolve().parents[2]
KIT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('nvme', PROJECT / 'scripts/migrate-nvme-macos.py')
nvme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nvme)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(work, base_initramfs):
    profile = json.loads((KIT / 'profile.json').read_text())
    release = (work / 'kernel.release').read_text().strip()
    if release != profile['release']:
        raise ValueError('Kernel release differs from pinned test profile')
    members = {name.rstrip('/'): item for name, item in
               nvme.initramfs_members(base_initramfs.read_bytes()).items()}
    config = members['etc/nvme-root.conf'][1].decode()
    config, count = re.subn(r"(?m)^KERNEL_RELEASE='[^']*'$", f"KERNEL_RELEASE='{release}'", config)
    if count != 1:
        raise ValueError('Missing unique kernel identity')
    # The test follows the established NVMe root, not any APFS or historical SD root.
    for expected in ["ROOT_UUID='7568fe83-378f-5b78-ab12-ccc36ff09a90'",
                     "ROOT_PARTITION_UUID='e80ee324-c4c5-4f3e-81b7-464adb71d41a'",
                     "ROOT_OFFSET='363598970880'", "ROOT_BYTES='126880841728'"]:
        if expected not in config:
            raise ValueError('Unexpected root identity: ' + expected)
    for name in list(members):
        if name == 'usr/lib/modules' or name.startswith('usr/lib/modules/') or name == 'etc/nvme-modules':
            del members[name]
    replacements = {
        'init': (stat.S_IFREG | 0o755, (KIT / 'init').read_bytes()),
        'etc/nvme-root.conf': (stat.S_IFREG | 0o644, config.encode()),
        'modules.tar.gz': (stat.S_IFREG | 0o644, (work / 'modules.tar.gz').read_bytes()),
        'mesa.tar.gz': (stat.S_IFREG | 0o644, (work / 'mesa.tar.gz').read_bytes()),
    }
    for source, target in [('runtime.sh', 'aurora-runtime.sh'), ('with-mesa', 'aurora-with-mesa'),
                           ('collect.sh', 'aurora-collect.sh'), ('aurora-test.service', 'aurora-test.service')]:
        replacements[target] = (stat.S_IFREG | 0o755, (KIT / source).read_bytes())
    members.update(replacements)
    # Place parent directories/symlinks before their children.
    entries = [(n, *members[n]) for n in sorted(members, key=lambda n: (n.count('/'), n))]
    raw = nvme.newc(nvme.archive_with_parents(entries, {}))
    output = work / 'kit'
    output.mkdir(exist_ok=True)
    (output / 'initramfs.img').write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    shutil.copyfile(work / 'Image', output / 'vmlinuz')
    shutil.copyfile(work / 'kernel.config', output / 'kernel.config')
    shutil.copyfile(work / 'boot.bin', output / 'boot.bin')
    shutil.copyfile(work / 'loader-receipt.json', output / 'loader-receipt.json')
    shutil.copyfile(work / 'builder-packages.txt', output / 'builder-packages.txt')
    shutil.copyfile(KIT / 'profile.json', output / 'profile.json')
    shutil.copyfile(KIT / 'collect.sh', output / 'collect.sh')
    shutil.copyfile(KIT / 'BOOT.md', output / 'BOOT.md')
    with tarfile.open(work / 'modules.tar.gz') as archive:
        names = archive.getnames()
        required = [f'lib/modules/{release}/modules.dep', f'lib/modules/{release}/modules.alias',
                    f'lib/modules/{release}/kernel/drivers/gpu/drm/asahi/asahi.ko',
                    f'lib/modules/{release}/kernel/drivers/nvme/host/nvme-apple.ko']
        if not all(name in names for name in required):
            raise ValueError('Missing matching module payload')
        if any('tas2764' in name or 'tas2770' in name or 'macaudio' in name for name in names):
            raise ValueError('Speaker driver found in test payload')
    decoded = nvme.initramfs_members((output / 'initramfs.img').read_bytes())
    for name, value in replacements.items():
        if decoded.get(name) != value:
            raise ValueError('Initramfs readback differs: ' + name)
    sources = {str(p.relative_to(PROJECT)): digest(p) for p in sorted(KIT.iterdir()) if p.is_file()}
    manifest = {'schema': 1, 'test': 'AURT002', 'kernel_release': release, 'profile': profile,
                'base_initramfs_sha256': digest(base_initramfs), 'source_files': sources,
                'native_boot_tested': False, 'speakers_enabled': False,
                'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                          for p in sorted(output.iterdir()) if p.is_file() and p.name != 'manifest.json'}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(output)
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=PROJECT / 'out/aurora-test')
    p.add_argument('--base-initramfs', type=Path, required=True)
    args = p.parse_args()
    package(args.work.resolve(), args.base_initramfs.resolve())
