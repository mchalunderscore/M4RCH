#!/usr/bin/env python3
"""Prepare Aurora vendor archives with this Mac's working Mriya firmware."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'installer'))
from asahi_firmware.core import FWFile, FWPackage  # noqa: E402

PREFIX = 'brcmfmac4388c2-pcie.apple,mriya'
SUFFIXES = ('.bin', '.clm_blob', '.sig', '.txcap_blob', '-WLMT-a.txt', '-WLMT-u.txt')


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('', '.', '..') for p in path.parts):
        raise ValueError(f'invalid archive path: {name}')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-root', type=Path, default=Path('/run/aurora-firmware/vendorfw'))
    parser.add_argument('--wifi-dir', type=Path, default=Path('/usr/lib/firmware/brcm'))
    parser.add_argument('--output', type=Path, required=True, help='new private output directory')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists')
    manifest = (args.vendor_root / '.vendorfw.manifest').read_text('ascii').splitlines()
    items = []
    seen = {}
    for line in manifest:
        fields = line.split(' ')
        if len(fields) == 4 and fields[0] == 'FILE' and fields[2] == 'SHA256':
            name, expected = fields[1], fields[3]
        elif len(fields) == 3 and fields[0] == 'LINK' and fields[2] in seen:
            name, expected = fields[1], seen[fields[2]]
        else:
            raise ValueError('unexpected existing vendor manifest')
        path = args.vendor_root.joinpath(*safe_path(name).parts)
        if name in seen or path.is_symlink() or not path.is_file():
            raise ValueError(f'missing or duplicate vendor entry: {name}')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise ValueError(f'vendor entry does not match manifest: {name}')
        seen[name] = digest
        items.append((name, data))
    for suffix in SUFFIXES:
        name = PREFIX + suffix
        path = args.wifi_dir / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f'missing, empty or symlinked Wi-Fi firmware: {name}')
        data = path.read_bytes()
        dest = 'brcm/' + name
        digest = hashlib.sha256(data).hexdigest()
        if dest in seen:
            if seen[dest] != digest:
                raise ValueError(f'existing vendor entry differs: {dest}')
            continue
        seen[dest] = digest
        items.append((dest, data))

    args.output.mkdir(mode=0o700, parents=False)
    try:
        package = FWPackage(str(args.output))
        for name, data in items:
            package.add_file(name, FWFile(name, data))
        package.close()
        with tarfile.open(args.output / 'firmware.tar') as archive:
            if set(archive.getnames()) != set(seen):
                raise ValueError('TAR entry list mismatch')
            for name, expected in seen.items():
                member = archive.extractfile(name)
                if member is None or hashlib.sha256(member.read()).hexdigest() != expected:
                    raise ValueError(f'TAR verification failed: {name}')
        # Verify the real generated CPIO by extracting it with the tool Aurora uses.
        with tempfile.TemporaryDirectory(prefix='m4rch-vendor-check-') as temp:
            with (args.output / 'firmware.cpio').open('rb') as source:
                subprocess.run(['cpio', '--quiet', '--extract', '--no-absolute-filenames'],
                               stdin=source, cwd=temp, check=True)
            extracted = Path(temp) / 'vendorfw'
            for name, expected in seen.items():
                path = extracted.joinpath(*safe_path(name).parts)
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError(f'CPIO verification failed: {name}')
            if (extracted / '.vendorfw.manifest').read_bytes() != (args.output / 'manifest.txt').read_bytes():
                raise ValueError('CPIO manifest mismatch')
    except Exception:
        shutil.rmtree(args.output)
        raise
    print(f'Private Aurora vendor archives prepared and verified: {len(seen)} files.')


if __name__ == '__main__':
    main()
