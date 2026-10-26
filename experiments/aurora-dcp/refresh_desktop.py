#!/usr/bin/env python3
"""Install revision 5 with verified r4 fallback and pre-DCP rollback intact."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
from package import PROJECT, OUTPUT, sha
from prepare_desktop_runtime import RELEASE


def configurations(original):
    assert "set default='m4rch-aurora-dcp001'" in original
    entry = re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n', original)
    assert entry and '/AUDP001/r3/vmlinuz' in entry[0] and '/AUDP001/r4/initramfs.img' in entry[0]
    assert len(re.findall(r'^menuentry ', original, re.M)) == 7
    old = entry[0]
    new = re.sub(r"^menuentry '[^']+'", "menuentry 'Aurora PR445 J614s DCP + GPU (AUDP001 r5; speakers disabled)'", old)
    new = new.replace('/AUDP001/r3/vmlinuz', '/AUDP001/r5/vmlinuz').replace('/AUDP001/r4/initramfs.img', '/AUDP001/r5/initramfs.img')
    assert new.count('appledrm.j614s_modeset=1') == 1
    new = new.replace('appledrm.j614s_modeset=1', 'appledrm.show_notch=1 appledrm.t6041_dcpext=0')
    assert 'j614s_modeset' not in new
    previous = re.sub(r"^menuentry '[^']+'", "menuentry 'Previous DCP r4 candidate (speakers disabled)'", old)
    previous = previous.replace('--id m4rch-aurora-dcp001 {', '--id m4rch-aurora-dcp004-previous {')
    result = original[:entry.start()] + new + '\n' + previous + original[entry.end():]
    assert len(re.findall(r'^menuentry ', result, re.M)) == 8
    assert result[result.index('--id m4rch-aurora-dcp002-retained'):]==original[original.index('--id m4rch-aurora-dcp002-retained'):]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP')); p.add_argument('--apply', action='store_true')
    a = p.parse_args(); esp = a.esp; out = OUTPUT / 'desktop-r5'
    spec = importlib.util.spec_from_file_location('direct', PROJECT / 'experiments/aurora-direct/stage.py')
    direct = importlib.util.module_from_spec(spec); spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['revision'] == 5 and manifest['kernel_release'] == RELEASE
    for name, value in manifest['files'].items(): assert sha(out / name) == value['sha256'], name
    for name, digest in manifest['kit_sources'].items(): assert sha(PROJECT / name) == digest, name
    previous = json.loads((esp / 'AUDP001/stage-receipt.json').read_text()); assert previous['revision'] == 4
    assert sha(esp / 'boot.bin') == previous['boot_sha256']
    assert sha(esp / 'grub/grub.cfg') == previous['grub_sha256']
    rollback = json.loads((esp / 'AUDP001/rollback.json').read_text())
    for name, item in rollback.items():
        assert sha(esp / name) == item['candidate_sha256'], name
        assert sha(esp / 'AUDP001' / item['backup']) == item['before_sha256'], name
    cleanup = json.loads((esp / 'AUBS001/cleanup-receipt.json').read_text())
    for name, digest in cleanup['preserved_payloads'].items(): assert sha(esp / name) == digest, name
    original = (esp / 'grub/grub.cfg').read_text(); updated = configurations(original)
    (out / 'grub.cfg').write_text(updated)
    target = esp / 'AUDP001/r5'; assert not target.exists(), 'Inspect existing revision 5 before retrying'
    # The user explicitly allowed erasing obsolete test kernel files. Retire
    # only the unreferenced r1 pair, after saving and hashing their exact bytes.
    retire = []
    rollback_grub = (esp / 'AUDP001' / rollback['grub/grub.cfg']['backup']).read_text()
    for name, source in [('AUDP001/vmlinuz', 'Image'), ('AUDP001/initramfs.img', 'initramfs.img')]:
        assert '/' + name not in original and '/' + name not in updated and '/' + name not in rollback_grub
        expected = OUTPUT / 'revision-1' / source
        archive = out / 'retired-r1' / Path(name).name
        present = (esp / name).exists()
        assert sha(esp / name if present else archive) == sha(expected), name
        retire.append({'path': name, 'bytes': expected.stat().st_size, 'sha256': sha(expected),
                       'archive': str(archive), 'already_retired': not present})
    needed = (out / 'Image').stat().st_size + (out / 'initramfs.img').stat().st_size + 3 * (out / 'boot.bin').stat().st_size + 4 * 1024**2
    free = shutil.disk_usage(esp).free
    assert free + sum(x['bytes'] for x in retire if not x['already_retired']) > needed + 32 * 1024**2
    plan = {'test': 'AUDP001', 'revision': 5, 'kernel_release': RELEASE, 'loader_revision': 'DCP005',
        'default': 'm4rch-aurora-dcp001', 'payload_directory': 'AUDP001/r5', 'fallback_entries': 7,
        'native_boot_tested': False, 'reboot_performed': False, 'speakers_enabled': False,
        'boot_sha256': sha(out / 'boot.bin'), 'grub_sha256': hashlib.sha256(updated.encode()).hexdigest(),
        'retire_unreferenced_revision1': retire, 'previous_r4_entry_preserved': True,
        'original_native_rollback_preserved': True, 'free_before': free,
        'rollback': 'python3 /Volumes/M4RCHESP/AUDP001/restore.py'}
    (out / 'stage-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    if not a.apply:
        print(json.dumps(plan, indent=2)); return
    for item in retire:
        archive = Path(item['archive']); archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists(): archive.write_bytes((esp / item['path']).read_bytes())
        assert sha(archive) == item['sha256']
    for item in retire:
        if not item['already_retired']:
            assert sha(esp / item['path']) == item['sha256']
            (esp / item['path']).unlink()
    # FAT32 can report its old free-block count immediately after unlink.
    subprocess.run(['sync'], check=True)
    assert shutil.disk_usage(esp).free > needed + 32 * 1024**2
    target.mkdir()
    for src, dst in [('boot.bin', 'previous.candidate.boot.bin'), ('grub/grub.cfg', 'previous.candidate.grub.cfg'),
                     ('AUDP001/stage-receipt.json', 'previous.stage-receipt.json'), ('AUDP001/rollback.json', 'previous.rollback.json')]:
        direct.atomic_write(target / dst, (esp / src).read_bytes())
    copies = [('Image', 'vmlinuz'), ('initramfs.img', 'initramfs.img')]
    copies += [(n, n) for n in ['profile.json', 'manifest.json', 'validation.json', 'kernel.config',
                               'j614s-desktop.patch', 'm1n1-flat-root.patch', 'desktop-source-manifest.json']]
    for src, dst in copies:
        direct.atomic_write(target / dst, (out / src).read_bytes())
        assert sha(target / dst) == sha(out / src)
    for item in rollback.values():
        item['previous_candidate_sha256'] = list(dict.fromkeys(item.get('previous_candidate_sha256', []) + [item['candidate_sha256']]))
    rollback['boot.bin']['candidate_sha256'] = plan['boot_sha256']
    rollback['grub/grub.cfg']['candidate_sha256'] = plan['grub_sha256']
    direct.atomic_write(esp / 'AUDP001/rollback.json', (json.dumps(rollback, indent=2) + '\n').encode())
    direct.atomic_write(esp / 'boot.bin', (out / 'boot.bin').read_bytes())
    direct.atomic_write(esp / 'grub/grub.cfg', updated.encode())
    for name, item in rollback.items():
        assert sha(esp / name) == item['candidate_sha256'], name
        assert sha(esp / 'AUDP001' / item['backup']) == item['before_sha256'], name
    for name, digest in cleanup['preserved_payloads'].items(): assert sha(esp / name) == digest, name
    for f in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)', updated): assert (esp / f.lstrip('/')).is_file(), f
    plan.update({'phase': 'staged-awaiting-manual-boot', 'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'free_after': shutil.disk_usage(esp).free})
    data = (json.dumps(plan, indent=2) + '\n').encode()
    direct.atomic_write(target / 'stage-receipt.json', data)
    direct.atomic_write(esp / 'AUDP001/stage-receipt.json', data)
    (out / 'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'], check=True)
    print(data.decode())


if __name__ == '__main__':
    main()
