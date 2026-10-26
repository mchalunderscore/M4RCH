#!/usr/bin/env python3
"""Package the complete opt-in GPU stack without replacing the working AURD001."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tarfile
import package as base

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent
WORK = PROJECT / 'out/aurora-direct/gpu16'
KIT = WORK / 'kit'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Base init context differs: ' + old[:70])
    return text.replace(old, new, 1)


def main():
    baseline = PROJECT / 'out/aurora-direct/kit'
    manifest = json.loads((baseline / 'manifest.json').read_text())
    if manifest['profile']['revision'] != 6:
        raise ValueError('Expected the retained runtime revision 6')
    for name, info in manifest['files'].items():
        if sha(baseline / name) != info['sha256']:
            raise ValueError('Base payload changed: ' + name)
    members = {name.rstrip('/'): item for name, item in
               base.nvme.initramfs_members((baseline / 'initramfs.img').read_bytes()).items()}
    init = members['init'][1].decode()
    init = replace_once(init, 'mkdir -p /run/aurora-modules', '''grep -q 'm4rch.aurora_gpu16=on' /proc/cmdline || stop 'GPU16 command line missing'
mkdir -p /run/aurora-modules''')
    init = replace_once(init, "echo \"Aurora CPUs:", "printf 'options asahi t6040_16core=1\\n' >>/run/aurora-direct/modprobe.conf\necho \"Aurora CPUs:")
    init = replace_once(init, '# Merge the current Aurora card definitions',
                        "sh /gpu16-discovery.sh /newroot || stop 'Cannot bind trusted GPU driver discovery'\n# Merge the current Aurora card definitions")
    init = replace_once(init, 'cp /plasma-aurora.desktop /run/aurora-userspace/wayland-sessions/', '''cp /plasma-aurora.desktop /run/aurora-userspace/wayland-sessions/
# Use the GPU wrapper even if SDDM remembers the ordinary Plasma Wayland entry.
for session in /run/aurora-userspace/wayland-sessions/*.desktop; do
    if grep -q 'startplasma-wayland' "$session"; then cp /plasma-aurora.desktop "$session"; fi
done''')
    init = replace_once(init, 'cp /aurora-runtime.sh /run/aurora-direct/runtime.sh', '''# The normal root may retain a console-only default from earlier bring-up.
# Enable its installed SDDM only in the temporary unit tree for this boot.
if [ -f /newroot/usr/lib/systemd/system/sddm.service ]; then
    mkdir -p /run/aurora-userspace/sddm-conf
    if [ -d /newroot/etc/sddm.conf.d ]; then
        cp -a /newroot/etc/sddm.conf.d/. /run/aurora-userspace/sddm-conf/ || stop 'Cannot preserve SDDM settings'
    fi
    cp /gpu16-sddm.conf /run/aurora-userspace/sddm-conf/zzzz-aurora-gpu16-wayland.conf
    mkdir -p /newroot/etc/sddm.conf.d
    mount --bind /run/aurora-userspace/sddm-conf /newroot/etc/sddm.conf.d || stop 'Cannot bind Wayland SDDM settings'
    for unit in sddm.service display-manager.service; do
        path=/run/aurora-userspace/systemd-system/$unit
        if [ -L "$path" ] && [ "$(readlink "$path")" = /dev/null ]; then rm "$path"; fi
    done
    ln -sf /usr/lib/systemd/system/sddm.service /run/aurora-userspace/systemd-system/display-manager.service
    mkdir -p /run/systemd/system/graphical.target.wants
    ln -s /usr/lib/systemd/system/sddm.service /run/systemd/system/graphical.target.wants/sddm.service
fi
cp /aurora-collect-base.sh /run/aurora-direct/collect-base.sh
cp /gpu16-profile.json /run/aurora-direct/gpu16-candidate.json
mkdir -p /run/systemd/system/multi-user.target.wants /run/systemd/user/plasma-kwin_wayland.service.d
cp /gpu16-kwin.conf /run/systemd/user/plasma-kwin_wayland.service.d/zzzz-aurora-gpu16.conf
cp /gpu16-recorder.sh /run/aurora-direct/recorder.sh
cp /gpu16-recorder.service /run/systemd/system/gpu16-recorder.service
ln -s ../gpu16-recorder.service /run/systemd/system/multi-user.target.wants/gpu16-recorder.service
cp /gpu16-vulkan.sh /run/aurora-direct/vulkan-startup.sh
cp /gpu16-vulkan.service /run/systemd/system/gpu16-vulkan.service
ln -s ../gpu16-vulkan.service /run/systemd/system/multi-user.target.wants/gpu16-vulkan.service
cp /gpu16-collect.service /run/systemd/system/gpu16-collect.service
cp /gpu16-collect.timer /run/systemd/system/gpu16-collect.timer
mkdir -p /run/systemd/system/timers.target.wants
ln -s ../gpu16-collect.timer /run/systemd/system/timers.target.wants/gpu16-collect.timer
cp /aurora-runtime.sh /run/aurora-direct/runtime.sh''')
    profile = {'test': 'AURG016', 'revision': 4, 'base_profile': manifest['profile'],
               'kernel_release': manifest['kernel_release'], 'kernel_sha256': sha(baseline / 'vmlinuz'),
               'base_initramfs_sha256': sha(baseline / 'initramfs.img'),
               'asahi_module_sha256': sha(WORK / 'asahi.ko'), 'patch_sha256': sha(WORK / 'gpu16.patch'),
               'experimental': 'Explicit module option; T6040, 1 die, 2 clusters, 10 slots each, masks 0x3db/0x3db; physical-slot buffers retained as an unqualified hypothesis',
               'render_and_compute_enabled': True, 'graphics': 'Pinned Aurora Vulkan plus Zink OpenGL; KWin separate render node',
               'driver_discovery': 'RAM-backed trusted system Vulkan ICD and EGL vendor directories, including secure KWin execution',
               'display_manager': 'Temporary Wayland SDDM greeter with wrapped KWin; preserve existing autologin settings',
               'speakers_enabled': False, 'native_boot_tested': False}
    replacements = {
        'init': (stat.S_IFREG | 0o755, init.encode()),
        'modules.tar.gz': (stat.S_IFREG | 0o644, (WORK / 'modules.tar.gz').read_bytes()),
        'mesa.tar.gz': (stat.S_IFREG | 0o644, (WORK / 'mesa.tar.gz').read_bytes()),
        'aurora-runtime.sh': (stat.S_IFREG | 0o755, (SOURCE / 'runtime.sh').read_bytes().replace(b'Aurora AURD001:', b'Aurora AURG016 full-render experiment:')),
        'aurora-with-mesa': (stat.S_IFREG | 0o755, (SOURCE / 'gpu16-with-mesa').read_bytes()),
        'aurora-collect.sh': (stat.S_IFREG | 0o755, (SOURCE / 'gpu16-collect.sh').read_bytes()),
        'aurora-collect-base.sh': (stat.S_IFREG | 0o755, (SOURCE / 'collect.sh').read_bytes()),
        'gpu16-collect.service': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-collect.service').read_bytes()),
        'gpu16-collect.timer': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-collect.timer').read_bytes()),
        'gpu16-kwin.conf': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-kwin.conf').read_bytes()),
        'gpu16-recorder.sh': (stat.S_IFREG | 0o755, (SOURCE / 'gpu16-recorder.sh').read_bytes()),
        'gpu16-recorder.service': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-recorder.service').read_bytes()),
        'gpu16-discovery.sh': (stat.S_IFREG | 0o755, (SOURCE / 'gpu16-discovery.sh').read_bytes()),
        'gpu16-vulkan.sh': (stat.S_IFREG | 0o755, (SOURCE / 'gpu16-vulkan.sh').read_bytes()),
        'gpu16-vulkan.service': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-vulkan.service').read_bytes()),
        'gpu16-sddm.conf': (stat.S_IFREG | 0o644, (SOURCE / 'gpu16-sddm.conf').read_bytes()),
        'gpu16-profile.json': (stat.S_IFREG | 0o644, (json.dumps(profile, indent=2) + '\n').encode()),
        'plasma-aurora.desktop': (stat.S_IFREG | 0o644, (SOURCE / 'plasma-aurora.desktop').read_bytes().replace(b'Plasma (Aurora GPU test)', b'Plasma (Aurora 16-core GPU)')),
    }
    release = manifest['kernel_release']
    module_path = f'lib/modules/{release}/kernel/drivers/gpu/drm/asahi/asahi.ko'
    with tarfile.open(WORK / 'modules.tar.gz') as archive:
        if hashlib.sha256(archive.extractfile(module_path).read()).hexdigest() != profile['asahi_module_sha256']:
            raise ValueError('Wrong GPU module in package')
        if any('tas2764' in p or 'tas2770' in p for p in archive.getnames()):
            raise ValueError('Speaker amplifier module in package')
    members.update(replacements)
    entries = [(name, *members[name]) for name in sorted(members, key=lambda name: (name.count('/'), name))]
    image = gzip.compress(base.nvme.newc(base.nvme.archive_with_parents(entries, {})), compresslevel=9, mtime=0)
    readback = base.nvme.initramfs_members(image)
    for name, value in replacements.items():
        if readback[name] != value:
            raise ValueError('Initramfs readback differs: ' + name)
    KIT.mkdir(exist_ok=True)
    (KIT / 'initramfs.img').write_bytes(image)
    (KIT / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    shutil.copyfile(baseline / 'vmlinuz', KIT / 'vmlinuz')
    for source, target in [('gpu16.patch', 'gpu16.patch'), ('runtime-dependencies.json', 'runtime-dependencies.json'),
                           ('runtime-loader-verification.json', 'runtime-loader-verification.json'),
                           ('secure-loader-verification.json', 'secure-loader-verification.json')]:
        shutil.copyfile(WORK / source, KIT / target)
    shutil.copyfile(SOURCE / 'GPU16.md', KIT / 'BOOT.md')
    shutil.copyfile(SOURCE / 'gpu16-collect.sh', KIT / 'collect.sh')
    result = {'test': 'AURG016', 'profile': profile,
              'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(KIT.iterdir()) if p.is_file() and p.name != 'manifest.json'},
              'source_files': {p.name: sha(p) for p in SOURCE.iterdir() if p.is_file()}}
    (KIT / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    (WORK / 'init.checked').write_text(init)
    print('GPU16 kit:', KIT, 'payload MiB:', sum(v['bytes'] for v in result['files'].values()) // 1024**2)


if __name__ == '__main__':
    main()
