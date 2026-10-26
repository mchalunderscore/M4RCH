#!/usr/bin/env python3
"""Stage AUBS001; only its paired Recovery script enrolls the first stage."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / 'out/aurora-bootstrap'
sys.path[:0] = [str(PROJECT / 'sdboot'), str(PROJECT / 'lib')]
import card
from card_disk import DiskUtil
import enrollment
import internal_boot

ESP_UUID = '5FDB35C6-3A66-416D-8358-6555FD99FCC5'
SYSTEM_UUID = 'AE094BB5-7339-4064-B333-9A2FA99108ED'
VGID = '05F89AF0-EFD8-44CB-ABEB-D805D7B34F63'
STORE_UUID = '3C5845F5-DAF6-489B-A2E0-54748B1E20CF'
NATIVE_BOOT = '81f7618228a446cceac84742bc25ff908b649fdf6575cfa95b1323e81d2a93e3'
GRUB = '805c2cb08859e12c9ea94b3705c90aa762b287d77496490416bf122c607d6f0d'
GPU = '07ce071cfbae89e058455885c2b27a4697915c49920a56aeeb98becc4c37949a'
BACKUP = 'aurora-bootstrap-AUBS001-backup'


def sha(path):
    return enrollment._info(path)['sha256']


def write(path, data, mode=0o644):
    enrollment._atomic(path, data, mode)


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def inputs():
    manifest = json.loads((OUTPUT / 'manifest.json').read_text())
    if manifest['test'] != 'AUBS001':
        raise ValueError('Unexpected test identity')
    for name, expected in manifest['files'].items():
        if Path(name).name != name or enrollment._info(OUTPUT / name) != expected:
            raise ValueError('Build artifact differs: ' + name)
    profile = json.loads((OUTPUT / 'profile.json').read_text())
    if profile['wallace_source_inputs'] or profile['speakers_enabled']:
        raise ValueError('Unexpected build policy')
    return manifest


def stub(dutil):
    info = dutil.info(SYSTEM_UUID)
    if not info['Internal'] or info['APFSVolumeGroupID'] != VGID or info['VolumeUUID'] != SYSTEM_UUID:
        raise ValueError('Not the existing Arch stub')
    mount = Path(info['MountPoint'])
    resources = card.checked_path(mount, 'Finish Installation.app/Contents/Resources')
    saved = json.loads(card.checked_path(resources, 'card.json').read_text())
    identity = enrollment._identity(saved)
    if (identity['vgid'] != VGID or identity['store_uuid'] != STORE_UUID
            or identity['platform_uuid'] != card.platform_uuid()):
        raise ValueError('Existing stub metadata/platform differs')
    main = dutil.info('/')
    main_store = dutil.info(main['APFSPhysicalStores'][0]['APFSPhysicalStore'])
    if (main['APFSVolumeGroupID'] != identity['source_macos_vgid']
            or main_store['DiskUUID'] != identity['source_macos_store_uuid']):
        raise ValueError('Original macOS identity differs')
    containers = [c for c in dutil.apfs()['Containers'] if c['ContainerReference'] == info['APFSContainerReference']]
    if len(containers) != 1 or containers[0]['PhysicalStores'] != [{
            'DeviceIdentifier': info['APFSPhysicalStores'][0]['APFSPhysicalStore'],
            'DiskUUID': STORE_UUID, 'Size': 4294967296}]:
        raise ValueError('Unexpected stub physical store')
    unused = dict.fromkeys(('device', 'root_device', *internal_boot.SD_KEYS), '')
    live = internal_boot.read_roles(dutil, containers[0], STORE_UUID, unused)
    if live['vgid'] != identity['vgid'] or any(live['roles'][r]['uuid'] != e['uuid'] for r, e in identity['roles'].items()):
        raise ValueError('Live APFS roles differ')
    return info, mount, resources, identity


def recovery_script(identity, boot, previous):
    rendered = enrollment.render(PROJECT, {**identity, 'previous_boot_sha256': previous}, boot)
    rendered = rendered.replace('The loader reads the SD card at boot. Later SD payload updates do not need enrollment.',
                                'The loader reads boot.bin on the internal Arch ESP. Later second-stage updates do not need enrollment.')
    return rendered


def rollback_script(identity, old_boot, new_sha, base_sha, old_script_sha):
    script = recovery_script(identity, old_boot, new_sha)
    script = script.replace('bundle="$resources/boot.bin"', f'bundle="$resources/{BACKUP}/boot.bin"')
    # Keep all existing paired-Recovery, owner, APFS, receipt and image checks.
    # Validate both boot stages before re-enrolling the preserved first stage.
    validation = f'''
diskutil mount '{ESP_UUID}' || die 'Cannot mount the existing Arch ESP.'
info '{ESP_UUID}' RollbackESP
same "$(plist "$work/RollbackESP.plist" DiskUUID)" '{ESP_UUID}' 'Arch ESP UUID'
rollback_esp=$(plist "$work/RollbackESP.plist" MountPoint) || die 'Arch ESP is unmounted.'
case $rollback_esp in /Volumes/*) ;; *) die 'Invalid ESP mount point.' ;; esac
[ ! -L "$rollback_esp" ] || die 'ESP mount is a link.'
same "$(shasum -a 256 "$resources/{BACKUP}/enroll.sh" | awk '{{print $1}}')" '{old_script_sha}' 'Previous enrollment script'
rollback_boot="$rollback_esp/AUBS001/boot.previous.bin"
[ -f "$rollback_boot" ] && [ ! -L "$rollback_boot" ] || die 'Missing previous second stage.'
same "$(shasum -a 256 "$rollback_boot" | awk '{{print $1}}')" '{NATIVE_BOOT}' 'Previous second stage'
same "$(shasum -a 256 "$rollback_esp/AUBS001/base.previous.json" | awk '{{print $1}}')" '{base_sha}' 'Previous selector receipt'
active_second=$(shasum -a 256 "$rollback_esp/boot.bin" | awk '{{print $1}}')
case $active_second in '{NATIVE_BOOT}'|'{sha(OUTPUT / 'boot.bin')}') ;; *) die 'Active second stage changed.' ;; esac
'''
    script = script.replace("# Apple's tools request the existing owner credentials; no passwords in argv.",
                            validation + "\n# Apple's tools request the existing owner credentials; no passwords in argv.")
    restore = f'''
mount -u -w "$system_dir" || die 'Cannot restore the stub files.'
cp "$bundle" "$resources/.AUBS001-restore.bin" || die 'Cannot restore first-stage source.'
mv "$resources/.AUBS001-restore.bin" "$resources/boot.bin" || die 'Cannot replace first-stage source.'
cp "$resources/{BACKUP}/enroll.sh" "$resources/.AUBS001-enroll.sh" || die 'Cannot restore enrollment script.'
mv "$resources/.AUBS001-enroll.sh" "$resources/enroll.sh" || die 'Cannot replace enrollment script.'
cp "$rollback_boot" "$rollback_esp/.AUBS001-restore.bin" || die 'Cannot restore second stage.'
mv "$rollback_esp/.AUBS001-restore.bin" "$rollback_esp/boot.bin" || die 'Cannot replace second stage.'
cp "$rollback_esp/AUBS001/base.previous.json" "$rollback_esp/AURD001/.AUBS001-restore.json" || die 'Cannot restore selector receipt.'
mv "$rollback_esp/AURD001/.AUBS001-restore.json" "$rollback_esp/AURD001/staging-receipt.json" || die 'Cannot replace selector receipt.'
sync
'''
    if script.count('\nfinish_metadata\n') != 1:
        raise ValueError('Recovery restoration anchor changed')
    return script.replace('\nfinish_metadata\n', restore + '\nfinish_metadata\n')


def stage():
    manifest = inputs()
    if sys.platform != 'darwin' or os.geteuid() != 0:
        raise ValueError('Staging requires macOS administrator authentication: run this script with sudo in Terminal')
    dutil = DiskUtil()
    info, system, resources, identity = stub(dutil)
    old_sha = sha(resources / 'boot.bin')
    if enrollment._receipt(resources, identity) != old_sha:
        raise ValueError('Existing first-stage source and enrolled receipt disagree; inspect before replacement')
    if card.checked_path(resources, BACKUP).exists() or (OUTPUT / 'staging-receipt.json').exists():
        raise ValueError('AUBS001 is already staged or has backups; preserve and inspect them')
    esp_info = dutil.info(ESP_UUID)
    if not esp_info.get('Mounted'):
        dutil.run('mount', ESP_UUID)
    esp = Path(dutil.info(ESP_UUID)['MountPoint'])
    spec = importlib.util.spec_from_file_location('direct_stage', PROJECT / 'experiments/aurora-direct/stage.py')
    direct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    if (sha(esp / 'boot.bin') != NATIVE_BOOT or sha(esp / 'grub/grub.cfg') != GRUB
            or sha(esp / 'AURG016/manifest.json') != GPU):
        raise ValueError('Native-working AURL001 loader / AURG016 default differs')
    archive = card.checked_path(esp, 'AUBS001')
    if archive.exists() or shutil.disk_usage(esp).free < 3 * (OUTPUT / 'boot.bin').stat().st_size + 1024 * 1024:
        raise ValueError('AUBS001 archive exists or ESP needs more free space')
    base = esp / 'AURD001/staging-receipt.json'
    old_base = base.read_bytes()
    candidate = recovery_script(identity, OUTPUT / 'stage1.bin', old_sha)
    backup = resources / BACKUP
    # Validate generated shell before the first write to either boot volume.
    host_candidate = OUTPUT / 'enroll.sh'
    write(host_candidate, candidate.encode(), 0o755)
    subprocess.run(['/bin/sh', '-n', str(host_candidate)], check=True)
    writable = card.mounted_writable(dutil, info['DeviceIdentifier'], SYSTEM_UUID)
    if writable != system or stub(dutil)[3] != identity or sha(resources / 'boot.bin') != old_sha:
        raise ValueError('Stub changed before staging')
    backup.mkdir(mode=0o700)
    for name in ['boot.bin', 'enroll.sh', 'enrolled.txt', 'card.json', 'stub-enrolled.txt']:
        original = card.checked_path(resources, name)
        if original.exists():
            write(backup / name, original.read_bytes(), 0o600)
            if sha(backup / name) != sha(original):
                raise ValueError('Stub backup differs: ' + name)
    rollback = rollback_script(identity, backup / 'boot.bin', sha(OUTPUT / 'stage1.bin'),
                               hashlib.sha256(old_base).hexdigest(), sha(backup / 'enroll.sh'))
    write(OUTPUT / 'rollback.sh', rollback.encode(), 0o755)
    subprocess.run(['/bin/sh', '-n', str(OUTPUT / 'rollback.sh')], check=True)
    write(resources / 'aurora-bootstrap-rollback.sh', rollback.encode(), 0o700)
    archive.mkdir()
    write(archive / 'boot.previous.bin', (esp / 'boot.bin').read_bytes())
    write(archive / 'base.previous.json', old_base)
    for name in ['boot.bin', 'manifest.json', 'profile.json']:
        write(archive / name, (OUTPUT / name).read_bytes())
    try:
        updated = json.loads(old_base)
        updated['loaders']['aurora_bootstrap'] = sha(OUTPUT / 'boot.bin')
        write(base, json_bytes(updated))
        write(esp / 'boot.bin', (OUTPUT / 'boot.bin').read_bytes())
        write(resources / 'boot.bin', (OUTPUT / 'stage1.bin').read_bytes(), 0o600)
        write(resources / 'enroll.sh', candidate.encode(), 0o700)
        if (sha(resources / 'boot.bin') != sha(OUTPUT / 'stage1.bin')
                or sha(esp / 'boot.bin') != sha(OUTPUT / 'boot.bin')
                or sha(esp / 'grub/grub.cfg') != GRUB or sha(esp / 'AURG016/manifest.json') != GPU
                or enrollment._receipt(resources, identity) != old_sha):
            raise ValueError('Staged pair readback differs')
    except BaseException:
        write(esp / 'boot.bin', (archive / 'boot.previous.bin').read_bytes())
        write(base, old_base)
        for name in ['boot.bin', 'enroll.sh']:
            write(resources / name, (backup / name).read_bytes(), 0o600)
        raise
    receipt = {'test': 'AUBS001', 'phase': 'staged-awaiting-paired-recovery',
               'esp': str(esp), 'stub': str(system), 'identity': identity,
               'previous_stage1_sha256': old_sha, 'stage1_sha256': sha(OUTPUT / 'stage1.bin'),
               'previous_stage2_sha256': NATIVE_BOOT, 'stage2_sha256': sha(OUTPUT / 'boot.bin'),
               'grub_sha256': GRUB, 'gpu_manifest_sha256': GPU,
               'enrolled_stage1_changed': False, 'native_boot_tested': False,
               'backup': str(backup), 'rollback': str(resources / 'aurora-bootstrap-rollback.sh')}
    write(OUTPUT / 'staging-receipt.json', json_bytes(receipt))
    write(archive / 'staging-receipt.json', json_bytes(receipt))
    subprocess.run(['/bin/sync'], check=True)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify host build artifacts without mounting or staging')
    args = parser.parse_args()
    if args.check:
        inputs()
        print('AUBS001 build artifacts verified; no volumes changed')
    else:
        stage()
