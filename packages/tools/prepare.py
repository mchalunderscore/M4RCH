#!/usr/bin/env python3
"""Prepare local makepkg sources from the working build and mounted Arch root.

This runs on the build host. Nothing here is installed as a system updater.
"""
from pathlib import Path
import argparse
import hashlib
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/packages'
SOURCE = OUT / 'source'
NAMES = ('linux-m4rch', 'mesa-m4rch', 'virglrenderer-m4rch', 'm1n1-m4rch', 'u-boot-m4rch',
         'linux-firmware-vendor-m4rch', 'alsa-ucm-conf-m4rch', 'asahi-scripts-m4rch',
         'mesa-flatpak-m4rch', 'avd-fw-m4rch', 'steam-m4rch', 'mbpfan-m4rch',
         'vesktop-m4rch', 'power-profiles-daemon-m4rch')


def archive(path, source, arcname):
    with tarfile.open(path, 'w:gz') as tar:
        tar.add(source, arcname=arcname)


def collect_alsa(target, destination):
    """Copy stock UCM and replace Apple board profiles with J614s profiles."""
    owner = next((target/'var/lib/pacman/local').glob('alsa-ucm-conf-*/files'))
    for name in owner.read_text().split('%FILES%\n', 1)[1].split('\n\n', 1)[0].splitlines():
        if not name.startswith('usr/share/alsa/') or name.endswith('/'):
            continue
        if name.startswith(('usr/share/alsa/ucm2/conf.d/aop_audio/',
                            'usr/share/alsa/ucm2/conf.d/macaudio/',
                            'usr/share/alsa/ucm2/conf.d/t8140-aop-audio/')):
            continue
        source = target/name
        dest = destination/str(Path(name).relative_to('usr/share/alsa'))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            dest.symlink_to(source.readlink())
        else:
            shutil.copy2(source, dest)
    shutil.copytree(ROOT/'packages/alsa-ucm-conf-m4rch/files', destination, dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/Volumes/ARCHROOT'))
    target = parser.parse_args().root
    recipes = OUT / 'recipes'
    recipes.mkdir(parents=True, exist_ok=True)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(SOURCE / 'asahi-scripts.tar.gz') == 'c35a2e56ea332f90475cbf6f8ef761bbdc437d084e2249cbec29e58cc4e4fa95'
    for name in NAMES:
        dest = recipes / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(ROOT / 'packages' / name, dest,
                        ignore=shutil.ignore_patterns('src', 'pkg', '__pycache__', '*.pkg.tar.*'))
        if name == 'power-profiles-daemon-m4rch':
            stock = ROOT / 'packages' / name / 'power-profiles-daemon-0.30-1-aarch64.pkg.tar.xz'
            shutil.copy2(stock, dest / stock.name)

    kernel = recipes / 'linux-m4rch'
    kernel_inputs = ROOT / 'out/external-investigation/promotion/linux'
    # Refuse stale inputs that omit either hardware-tested fix.
    for patch in ('linux-asahi-deferred-close-rebind.patch',
                  'experimental-aurora-pr512-fan.patch',
                  'experimental-j614s-fan-unlock-retry.patch',
                  'experimental-j614s-hdr.patch',
                  'experimental-j614s-hdr-gpu-conversion.patch',
                  'experimental-j614s-hdr-transfer-probe.patch',
                  'experimental-j614s-hdr-edr-ratio-probe.patch',
                  'j614s-hdr-main-default.patch'):
        if (ROOT / 'patches' / patch).read_bytes() not in (kernel_inputs / 'kernel.patch').read_bytes():
            raise SystemExit(f'Kernel build inputs do not include {patch}.')
    if b'Linux version 7.3.0-m4rch-vrr-ext ' not in (kernel_inputs / 'Image').read_bytes():
        raise SystemExit('Kernel build inputs do not contain the promoted VRR image.')
    for name in ('Image', 'modules.tar.gz', 'apple-j614s.dtb'):
        shutil.copy2(kernel_inputs / name, kernel/name)
    for name in ('kernel.config', 'kernel.patch', 'gpu-diagnostics.patch',
                 'aurora-vrr.patch', 'force-vrr.patch', 'wake-hpd.patch',
                 'wake-reapply.patch', 'external-display.patch'):
        source = ROOT / 'packages/linux-m4rch/promoted-source' / name
        if sha(source) != sha(kernel_inputs / name):
            raise SystemExit(f'Preserved kernel source differs from promoted inputs: {name}')
        shutil.copy2(source, kernel/name)
    shutil.copy2(ROOT/'out/external-investigation/promotion/m1n1/m1n1.bin', recipes/'m1n1-m4rch/m1n1.bin')
    m1n1_patch = ROOT/'packages/m1n1-m4rch/promoted-source/external-handoff.patch'
    if sha(m1n1_patch) != sha(ROOT/'out/external-investigation/promotion/m1n1/external-handoff.patch'):
        raise SystemExit('Preserved m1n1 source differs from promoted inputs.')
    shutil.copy2(m1n1_patch, recipes/'m1n1-m4rch/external-handoff.patch')
    required_uboot_patch = ROOT / 'patches/uboot-j614s-default-handoff.patch'
    if required_uboot_patch.read_bytes() not in (ROOT / 'out/external-investigation/promotion/uboot/uboot.patch').read_bytes():
        raise SystemExit('U-Boot build inputs still require the experimental mode file.')
    uboot_patch = ROOT/'packages/u-boot-m4rch/promoted-source/uboot.patch'
    if sha(uboot_patch) != sha(ROOT/'out/external-investigation/promotion/uboot/uboot.patch'):
        raise SystemExit('Preserved U-Boot source differs from promoted inputs.')
    for source, name in [(ROOT/'out/external-investigation/promotion/uboot/u-boot-nodtb.bin', 'u-boot-nodtb.bin'),
                         (uboot_patch, 'uboot.patch'), (SOURCE/'COPYING', 'COPYING')]:
        shutil.copy2(source, recipes/'u-boot-m4rch'/name)

    # Firmware stays local to the machine it was extracted from.
    firmware = OUT/'firmware'
    if firmware.exists():
        shutil.rmtree(firmware)
    for owner in (target/'var/lib/pacman/local').glob('*/files'):
        if not owner.parent.name.startswith(('config-m4rch-', 'firmware-apple-m4rch-', 'linux-firmware-vendor-m4rch-')):
            continue
        for name in owner.read_text().split('%FILES%\n', 1)[1].split('\n\n', 1)[0].splitlines():
            if not name.startswith('usr/lib/firmware/') or name.endswith('/'):
                continue
            dest = firmware/str(Path(name).relative_to('usr/lib/firmware'))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target/name, dest)
    if (SOURCE/'firmware').is_dir():
        shutil.copytree(SOURCE/'firmware', firmware, dirs_exist_ok=True)
    archive(recipes/'linux-firmware-vendor-m4rch/firmware.tar.gz', firmware, 'firmware')
    alsa = OUT/'alsa'
    if alsa.exists():
        shutil.rmtree(alsa)
    # Copy only package-owned UCM files, including symlinks; never user policy.
    collect_alsa(target, alsa)
    archive(recipes/'alsa-ucm-conf-m4rch/alsa.tar.gz', alsa, 'alsa')
    scripts = recipes/'asahi-scripts-m4rch'
    archive(scripts/'files.tar.gz', scripts/'files', 'files')
    shutil.copy2(SOURCE/'asahi-scripts.tar.gz', scripts/'asahi-scripts.tar.gz')
    shutil.copy2(SOURCE/'flatpak-extensions.tar.gz', recipes/'mesa-flatpak-m4rch/flatpak-extensions.tar.gz')
    shutil.copy2(SOURCE/'steam-launcher.deb', recipes/'steam-m4rch/steam-launcher.deb')
    shutil.copy2(SOURCE/'mbpfan-source.tar.gz', recipes/'mbpfan-m4rch/mbpfan-source.tar.gz')
    for filename in ('electron45.zip', 'vesktop-app.tar.gz'):
        shutil.copy2(SOURCE/filename, recipes/'vesktop-m4rch'/filename)
    # Record real checksums for every local source in ordinary PKGBUILDs.
    sources = {
        'linux-m4rch': ['Image', 'modules.tar.gz', 'linux-m4rch.preset', 'apple-j614s.dtb', 'kernel.config', 'kernel.patch', 'gpu-diagnostics.patch', 'aurora-vrr.patch', 'force-vrr.patch', 'wake-hpd.patch', 'wake-reapply.patch', 'external-display.patch', 'GPL-2.0'],
        'm1n1-m4rch': ['m1n1.bin', 'external-handoff.patch', 'LICENSE'],
        'u-boot-m4rch': ['u-boot-nodtb.bin', 'uboot.patch', 'COPYING'],
        'linux-firmware-vendor-m4rch': ['firmware.tar.gz'],
        'alsa-ucm-conf-m4rch': ['alsa.tar.gz'],
        'asahi-scripts-m4rch': ['asahi-scripts.tar.gz', 'files.tar.gz'],
        'mesa-flatpak-m4rch': ['flatpak-extensions.tar.gz'],
        'steam-m4rch': ['steam-launcher.deb', 'steam', 'steam-native4k-launch-loop.sh', 'userpages.c', 'userpages-prctl.h'],
        'mbpfan-m4rch': ['mbpfan-source.tar.gz', 'macsmc.patch', 'smooth-curve.patch', 'mbpfan.service', 'mbpfan.conf'],
        'vesktop-m4rch': ['electron45.zip', 'vesktop-app.tar.gz'],
    }
    for name, files in sources.items():
        path = recipes/name/'PKGBUILD'
        with path.open('a') as stream:
            stream.write('\nsha256sums=(' + ' '.join(repr(sha(path.parent/f)) for f in files) + ')\n')
    database = OUT/'native-pacman-local'
    if database.exists():
        shutil.rmtree(database)
    shutil.copytree(target/'var/lib/pacman/local', database, symlinks=True)
    print('Prepared ordinary makepkg directories in', recipes)


if __name__ == '__main__':
    main()
