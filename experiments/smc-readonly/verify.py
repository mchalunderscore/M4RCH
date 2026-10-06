#!/usr/bin/env python3
"""Refuse loading the diagnostic on a different running kernel build."""
import hashlib,json,platform,struct,subprocess
from pathlib import Path


def build_id(notes):
    offset=0
    while offset+12<=len(notes):
        namesz,descsz,kind=struct.unpack_from('<III',notes,offset);offset+=12
        name=notes[offset:offset+namesz];offset+=(namesz+3)&~3
        desc=notes[offset:offset+descsz];offset+=(descsz+3)&~3
        if name==b'GNU\0' and kind==3 and len(desc)==descsz:return desc.hex()
    raise ValueError('Running kernel GNU build ID absent')


def main():
    kit=Path(__file__).resolve().parent
    subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=kit,check=True)
    receipt=json.loads((kit/'build.json').read_text())
    if platform.release()!=receipt['kernel_release']:
        raise ValueError('Different running kernel release')
    if build_id(Path('/sys/kernel/notes').read_bytes())not in receipt['kernel_build_ids']:
        raise ValueError('Different running kernel build ID; do not force-load')
    provenance=json.loads(Path('/usr/share/doc/linux-m4rch/build-provenance.json').read_text())
    if provenance['modules_sha256']!=receipt['modules_sha256']:
        raise ValueError('Different installed module provenance')
    print('Exact running kernel and installed module provenance accepted.')


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:raise SystemExit(str(exc))
