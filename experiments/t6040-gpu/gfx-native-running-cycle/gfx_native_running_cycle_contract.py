# SPDX-License-Identifier: GPL-2.0-only
"""Boot Running notification and own HOST power handshake before second202."""
import copy
import hashlib
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-idle-cycle'
BASE_SHA='71503ee4dd3350db67eebda25e7d4afdba90151e7e7daffabfbd803a6b749920'
if hashlib.sha256((BASE/'gfx_native_idle_cycle_contract.py').read_bytes()).hexdigest()!=BASE_SHA:
 raise ValueError('Frozen native idle-cycle contract changed')
sys.path.insert(0,str(BASE))
from gfx_native_idle_cycle_contract import CONTRACT as BASE_CONTRACT
from gfx_native_idle_cycle_contract import validate_receipt as validate_base_receipt
from gfx_native_idle_cycle_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_idle_cycle_contract import (qualify_adt,qualify_linux_dt,
 qualify_startup_retention,qualify_graph_startup,record_fields,log_delta,
 qualify_first_off_logs,records,one_record,require_fields,REFUSED_BOOTS as BASE_REFUSED_BOOTS)
from gfx_reset_contract import require

FAMILY_KEY='gfx_native_running_cycle_scope'
COMMANDS=('sample','gfx-snapshot','gfx-powergate','gfx-native-running-cycle')
OPERATION_SCHEMA='m4rch.gfx-native-running-cycle-operation.v1'
REFUSED_BOOTS=BASE_REFUSED_BOOTS+('54e21e8f-b6f8-42cc-a5e5-e3f42831b870',)
CONTRACT=copy.deepcopy(BASE_CONTRACT)
CONTRACT.update({'version':10,'commands':list(COMMANDS),
 'after_attempt':['sample','gfx-snapshot','gfx-native-running-cycle'],
 'after_powergate_intent':['sample','gfx-snapshot','gfx-native-running-cycle'],
 'retained_cycle_command':'gfx-native-running-cycle',
 'retained_cycle_boot_running_observation_required_before_host_power':True,
 'retained_cycle_boot_running_message':0x0070000000000020,
 'retained_cycle_host_power_requests_maximum':1,
 'retained_cycle_host_power_request':0x00b0000000000020,
 'retained_cycle_host_power_reply':0x00b0000000000020,
 'retained_cycle_host_power_reply_requires_own_request':True,
 'retained_cycle_host_power_maximum_polls':2001,
 'retained_cycle_host_power_nominal_timeout_ms':2000,
 'retained_cycle_host_power_reserved_journal_slots':2,
 'retained_cycle_boot_running_required_after_endpoint_map':True,
 'retained_cycle_host_power_fresh_guards_before_after_intent_and_reply':True,
 'retained_cycle_boot_and_host_running_required_before_second202':True,
 'retained_cycle_running_messages_are_shutdown_ack':False})


def validate_receipt(receipt):
 trial=receipt.get('graph_recovery_trial',{});selected=trial.get(FAMILY_KEY)
 if selected is None:return False
 require(selected==CONTRACT and not any(key in trial for key in
  ('gfx_native_idle_cycle_scope','gfx_native_retained_cycle_scope','gfx_retained_power_cycle_scope',
   'gfx_native_powergate_drain_scope','gfx_native_powergate_scope',
   'gfx_native_status_execution_scope','gfx_coordinated_execution_scope',
   'gfx_coordinated_power_off_scope','gfx_power_off_scope','gfx_reset_scope')),
  'Unknown or mixed native running-cycle contract')
 view=copy.deepcopy(receipt);view['graph_recovery_trial'].pop(FAMILY_KEY)
 view['graph_recovery_trial']['gfx_native_idle_cycle_scope']=BASE_CONTRACT
 return validate_base_receipt(view)

def qualify_powergate_startup(delta,report,returncode,refcount):
 if any(marker in delta for marker in ('m4rch gfx-native-idle-cycle-session: ',
  'm4rch gfx-native-idle-cycle-startup-retained: ')):return None
 translated=delta.replace('m4rch gfx-native-running-cycle-session: ',
  'm4rch gfx-native-idle-cycle-session: ').replace(
  'm4rch gfx-native-running-cycle-startup-retained: ',
  'm4rch gfx-native-idle-cycle-startup-retained: ')
 proof=qualify_base_startup(translated,report,returncode,refcount)
 if proof is not None:
  proof['ready_record']=proof['ready_record'].replace('gfx-native-idle-cycle-session','gfx-native-running-cycle-session')
  proof['commands_admitted']=list(COMMANDS)
 return proof
