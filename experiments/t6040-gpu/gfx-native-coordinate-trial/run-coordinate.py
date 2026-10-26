#!/usr/bin/env python3
"""Typed retained commands for the separate paired coordination candidate."""
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
BASE = HERE.parent / 'gfx-poweroff-trial/run-poweroff.py'
BASE_SHA = '1cc38f25f0c7615ffdd2886ba92d8ab76113a4039508639d46bd8ed8bf38b2b7'


def runner_source():
    raw = BASE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError('Frozen resident power-off runner changed')
    old = 'from gfx_poweroff_contract import validate_receipt as validate_poweroff_receipt'
    source = raw.decode()
    if source.count(old) != 1:
        raise ValueError('Resident contract import changed')
    return source.replace(old,
        'from gfx_coordinate_contract import validate_receipt as validate_poweroff_receipt', 1)


exec(compile(runner_source(), str(BASE), 'exec'), globals())
