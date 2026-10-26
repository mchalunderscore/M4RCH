#!/usr/bin/env python3
"""Install AUDP001 r10, preserving the r9 kernel and original rollback."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from package_j616 import OUT, RELEASE
from package import PROJECT, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    esp = Path('/Volumes/M4RCHESP')
    spec = importlib.util.spec_from_file_location('direct_stage', PROJECT / 'experiments/aurora-direct/stage.py')
    direct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    manifest = json.loads((OUT / 'manifest.json').read_text())
    assert manifest['revision'] == 10
    for name, item in manifest['files'].items():
        assert sha(OUT / name) == item['sha256'], name
    for name, digest in manifest['kit_sources'].items():
        assert sha(PROJECT / name) == digest, name
    previous = json.loads((esp / 'AUDP001/stage-receipt.json').read_text())
    assert previous['revision'] == 9
    assert sha(esp / 'boot.bin') == previous['boot_sha256']
    assert sha(esp / 'grub/grub.cfg') == previous['grub_sha256']
    rollback = json.loads((esp / 'AUDP001/rollback.json').read_text())
    for name, item in rollback.items():
        assert sha(esp / name) == item['candidate_sha256']
        assert sha(esp / 'AUDP001' / item['backup']) == item['before_sha256']
    original = (esp / 'grub/grub.cfg').read_text()
    blocks = re.findall(r'(?ms)^menuentry .*?^\}\n', original)
    current = next(b for b in blocks if ' --id m4rch-aurora-dcp001 {' in b)
    obsolete = next(b for b in blocks if ' --id m4rch-aurora-dcp006-previous {' in b)
    new = re.sub(r'^menuentry .*?\{',
        "menuentry 'Aurora merged J616s DCP + J614s GPU (AUDP001 r10; speakers disabled)' --id m4rch-aurora-dcp001 {", current, count=1)
    new = new.replace('/AUDP001/r7/vmlinuz', '/AUDP001/r10/vmlinuz').replace('/AUDP001/r9/initramfs.img', '/AUDP001/r10/initramfs.img')
    new = new.replace(' apple_dart.j713_dcp=1', '').replace(' apple_dart.j713_display=1', '')
    fallback = re.sub(r'^menuentry .*?\{',
        "menuentry 'Previous r9 kernel (GPU/framebuffer; speakers disabled)' --id m4rch-aurora-dcp009-previous {", current, count=1)
    fallback = fallback.replace('m4rch.dcp=1', 'm4rch.dcp=0').replace(' apple_dart.j713_dcp=1', '').replace(' apple_dart.j713_display=1', '')
    updated = original.replace(obsolete, '').replace(current, new + '\n' + fallback)
    assert "set default='m4rch-aurora-dcp001'" in updated
    assert len(re.findall(r'^menuentry ', updated, re.M)) == 9
    assert '/AUDP001/r10/vmlinuz' in new and 'apple_dart.j713' not in new
    old_rollback_grub = (esp / 'AUDP001' / rollback['grub/grub.cfg']['backup']).read_text()
    retire = []
    for relative, source in [('AUDP001/r6/initramfs.img', 'bootfb-r6/initramfs.img'),
                             ('AUDP001/r5/vmlinuz', 'desktop-r5/Image')]:
        assert '/' + relative not in updated + old_rollback_grub
        path = esp / relative
        expected = OUT.parent / source
        assert sha(path) == sha(expected)
        archive = OUT / 'retired-r6' / Path(relative).parent.name / Path(relative).name
        retire.append({'path': relative, 'bytes': path.stat().st_size,
                       'sha256': sha(path), 'archive': str(archive)})
    retired = {'/' + x['path'] for x in retire}
    referenced = set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)', original + old_rollback_grub))
    protected = {n: sha(esp / n.lstrip('/')) for n in referenced - retired}
    cleanup = json.loads((esp / 'AUBS001/cleanup-receipt.json').read_text())
    for name, digest in cleanup['preserved_payloads'].items():
        assert sha(esp / name) == digest
    needed = sum((OUT / n).stat().st_size for n in ['Image', 'initramfs.img']) + 4 * (OUT / 'boot.bin').stat().st_size + 4 * 1024**2
    assert shutil.disk_usage(esp).free + sum(x['bytes'] for x in retire) > needed + 32 * 1024**2
    target = esp / 'AUDP001/r10'
    assert not target.exists()
    plan = {'test': 'AUDP001', 'revision': 10, 'kernel_release': RELEASE,
        'loader_revision': 'AUDP010', 'default': 'm4rch-aurora-dcp001',
        'payload_directory': 'AUDP001/r10', 'fallback_entries': 8,
        'boot_sha256': sha(OUT / 'boot.bin'), 'kernel_sha256': sha(OUT / 'Image'),
        'grub_sha256': hashlib.sha256(updated.encode()).hexdigest(),
        'protected_payloads': protected, 'retired_obsolete_payloads': retire,
        'stage1_changed': False, 'speakers_enabled': False, 'native_boot_tested': False,
        'reboot_performed': False, 'r9_fallback': 'same r9 kernel/runtime, framebuffer/GPU display under the new loader',
        'previous_loader_backup': 'AUDP001/r10/previous.candidate.boot.bin',
        'rollback': 'python3 /Volumes/M4RCHESP/AUDP001/restore.py',
        'free_before': shutil.disk_usage(esp).free}
    (OUT / 'grub.cfg').write_text(updated)
    (OUT / 'stage-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    if not args.apply:
        print(json.dumps(plan, indent=2))
        return
    for item in retire:
        archive = Path(item['archive'])
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes((esp / item['path']).read_bytes())
        assert sha(archive) == item['sha256']
    for item in retire:
        (esp / item['path']).unlink()
    subprocess.run(['sync'], check=True)
    assert shutil.disk_usage(esp).free > needed + 32 * 1024**2
    target.mkdir()
    for src, dst in [('boot.bin', 'previous.candidate.boot.bin'), ('grub/grub.cfg', 'previous.candidate.grub.cfg'),
                     ('AUDP001/stage-receipt.json', 'previous.stage-receipt.json'), ('AUDP001/rollback.json', 'previous.rollback.json')]:
        direct.atomic_write(target / dst, (esp / src).read_bytes())
    copies = [('Image', 'vmlinuz'), ('initramfs.img', 'initramfs.img')]
    copies += [(n, n) for n in ['boot.bin', 'profile.json', 'manifest.json', 'validation.json',
                               'kernel.config', 'kernel.release', 'source-audit.json',
                               'kernel-j614s.patch', 'm1n1-j614s.patch', 'uboot-j614s.patch']]
    for src, dst in copies:
        direct.atomic_write(target / dst, (OUT / src).read_bytes())
        assert sha(target / dst) == sha(OUT / src)
    for name, item in rollback.items():
        item['previous_candidate_sha256'] = list(dict.fromkeys(
            item.get('previous_candidate_sha256', []) + [item['candidate_sha256']]))
        item['candidate_sha256'] = plan['boot_sha256'] if name == 'boot.bin' else plan['grub_sha256']
    direct.atomic_write(esp / 'AUDP001/rollback.json', (json.dumps(rollback, indent=2) + '\n').encode())
    direct.atomic_write(esp / 'boot.bin', (OUT / 'boot.bin').read_bytes())
    direct.atomic_write(esp / 'grub/grub.cfg', updated.encode())
    for name, digest in protected.items():
        assert sha(esp / name.lstrip('/')) == digest, name
    for name, item in rollback.items():
        assert sha(esp / name) == item['candidate_sha256']
        assert sha(esp / 'AUDP001' / item['backup']) == item['before_sha256']
    for name in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)', updated):
        assert (esp / name.lstrip('/')).is_file(), name
    plan.update({'phase': 'staged-awaiting-manual-boot',
                 'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'free_after': shutil.disk_usage(esp).free})
    data = (json.dumps(plan, indent=2) + '\n').encode()
    direct.atomic_write(target / 'stage-receipt.json', data)
    direct.atomic_write(esp / 'AUDP001/stage-receipt.json', data)
    (OUT / 'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'], check=True)
    print(data.decode())


if __name__ == '__main__':
    main()
