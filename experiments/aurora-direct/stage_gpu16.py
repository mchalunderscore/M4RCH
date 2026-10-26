#!/usr/bin/env python3
"""Install an independent GPU kit and add verified working fallback entries."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from stage import PROJECT, atomic_write, sha, validate_esp


def checked(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, info in manifest['files'].items():
        if Path(name).name != name or sha(directory / name) != info['sha256']:
            raise ValueError('Payload differs: ' + str(directory / name))
    return manifest


def checked_gpu_fallback(esp):
    directory = esp / 'AURG016.saved-r3'
    if not directory.exists():
        return None
    receipt = json.loads((directory / 'fallback-receipt.json').read_text())
    if (receipt['kernel_path'] != 'AURD001/vmlinuz'
            or receipt['kernel_sha256'] != sha(esp / 'AURD001/vmlinuz')
            or receipt['initramfs_sha256'] != sha(directory / 'initramfs.img')
            or receipt['profile_sha256'] != sha(directory / 'profile.json')
            or receipt['boot_sha256'] != sha(esp / 'AURD001/boot.bin')
            or json.loads((directory / 'profile.json').read_text())['revision'] != 3):
        raise ValueError('Working GPU revision 3 fallback differs')
    return directory


def preserve_working_gpu(esp):
    validate_esp(esp)
    if checked_gpu_fallback(esp):
        return
    source = esp / 'AURG016'
    manifest = checked(source)
    if manifest['profile']['revision'] != 3:
        raise ValueError('Expected the native working GPU revision 3')
    if sha(source / 'vmlinuz') != sha(esp / 'AURD001/vmlinuz'):
        raise ValueError('Working GPU fallback kernel differs from retained baseline')
    directory = esp / 'AURG016.saved-r3'
    if shutil.disk_usage(esp).free < (source / 'initramfs.img').stat().st_size + 16 * 1024**2:
        raise ValueError('Insufficient space to preserve the working GPU initramfs')
    directory.mkdir()
    for name in ['initramfs.img', 'profile.json']:
        atomic_write(directory / name, (source / name).read_bytes())
    receipt = {'kernel_path': 'AURD001/vmlinuz', 'kernel_sha256': sha(source / 'vmlinuz'),
               'initramfs_sha256': sha(source / 'initramfs.img'), 'profile_sha256': sha(source / 'profile.json'),
               'boot_sha256': sha(esp / 'AURD001/boot.bin'), 'source_manifest_sha256': sha(source / 'manifest.json'),
               'native_result': 'Owner started accelerated Plasma manually; native logs identify the M4 Pro Vulkan and Zink renderer'}
    atomic_write(directory / 'fallback-receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())
    checked_gpu_fallback(esp)
    subprocess.run(['sync'], check=True)


def configurations(original, saved, gpu_saved=None):
    if 'AURG016' in original or len(re.findall(r'(?m)^set default=.*$', original)) != 1:
        raise ValueError('Unexpected base GRUB')
    common = re.findall(r'(?m)^\s*linux /AURD001/vmlinuz (.+)$', original)[0]
    if 'm4rch.aurora_gpu=off' in common or '7568fe83-378f-5b78-ab12-ccc36ff09a90' not in common:
        raise ValueError('Wrong base command line')
    common = ' '.join(p for p in common.split() if not p.startswith('systemd.unit='))
    additions = ''
    for title, identifier, directory, extra in [
        ('Experimental Aurora 16-core GPU (Plasma/Zink)', 'm4rch-aurora-gpu16', 'AURG016', ' m4rch.aurora_gpu16=on systemd.unit=graphical.target'),
        ('Experimental Aurora 16-core GPU (console recovery)', 'm4rch-aurora-gpu16-console', 'AURG016', ' m4rch.aurora_gpu16=on systemd.unit=multi-user.target'),
        ('Aurora direct - last successful revision 5', 'm4rch-aurora-native-r5', saved.name, ''),
    ]:
        additions += f"\nmenuentry '{title}' --id {identifier} {{\n"
        additions += '    search --no-floppy --fs-uuid --set=root 33CE-1F10\n'
        additions += f'    linux /{directory}/vmlinuz {common}{extra}\n'
        additions += f'    initrd /{directory}/initramfs.img\n}}\n'
    if gpu_saved:
        additions += "\nmenuentry 'Aurora GPU - working revision 3 (manual Plasma)' --id m4rch-aurora-gpu-native-r3 {\n"
        additions += '    search --no-floppy --fs-uuid --set=root 33CE-1F10\n'
        additions += f'    linux /AURD001/vmlinuz {common} m4rch.aurora_gpu16=on systemd.unit=multi-user.target\n'
        additions += f'    initrd /{gpu_saved.name}/initramfs.img\n}}\n'
    return (re.sub(r'(?m)^set default=.*$', "set default='m4rch-aurora-gpu16'", original) + additions).encode()


def stage(kit, esp):
    validate_esp(esp)
    manifest = checked(kit)
    if manifest['test'] != 'AURG016' or manifest['profile']['speakers_enabled']:
        raise ValueError('Wrong GPU kit')
    base = esp / 'AURD001'
    baseline = checked(base)
    if baseline['profile']['revision'] != 6:
        raise ValueError('Base revision differs')
    receipt = json.loads((base / 'staging-receipt.json').read_text())
    grub = esp / 'grub/grub.cfg'
    if sha(grub) not in receipt['configurations'].values() or sha(esp / 'boot.bin') != receipt['loaders']['test']:
        raise ValueError('Unexpected active boot pair')
    if (base / 'mode').read_text() != 'test\n':
        raise ValueError('Expected primary board handoff')
    candidates = sorted(esp.glob('AURD001.saved-r5-*'))
    if len(candidates) != 1:
        raise ValueError('Expected one successful revision 5 archive')
    saved = candidates[0]
    if checked(saved)['profile']['revision'] != 5 or sha(saved / 'boot.bin') != sha(esp / 'boot.bin'):
        raise ValueError('Native fallback requires a different loader')
    if sha(kit / 'vmlinuz') != sha(base / 'vmlinuz'):
        raise ValueError('GPU module must use the retained kernel ABI')
    destination = esp / 'AURG016'
    if destination.exists():
        raise ValueError('GPU kit already installed; preserve it first')
    if shutil.disk_usage(esp).free < sum(v['bytes'] for v in manifest['files'].values()) + 8 * 1024**2:
        raise ValueError('Insufficient ESP space')
    original = grub.read_bytes()
    gpu_saved = checked_gpu_fallback(esp)
    config = configurations(original.decode(), saved, gpu_saved)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = PROJECT / 'out/aurora-direct/gpu16/backups' / stamp
    backup.mkdir(parents=True)
    for source, name in [(grub, 'grub.cfg'), (base / 'staging-receipt.json', 'staging-receipt.json'), (esp / 'boot.bin', 'boot.bin')]:
        shutil.copyfile(source, backup / name)
        if sha(source) != sha(backup / name):
            raise ValueError('Backup readback differs')
    destination.mkdir()
    for name in [*manifest['files'], 'manifest.json']:
        shutil.copyfile(kit / name, destination / name)
        if sha(kit / name) != sha(destination / name):
            raise ValueError('GPU readback differs: ' + name)
    checked(destination)
    updated = dict(receipt)
    updated['configurations'] = {**receipt['configurations'], 'gpu16': hashlib.sha256(config).hexdigest()}
    updated['loaders'] = {**receipt['loaders'], 'gpu16': receipt['loaders']['test']}
    gpu_receipt = {'test': 'AURG016', 'backup': str(backup), 'manifest_sha256': sha(destination / 'manifest.json'),
                   'boot_sha256': sha(esp / 'boot.bin'), 'grub_sha256': hashlib.sha256(config).hexdigest(),
                   'native_r5_fallback': str(saved), 'base_manifest_sha256': sha(base / 'manifest.json'),
                   'native_boot_tested': False, 'speakers_enabled': False}
    if gpu_saved:
        gpu_receipt['native_gpu_r3_fallback'] = str(gpu_saved)
    try:
        atomic_write(base / 'grub.gpu16.cfg', config)
        atomic_write(base / 'staging-receipt.json', (json.dumps(updated, indent=2) + '\n').encode())
        atomic_write(destination / 'staging-receipt.json', (json.dumps(gpu_receipt, indent=2) + '\n').encode())
        atomic_write(grub, config)
    except BaseException:
        atomic_write(grub, original)
        atomic_write(base / 'staging-receipt.json', (backup / 'staging-receipt.json').read_bytes())
        raise
    if sha(esp / 'boot.bin') != gpu_receipt['boot_sha256']:
        raise ValueError('Loader changed during GPU staging')
    checked(base)
    checked(saved)
    subprocess.run(['sync'], check=True)
    (PROJECT / 'out/aurora-direct/gpu16/staging-receipt.json').write_text(json.dumps(gpu_receipt, indent=2) + '\n')
    print('Staged AURG016 as GRUB default; native revision 5 and AURD001 remain available')


def replace_installed(kit, esp):
    """Archive the failed candidate, select the normal boot, then replace it."""
    from select_boot import select
    validate_esp(esp)
    destination = esp / 'AURG016'
    old, new = checked(destination), checked(kit)
    if new['test'] != old['test'] or new['profile']['revision'] <= old['profile']['revision']:
        raise ValueError('Expected a newer revision of the same GPU experiment')
    if sha(kit / 'vmlinuz') != sha(destination / 'vmlinuz') or new['profile']['speakers_enabled']:
        raise ValueError('Replacement must retain the kernel and speaker exclusion')
    old_receipt = json.loads((destination / 'staging-receipt.json').read_text())
    if old_receipt['manifest_sha256'] != sha(destination / 'manifest.json'):
        raise ValueError('Installed GPU receipt differs')
    if old['profile']['revision'] == 3:
        preserve_working_gpu(esp)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = PROJECT / 'out/aurora-direct/gpu16/backups' / f'installed-r{old["profile"]["revision"]}-{stamp}'
    shutil.copytree(destination, archive)
    for source in destination.rglob('*'):
        if source.is_file() and sha(source) != sha(archive / source.relative_to(destination)):
            raise ValueError('Installed candidate archive differs: ' + str(source))
    checked(archive)
    # The ordinary revision 6 remains bootable throughout replacement. Free only
    # this hash-verified generated candidate; its exact old kit is on the host.
    select('test', esp)
    shutil.rmtree(destination)
    try:
        stage(kit, esp)
    except BaseException:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(archive, destination)
        checked(destination)
        select('test', esp)
        subprocess.run(['sync'], check=True)
        raise
    print('Prior GPU candidate preserved:', archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, default=PROJECT / 'out/aurora-direct/gpu16/kit')
    parser.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    parser.add_argument('--replace', action='store_true', help='Hash-archive and replace an older GPU revision')
    args = parser.parse_args()
    (replace_installed if args.replace else stage)(args.kit.resolve(), args.esp)
