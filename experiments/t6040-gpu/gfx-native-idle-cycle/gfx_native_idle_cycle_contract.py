# SPDX-License-Identifier: GPL-2.0-only
"""Stage-specific native idle boundary, conditional on own second paired ON."""
import copy
import hashlib
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-retained-cycle'
BASE_SHA='55db8b571c94eadc4789a658cb3af5512befc359403eb989c25e489989343361'
if hashlib.sha256((BASE/'gfx_native_retained_cycle_contract.py').read_bytes()).hexdigest()!=BASE_SHA:
 raise ValueError('Frozen native retained-cycle contract changed')
sys.path.insert(0,str(BASE))
from gfx_native_retained_cycle_contract import CONTRACT as BASE_CONTRACT
from gfx_native_retained_cycle_contract import validate_receipt as validate_base_receipt
from gfx_native_retained_cycle_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_retained_cycle_contract import (qualify_adt,qualify_linux_dt,
 qualify_startup_retention,qualify_graph_startup,record_fields,log_delta,
 qualify_first_off_logs,records,one_record,require_fields,REFUSED_BOOTS as BASE_REFUSED_BOOTS)
from gfx_reset_contract import require

FAMILY_KEY='gfx_native_idle_cycle_scope'
COMMANDS=('sample','gfx-snapshot','gfx-powergate','gfx-native-idle-cycle')
OPERATION_SCHEMA='m4rch.gfx-native-idle-cycle-operation.v1'
REFUSED_BOOTS=BASE_REFUSED_BOOTS+('96264748-b049-403f-9240-975716f71d0c',)
CONTRACT=copy.deepcopy(BASE_CONTRACT)
CONTRACT.pop('retained_cycle_pre_start_status48_values')
CONTRACT.update({'version':9,'commands':list(COMMANDS),
 'after_attempt':['sample','gfx-snapshot','gfx-native-idle-cycle'],
 'after_powergate_intent':['sample','gfx-snapshot','gfx-native-idle-cycle'],
 'retained_cycle_command':'gfx-native-idle-cycle',
 'retained_cycle_pre_paired_on_status48_values':[0x6a,0x6c],
 'retained_cycle_post_paired_on_status48_values':[0x6a,0x6c,0x6d],
 'retained_cycle_idle_status_requires_own_second_on':True,
 'retained_cycle_pre_on_status6d_refused':True,
 'retained_cycle_stage_specific_start_admission':True,
 'retained_cycle_idle_status_is_experimental_hypothesis':True})

def validate_receipt(receipt):
 trial=receipt.get('graph_recovery_trial',{});selected=trial.get(FAMILY_KEY)
 if selected is None:return False
 require(selected==CONTRACT and not any(key in trial for key in
  ('gfx_native_retained_cycle_scope','gfx_retained_power_cycle_scope',
   'gfx_native_powergate_drain_scope','gfx_native_powergate_scope',
   'gfx_native_status_execution_scope','gfx_coordinated_execution_scope',
   'gfx_coordinated_power_off_scope','gfx_power_off_scope','gfx_reset_scope')),
  'Unknown or mixed native idle-cycle contract')
 view=copy.deepcopy(receipt);view['graph_recovery_trial'].pop(FAMILY_KEY)
 view['graph_recovery_trial']['gfx_native_retained_cycle_scope']=BASE_CONTRACT
 return validate_base_receipt(view)

def qualify_powergate_startup(delta,report,returncode,refcount):
 if any(marker in delta for marker in ('m4rch gfx-native-retained-cycle-session: ',
  'm4rch gfx-native-retained-cycle-startup-retained: ')):return None
 translated=delta.replace('m4rch gfx-native-idle-cycle-session: ',
  'm4rch gfx-native-retained-cycle-session: ').replace(
  'm4rch gfx-native-idle-cycle-startup-retained: ',
  'm4rch gfx-native-retained-cycle-startup-retained: ')
 proof=qualify_base_startup(translated,report,returncode,refcount)
 if proof is not None:
  proof['ready_record']=proof['ready_record'].replace('gfx-native-retained-cycle-session','gfx-native-idle-cycle-session')
  proof['commands_admitted']=list(COMMANDS)
 return proof
