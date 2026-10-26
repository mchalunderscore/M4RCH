#!/usr/bin/env python3
"""Apply the reviewed, pinned upstream PR diffs to the native-working port."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

KIT=Path(__file__).resolve().parent
PINS={429:'90c0d00eb53799ed927526d90a4425ec07a9baa6',
      427:'bec833e0bc581f74744265f0613832e8291db0cc',
      433:'986ec63833586a1451575a4fb05b3d2b95679a53'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--output',type=Path,default=KIT.parents[1]/'out/aurora-dcp')
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args(); records=[]
    for n,head in PINS.items():
        metadata=json.loads((KIT/f'upstream/pr-{n}.json').read_text())
        assert metadata['head']==head and metadata['pr']==n
        path=KIT/f'upstream/pr-{n}.patch'
        command=['git','apply','--check']+(['--reverse'] if args.verify else [])+[str(path)]
        subprocess.run(command,cwd=args.root,check=True)
        records.append({**metadata,'patch_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if not args.verify:
        for n in PINS:
            subprocess.run(['git','apply',str(KIT/f'upstream/pr-{n}.patch')],cwd=args.root,check=True)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'upstream-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Verified pinned upstream patches' if args.verify else 'Applied pinned upstream patches')

if __name__=='__main__': main()
