#!/usr/bin/env python3
"""Stage Aurora UCM with the J614s three-channel microphone profile."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'a270b2e2d705ed521b07d008aac45283c75fb986'
SOURCE_SHA = '7b5cd23b7ee22cd1c69c4d3b090f5140f7f04fb53d3578349101c8e916faf261'
RECIPE_SHA = '6e031ec80e5b1646a2cb98b188d11f093be3d414cd28cabb5a20ad658f4fbeb3'
PROFILE_SHA = '4e91273ea14439ea05fd7b5b83c8fc27054f32fc35f6c9ee6107ca9bd983461e'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'unexpected Aurora recipe: {old!r}')
    return text.replace(old, new, 1)


def stage(recipe: Path, archive: Path, output: Path) -> None:
    profile = ROOT / 'packages/alsa-ucm-conf-aurora-j614s/j614s-hpai.conf'
    if output.exists():
        raise ValueError('output already exists')
    if digest(recipe) != RECIPE_SHA or digest(archive) != SOURCE_SHA or digest(profile) != PROFILE_SHA:
        raise ValueError('recipe, source or profile digest mismatch')
    text = recipe.read_text()
    text = replace_once(text, 'pkgrel=2\n', 'pkgrel=2.1\n')
    text = replace_once(text, 'source=("ucm::git+$url.git#commit=$_commit")\nsha256sums=(\'SKIP\')',
        f'source=("ucm-${{_commit}}.tar.gz::https://codeload.github.com/aurora-silicon/alsa-ucm-conf-asahi/tar.gz/${{_commit}}" j614s-hpai.conf)\nsha256sums=(\'{SOURCE_SHA}\' \'{PROFILE_SHA}\')')
    text = replace_once(text, 'package() {\n', f'prepare() {{\n  mv "alsa-ucm-conf-asahi-{COMMIT}" ucm\n}}\npackage() {{\n')
    text = replace_once(text, 'cp -a ucm/ucm2 "$pkgdir/usr/share/alsa/"',
                        'cp -a --no-preserve=ownership ucm/ucm2 "$pkgdir/usr/share/alsa/"')
    text = replace_once(text, '  install -Dm644 ucm/LICENSE.asahi',
        '  install -Dm644 "$srcdir/j614s-hpai.conf" "$pkgdir/usr/share/alsa/ucm2/conf.d/aop_audio/MacBook Pro J614 High-Power Audio Interface.conf"\n  install -Dm644 ucm/LICENSE.asahi')
    output.mkdir(parents=True)
    try:
        shutil.copy2(archive, output / f'ucm-{COMMIT}.tar.gz')
        shutil.copy2(profile, output / 'j614s-hpai.conf')
        (output / 'PKGBUILD').write_text(text)
        (output / 'PROVENANCE').write_text(
            f'ALARM 2d2555ecc578d6f40fa738c9c5b4e639f116a3cf\nAurora source {COMMIT}\n'
            f'source sha256 {SOURCE_SHA}\nJ614s profile sha256 {PROFILE_SHA}\n'
            'Candidate: no system installation; validate against the real microphone.\n')
    except Exception:
        shutil.rmtree(output)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        stage(args.recipe, args.source_archive, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f'staging refused: {error}\n')
    print(f'Staged Aurora UCM candidate in {args.output}; nothing installed.')


if __name__ == '__main__':
    main()
