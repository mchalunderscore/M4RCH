# SPDX-License-Identifier: GPL-2.0-only
"""Distinct bounded EP32 admission drain before the sole native PWRGATE."""
import copy
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-native-powergate'
BASE_SHA = '4f69ad092660f88207601a5f6ca7992ef33ea15ed89d2c4b4f245cbf82b49e74'
if hashlib.sha256((BASE/'gfx_native_powergate_contract.py').read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('Frozen PWRGATE contract changed')
sys.path.insert(0, str(BASE))
from gfx_native_powergate_contract import CONTRACT as BASE_CONTRACT
from gfx_native_powergate_contract import validate_receipt as validate_base_receipt
from gfx_native_powergate_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_powergate_contract import (COMMANDS, qualify_adt, qualify_linux_dt,
    qualify_startup_retention, qualify_graph_startup, record_fields)
from gfx_reset_contract import require

FAMILY_KEY = 'gfx_native_powergate_drain_scope'
REFUSED_BOOTS = ('94cb4163-fc21-43ec-9489-07c54e549885',
                 'd841b8bf-bf1f-4499-9508-caf275909695')
CONTRACT = copy.deepcopy(BASE_CONTRACT)
CONTRACT.update({
    'version': 6,
    'off_order': ['bounded-fresh-qualified-ep32-admission-drain'] + BASE_CONTRACT['off_order'],
    'bounded_admission_drain': True,
    'nominal_admission_deadline_ms': 11,
    'maximum_admission_wait_polls': 12,
    'maximum_admission_rx_messages': 64,
    'maximum_successful_admission_rx_messages': 63,
    'qualified_admission_endpoint32_only': True,
    'stale_ep0_refused': True,
    'precise_admission_operands_logged': True,
})


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    selected = trial.get(FAMILY_KEY)
    if selected is None:
        return False
    require(selected == CONTRACT and not any(key in trial for key in (
        'gfx_native_powergate_scope', 'gfx_native_status_execution_scope',
        'gfx_coordinated_execution_scope', 'gfx_coordinated_power_off_scope',
        'gfx_power_off_scope', 'gfx_reset_scope')), 'Unknown or mixed native powergate drain contract')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_native_powergate_scope'] = BASE_CONTRACT
    return validate_base_receipt(view)


def qualify_powergate_startup(delta, report, returncode, refcount):
    """Reuse exact prior startup gates with distinct, non-interchangeable markers."""
    old_markers = ('m4rch gfx-native-powergate-session: ',
                   'm4rch gfx-native-powergate-startup-retained: ')
    if any(marker in delta for marker in old_markers):
        return None
    translated = delta.replace('m4rch gfx-native-powergate-drain-session: ', old_markers[0])
    translated = translated.replace('m4rch gfx-native-powergate-drain-startup-retained: ', old_markers[1])
    proof = qualify_base_startup(translated, report, returncode, refcount)
    if proof is not None:
        proof['ready_record'] = proof['ready_record'].replace(old_markers[0], 'm4rch gfx-native-powergate-drain-session: ')
    return proof
