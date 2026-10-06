#!/usr/bin/env python3
"""Restore the captured accepted ESP files; no partition or boot-policy changes."""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess


def main():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo')
    kit = Path(__file__).resolve().parent
    boot = kit.parent
    receipt = json.loads((kit/'build.json').read_text())
    # The kit lives directly on the ESP. On FAT there are no Unix symlinks;
    # still reject unexpected path types before writing any boot file.
    if platform.system() == 'Darwin':
        info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist',str(boot)]))
        if info.get('MountPoint') != str(boot) or info.get('VolumeUUID','').upper() != receipt['boot_volume_uuid_macos']:
            raise ValueError('Not the enrolled test SD ESP')
    elif platform.system() == 'Linux':
        if subprocess.check_output(['findmnt','-n','-o','FSTYPE','--target',str(boot)],text=True).strip() != 'vfat':
            raise ValueError('Not a mounted FAT ESP')
        device = subprocess.check_output(['findmnt','-n','-o','SOURCE','--target',str(boot)],text=True).strip()
        if subprocess.check_output(['blkid','-s','UUID','-o','value',device],text=True).strip().upper() != receipt['boot_uuid_linux']:
            raise ValueError('Different FAT UUID')
    else:
        raise ValueError('Run from macOS or native Linux')
    current = boot/'vmlinuz-linux-m4rch'
    allowed = {receipt['kernel_image_sha256'],receipt['accepted_kernel_image_sha256']}
    if current.is_symlink() or hashlib.sha256(current.read_bytes()).hexdigest() not in allowed:
        raise ValueError('Current boot kernel is neither the diagnostic nor its accepted rollback')
    records = json.loads((kit/'rollback-boot.json').read_text())
    for name,digest in records.items():
        if name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe rollback path')
        source,target = kit/'rollback-boot'/name,boot/name
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('Rollback checksum mismatch')
        if any(p.is_symlink() for p in [target,*target.parents]):
            raise ValueError('Symlink in boot destination')
        if not target.is_file():
            raise ValueError('Missing regular boot destination')
    # Restore initrd/overlay/config first; publish the accepted kernel last.
    names = [n for n in records if n != 'vmlinuz-linux-m4rch']+['vmlinuz-linux-m4rch']
    for name in names:
        target = boot/name
        data = (kit/'rollback-boot'/name).read_bytes()
        temporary = target.with_name(target.name+'.m4rch-restore-tmp')
        if temporary.exists() or temporary.is_symlink():
            raise ValueError('Stale temporary rollback file; investigate first')
        with temporary.open('xb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temporary,target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != records[name]:
            raise ValueError('Restored boot file checksum mismatch')
    subprocess.run(['sync'],check=True)
    print('Accepted ESP files restored. No enrollment change. Linux package rollback is separate.')


if __name__ == '__main__':
    try:
        main()
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
