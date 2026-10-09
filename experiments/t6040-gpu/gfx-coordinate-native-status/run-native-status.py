#!/usr/bin/env python3
"""Typed native STATUS execution owner operations; no load/free/reboot."""
import copy
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
BASE = BASE_KIT / 'gfx-coordinate-execution/run-execution.py'
BASE_SHA = 'bc3daf41e4fcac881ce20feb98cedc5482c33525a083204f4e266096b9595cfc'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE_KIT))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Native STATUS resident insertion point changed: ' + old[:90])
    return source.replace(old, new, 1)


def base_runner():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Frozen conditional execution resident runner changed')
    return runpy.run_path(str(BASE))


def execution_admission(name, receipt, state):
    from gfx_native_status_contract import FAMILY_KEY, validate_receipt
    from gfx_execution_contract import CONTRACT as EXECUTION_CONTRACT
    require(validate_receipt(receipt), 'Distinct native STATUS execution scope missing')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_coordinated_execution_scope'] = EXECUTION_CONTRACT
    # Only reuse common execution admission on a local view. The canonical
    # native-status receipt remains distinct and is refused by old wrappers.
    return base_runner()['execution_admission'](name, view, state)


def runner_source():
    source = base_runner()['runner_source']()
    return replace_once(source,
        'from gfx_execution_contract import validate_receipt as validate_gfx_reset_receipt',
        'from gfx_native_status_contract import validate_receipt as validate_gfx_reset_receipt')


exec(compile(runner_source(), str(BASE), 'exec'), globals())
