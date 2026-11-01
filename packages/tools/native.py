#!/usr/bin/env python3
"""Prepare or build a maintained package on native Arch Linux ARM.

The boot packages repackage locally retained artifacts; the retained inputs have been booted in a qualification trial. This is not a kernel or bootloader source build. No command installs a package.

Aurora's ALARM scripts/build-package supplies the native makepkg pattern:
https://github.com/aurora-silicon/alarm-aurora/blob/main/scripts/build-package
Our preparation step is local because the three J614s boot packages carry
board-specific, prebuilt inputs. Aurora ALARM #65 merged this Mesa source pin;
ALARM #61, covering kernel configuration, remained open when reviewed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'cache/installed-20261031'
PROMOTED_CACHE = ROOT / 'cache/touchid-promotion/inputs'
SD_PROMOTED_UBOOT = ROOT / 'cache/jack-promotion/inputs/u-boot-nodtb.bin'
LINUX_PROMOTED_CACHE = ROOT / 'cache/aurora1-promotion/linux-package'
RECIPES = ('linux-m4rch', 'm1n1-m4rch', 'u-boot-m4rch', 'mesa-m4rch')
LINUX_PATCHES = ('upstream-integration.patch', 'mtp-handoff.patch', 'touchid.patch', 'jack.patch')
LINUX_SOURCES = (
    'Image', 'modules.tar.gz', 'linux-m4rch.preset', 'mkinitcpio-m4rch.conf',
    'm4rch-j614s.conf', 'update-m1n1', '50-m4rch.cfg', 'apple-j614s.dtb',
    'kernel.config', 'upstream-integration.patch', 'mtp-handoff.patch', 'touchid.patch', 'jack.patch',
    'source-stack.md', 't6040-j614s.dts', 'GPL-2.0',
)
M1_SOURCES = ('m1n1.bin', 'upstream-integration.patch', 'source-stack.md', 'LICENSE', 'licenses.tar.gz')
UBOOT_SOURCES = ('u-boot-nodtb.bin', 'behaviour.patch', 'reservation.patch', 'sd-handoff.patch', 'source-stack.md', 'uboot.config', 'COPYING')
PINNED_INPUTS = {
    'linux-package/Image': '1ef76fe0a222fb9caa2c03efc63986a7c1c0209158519b9e6a793be92c78b071',
    'linux-package/modules.tar.gz': '10e02c338089df27008f9420e1a95f984b64c0ebf9354bbc321e2f3e79b38d5e',
    'linux-package/apple-j614s.dtb': 'e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8',
    'linux-package/kernel.config': '80d5c60810efbd76d60e419e12c10465dd7dc491e381bbf8c644c921d5b6c16e',
    'm1n1.bin': 'fe9571af510cec542852e88a21928be29a855c66b2937fc3938a6cdedb3fc501',
    'u-boot-nodtb.bin': 'b25192d5f2f4c07f49ee0cc6f15d2c9ec5199cf201cc608c1a651c249ba0b018',
}


def assemble_patch(project: str, name: str, destination: Path) -> None:
    """Reconstruct the exact installed-source record from its ordered parts."""
    source = ROOT / 'packages' / project / 'promoted-source'
    provenance = source / 'provenance' / (name + '.gz')
    if provenance.exists():
        content = gzip.decompress(provenance.read_bytes())
        checksum = source / 'provenance' / (name.removesuffix('.patch') + '.sha256')
    else:
        directory = source / 'patches' / name.removesuffix('.patch')
        parts = directory.joinpath('series').read_text().splitlines()
        if not parts or any(Path(part).name != part for part in parts):
            raise ValueError(f'Invalid patch series: {directory}')
        content = b''.join(directory.joinpath(part).read_bytes() for part in parts)
        checksum = directory / 'original.sha256'
    if hashlib.sha256(content).hexdigest() != checksum.read_text().split()[0]:
        raise ValueError(f'Source record does not reproduce {name}: {source}')
    destination.write_bytes(content)


def digest(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify(name: str) -> Path:
    if name.startswith('linux-package/'):
        path = LINUX_PROMOTED_CACHE / name.removeprefix('linux-package/')
    elif name == 'u-boot-nodtb.bin':
        path = SD_PROMOTED_UBOOT
    else:
        path = (CACHE if name == 'm1n1.bin' else PROMOTED_CACHE) / name
    if not path.is_file():
        raise ValueError(f'missing required retained input: {path}')
    if digest(path) != PINNED_INPUTS[name]:
        raise ValueError(f'retained input does not match its booted digest: {path}')
    return path


def copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ValueError(f'missing required input: {source}')
    shutil.copy2(source, target)


def verify_recipe_sources(work: Path, expected: tuple[str, ...]) -> None:
    """Do not silently associate generated checksums with changed source order."""
    result = subprocess.run(['makepkg', '--printsrcinfo'], cwd=work, check=True,
                            text=True, stdout=subprocess.PIPE)
    actual = tuple(line.split(' = ', 1)[1] for line in result.stdout.splitlines()
                   if line.strip().startswith('source = '))
    if actual != expected:
        raise ValueError(f'{work / "PKGBUILD"}: source list differs from the native preparer; '
                         'update and review the preparer before building')


def prepare_boot(name: str, work: Path) -> None:
    package = ROOT / 'packages' / name
    source_record = package / 'promoted-source'
    if name == 'linux-m4rch':
        for filename in ('Image', 'modules.tar.gz', 'apple-j614s.dtb', 'kernel.config'):
            copy(verify('linux-package/' + filename), work / filename)
        if digest(source_record / 'upstream-integration.config') != PINNED_INPUTS['linux-package/kernel.config']:
            raise ValueError('recorded kernel config does not match the booted input')
        for filename in ('mkinitcpio-m4rch.conf', 'm4rch-j614s.conf',
                         'update-m1n1', '50-m4rch.cfg'):
            copy(package / 'promoted-inputs' / filename, work / filename)
        for filename in ('linux-m4rch.preset', 'GPL-2.0'):
            copy(package / filename, work / filename)
        for filename in ('source-stack.md', 't6040-j614s.dts'):
            copy(source_record / filename, work / filename)
        for filename in LINUX_PATCHES:
            assemble_patch(name, filename, work / filename)
        sources = LINUX_SOURCES
    elif name == 'm1n1-m4rch':
        copy(verify('m1n1.bin'), work / 'm1n1.bin')
        copy(source_record / 'source-stack.md', work / 'source-stack.md')
        copy(package / 'LICENSE', work / 'LICENSE')
        with tarfile.open(work / 'licenses.tar.gz', 'w:gz') as archive:
            archive.add(package / 'licenses', arcname='licenses')
        assemble_patch(name, 'upstream-integration.patch', work / 'upstream-integration.patch')
        sources = M1_SOURCES
    else:
        copy(verify('u-boot-nodtb.bin'), work / 'u-boot-nodtb.bin')
        for filename in ('source-stack.md', 'uboot.config'):
            copy(source_record / filename, work / filename)
        assemble_patch(name, 'behaviour.patch', work / 'behaviour.patch')
        assemble_patch(name, 'reservation.patch', work / 'reservation.patch')
        assemble_patch(name, 'sd-handoff.patch', work / 'sd-handoff.patch')
        copying = package / 'COPYING'
        if digest(copying) != '8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643':
            raise ValueError('U-Boot COPYING does not match the pinned upstream license')
        copy(copying, work / 'COPYING')
        sources = UBOOT_SOURCES
    verify_recipe_sources(work, sources)
    sums = ' '.join(repr(digest(work / filename)) for filename in sources)
    with (work / 'PKGBUILD').open('a') as recipe:
        recipe.write(f'\nsha256sums=({sums})\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'build'), help='prepare inputs or build a package')
    parser.add_argument('package', choices=RECIPES, help='package to prepare or build')
    parser.add_argument('--workdir', type=Path, default=ROOT / 'out/native',
                        help='parent for new per-build directories (default: out/native)')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('native Linux AArch64 is required')
    if os.geteuid() == 0:
        parser.error('run as an ordinary user; makepkg must not run as root')
    if not shutil.which('makepkg'):
        parser.error('makepkg is required; install the Arch base-devel tools')

    args.workdir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.package + '-', dir=args.workdir))
    print(f'Working directory: {work}', flush=True)
    try:
        copy(ROOT / 'packages' / args.package / 'PKGBUILD', work / 'PKGBUILD')
        if args.package != 'mesa-m4rch':
            prepare_boot(args.package, work)
            print('Prepared from retained binary inputs; this does not rebuild their sources.', flush=True)
        else:
            print('Mesa source is downloaded and verified by makepkg during build.', flush=True)
        if args.action == 'build':
            # A fresh directory avoids overwriting an earlier build. Never use
            # --syncdeps: dependencies or system packages are not installed here.
            env = os.environ.copy()
            env.update(PKGDEST=str(work.resolve()), SRCDEST=str(work.resolve()),
                       BUILDDIR=str((work / 'build').resolve()))
            subprocess.run(['makepkg', '--noconfirm'], cwd=work, env=env, check=True)
            archives = subprocess.check_output(['makepkg', '--packagelist'], cwd=work, env=env, text=True)
            for name in archives.splitlines():
                path = Path(name)
                if not path.is_file():
                    raise ValueError(f'makepkg did not produce its expected package: {path}')
                print(f'Package: {path}', flush=True)
            print('Nothing was installed.', flush=True)
        else:
            print(f'Prepared recipe: {work / "PKGBUILD"}', flush=True)
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Cannot {args.action} {args.package}: {error}', file=sys.stderr)
        print(f'Partial files, if any, are retained at {work}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
