#!/usr/bin/env python3
"""Separate native STATUS predicate + conditional retained draw; no reboot."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-coordinate-execution/run-root-execution.py'
BASE_SHA = 'c4bbdd7ba790031cfe499f031fb6a9781b4f19e88b5bb7473881b6f449f724e3'
sys.path.insert(0, str(HERE))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Native STATUS cold insertion point changed: ' + old[:90])
    return source.replace(old, new, 1)


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Frozen conditional execution cold runner changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    source = replace_once(source,
        'from gfx_execution_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup',
        'from gfx_native_status_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup')
    source = replace_once(source, 'from gfx_execution_contract import qualify_startup_retention',
                          'from gfx_native_status_contract import qualify_startup_retention')
    source = replace_once(source, "parent/'run-execution.py'", "parent/'run-native-status.py'")
    source = replace_once(source, '    qualify_linux_dt()\n',
                          '    linux_dt_resource_layout = qualify_linux_dt()\n')
    source = replace_once(source, "report = {'boot_id':boot, 'adt_sha256':sha(raw)",
        "report = {'boot_id':boot, 'linux_dt_resource_layout':linux_dt_resource_layout, 'adt_sha256':sha(raw)")
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
