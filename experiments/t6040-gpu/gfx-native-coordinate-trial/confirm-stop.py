#!/usr/bin/env python3
"""Known returned STOP EAGAIN confirmation for the exact new candidate only.
Metadata only: never writes sysfs or hardware, retries STOP or admits OFF.
"""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-poweroff-observation/confirm-stop.py'
BASE_SHA = 'ff6aecb9010e81c8bc9474e1913e8a195036d0802f153d0573560a9e745b7b36'
raw = BASE.read_bytes()
if hashlib.sha256(raw).hexdigest() != BASE_SHA:
    raise ValueError('Frozen known-STOP confirmation helper changed')
source = raw.decode()
changes = {
    "KIT = ROOT / 'experiments/t6040-gpu/gfx-poweroff-trial'":
        "KIT = Path(__file__).resolve().parent",
    "str(KIT / 'run-poweroff.py')": "str(KIT / 'run-coordinate.py')",
    '8644ae827a06da50d9793199a7c780305cff85abb9c9e826cde41b967971f471':
        '0afe3eed85958b124be56e7ed4c0f76595bf8271c016c44d47c4903ebe5a669c',
    '4b4914b677c15b55718e6e96f4d6683a0dd295f4337659aff709a8ffef931be0':
        'a7b3f21acfa50fcc35dba6d46f86d575e166d562c4dd0c575e5d58fd7d26b7f0',
}
for old, new in changes.items():
    if source.count(old) != 1:
        raise ValueError('Known-STOP insertion point changed')
    source = source.replace(old, new, 1)
exec(compile(source, str(BASE), 'exec'), globals())
