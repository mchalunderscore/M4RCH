#!/usr/bin/env python3
"""Stage an unqualified J614s overlay on a pinned Aurora Aura recipe."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'a9cad94edb46fd4baf77c6cb1776b3bb5f1a566f'
ALARM = '2d2555ecc578d6f40fa738c9c5b4e639f116a3cf'
HASHES = {
    'PKGBUILD': '71a01ef213401392cb7c92d0d58de84b7666a9a798f80ea7c01884ac157c8991',
    'archive': '24b7c1a8269d53e4e91fa17080caa09ca5fada1a52e449802645848e2eef3690',
    'build-qualification.json': 'be9ca721c037a0366c97a1525d6a69215ff15d5b190436b596c10f602e3a8674',
    'validate-qualification.py': 'd89f89a68105e4663bdf14bf9d4d70f3fad79538a4c566e8fae73c0b40a9be26',
}
PATCHES = [
 ('01-dapf-corrected.patch', '4ae669015072c8fa96516bb9d565738245fd4affca9578bf579fe25a4c3fe7c6'),
 ('02-flat-root-address-translation.patch', '4ec0b400a54dc9dd5d93741d787abe26cfff25e97ceb98530c1d2e173afb5bfe'),
 ('03-inherited-display-handoff.patch', '34959946df3e908784a1811ef1f763b8c4b019c1fd3df776f843def58c386667'),
 ('04-prune-cpu-cooling-references.patch', 'ceef3ad4a2432c7972ae73c4acb628d4c2bc5a15e9f4eb0d30b3dc431d2510a1'),
 ('05-sd-power.patch', '4db0a801028fd1952be5884ceeb0a080276febd4a005d8ab907b8db2a449c5e9'),
 ('08-mcc-board-admission.patch', '88075d40002bce6c0a8c6c69686293ebe84c85f678fa45af6be448364fcef6ec'),
]

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'unexpected recipe content: {old!r}')
    return text.replace(old, new, 1)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe-dir', type=Path, required=True)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    try:
        if a.output.exists():
            raise ValueError(f'output already exists: {a.output}')
        inputs = {n: a.recipe_dir / n for n in HASHES if n != 'archive'}
        inputs['archive'] = a.source_archive
        for name, path in inputs.items():
            if digest(path) != HASHES[name]:
                raise ValueError(f'unexpected digest: {path}')
        patchdir = ROOT / 'packages/m1n1-m4rch/promoted-source/patches/upstream-integration'
        patches = []
        for name, expected in PATCHES:
            path = ROOT / 'packages/aura-j614s' / name if name.startswith(('01-', '05-')) else patchdir / name
            if digest(path) != expected:
                raise ValueError(f'unexpected patch: {path}')
            patches.append(path)
        text = inputs['PKGBUILD'].read_text()
        text = replace(text, 'pkgrel=2\n', 'pkgrel=2.4\n')
        old = 'source=("aura::git+$url.git#commit=$_commit" build-qualification.json validate-qualification.py)\nsha256sums=(\'SKIP\' \'be9ca721c037a0366c97a1525d6a69215ff15d5b190436b596c10f602e3a8674\' \'d89f89a68105e4663bdf14bf9d4d70f3fad79538a4c566e8fae73c0b40a9be26\')'
        archive = f'aura-{COMMIT}.tar.gz'
        names = [archive, 'build-qualification.json', 'validate-qualification.py'] + [p.name for p in patches]
        hashes = [HASHES['archive'], HASHES['build-qualification.json'], HASHES['validate-qualification.py']] + [x[1] for x in PATCHES]
        text = replace(text, old, 'source=(' + ' '.join(f"'{n}'" for n in names) + ')\nsha256sums=(' + ' '.join(f"'{h}'" for h in hashes) + ')')
        oldprepare = '  rustup toolchain install 1.99.0 --profile minimal --target aarch64-unknown-none-softfloat\n  [[ $(git -C aura rev-parse HEAD) == "$_commit" ]]'
        commands = '\n'.join(f'  patch --batch --forward --fuzz=0 -Np1 -i "$srcdir/{p.name}"' for p in patches)
        text = replace(text, oldprepare, f'  rustup run 1.99.0 rustc --version\n  mv "aura-{COMMIT}" aura\n  cd aura\n{commands}')
        text = replace(text, '  install -Dm644 "$srcdir/build-qualification.json" "$pkgdir/usr/share/doc/aura/build-qualification.json"', '  install -Dm644 "$srcdir/build-qualification.json" "$pkgdir/usr/share/doc/aura/build-qualification.json"\n  install -Dm644 "$startdir/M4RCH-PROVENANCE" "$pkgdir/usr/share/doc/aura/M4RCH-PROVENANCE"')
        a.output.mkdir(parents=True)
        try:
            shutil.copyfile(a.source_archive, a.output / archive)
            for name in ('build-qualification.json', 'validate-qualification.py'):
                shutil.copyfile(inputs[name], a.output / name)
            for p in patches:
                shutil.copyfile(p, a.output / p.name)
            (a.output / 'PKGBUILD').write_text(text)
            (a.output / 'M4RCH-PROVENANCE').write_text(
                f'Experimental J614s overlay; not hardware qualified.\nAurora ALARM: {ALARM}\n'
                f'Aura base: {COMMIT}\nArchive SHA-256: {HASHES["archive"]}\n' +
                ''.join(f'{name} SHA-256: {h}\n' for name, h in PATCHES))
        except Exception:
            shutil.rmtree(a.output)
            raise
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(f'Staged unqualified Aurora Aura overlay at {a.output}; nothing installed.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
