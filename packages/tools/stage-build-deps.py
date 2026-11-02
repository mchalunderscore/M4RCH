#!/usr/bin/env python3
"""Fetch and unpack signed pacman build dependencies into a new directory.

The local sync database selects versions and holds hashes and signatures.
This is a build environment, not a package installation or dependency solver
for a clean system: dependencies already installed on the host remain shared.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.parse
import urllib.request


def read_desc(archive: tarfile.TarFile, name: str) -> dict[str, str]:
    lines = archive.extractfile(name).read().decode().splitlines()
    return {line[1:-1]: lines[i + 1] for i, line in enumerate(lines[:-1])
            if line.startswith('%') and line.endswith('%') and lines[i + 1]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--download-only', action='store_true', help='verify packages without extracting them')
    parser.add_argument('--mirror', help='fetch all selected packages from this repository base URL')
    parser.add_argument('--repository', help='select the named repository packages without resolving dependencies')
    parser.add_argument('packages', nargs='+')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists')
    if any(not all(c.isalnum() or c in '@._+-' for c in name) for name in args.packages):
        parser.error('package names contain unsupported characters')
    if args.repository:
        if not args.mirror or not all(c.isalnum() or c in '._-' for c in args.repository):
            parser.error('--repository requires a safe repository name and --mirror')
        by_name = {}
        with tarfile.open(f'/var/lib/pacman/sync/{args.repository}.db') as db:
            for member in db:
                if member.name.endswith('/desc'):
                    desc = read_desc(db, member.name)
                    by_name[desc.get('NAME')] = desc
        if any(name not in by_name for name in args.packages):
            parser.error('a requested package is missing from the repository database')
        selected = [[args.repository, name, by_name[name]['VERSION'], args.mirror]
                    for name in args.packages]
    else:
        result = subprocess.run(['pacman', '-Sp', '--print-format', '%r\t%n\t%v\t%l', *args.packages],
                                check=True, text=True, stdout=subprocess.PIPE)
        selected = [line.split('\t') for line in result.stdout.splitlines()]
    if not selected or any(len(row) != 4 for row in selected):
        raise SystemExit('unexpected pacman dependency output')
    by_repo = {}
    for repo, _, _, _ in selected:
        if repo not in by_repo:
            entries = {}
            with tarfile.open(f'/var/lib/pacman/sync/{repo}.db') as db:
                for member in db:
                    if member.name.endswith('/desc'):
                        desc = read_desc(db, member.name)
                        entries[(desc.get('NAME'), desc.get('VERSION'))] = desc
            by_repo[repo] = entries
    args.output.mkdir(parents=True)
    packages = args.output / 'packages'
    root = args.output / 'root'
    packages.mkdir()
    if not args.download_only:
        root.mkdir()
    records = []
    try:
        for repo, name, version, url in selected:
            desc = by_repo[repo].get((name, version))
            if not desc or any(k not in desc for k in ('FILENAME', 'SHA256SUM', 'PGPSIG')):
                raise ValueError(f'missing signed sync metadata for {name} {version}')
            filename = desc['FILENAME']
            if Path(filename).name != filename:
                raise ValueError(f'unsafe filename for {name}')
            target = packages / filename
            print(f'Fetching {name} {version}', flush=True)
            if args.mirror:
                source = args.mirror.rstrip('/') + '/' + urllib.parse.quote(filename, safe='')
                with urllib.request.urlopen(source, timeout=90) as response, target.open('wb') as out:
                    shutil.copyfileobj(response, out)
            elif url.startswith('file://'):
                shutil.copyfile(urllib.parse.unquote(urllib.parse.urlparse(url).path), target)
            else:
                # Preserve the configured mirror, escaping the epoch in filenames.
                base = url.rsplit('/', 1)[0]
                source = base + '/' + urllib.parse.quote(filename, safe='')
                with urllib.request.urlopen(source, timeout=90) as response, target.open('wb') as out:
                    shutil.copyfileobj(response, out)
            with target.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != desc['SHA256SUM']:
                raise ValueError(f'package digest mismatch: {name}')
            signature = packages / (filename + '.sig')
            signature.write_bytes(base64.b64decode(desc['PGPSIG'], validate=True))
            subprocess.run(['pacman-key', '--verify', str(signature), str(target)], check=True)
            if not args.download_only:
                subprocess.run(['bsdtar', '-xf', str(target), '-C', str(root), '--no-same-owner'], check=True)
            records.append({'repo': repo, 'name': name, 'version': version, 'file': filename, 'sha256': actual})
        # Arch's rustup proxies point to /usr/bin/rustup. Keep them inside the
        # extracted environment instead of resolving to the host's /usr.
        bin_dir = root / 'usr/bin'
        if bin_dir.is_dir():
            for path in bin_dir.iterdir():
                if path.is_symlink() and str(path.readlink()) == '/usr/bin/rustup':
                    path.unlink()
                    path.symlink_to('rustup')
        (args.output / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    except Exception:
        # Leave incomplete inputs for inspection; do not silently reuse them.
        print(f'Incomplete environment retained at {args.output}', flush=True)
        raise
    action = f'verified and extracted to {root}' if not args.download_only else f'verified at {packages}'
    print(f'Package files {action}; nothing installed.')


if __name__ == '__main__':
    main()
