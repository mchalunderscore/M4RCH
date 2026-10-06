#!/usr/bin/env python3
"""Switch the identified SD GRUB configuration back to the normal entry."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Expected a regular file: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(root, kit, info):
    receipt = json.loads((kit / 'build.json').read_text())
    card = json.loads((kit / 'card.json').read_text())
    if info.get('MountPoint') != str(root) or info.get('VolumeUUID') != card['macos_volume_uuid']:
        raise ValueError('Mounted SD identity differs from the trial receipt')
    for name, key in (('vmlinuz-linux-m4rch', 'normal_kernel_sha256'),
                      ('initramfs-linux-m4rch.img', 'initramfs_sha256')):
        if digest(root / name) != receipt[key]:
            raise ValueError('Normal boot artifacts changed; inspect instead of switching blindly')
    cfg = root / 'grub/grub.cfg'
    if (root / 'grub').is_symlink() or kit.is_symlink():
        raise ValueError('Unexpected symlink in the boot layout')
    expected = {}
    for name in ('grub-normal.cfg', 'grub-trial.cfg'):
        if digest(kit / name) != receipt[name + '_sha256']:
            raise ValueError('Saved GRUB configuration failed verification')
        expected[name] = (kit / name).read_bytes()
    if digest(cfg) not in {receipt[n + '_sha256'] for n in expected}:
        raise ValueError('GRUB changed since staging; edit its default manually after inspection')
    tmp = cfg.with_name('grub.cfg.normal-new')
    with tmp.open('xb') as stream:
        stream.write(expected['grub-normal.cfg'])
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, cfg)
    if cfg.read_bytes() != expected['grub-normal.cfg']:
        raise ValueError('Readback mismatch')


def main():
    if sys.platform != 'darwin' or os.geteuid() != 0:
        raise ValueError('Run with sudo from macOS after mounting the SD ESP')
    kit = Path(__file__).resolve().parent
    root = kit.parent
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', str(root)]))
    select(root, kit, info)
    subprocess.run(['/bin/sync'], check=True)
    print('GRUB now selects m4rch-normal. Kernels and enrollment unchanged.')


if __name__ == '__main__':
    main()
