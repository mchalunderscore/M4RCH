#!/usr/bin/env python3
"""Build the Arch packages in the existing Arch Linux ARM container."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
VM = 'm4rch-arch-packages'


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/Volumes/ARCHROOT'))
    args = parser.parse_args()
    # The current build VM retains the populated compiler/build caches.
    state = json.loads(subprocess.check_output(['container', 'list', '--all', '--format', 'json']))
    vm = next((item for item in state if item.get('id') == VM), None)
    if vm is None:
        raise SystemExit('Prepare the Arch build container first; see packages/README.md.')
    if vm.get('status', {}).get('state') != 'running':
        run('container', 'start', VM)
    run(sys.executable, TOOLS/'prepare.py', '--root', args.root)
    run('container', 'exec', VM, 'bash', '/project/packages/tools/build.sh')
    run('container', 'exec', VM, 'bash', '/project/packages/tools/validate.sh')
    run(sys.executable, TOOLS/'validate-target-abi.py')
    out = ROOT/'out/packages'
    shutil.copy2(ROOT/'packages/install.sh', out/'install.sh')
    shutil.copy2(ROOT/'packages/README.md', out/'README.md')
    files = sorted(out.glob('*.pkg.tar.zst')) + [out/'install.sh']
    files += sorted((out/'dependencies').glob('*.pkg.tar.*'))
    (out/'SHA256SUMS').write_text(''.join(
        hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(out))+'\n'
        for path in files))


if __name__ == '__main__':
    main()
