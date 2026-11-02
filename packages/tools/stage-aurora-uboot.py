#!/usr/bin/env python3
"""Stage an experimental U-Boot package from a verified Aurora recipe.

These baselines exercise the integration; this is not a release or an
instruction to install it. No system paths or existing outputs are modified.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
ALARM_COMMIT = '149e3a0c406efe70d79aa3db55c3ff59bf42c0fa'
RECIPE_HASH = 'fb8f38a4503f7b84c2489e4e64732a3a47e5139bb675049859f1fa182db52b6d'
SOURCE_COMMIT = '01f255b636737bc783b581b04584d1224ab06cf4'
SOURCE_HASH = 'b1656feb1edcb418d4bf2f83aeb750be94fcd824a20f40259b90f75c67f5300a'
SERIES = ('behaviour', 'reservation', 'sd-handoff')
BASELINES = {
    'historical': (ALARM_COMMIT, RECIPE_HASH, SOURCE_COMMIT, SOURCE_HASH),
    'proposed': (
        '2d2555ecc578d6f40fa738c9c5b4e639f116a3cf',
        'b4b5ee01bcb3d36691ed4a5d0f07caba1935a15589f95db40be7f7d8c73ab384',
        'd30213eadcaa886f4206d7661b61bc6cf7837828',
        '67335b3fb832ab68bbde95e9f9b3808ace0fff96438786f34227dd5cdc9fe495',
    ),
}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'Aurora recipe no longer has the expected input: {old!r}')
    return text.replace(old, new, 1)


def stage(recipe: Path, archive: Path, output: Path, baseline: str) -> None:
    alarm_commit, recipe_hash, source_commit, source_hash = BASELINES[baseline]
    if output.exists():
        raise ValueError(f'output already exists: {output}')
    if digest(recipe) != recipe_hash or digest(archive) != source_hash:
        raise ValueError('Aurora recipe or source archive does not match the pinned digest')
    text = recipe.read_text()
    patches = []
    patch_root = ROOT / 'packages/u-boot-m4rch/promoted-source/patches'
    for series in SERIES:
        folder = patch_root / series
        names = folder.joinpath('series').read_text().splitlines()
        if not names or any(Path(name).name != name or not name.endswith('.patch') for name in names):
            raise ValueError(f'invalid series: {folder}')
        files = [folder / name for name in names]
        content = b''.join(path.read_bytes() for path in files)
        expected = folder.joinpath('original.sha256').read_text().split()[0]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f'patch series does not match its recorded digest: {series}')
        for path in files:
            content = path.read_bytes()
            if baseline == 'proposed' and series == 'behaviour' and path.name == '06-j614s-retained-input.patch':
                # Upstream PR 28 changed the FIFO success message to debug().
                # The rejected hunk only renamed log messages, so retain the
                # upstream logging rather than undo its quiet-boot behavior.
                before, marker, rest = content.partition(b'@@ -1568,12 +1570,12 @@\n')
                discarded, next_marker, after = rest.partition(b'@@ -1616,15 +1618,17 @@\n')
                if not marker or not next_marker or b'input discovery FIFO' not in discarded:
                    raise ValueError('unexpected retained-input logging hunk')
                content = before + next_marker + after
            patches.append((f'{series}-{path.name}', content))

    archive_name = f'u-boot-{source_commit}.tar.gz'
    sources = ' '.join([f"'{archive_name}'"] + [f"'{name}'" for name, _ in patches])
    checksums = ' '.join([f"'{source_hash}'"] + [f"'{hashlib.sha256(content).hexdigest()}'" for _, content in patches])
    text = replace_once(text, 'pkgrel=1\n', 'pkgrel=1.1\n')
    text = replace_once(text, 'source=("u-boot::git+$url.git#commit=$_commit")\nsha256sums=(\'SKIP\')',
                        f'source=({sources})\nsha256sums=({checksums})')
    commands = '\n'.join(f'  patch --batch --forward --fuzz=0 -Np1 -i "$srcdir/{name}"' for name, _ in patches)
    prepare = (f'prepare() {{\n  mv "u-boot-{source_commit}" u-boot\n'
               f'  cd u-boot\n{commands}\n}}\n')
    text = replace_once(text, 'build() {\n', prepare + 'build() {\n')

    output.mkdir(parents=True)
    try:
        shutil.copyfile(archive, output / archive_name)
        for name, content in patches:
            (output / name).write_bytes(content)
        (output / 'PKGBUILD').write_text(text)
        (output / 'PROVENANCE').write_text(
            f'Aurora ALARM commit: {alarm_commit}\nAurora PKGBUILD SHA-256: {recipe_hash}\n'
            f'U-Boot commit: {source_commit}\nU-Boot archive SHA-256: {source_hash}\n'
            f'Experimental {baseline} baseline; not qualified for installation.\n'
            + ''.join(f'{name} SHA-256: {hashlib.sha256(content).hexdigest()}\n' for name, content in patches))
    except Exception:
        shutil.rmtree(output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True, help='pinned Aurora uboot-aurora/PKGBUILD')
    parser.add_argument('--source-archive', type=Path, required=True, help='pinned U-Boot source tarball')
    parser.add_argument('--output', type=Path, required=True, help='new staging directory')
    parser.add_argument('--baseline', choices=BASELINES, default='proposed')
    args = parser.parse_args()
    try:
        stage(args.recipe, args.source_archive, args.output, args.baseline)
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(f'Staged experimental package in {args.output}; nothing installed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
