#!/usr/bin/env python3
"""Preserve the installed candidate and stage its checked replacement from stable."""
import argparse
import datetime
import json
from pathlib import Path
from select_boot import select
from stage import PROJECT, atomic_write, sha, stage, validate_esp


def check_payload(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, item in manifest['files'].items():
        if Path(name).name != name or sha(directory / name) != item['sha256']:
            raise ValueError('Payload differs: ' + str(directory / name))
    return manifest


def restage(kit, esp):
    validate_esp(esp)
    new = check_payload(kit)
    destination = esp / 'AURD001'
    old = check_payload(destination)
    old_revision = old['profile'].get('revision', 1)
    new_revision = new['profile'].get('revision', 1)
    if old_revision < 1 or new_revision != old_revision + 1:
        raise ValueError('Expected an installed revision and its immediate replacement')
    if new['profile']['loader']['previous_boot_sha256'] != '4de31bba9eb209aada9b3ce40f5d7af1303ea79022d4edead2c909aeea7a71a2':
        raise ValueError('Replacement must be staged from the original stable pair')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archived = esp / (f'AURD001.saved-r{old_revision}-' + stamp)
    if archived.exists():
        raise ValueError('Archive already exists')
    # The stable pair boots AURA001, independently of the directory we move.
    # select verifies both current and stored loader/config hashes first.
    select('stable', esp)
    stable_loader = (esp / 'boot.bin').read_bytes()
    stable_config = (esp / 'grub/grub.cfg').read_bytes()
    destination.rename(archived)
    try:
        stage(kit, esp)
    except BaseException:
        atomic_write(esp / 'boot.bin', stable_loader)
        atomic_write(esp / 'grub/grub.cfg', stable_config)
        if destination.exists():
            destination.rename(esp / ('AURD001.incomplete-' + stamp))
        archived.rename(destination)
        raise
    print('Previous native candidate preserved:', archived)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, default=PROJECT / 'out/aurora-direct/kit')
    parser.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    args = parser.parse_args()
    restage(args.kit.resolve(), args.esp)
