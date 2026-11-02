#!/usr/bin/env python3
"""Stage a coordinated, unqualified Aurora Mesa package family."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'c208afc352e9d4c10ee71c883a369a9079dd7d84'
ARCHIVE_SHA = 'a8ca816b201673a9e2cf5aeafefdfa1bdffe2e14cd125b3bffd1cfe5040a3b0b'
PATCH_SHA = '2d2d0abab03e34e93133770bfde6680c098b6bd9d9e37c67cc34baf936c9cfa2'
INPUTS = {
 'mesa-aurora/PKGBUILD': 'f34893b2e823cda2c998c6be7d08c1ff81fa06daae50b2da38da910b75053d6c',
 'mesa-aurora-fex-guest/PKGBUILD': 'f476db4417006f514616c19b8a1119ee95549d301f9a15d06a2596e2374b7aaa',
 'mesa-aurora-fex-guest/60-aurora-fex-mesa-upgrade.hook': 'acd1e005a05bd8e229300a846863b6fcb3c29f389d66d9c8b903cb5d70913503',
 'mesa-aurora-fex-guest/aurora-fex-mesa.service': '20eef88ebcb0bf5d09afdcb28696c588e516ab69775e343f3cd75b9d57cdd907',
 'mesa-aurora-fex-guest/mesa-aurora-fex-guest.install': 'f5de772228f743d9362cfb460295115d31bb9383fe34f4b81b78426396bf24f8',
 'aurora-flatpak-gl/PKGBUILD': '5db72941055263305681867e7023517ac9c131538ef9bbea43ad0276423b0815',
 'aurora-flatpak-gl/60-aurora-flatpak-gl.conf': '32cf9c71aef5f13664369f299a2872835302410fd1a03ddca2a13a87879357b3',
 'aurora-flatpak-gl/LICENSE': '811207d92b81da5b5e97cdfa52542769d8783325da5b422262ccecfa2d23c5a9',
 'aurora-flatpak-gl/aurora-flatpak-gl': '52c6ffed0efa0890d6d23f8cc0030a5228b0ea86e5a540ce4131d31a54f4db05',
 'aurora-flatpak-gl/aurora-flatpak-gl.install': 'da803d1e81ee40f34c4c130a6c12f103814ae48e4ed9c45a6bde13652ae16429',
 'aurora-flatpak-gl/aurora-flatpak-gl.sh': 'e193fb70d360d81729615a18e9eb08dd715839f78767d82fde218727b1ca49f2',
 'aurora-flatpak-gl/build-extension.sh': 'fbf43ba7469f68af08def39f87881a2e717424c317d5c7130c13c5556a969b0b',
 'aurora-flatpak-gl/org.freedesktop.Platform.GL.aurora.yml.in': 'b88c55dc31d08a55e5a94a8122457c037b8ee1fc901163851fcff517f552ed29',
 'aurora-flatpak-gl/validate-repo.sh': 'da14ca864bda4cb8f1e7b10f8f2b08527fb5761b89ed848b336a284ea53843c7',
 'aurora-flatpak-gl/validate-repository.py': 'f1134c780eee79487b6b29cc14d3c91ec423813289e2d9faa1f131ab1ef5cc53',
}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'unexpected Aurora recipe content: {old!r}')
    return text.replace(old, new, 1)


def stage(recipes: Path, archive: Path, output: Path) -> None:
    patch = ROOT / 'packages/mesa-m4rch/0001-zink-wayland-drawable-lifetime.patch'
    if output.exists():
        raise ValueError('output already exists')
    if digest(archive) != ARCHIVE_SHA or digest(patch) != PATCH_SHA:
        raise ValueError('Mesa archive or local patch digest mismatch')
    for name, expected in INPUTS.items():
        if digest(recipes / name) != expected:
            raise ValueError(f'Aurora recipe input mismatch: {name}')
    output.mkdir(parents=True)
    try:
        for relative in INPUTS:
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipes / relative, target)
        for name in ('mesa-aurora', 'mesa-aurora-fex-guest', 'aurora-flatpak-gl'):
            directory = output / name
            shutil.copy2(patch, directory / 'm4rch-zink.patch')
            if name != 'aurora-flatpak-gl':
                shutil.copy2(archive, directory / f'mesa-{COMMIT}.tar.gz')
            recipe = directory / 'PKGBUILD'
            text = replace_once(recipe.read_text(), 'pkgrel=1\n', 'pkgrel=1.1\n')
            if name == 'mesa-aurora':
                # Fakeroot cannot preserve host ownership in the isolated
                # build namespace. Package files still receive fakeroot's
                # package ownership; preserve every other cp -a attribute.
                text = replace_once(text, 'cp -a "$srcdir/mesa-stage/usr" "$pkgdir/"',
                                    'cp -a --no-preserve=ownership "$srcdir/mesa-stage/usr" "$pkgdir/"')
                text = replace_once(text, 'cp -a "$srcdir"/mesa-stage/usr/share/vulkan/icd.d/*asahi*.json',
                                    'cp -a --no-preserve=ownership "$srcdir"/mesa-stage/usr/share/vulkan/icd.d/*asahi*.json')
                text = replace_once(text, 'source=("mesa::git+$url.git#commit=$_commit")\nsha256sums=(\'SKIP\')',
                    f'source=("mesa-${{_commit}}.tar.gz::https://codeload.github.com/aurora-silicon/mesa/tar.gz/${{_commit}}" m4rch-zink.patch)\nsha256sums=(\'{ARCHIVE_SHA}\' \'{PATCH_SHA}\')')
                prepare = 'prepare() {\n  mv "mesa-$_commit" mesa\n  cd mesa\n  patch --batch --forward --fuzz=0 -Np1 -i "$srcdir/m4rch-zink.patch"\n}\n'
                text = replace_once(text, 'build() {\n', prepare + 'build() {\n')
            elif name == 'mesa-aurora-fex-guest':
                text = replace_once(text, 'cp -a "$srcdir/layer/usr" "$layer/"',
                                    'cp -a --no-preserve=ownership "$srcdir/layer/usr" "$layer/"')
                extra = f"source+=(m4rch-zink.patch)\nsha256sums+=('{PATCH_SHA}')\n"
                prepare = 'prepare() {\n  cd "mesa-$_commit"\n  patch --batch --forward --fuzz=0 -Np1 -i "$srcdir/m4rch-zink.patch"\n}\n'
                text = replace_once(text, 'build() {\n', extra + prepare + 'build() {\n')
            else:
                manifest = directory / 'org.freedesktop.Platform.GL.aurora.yml.in'
                content = replace_once(manifest.read_text(), "        sha256: '@SHA256@'\n",
                    "        sha256: '@SHA256@'\n      - type: patch\n        path: m4rch-zink.patch\n")
                manifest.write_text(content)
                script = directory / 'build-extension.sh'
                content = replace_once(script.read_text(), 'manifest=$work/org.freedesktop.Platform.GL.aurora.yml\n',
                    'manifest=$work/org.freedesktop.Platform.GL.aurora.yml\ncp "$here/m4rch-zink.patch" "$work/m4rch-zink.patch"\n')
                script.write_text(content)
                text = replace_once(text, INPUTS['aurora-flatpak-gl/build-extension.sh'], digest(script))
                text = replace_once(text, INPUTS['aurora-flatpak-gl/org.freedesktop.Platform.GL.aurora.yml.in'], digest(manifest))
                extra = f"source+=(m4rch-zink.patch)\nsha256sums+=('{PATCH_SHA}')\n"
                text = replace_once(text, 'build() {\n', extra + 'build() {\n')
            recipe.write_text(text)
        (output / 'PROVENANCE').write_text(
            f'Aurora ALARM 2d2555ecc578d6f40fa738c9c5b4e639f116a3cf\nMesa {COMMIT}\n'
            f'archive sha256 {ARCHIVE_SHA}\nlocal Zink patch sha256 {PATCH_SHA}\n'
            'Native, guest and Flatpak pkgrel 1.1. Requires qualification.\n')
    except Exception:
        shutil.rmtree(output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipes', type=Path, required=True, help='Aurora ALARM packages directory')
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        stage(args.recipes, args.source_archive, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f'staging refused: {error}\n')
    print(f'Staged experimental Mesa family at {args.output}; nothing installed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
