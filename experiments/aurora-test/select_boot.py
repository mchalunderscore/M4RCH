#!/usr/bin/env python3
"""Select the prepared test, GPU-off fallback, or exact previous GRUB config."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from stage import PROJECT, atomic_write, sha, validate_esp


def select(choice, esp):
    validate_esp(esp)
    receipt = json.loads((esp / 'AURT002/staging-receipt.json').read_text())
    grub = esp / 'grub/grub.cfg'
    if sha(grub) not in receipt['configurations'].values():
        raise ValueError('GRUB was edited since staging; preserve/reconcile those edits first')
    if sha(esp / 'boot.bin') not in receipt['loaders'].values():
        raise ValueError('boot.bin changed since staging; preserve/reconcile it first')
    data = (esp / f'AURT002/grub.{choice}.cfg').read_bytes()
    if hashlib.sha256(data).hexdigest() != receipt['configurations'][choice]:
        raise ValueError('Saved configuration checksum differs')
    backup = PROJECT / 'out/aurora-test/backups'
    backup.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (backup / f'grub-before-{choice}-{stamp}.cfg').write_bytes(grub.read_bytes())
    loader = esp / 'AURT002' / ('boot.previous.bin' if choice == 'previous' else 'boot.bin')
    if sha(loader) != receipt['loaders'][choice]:
        raise ValueError('Saved loader checksum differs')
    old_loader, old_grub = (esp / 'boot.bin').read_bytes(), grub.read_bytes()
    try:
        if choice != 'previous':
            atomic_write(esp / 'AURT002/mode', (choice + '\n').encode())
        atomic_write(esp / 'boot.bin', loader.read_bytes())
        atomic_write(grub, data)
    except BaseException:
        atomic_write(esp / 'boot.bin', old_loader)
        atomic_write(grub, old_grub)
        raise
    subprocess.run(['sync'], check=True)
    print('Selected:', choice)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('choice', choices=['test', 'framebuffer', 'previous'])
    p.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    a = p.parse_args()
    select(a.choice, a.esp)
