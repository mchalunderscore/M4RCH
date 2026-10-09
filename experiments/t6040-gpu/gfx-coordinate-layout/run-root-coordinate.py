#!/usr/bin/env python3
"""Unchanged frozen cold flow with the exact inspected current OF layout."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-native-coordinate-trial/run-root-coordinate.py'
sys.path.insert(0, str(HERE))


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != '70374782e554472e2d949b2cb0fe7ffe35e8cac5a8a159e4cf7cfc3daba18292':
        raise ValueError('Frozen cold coordinator changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    for old, new in [
        ('from gfx_coordinate_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup',
         'from gfx_layout_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup'),
        ('from gfx_coordinate_contract import qualify_startup_retention',
         'from gfx_layout_contract import qualify_startup_retention')]:
        if source.count(old) != 1:
            raise ValueError('Fresh layout cold insertion changed')
        source = source.replace(old, new, 1)
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
