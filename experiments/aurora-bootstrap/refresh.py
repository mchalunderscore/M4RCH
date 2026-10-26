#!/usr/bin/env python3
"""Install revision 2's CPU-placeholder correction without first-stage changes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

from stage import OUTPUT, PROJECT, GRUB, GPU, NATIVE_BOOT, ESP_UUID, inputs, sha, write, json_bytes, stub, card, enrollment, DiskUtil
from repair_control import R1_BOOT, R2_BOOT


def main():
    manifest = inputs()
    revision = manifest.get('revision')
    if revision not in (2, 3):
        raise ValueError('Expected AUBS001 revision 2 or 3')
    receipt = json.loads((OUTPUT / 'revisions/r1/staging-receipt.json').read_text())
    if receipt['stage2_sha256'] != R1_BOOT or sha(OUTPUT / 'stage1.bin') != receipt['stage1_sha256']:
        raise ValueError('Initial staging receipt or unchanged first stage differs')
    if os.geteuid() != 0:
        raise ValueError('macOS authentication is needed: run this refresh script with sudo in Terminal')
    dutil = DiskUtil()
    info, system, resources, identity = stub(dutil)
    if sha(resources / 'boot.bin') != receipt['stage1_sha256']:
        raise ValueError('Staged first-stage source changed')
    enrolled = enrollment._receipt(resources, identity)
    if enrolled not in (receipt['stage1_sha256'], receipt['previous_stage1_sha256']):
        raise ValueError('Unexpected first-stage enrollment receipt')
    rollback_path = resources / 'aurora-bootstrap-rollback.sh'
    original_rollback = (OUTPUT / 'revisions/r1/rollback.sh').read_text()
    current_rollback = rollback_path.read_text()
    anchor = "case $active_second in '" + NATIVE_BOOT + "'|'" + R1_BOOT + "')"
    if original_rollback.count(anchor) != 1:
        raise ValueError('Rollback selector anchor differs')
    candidate = sha(OUTPUT / 'boot.bin')
    previous_rollback = original_rollback.replace(anchor, anchor[:-1] + "|'" + R2_BOOT + "')")
    accepted = [R2_BOOT] + ([candidate] if candidate != R2_BOOT else [])
    updated_rollback = original_rollback.replace(anchor, anchor[:-1] + ''.join("|'" + value + "'" for value in accepted) + ')')
    if current_rollback not in (original_rollback, previous_rollback, updated_rollback):
        raise ValueError('Installed rollback script changed')
    host_rollback = OUTPUT / ('rollback-revision' + str(revision) + '.sh')
    write(host_rollback, updated_rollback.encode(), 0o755)
    subprocess.run(['/bin/sh', '-n', str(host_rollback)], check=True)
    esp = Path(receipt['esp'])
    esp_info = dutil.info(ESP_UUID)
    if not esp_info.get('Mounted'):
        dutil.run('mount', ESP_UUID)
    if Path(dutil.info(ESP_UUID)['MountPoint']) != esp:
        raise ValueError('ESP mount point differs from its staging receipt')
    spec = importlib.util.spec_from_file_location('direct_stage', PROJECT / 'experiments/aurora-direct/stage.py')
    direct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    from cleanup_esp import expected_grub
    grub_expected = expected_grub(esp)
    target, archive = esp / 'boot.bin', esp / 'AUBS001'
    if sha(target) not in (R1_BOOT, R2_BOOT, candidate):
        raise ValueError('Unexpected active loader')
    for path, expected in [(esp / 'grub/grub.cfg', grub_expected), (esp / 'AURG016/manifest.json', GPU),
                           (archive / 'boot.previous.bin', NATIVE_BOOT)]:
        if sha(path) != expected:
            raise ValueError('Working configuration or rollback differs: ' + str(path))
    if shutil.disk_usage(esp).free < (OUTPUT / 'boot.bin').stat().st_size + 512 * 1024:
        raise ValueError('Insufficient ESP space for atomic replacement')
    base = esp / 'AURD001/staging-receipt.json'
    selectors = json.loads(base.read_text())
    if selectors['loaders'].get('aurora_bootstrap') not in (R1_BOOT, R2_BOOT, candidate):
        raise ValueError('Unexpected bootstrap selector receipt')
    selectors['loaders']['aurora_bootstrap'] = candidate
    card.mounted_writable(dutil, info['DeviceIdentifier'], identity['roles']['System']['uuid'])
    write(rollback_path, updated_rollback.encode(), 0o700)
    write(archive / 'staging-receipt.r1.json', (OUTPUT / 'revisions/r1/staging-receipt.json').read_bytes())
    # Both versions use the same first stage, handoff validation and U-Boot.
    # Atomic replacement leaves a valid complete image at every point.
    write(target, (OUTPUT / 'boot.bin').read_bytes())
    for name in ['boot.bin', 'manifest.json', 'profile.json']:
        write(archive / name, (OUTPUT / name).read_bytes())
    write(base, json_bytes(selectors))
    if sha(target) != candidate or sha(archive / 'boot.bin') != candidate or sha(esp / 'grub/grub.cfg') != grub_expected:
        raise ValueError('ESP readback differs')
    updated = {**receipt, 'revision': revision, 'stage2_sha256': candidate,
               'phase': 'revision' + str(revision) + '-staged-awaiting-native-boot', 'first_stage_reenrollment_required': False,
               'enrolled_stage1_sha256': enrolled,
               'aurora_first_stage_enrollment_confirmed': enrolled == receipt['stage1_sha256'],
               'revision1_native_result': 'U-Boot adopted live ANS; Linux handoff rejected missing boot-CPU fields',
               'changed': ('Only control-DT cpu@10100 spin-table placeholders' if revision == 2 else
                           'Only control-DT Wi-Fi/Bluetooth board identity: hostomel -> mriya') + '; first-stage and U-Boot bytes unchanged'}
    if revision == 3:
        updated['revision2_native_result'] = 'Owner confirmed boot worked; Wi-Fi unavailable'
    updated.pop('enrolled_stage1_changed', None)
    updated['grub_sha256'] = grub_expected
    write(archive / 'staging-receipt.json', json_bytes(updated))
    write(OUTPUT / 'staging-receipt.json', json_bytes(updated))
    subprocess.run(['/bin/sync'], check=True)
    print(json.dumps(updated, indent=2))


if __name__ == '__main__':
    main()
