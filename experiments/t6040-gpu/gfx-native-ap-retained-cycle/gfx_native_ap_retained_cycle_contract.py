# SPDX-License-Identifier: GPL-2.0-only
"""Carry a proved cold AP20 across retained sleep; never send a second HOST ON."""
import copy
import hashlib
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-running-cycle'
BASE_SHA='7398c46b2a1cfec55f62240456982063203576ccb9ec158c118e8dd9a7c50282'
if hashlib.sha256((BASE/'gfx_native_running_cycle_contract.py').read_bytes()).hexdigest()!=BASE_SHA:
 raise ValueError('Frozen native Running-cycle contract changed')
sys.path.insert(0,str(BASE))
from gfx_native_running_cycle_contract import CONTRACT as BASE_CONTRACT
from gfx_native_running_cycle_contract import validate_receipt as validate_base_receipt
from gfx_native_running_cycle_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_running_cycle_contract import (qualify_adt,qualify_linux_dt,
 qualify_startup_retention,qualify_graph_startup,record_fields,log_delta,
 qualify_first_off_logs,records,one_record,require_fields,REFUSED_BOOTS as BASE_REFUSED_BOOTS)
from gfx_reset_contract import require
FAMILY_KEY='gfx_native_ap_retained_cycle_scope'
COMMANDS=('sample','gfx-snapshot','gfx-powergate','gfx-native-ap-retained-cycle')
OPERATION_SCHEMA='m4rch.gfx-native-ap-retained-cycle-operation.v1'
REFUSED_BOOTS=BASE_REFUSED_BOOTS+('df540c1c-5ec4-44f5-894c-37be6c2f3527',)
REMOVED_CONTRACT_KEYS=(
 'retained_cycle_boot_running_observation_required_before_host_power',
 'retained_cycle_host_power_request','retained_cycle_host_power_reply',
 'retained_cycle_host_power_reply_requires_own_request',
 'retained_cycle_host_power_maximum_polls','retained_cycle_host_power_nominal_timeout_ms',
 'retained_cycle_host_power_reserved_journal_slots',
 'retained_cycle_host_power_fresh_guards_before_after_intent_and_reply',
 'retained_cycle_boot_and_host_running_required_before_second202')
CONTRACT=copy.deepcopy(BASE_CONTRACT)
for key in REMOVED_CONTRACT_KEYS:CONTRACT.pop(key)
CONTRACT.update({'version':11,'commands':list(COMMANDS),
 'after_attempt':['sample','gfx-snapshot','gfx-native-ap-retained-cycle'],
 'after_powergate_intent':['sample','gfx-snapshot','gfx-native-ap-retained-cycle'],
 'retained_cycle_command':'gfx-native-ap-retained-cycle',
 'retained_cycle_host_power_requests_maximum':0,
 'cold_ap_power_request':0x00b0000000000020,
 'cold_ap_power_reply':0x00b0000000000020,
 'cold_ap_exact_owned_reply_required_before_root_publication':True,
 'retained_ap_state_required_before_second_pm_get':0x20,
 'retained_ap_state_preserved_across_management202':True,
 'retained_ap_unknown_state_refused':True,
 'retained_ap_skip_intent_maximum':1,
 'retained_ap_skip_requires_exact_fresh_running':True,
 'retained_ap_skip_guarded_before_and_after_logging':True,
 'retained_ap_skip_is_fresh_reply':False,
 'retained_ap_skip_and_cold_proof_required_before_second202':True,
 'retained_ap_skip_reserved_ack_journal_slots':1,
 'retained_ap_native_runtime_flags_observed':False,
 'retained_ap_b201_or_b0_admitted':False})


def validate_receipt(receipt):
 trial=receipt.get('graph_recovery_trial',{});selected=trial.get(FAMILY_KEY)
 if selected is None:return False
 require(selected==CONTRACT and not any(key in trial for key in
  ('gfx_native_running_cycle_scope','gfx_native_idle_cycle_scope',
   'gfx_native_retained_cycle_scope','gfx_retained_power_cycle_scope',
   'gfx_native_powergate_drain_scope','gfx_native_powergate_scope',
   'gfx_native_status_execution_scope','gfx_coordinated_execution_scope',
   'gfx_coordinated_power_off_scope','gfx_power_off_scope','gfx_reset_scope')),
  'Unknown or mixed native retained AP-cycle contract')
 view=copy.deepcopy(receipt);view['graph_recovery_trial'].pop(FAMILY_KEY)
 view['graph_recovery_trial']['gfx_native_running_cycle_scope']=BASE_CONTRACT
 return validate_base_receipt(view)


def qualify_powergate_startup(delta,report,returncode,refcount):
 if any(marker in delta for marker in ('m4rch gfx-native-running-cycle-session: ',
  'm4rch gfx-native-running-cycle-startup-retained: ')):return None
 translated=delta.replace('m4rch gfx-native-ap-retained-cycle-session: ',
  'm4rch gfx-native-running-cycle-session: ').replace(
  'm4rch gfx-native-ap-retained-cycle-startup-retained: ',
  'm4rch gfx-native-running-cycle-startup-retained: ')
 proof=qualify_base_startup(translated,report,returncode,refcount)
 if proof is None:return None
 try:
  cold=records(delta,'gfx-native-ap-retained-cold')
  fields={'phase','request_attempted','request_write_attempted','request_message',
   'request_metadata','reply_observed','reply_message','reply_metadata','ap_remote_state','ap_remote_known'}
  require(len(cold)==2 and all(set(row)==fields for row in cold),
   'Missing or ambiguous owned cold AP proof')
  request,reply=cold
  common={'request_attempted':1,'request_message':CONTRACT['cold_ap_power_request'],'request_metadata':0}
  require_fields(request,dict(common,phase='request',request_write_attempted=0,
   reply_observed=0,reply_message=0,reply_metadata=0,ap_remote_state=0,ap_remote_known=0),
   'Unqualified cold AP intent')
  require_fields(reply,dict(common,phase='reply',request_write_attempted=1,
   reply_observed=1,reply_message=CONTRACT['cold_ap_power_reply'],ap_remote_state=0x20,ap_remote_known=1),
   'Unqualified exact cold AP reply')
  require(0 <= reply['reply_metadata'] < 0xffffffffffffffff and reply['reply_metadata']&0xff==0,
   'Cold AP reply endpoint or metadata invalid')
  prefix='m4rch gfx-native-ap-retained-cold: '
  root_marker='G16S root sent to EP32'
  require(delta.count(root_marker)==1 and
   delta.index(prefix+'phase=request ') < delta.index(prefix+'phase=reply ') <
   delta.index(root_marker) < delta.index('m4rch gfx-native-ap-retained-cycle-session: '),
   'Cold AP proof/root publication chronology differs')
  proof['ready_record']=proof['ready_record'].replace('gfx-native-running-cycle-session','gfx-native-ap-retained-cycle-session')
  proof['commands_admitted']=list(COMMANDS)
  proof['cold_ap_power']={'request':request,'reply':reply,'wire_state':0x20,
   'retained_skip_is_fresh_reply':False}
  return proof
 except (ValueError,TypeError,KeyError):return None
