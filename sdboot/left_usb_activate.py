#!/usr/bin/env python3
"""Activate or roll back the staged both-left USB trial after package installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Not a regular file: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace(source, target):
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.left-usb-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('activate','rollback'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Run with sudo in native Linux')
    kit = Path(__file__).resolve().parent
    subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=kit,check=True)
    receipt = json.loads((kit/'deployment.json').read_text())
    mount = json.loads(subprocess.check_output(['findmnt','-J','--mountpoint','/boot','-o','TARGET,FSTYPE,UUID']))['filesystems']
    if len(mount)!=1 or mount[0]['fstype']!='vfat' or mount[0]['uuid'].upper()!=receipt['boot_fat_uuid'].upper():
        raise ValueError('The expected SD ESP is not mounted at /boot')
    target=Path('/boot/dtbs/board.dtbo')
    current=digest(target)
    before=receipt['capacity_overlay_sha256'];after=receipt['left_overlay_sha256']
    if current not in (before,after):
        raise ValueError('Unexpected overlay; preserve it and investigate before replacing')
    if args.action=='activate':
        if digest(Path('/boot/vmlinuz-linux-m4rch'))!=receipt['kernel_sha256']:
            raise ValueError('Install the matching update kit first; the staged SD kernel differs')
        provenance=json.loads(Path('/usr/share/doc/linux-m4rch/build-provenance.json').read_text())
        if provenance['kernel_release']!=receipt['kernel_release'] or provenance['modules_sha256']!=receipt['modules_sha256']:
            raise ValueError('Matching kernel/module package provenance is absent')
        release=receipt['kernel_release']
        if not (Path('/usr/lib/modules')/release/'modules.dep').is_file():
            raise ValueError('The matching module tree is absent')
        source=kit/'board-left-usb.dtbo'; expected=after
    else:
        source=kit/'board-capacity.dtbo';expected=before
    if digest(source)!=expected:
        raise ValueError('Staged overlay checksum mismatch')
    replace(source,target)
    if digest(target)!=expected:
        raise ValueError('Overlay readback failed')
    os.sync()
    print(f'{args.action}: SD overlay verified. Reboot Linux normally; no Recovery enrollment.')


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        raise SystemExit(f'm4rch: {exc}')
