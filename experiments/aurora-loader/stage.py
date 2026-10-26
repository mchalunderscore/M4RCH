#!/usr/bin/env python3
"""Install or restore the Aurora loader while preserving the working GPU kit."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / 'out/aurora-loader'
spec = importlib.util.spec_from_file_location('aurora_direct_stage', PROJECT / 'experiments/aurora-direct/stage.py')
direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(direct)
atomic_write, validate_esp = direct.atomic_write, direct.validate_esp


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def check_manifest(directory, name='manifest.json'):
    manifest = json.loads((directory / name).read_text())
    for relative, info in manifest['files'].items():
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Invalid manifest path')
        path = directory / relative
        if path.is_symlink() or path.stat().st_size != info['bytes'] or sha(path) != info['sha256']:
            raise ValueError('Payload differs: ' + str(path))
    return manifest


def verify(esp):
    validate_esp(esp)
    directory = esp / 'AURL001'
    receipt = json.loads((directory / 'staging-receipt.json').read_text())
    for name, expected in receipt['payloads'].items():
        if sha(directory / name) != expected:
            raise ValueError('Loader archive differs: ' + name)
    current = sha(esp / 'boot.bin')
    if current not in [receipt['candidate_sha256'], receipt['previous_sha256']]:
        raise ValueError('Unknown active loader')
    if sha(esp / 'grub/grub.cfg') != receipt['grub_sha256']:
        raise ValueError('GRUB changed after this loader was staged')
    if sha(esp / 'AURG016/manifest.json') != receipt['gpu_manifest_sha256']:
        raise ValueError('GPU kit changed after this loader was staged')
    check_manifest(esp / 'AURG016')
    base = json.loads((esp / 'AURD001/staging-receipt.json').read_text())
    if current not in base['loaders'].values():
        raise ValueError('Boot selector no longer recognizes the active loader')
    return {'test': 'AURL001', 'active': 'aurora' if current == receipt['candidate_sha256'] else 'previous',
            'boot_sha256': current, 'grub_sha256': receipt['grub_sha256'],
            'gpu_kit_unchanged': True, 'native_boot_tested': False}


def install(esp):
    validate_esp(esp)
    check_manifest(OUTPUT)
    profile = json.loads((OUTPUT / 'profile.json').read_text())
    if profile['test'] != 'AURL001' or profile['revision'] != 1 or profile['speakers_enabled']:
        raise ValueError('Wrong loader profile')
    directory = esp / 'AURL001'
    if directory.exists():
        raise ValueError('AURL001 is already present; verify or restore it before replacing')
    gpu = check_manifest(esp / 'AURG016')
    if gpu['profile']['revision'] != 4 or gpu['profile']['speakers_enabled']:
        raise ValueError('Expected the unchanged GPU revision 4')
    gpu_receipt = json.loads((esp / 'AURG016/staging-receipt.json').read_text())
    boot, grub = esp / 'boot.bin', esp / 'grub/grub.cfg'
    if (sha(boot) != gpu_receipt['boot_sha256'] or sha(grub) != gpu_receipt['grub_sha256']
            or sha(esp / 'AURG016/manifest.json') != gpu_receipt['manifest_sha256']
            or "set default='m4rch-aurora-gpu16'" not in grub.read_text()
            or (esp / 'AURD001/mode').read_text() != 'test\n'):
        raise ValueError('The working boot configuration differs')
    base_path = esp / 'AURD001/staging-receipt.json'
    base_original = base_path.read_bytes()
    base = json.loads(base_original)
    if sha(boot) not in base['loaders'].values() or sha(grub) not in base['configurations'].values():
        raise ValueError('Unrecognized loader/configuration pair')
    required = 2 * (OUTPUT / 'boot.bin').stat().st_size + boot.stat().st_size + 4 * 1024**2
    if shutil.disk_usage(esp).free < required:
        raise ValueError('Insufficient ESP space for candidate, rollback and atomic replacement')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = OUTPUT / 'backups' / stamp
    backup.mkdir(parents=True)
    for source, name in [(boot, 'boot.previous.bin'), (grub, 'grub.previous.cfg'),
                         (base_path, 'base-staging-receipt.json'),
                         (esp / 'AURG016/staging-receipt.json', 'gpu-staging-receipt.json')]:
        shutil.copyfile(source, backup / name)
        if sha(source) != sha(backup / name):
            raise ValueError('Backup readback differs: ' + name)
    directory.mkdir()
    for source, name in [(OUTPUT / 'boot.bin', 'boot.bin'), (OUTPUT / 'profile.json', 'profile.json'),
                         (OUTPUT / 'manifest.json', 'build-manifest.json'),
                         (backup / 'boot.previous.bin', 'boot.previous.bin'),
                         (backup / 'grub.previous.cfg', 'grub.previous.cfg')]:
        atomic_write(directory / name, source.read_bytes())
        if sha(source) != sha(directory / name):
            raise ValueError('ESP archive readback differs: ' + name)
    previous, candidate = sha(boot), sha(directory / 'boot.bin')
    receipt = {'test': 'AURL001', 'revision': 1, 'backup': str(backup),
               'candidate_sha256': candidate, 'previous_sha256': previous,
               'grub_sha256': sha(grub), 'gpu_manifest_sha256': sha(esp / 'AURG016/manifest.json'),
               'payloads': {p.name: sha(p) for p in directory.iterdir()},
               'native_boot_tested': False, 'speakers_enabled': False,
               'stage1_changed': False, 'kernel_or_initramfs_changed': False}
    # Existing selectors can recognize this new loader and restore their exact
    # previous loader/configuration pair. Their stored payloads stay untouched.
    base['loaders']['aurora_loader'] = candidate
    try:
        atomic_write(directory / 'staging-receipt.json', json_bytes(receipt))
        atomic_write(base_path, json_bytes(base))
        atomic_write(boot, (directory / 'boot.bin').read_bytes())
        result = verify(esp)
    except BaseException:
        atomic_write(boot, (backup / 'boot.previous.bin').read_bytes())
        atomic_write(base_path, base_original)
        raise
    subprocess.run(['sync'], check=True)
    (OUTPUT / 'staging-receipt.json').write_bytes(json_bytes(receipt))
    (OUTPUT / 'final-verification.json').write_bytes(json_bytes(result))
    print(json.dumps(result))


def restore(esp):
    validate_esp(esp)
    directory = esp / 'AURL001'
    receipt = json.loads((directory / 'staging-receipt.json').read_text())
    previous = directory / 'boot.previous.bin'
    if sha(previous) != receipt['previous_sha256']:
        raise ValueError('Previous loader backup differs')
    boot = esp / 'boot.bin'
    if sha(boot) not in [receipt['candidate_sha256'], receipt['previous_sha256']]:
        raise ValueError('Active loader changed; inspect before restoring')
    base_path = esp / 'AURD001/staging-receipt.json'
    base = json.loads(base_path.read_text())
    if base['loaders'].get('aurora_loader') not in [None, receipt['candidate_sha256']]:
        raise ValueError('Another loader replaced the receipt entry')
    atomic_write(boot, previous.read_bytes())
    base['loaders'].pop('aurora_loader', None)
    atomic_write(base_path, json_bytes(base))
    subprocess.run(['sync'], check=True)
    print('Restored the previous native-working Gravity-based loader; GRUB and GPU kit retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'restore', 'verify'])
    parser.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    args = parser.parse_args()
    if args.action == 'verify':
        print(json.dumps(verify(args.esp)))
    elif args.action == 'restore':
        restore(args.esp)
    else:
        install(args.esp)
