# SPDX-License-Identifier: GPL-2.0-only
"""Separate paired native ON between guarded ACTIVE reentry and one START."""
import copy
import hashlib
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-retained-power-cycle'
BASE_SHA='68ee7b4b986903a9c720c9912f165a5e402f63aa3b77eb2427d556d8a2957fe8'
if hashlib.sha256((BASE/'gfx_retained_power_cycle_contract.py').read_bytes()).hexdigest()!=BASE_SHA:
    raise ValueError('Frozen retained-cycle contract changed')
sys.path.insert(0,str(BASE))
from gfx_retained_power_cycle_contract import CONTRACT as BASE_CONTRACT
from gfx_retained_power_cycle_contract import validate_receipt as validate_base_receipt
from gfx_retained_power_cycle_contract import qualify_powergate_startup as qualify_base_startup
from gfx_retained_power_cycle_contract import (qualify_adt,qualify_linux_dt,
    qualify_startup_retention,qualify_graph_startup,record_fields,log_delta,
    qualify_first_off_logs,records,one_record,require_fields)
from gfx_reset_contract import require

FAMILY_KEY='gfx_native_retained_cycle_scope'
COMMANDS=('sample','gfx-snapshot','gfx-powergate','gfx-native-retained-cycle')
OPERATION_SCHEMA='m4rch.gfx-native-retained-cycle-operation.v1'
REFUSED_BOOTS=('94cb4163-fc21-43ec-9489-07c54e549885',
    'd841b8bf-bf1f-4499-9508-caf275909695','16868560-efd7-4c98-b58d-45cb88280d46',
    '5bf0a178-e6d8-4def-8088-74ad7ea87727')
CONTRACT=copy.deepcopy(BASE_CONTRACT)
CONTRACT.pop('retained_cycle_pre_start_status48')
CONTRACT.update({'version':8,'commands':list(COMMANDS),
    'after_attempt':['sample','gfx-snapshot','gfx-native-retained-cycle'],
    'after_powergate_intent':['sample','gfx-snapshot','gfx-native-retained-cycle'],
    'retained_cycle_command':'gfx-native-retained-cycle',
    'retained_cycle_pre_start_status48_values':[0x6a,0x6c],
    'retained_cycle_fresh_guard_before_paired_on':True,
    'retained_cycle_separate_paired_on_before_start':True,
    'retained_cycle_refresh_guards_after_paired_on':True,
    'retained_cycle_pre_start_tx_available':True,
    'retained_cycle_status_values_are_success_proof':False,
    'retained_cycle_refresh_guards_after_start_intent_log':True,
    'retained_cycle_immediate_start_fresh_ctrl_rmw':True,
    'retained_cycle_maximum_log_row_bytes':511,
    'retained_cycle_complete_structured_log_rows':True})


def validate_receipt(receipt):
    trial=receipt.get('graph_recovery_trial',{})
    selected=trial.get(FAMILY_KEY)
    if selected is None:return False
    require(selected==CONTRACT and not any(key in trial for key in
        ('gfx_retained_power_cycle_scope','gfx_native_powergate_drain_scope',
         'gfx_native_powergate_scope','gfx_native_status_execution_scope',
         'gfx_coordinated_execution_scope','gfx_coordinated_power_off_scope',
         'gfx_power_off_scope','gfx_reset_scope')),'Unknown or mixed native retained-cycle contract')
    view=copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_retained_power_cycle_scope']=BASE_CONTRACT
    return validate_base_receipt(view)


def qualify_powergate_startup(delta,report,returncode,refcount):
    if any(marker in delta for marker in ('m4rch gfx-retained-power-cycle-session: ',
        'm4rch gfx-retained-power-cycle-startup-retained: ')):return None
    translated=delta.replace('m4rch gfx-native-retained-cycle-session: ',
        'm4rch gfx-retained-power-cycle-session: ').replace(
        'm4rch gfx-native-retained-cycle-startup-retained: ',
        'm4rch gfx-retained-power-cycle-startup-retained: ')
    proof=qualify_base_startup(translated,report,returncode,refcount)
    if proof is not None:
        proof['ready_record']=proof['ready_record'].replace('gfx-retained-power-cycle-session',
            'gfx-native-retained-cycle-session')
        proof['commands_admitted']=list(COMMANDS)
    return proof
