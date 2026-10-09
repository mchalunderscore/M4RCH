#!/usr/bin/env python3
"""Frozen typed no-work operations bound to the inspected fresh-layout scope."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-native-coordinate-trial/run-coordinate.py'
sys.path.insert(0, str(HERE))


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != 'c2a8760c3106cf96777ab463c0324bf8fede2c9029c6fb3f98273efa7c3e8a77':
        raise ValueError('Frozen typed coordinator changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    old = 'from gfx_coordinate_contract import validate_receipt as validate_poweroff_receipt'
    if source.count(old) != 1:
        raise ValueError('Fresh layout typed insertion changed')
    return source.replace(old,
        'from gfx_layout_contract import validate_receipt as validate_poweroff_receipt', 1)


exec(compile(runner_source(), str(BASE), 'exec'), globals())
