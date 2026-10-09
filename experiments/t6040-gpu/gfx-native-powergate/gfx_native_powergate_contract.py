# SPDX-License-Identifier: GPL-2.0-only
"""Distinct no-work management PWRGATE contract; frozen STATUS helpers are inputs."""
import copy
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
STATUS = BASE_KIT / 'gfx-coordinate-native-status'
STATUS_CONTRACT_SHA = 'a8d70c3bf2c09525a6742015a282cc59f0c10c27c524e3d295d294e781cae912'
if hashlib.sha256((STATUS / 'gfx_native_status_contract.py').read_bytes()).hexdigest() != STATUS_CONTRACT_SHA:
    raise ValueError('Frozen native STATUS contract changed')
sys.path.insert(0, str(STATUS))
from gfx_native_status_contract import CONTRACT as STATUS_CONTRACT
from gfx_native_status_contract import (validate_receipt as validate_status_receipt,
    qualify_adt, qualify_linux_dt, qualify_startup_retention, qualify_graph_startup,
    record_fields)
from gfx_reset_contract import require

FAMILY_KEY = 'gfx_native_powergate_scope'
COMMANDS = ('sample', 'gfx-snapshot', 'gfx-powergate')
REFUSED_BOOT = '94cb4163-fc21-43ec-9489-07c54e549885'
CONTRACT = copy.deepcopy(STATUS_CONTRACT)
CONTRACT.update({
    'version': 5,
    'conditional_execution_profile': False,
    'commands': list(COMMANDS),
    'maximum_triangle_publications': 0,
    'work_publication_admitted': False,
    'dormant_draw_fixture_preserved_for_comparison_only': True,
    'off_order': ['management-powergate-202-and-own-ack', 'native-checked-cpu-stop',
                  'pmp-request-and-native-success', 'pmc-rail-votes', 'physical-off'],
    'powergate_management_request': 0x0060000000000202,
    'powergate_ack': 'Own published 202 request, fresh empty RX, EP0 type nibble7 and low8 in {1,2}; other frames recorded',
    'maximum_powergate_intents': 1,
    'maximum_powergate_requests': 1,
    'maximum_powergate_ack_ms': 2000,
    'maximum_powergate_ack_polls': 2001,
    'maximum_powergate_rx_messages': 64,
    'pre_stop_idle_polls': 11,
    'fresh_cpu_stop_rmw_masks': [0x10, 0x20],
    'paired_off_requires_own_ack_and_checked_cpu_stop': True,
    'unknown_ack_or_stop_keeps_pm_held': True,
    'powergate_intent_durable_before_command_open': True,
    'after_powergate_intent': ['sample', 'gfx-snapshot'],
    'after_unknown_operation': ['sample', 'gfx-snapshot'],
    'initial_recovery_cycles_unchanged': True,
    'initial_admitted_states': ['healthy2cycles', 'diagnostic0or1cycles'],
    'separate_stop_off_recover_control_trace_submit_admitted': False,
    'restart_allowed': False,
    'dma_retirement_verified': False,
})


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    selected = trial.get(FAMILY_KEY)
    if selected is None:
        return False
    require(selected == CONTRACT and not any(key in trial for key in (
        'gfx_native_status_execution_scope', 'gfx_coordinated_execution_scope',
        'gfx_coordinated_power_off_scope', 'gfx_power_off_scope', 'gfx_reset_scope')),
        'Unknown or mixed native powergate contract')
    # The immutable dormant draw metadata satisfies the old structural validator
    # only on this local view. It admits no work in the canonical new profile.
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_native_status_execution_scope'] = STATUS_CONTRACT
    return validate_status_receipt(view)


def qualify_powergate_startup(delta, report, returncode, refcount):
    """Return a typed startup proof, or None; never infer state from absent text."""
    try:
        lines = delta.splitlines()
        require(not any('m4rch gfx-native-powergate-startup-retained: ' in line for line in lines),
                'Unknown native startup remains sealed')
        on = [line for line in lines if 'm4rch gfx-coordinate-observation: ' in line]
        owner = [line for line in lines if 'm4rch gfx-coordinate-owner: phase=post-active-on' in line]
        require(qualify_graph_startup(on, owner, returncode, refcount, report),
                'Unqualified native ON boundary')
        marker = 'm4rch gfx-native-powergate-session: '
        records = [line for line in lines if marker in line]
        require(len(records) == 1, 'Missing or ambiguous powergate startup marker')
        fields = record_fields(records[0], marker)
        require(set(fields) == {'ready', 'initial_recovery_failed',
                'initial_completed_cycles', 'startup_work_submitted'} and
                fields['ready'] == '1' and fields['startup_work_submitted'] == '0',
                'Unqualified powergate startup fields')
        failed = int(fields['initial_recovery_failed'], 0)
        cycles = int(fields['initial_completed_cycles'], 0)
        require((failed == 0 and cycles == 2) or (failed == 1 and cycles in (0, 1)),
                'Unexpected initial recovery state')
        session_records = [line for line in lines if 'm4rch recovery-session: ' in line]
        require(len(session_records) == 1, 'Missing or ambiguous retained session marker')
        retained = record_fields(session_records[0].split(';', 1)[0], 'm4rch recovery-session: ')
        expected = {'diagnostic': '1', 'sealed': '1'} if failed else {'resident': '1'}
        expected.update(control_ready='0', work_submitted='0', allocations_retained='1')
        require(retained == expected,
                'Retained session marker contradicts powergate startup')
        return {'qualified': True, 'initial_recovery_failed': bool(failed),
                'initial_completed_cycles': cycles, 'startup_work_submitted': False,
                'session_record': session_records[0], 'ready_record': records[0],
                'commands_admitted': list(COMMANDS)}
    except (ValueError, TypeError):
        return None
