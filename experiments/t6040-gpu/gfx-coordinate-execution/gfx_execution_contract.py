# SPDX-License-Identifier: GPL-2.0-only
"""Distinct retained execution profile; the frozen no-work trial is unchanged."""
import copy
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(BASE_KIT / 'gfx-native-coordinate-trial'))
from gfx_coordinate_contract import CONTRACT as COORDINATE_CONTRACT
from gfx_coordinate_contract import (qualify_adt, qualify_linux_dt,
    qualify_graph_startup, qualify_startup_retention,
    validate_receipt as validate_coordinate_receipt)
from gfx_reset_contract import require

CONTRACT = copy.deepcopy(COORDINATE_CONTRACT)
CONTRACT.update({
    'version': 3,
    'conditional_execution_profile': True,
    'commands': ['sample', 'gfx-snapshot', 'stop', 'gfx-poweroff',
                 'control', 'recover', 'trace-off', 'submit'],
    'minimum_completed_idle_recovery_cycles': 4,
    'requires_successful_native_trace_off': True,
    'maximum_triangle_publications': 1,
    'work_intent_quarantines_before_first_publication': True,
    'after_work_intent': ['sample', 'gfx-snapshot'],
    'off_requires_no_work_intent': True,
    'typed_work_diagnostics_do_not_drain_receive': True,
    'healthy_receive_worker_retained_for_completion': True,
    'rendering_verified': False,
})


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    selected = trial.get('gfx_coordinated_execution_scope')
    if selected is None:
        return False
    require(selected == CONTRACT and not any(key in trial for key in
        ('gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope')),
        'Unknown or mixed execution scope')
    require(trial.get('deferred_triangle_available') is True and
        trial.get('progress_trace', {}).get('native_trace_disable') ==
            dict(object='status_a', byte_offset=0, value=0,
                 force_snapshot_opcode=22, minimum_completed_idle_cycles=4),
        'Existing recovery and native trace-off prerequisites missing')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop('gfx_coordinated_execution_scope')
    view['graph_recovery_trial']['gfx_coordinated_power_off_scope'] = COORDINATE_CONTRACT
    return validate_coordinate_receipt(view)
