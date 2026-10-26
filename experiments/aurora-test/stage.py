#!/usr/bin/env python3
"""Stage a matched AURT002 boot.bin/GRUB test with a verified prior pair."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
ESP_UUID = '5FDB35C6-3A66-416D-8358-6555FD99FCC5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_esp(esp):
    if esp.is_symlink() or not esp.is_dir():
        raise ValueError('ESP is not a real mounted directory')
    data = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(esp)]))
    expected = {'DiskUUID': ESP_UUID, 'Internal': True, 'WholeDisk': False,
                'PartitionMapPartitionOffset': 362525229056, 'Size': 1073741824,
                'FilesystemType': 'msdos', 'MountPoint': str(esp)}
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError('ESP identity differs: ' + key)
    return data


def atomic_write(path, data):
    temp = path.with_name(path.name + '.aurora-tmp')
    if temp.exists():
        raise ValueError('Inspect existing temporary file: ' + str(temp))
    try:
        with temp.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        if temp.read_bytes() != data:
            raise ValueError('Staged readback differs')
        os.replace(temp, path)
        if path.read_bytes() != data:
            raise ValueError('Installed readback differs')
    finally:
        temp.unlink(missing_ok=True)


def configurations(original, release):
    if len(re.findall(r'(?m)^set default=.*$', original)) != 1:
        raise ValueError('Expected exactly one existing default')
    if 'AURT002' in original:
        raise ValueError('AURT002 already appears in GRUB; inspect before staging')
    for expected in ['33CE-1F10', '7568fe83-378f-5b78-ab12-ccc36ff09a90']:
        if expected not in original:
            raise ValueError('Existing ESP/root identity differs')
    common = ('root=UUID=7568fe83-378f-5b78-ab12-ccc36ff09a90 rw console=tty0 '
              'rdinit=/init idle=wfi arm64.nowfxt pd_ignore_unused clk_ignore_unused '
              'modprobe.blacklist=asahi,asahi_m4,appledrm,snd_soc_tas2764,snd_soc_tas2770')
    additions = ''
    for entry, title, extra in [('m4rch-aurora-test2', 'Aurora J614s test 2 (speakers disabled)', ''),
                                 ('m4rch-aurora-test2-fb', 'Aurora J614s test 2 (GPU off fallback)', ' m4rch.aurora_gpu=off')]:
        additions += f"\nmenuentry '{title}' --id {entry} {{\n"
        additions += '    search --no-floppy --fs-uuid --set=root 33CE-1F10\n'
        additions += f'    linux /AURT002/vmlinuz {common}{extra}\n'
        additions += '    initrd /AURT002/initramfs.img\n}\n'
    result = {'previous': original.encode()}
    for name, entry in [('test', 'm4rch-aurora-test2'), ('framebuffer', 'm4rch-aurora-test2-fb')]:
        text = re.sub(r'(?m)^set default=.*$', "set default='" + entry + "'", original)
        result[name] = (text + additions).encode()
    return result


def stage(kit, esp):
    identity = validate_esp(esp)
    manifest = json.loads((kit / 'manifest.json').read_text())
    for name, item in manifest['files'].items():
        if Path(name).name != name or sha(kit / name) != item['sha256']:
            raise ValueError('Kit checksum differs: ' + name)
    destination = esp / 'AURT002'
    if destination.exists():
        raise ValueError('AURT002 already exists; preserve and inspect it first')
    grub = esp / 'grub/grub.cfg'
    original = grub.read_text()
    configs = configurations(original, manifest['kernel_release'])
    protected = {str(p.relative_to(esp)): sha(p) for p in
                 [esp / 'boot.bin', esp / 'dtbs/board.dtbo', esp / 'AURA001/vmlinuz', esp / 'AURA001/initramfs.img']}
    profile = json.loads((kit / 'profile.json').read_text())
    loader = json.loads((kit / 'loader-receipt.json').read_text())
    if protected['boot.bin'] != profile['loader']['previous_boot_sha256']:
        raise ValueError('Installed loader differs from the reviewed native baseline')
    for key, field in [('m1n1.bin', 'm1n1_sha256'), ('baseline.dtb', 'baseline_dtb_sha256')]:
        if loader[key] != profile['loader'][field]:
            raise ValueError('Test loader changed its native baseline component: ' + key)
    if loader['boot.bin'] != sha(kit / 'boot.bin'):
        raise ValueError('Loader packing receipt differs')
    needed = sum((kit / name).stat().st_size for name in manifest['files']) + 8 * 1024**2
    if shutil.disk_usage(esp).free < needed:
        raise ValueError('Not enough ESP space')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = PROJECT / 'out/aurora-test/backups' / stamp
    backup.mkdir(parents=True)
    shutil.copyfile(grub, backup / 'grub.cfg')
    # Preserve and verify the original loader before replacing the pair.
    shutil.copyfile(esp / 'boot.bin', backup / 'boot.bin')
    if sha(backup / 'boot.bin') != protected['boot.bin']:
        raise ValueError('Loader backup differs')
    destination.mkdir()
    shutil.copyfile(backup / 'boot.bin', destination / 'boot.previous.bin')
    for name in [*manifest['files'], 'manifest.json']:
        shutil.copyfile(kit / name, destination / name)
        if sha(destination / name) != sha(kit / name):
            raise ValueError('ESP readback differs: ' + name)
    for name, data in configs.items():
        atomic_write(destination / ('grub.' + name + '.cfg'), data)
    receipt = {'schema': 1, 'test': 'AURT002', 'esp_identity': identity,
               'backup': str(backup), 'protected_files': protected,
               'configurations': {name: hashlib.sha256(data).hexdigest() for name, data in configs.items()},
               'loaders': {'previous': protected['boot.bin'], 'test': sha(kit / 'boot.bin'),
                           'framebuffer': sha(kit / 'boot.bin')},
               'kernel_release': manifest['kernel_release'], 'native_boot_tested': False}
    (destination / 'staging-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    # Make the boot change only after all payloads/configurations have verified.
    for name, checksum in protected.items():
        if sha(esp / name) != checksum:
            raise ValueError('Existing payload changed during staging: ' + name)
    try:
        atomic_write(destination / 'mode', b'test\n')
        atomic_write(esp / 'boot.bin', (kit / 'boot.bin').read_bytes())
        atomic_write(grub, configs['test'])
    except BaseException:
        atomic_write(esp / 'boot.bin', (backup / 'boot.bin').read_bytes())
        atomic_write(grub, configs['previous'])
        raise
    subprocess.run(['sync'], check=True)
    (backup / 'staging-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Staged AURT002 and selected its GRUB entry. Backup:', backup)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', type=Path, default=PROJECT / 'out/aurora-test/kit')
    p.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    args = p.parse_args()
    stage(args.kit.resolve(), args.esp)
