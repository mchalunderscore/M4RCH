# SPDX-License-Identifier: GPL-2.0-only
"""Three bounded epochs, with distinct retained management predecessors."""
import copy
import hashlib
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-ap-retained-cycle'
if hashlib.sha256((BASE/'gfx_native_ap_retained_cycle_contract.py').read_bytes()).hexdigest()!= '058706e562468d97698c5c64dcb89aa9cb88bfe5b2d2d9fd7d9a629de7b45f51':
 raise ValueError('Frozen AP-retained contract changed')
sys.path.insert(0,str(BASE))
from gfx_native_ap_retained_cycle_contract import CONTRACT as BASE_CONTRACT
from gfx_native_ap_retained_cycle_contract import validate_receipt as validate_base_receipt
from gfx_native_ap_retained_cycle_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_ap_retained_cycle_contract import (qualify_adt,qualify_linux_dt,
 qualify_startup_retention,qualify_graph_startup,record_fields,log_delta,
 qualify_first_off_logs,records,one_record,require_fields,REFUSED_BOOTS as BASE_REFUSED_BOOTS)
from gfx_reset_contract import require

FAMILY_KEY='gfx_native_ap_repeat_cycle_scope'
SECOND_COMMAND='gfx-native-ap-repeat-cycle'
THIRD_COMMAND='gfx-native-ap-repeat-third'
COMMANDS=('sample','gfx-snapshot','gfx-powergate',SECOND_COMMAND,THIRD_COMMAND)
OPERATION_SCHEMA='m4rch.gfx-native-ap-repeat-cycle-operation.v1'
REFUSED_BOOTS=BASE_REFUSED_BOOTS+('911ae710-78af-4702-8dfc-f4145decbd38',)
CONTRACT=copy.deepcopy(BASE_CONTRACT)
CONTRACT.update({
 'version':12,'commands':list(COMMANDS),
 'after_attempt':['sample','gfx-snapshot',SECOND_COMMAND,THIRD_COMMAND],
 'after_powergate_intent':['sample','gfx-snapshot',SECOND_COMMAND,THIRD_COMMAND],
 'retained_cycle_command':SECOND_COMMAND,'retained_third_command':THIRD_COMMAND,
 'retained_cycle_after_intent':['sample','gfx-snapshot',THIRD_COMMAND],
 'maximum_retained_cycle_intents':2,'maximum_retained_cycle_pm_gets':2,
 'maximum_retained_cycle_starts':2,'maximum_retained_cycle_powergate_requests':2,
 'maximum_retained_cycle_pm_puts':2,'maximum_total_pm_puts':3,
 'retained_ap_skip_intent_maximum':2,
 'maximum_epochs':3,'retained_epoch_ids':[2,3],
 'maximum_per_retained_epoch_intents':1,'maximum_per_retained_epoch_pm_gets':1,
 'maximum_per_retained_epoch_starts':1,'maximum_per_retained_epoch_requests':1,
 'maximum_per_retained_epoch_pm_puts':1,'maximum_total_powergate_requests':3,
 'maximum_total_coordinator_on_notifications':3,'maximum_total_coordinator_off_notifications':3,
 'third_requires_exact_second_off_proof':True,'second_off_raw_input_count':7,
 'second_off_qualifier_distinct_from_first':True,
 'predecessor_proofs_rebuilt_from_exact_operation_delta':True,
 'first_and_second_epoch_evidence_immutable':True,
 'separate_third_intent_pm_reference_coordination_and_journal':True,
 'epoch_bound_structured_rows':True,'lost_or_unknown_history_seals_controls':True,
 'refused_boot_guard_precedes_candidate_or_live_reads':True,
 'after_third_intent':['sample','gfx-snapshot'],
 'retained_application_map_ack_bitmap':0,'application_rejoin_admitted':False})

def validate_receipt(receipt):
 trial=receipt.get('graph_recovery_trial',{});selected=trial.get(FAMILY_KEY)
 if selected is None:return False
 require(selected==CONTRACT and not any(k.endswith('_scope') and k!=FAMILY_KEY for k in trial),
  'Unknown or mixed AP-repeat contract')
 view=copy.deepcopy(receipt);view['graph_recovery_trial'].pop(FAMILY_KEY)
 view['graph_recovery_trial']['gfx_native_ap_retained_cycle_scope']=BASE_CONTRACT
 return validate_base_receipt(view)

def qualify_powergate_startup(delta,report,returncode,refcount):
 if any(marker in delta for marker in ('m4rch gfx-native-ap-retained-cycle-session: ',
  'm4rch gfx-native-ap-retained-cycle-startup-retained: ',
  'm4rch gfx-native-ap-retained-cold: ')):return None
 try:
  cold=records(delta,'gfx-native-ap-repeat-cold')
  require(len(cold)==2 and all(r.get('epoch')==1 for r in cold),'Cold AP epoch missing or crossed')
  ready=records(delta,'gfx-native-ap-repeat-cycle-session')
  require(len(ready)==1 and ready[0].get('epoch')==1,'Cold ready epoch missing or crossed')
 except (ValueError,KeyError,TypeError):return None
 translated=delta.replace('gfx-native-ap-repeat-cycle-session: epoch=1 ','gfx-native-ap-retained-cycle-session: ').replace(
  'gfx-native-ap-repeat-cycle-startup-retained','gfx-native-ap-retained-cycle-startup-retained').replace(
  'gfx-native-ap-repeat-cold','gfx-native-ap-retained-cold')
 # Preserve the frozen exact cold field set after separately binding E1.
 translated=translated.replace('gfx-native-ap-retained-cold: phase=request epoch=1 ',
  'gfx-native-ap-retained-cold: phase=request ').replace('gfx-native-ap-retained-cold: phase=reply epoch=1 ',
  'gfx-native-ap-retained-cold: phase=reply ')
 proof=qualify_base_startup(translated,report,returncode,refcount)
 if proof is None:return None
 proof['ready_record']=proof['ready_record'].replace('gfx-native-ap-retained-cycle-session: ',
  'gfx-native-ap-repeat-cycle-session: epoch=1 ')
 proof['commands_admitted']=list(COMMANDS)
 proof['cold_ap_power']['request'],proof['cold_ap_power']['reply']=cold
 return proof

def qualify_retained_off_logs(delta,epoch=2):
 """Qualify only the epoch's own new rows, never historical first-OFF rows."""
 require(epoch in (2,3),'Unknown retained epoch')
 prefix=SECOND_COMMAND if epoch==2 else THIRD_COMMAND
 other=THIRD_COMMAND if epoch==2 else SECOND_COMMAND
 require('m4rch '+other+':' not in delta and 'm4rch '+other+'-' not in delta,
  'Crossed retained epoch log delta')
 require('m4rch gfx-native-ap-retained-cycle' not in delta,'Old retained family log delta')
 families=[prefix,prefix+'-state',prefix+'-transport',prefix+'-management',prefix+'-off',prefix+'-on']
 groups=[records(delta,p) for p in families]
 field_sets=[
  set('phase epoch result refused_condition intent first_off_fields_historical powercycle_complete application_rejoined allocations_retained unknown terminal_result restart_allowed dma_retirement_verified'.split()),
  set('phase epoch identity_captured identities_preserved first_off_preserved pm_get_attempted pm_get_result second_ref_held held usage runtime_error runtime_status active suspended'.split()),
  set('phase epoch second_on_attempted second_on_complete boundary_qualified control44 status48 rx_status tx_status start_attempted hello_reply_attempts hello_replied map_reply_attempts endpoint_map appmap map_seen protocol_records protocol_polls guard_jiffies cached operand_samples_atomic'.split()),
  set('phase epoch second_request_attempted second_ack_observed second_ack_message second_ack_metadata second_ack_polls second_idle_polls second_clear10_attempted second_clear20_attempted second_cpu_stopped'.split()),
  set('phase epoch second_off_attempted second_off_complete second_pm_put_attempted second_pm_put_result second_off_snapshot_result second_off_samples second_provider_off_observed second_accounting_ok'.split()),
  set('phase epoch boot_running_observed boot_running_message boot_running_metadata cold_ap_request_attempted cold_ap_reply_observed cold_ap_reply_message cold_ap_reply_metadata ap_remote_state ap_remote_known host_on_skip_attempted host_on_skipped'.split())]
 if epoch==3:
  field_sets=[{k.replace('second_','third_') for k in fields} for fields in field_sets]
  field_sets[0].add('second_epoch_preserved')
 require(all(set(row)==fields for group,fields in zip(groups,field_sets) for row in group),
  'Unknown or missing retained row fields')
 phases=['intent','second-pm-get-intent','cold-boundary','cold-boundary','second-start-intent',
  'second-start-return','autonomous-map-retained','boot-running-observed',
  'retained-ap-on-skip-intent','retained-ap-on-skipped','second-pwr-gate-intent',
  'second-cpu-stop-return','second-coordinate-off-intent','second-physical-off','retained-final']
 if epoch==3:phases=[p.replace('second-','third-') for p in phases]
 require(all([r.get('phase') for r in g]==phases for g in groups),
  'Missing, duplicate, stale or incomplete retained phase groups')
 require(all(r.get('epoch')==epoch for g in groups for r in g),'Unbound retained phase epoch')
 for r in groups[0]:
  require_fields(r,dict(result=0,refused_condition='none',intent=1,first_off_fields_historical=1,unknown=0,
   application_rejoined=0,allocations_retained=174,restart_allowed=0,dma_retirement_verified=0),
   'Retained attempt refused or weakened')
 require(all(r.get('powercycle_complete')==int(i==len(phases)-1) for i,r in enumerate(groups[0])),
  'Premature retained success marker')
 raw_final=[g[-1] for g in groups]
 require_fields(raw_final[0],dict(terminal_result=0),'Retained terminal result not successful')
 final=[{k.replace('third_','second_'):v for k,v in r.items()} if epoch==3 else r for r in raw_final]
 if epoch==3:require_fields(raw_final[0],dict(second_epoch_preserved=1),'Third epoch changed immutable second epoch')
 require_fields(final[1],dict(identity_captured=1,identities_preserved=1,first_off_preserved=1,
  pm_get_attempted=1,pm_get_result=0,second_ref_held=0,held=0,usage=0,runtime_error=0,
  runtime_status=2,active=0,suspended=1),'Retained final accounting differs')
 require_fields(final[2],dict(second_on_attempted=1,second_on_complete=1,boundary_qualified=1,
  control44=0,start_attempted=1,hello_reply_attempts=1,hello_replied=1,map_reply_attempts=2,
  endpoint_map=1,appmap=3,map_seen=3,protocol_records=5,cached=1,operand_samples_atomic=0),
  'Retained management protocol incomplete')
 require(type(final[2].get('guard_jiffies')) is int and final[2]['guard_jiffies']>=0,
  'Retained cached sample provenance absent')
 require(1<=final[2].get('protocol_polls',0)<=4001,'Retained protocol poll bound differs')
 require_fields(final[3],dict(second_request_attempted=1,second_ack_observed=1,
  second_clear10_attempted=1,second_clear20_attempted=1,second_cpu_stopped=1),
  'Retained own ACK or checked stop incomplete')
 ack=final[3]['second_ack_message'];meta=final[3]['second_ack_metadata']
 require((ack>>52)&0xf==7 and ack&0xff in (1,2) and meta&0xff==0 and
  0<=meta<0xffffffffffffffff and 1<=final[3].get('second_ack_polls',0)<=2001 and
  1<=final[3].get('second_idle_polls',0)<=11,'Retained own ACK operands invalid')
 require_fields(final[4],dict(second_off_attempted=1,second_off_complete=1,second_pm_put_attempted=1,
  second_pm_put_result=0,second_off_snapshot_result=0,second_provider_off_observed=1,
  second_accounting_ok=1),'Retained OFF/put not qualified')
 require(1<=final[4].get('second_off_samples',0)<=101,'Retained physical OFF bound differs')
 require_fields(final[5],dict(boot_running_observed=1,boot_running_message=0x0070000000000020,
  cold_ap_request_attempted=1,cold_ap_reply_observed=1,cold_ap_reply_message=0x00b0000000000020,
  ap_remote_state=0x20,ap_remote_known=1,host_on_skip_attempted=1,host_on_skipped=1),
  'Retained AP20 or own Running proof incomplete')
 rx=records(delta,prefix+'-rx')
 require(len(rx)==5 and [r.get('index') for r in rx]==list(range(1,6)) and
  all(r.get('epoch')==epoch for r in rx),'Missing or crossed retained receive provenance')
 require([r.get('message') for r in rx[:4]]==[0x00100000000c000c,0x0080000000000003,
  0x0088000100000003,0x0070000000000020] and rx[-1]['message']==ack and
  rx[-1]['metadata']==meta and all(0<=r['metadata']<0xffffffffffffffff and r['metadata']&0xff==0 for r in rx),
  'Retained ordered protocol or own ACK differs')
 tx=records(delta,prefix+'-tx')
 require([r.get('packet') for r in tx]==[0x00200000000c000c,0x0080000000000001,0x0088000100000000] and
  all(r.get('epoch')==epoch for r in tx),'Retained management-only transmit map differs')
 require(all(r.get('endpoint')==0 and r.get('root_publications')==0 and
  r.get('application_starts')==0 and r.get('init220_requests')==0 for r in tx),
  'Unexpected retained application or work publication')
 coord=records(delta,'gfx-native-ap-repeat-coordinate')
 require(len(coord)==2 and [r.get('enabled') for r in coord]==[1,0] and
  all(r.get('epoch')==epoch for r in coord),'Retained paired coordination provenance differs')
 for r,enabled in zip(coord,(1,0)):
  require_fields(r,dict(result=0,request_attempted=1,votes_attempted=3,votes_verified=3,
   first_on_complete=1,first_off_complete=1,first_session_reset=0,
   **({'on_attempted':1,'on_complete':1} if enabled else {'off_attempted':1,'off_complete':1})),
   'Retained paired coordination incomplete')
  require((r.get('request_acked'),r.get('ack_bypassed')) in ((1,0),(0,1)),
   'Retained coordination success branch invalid')
  before=r.get('request_before');written=r.get('request_written')
  require(type(before) is int and 0<=before<0xffffffffffffffff and
   bool(before&8192) is (not bool(enabled)) and written==(before|8192 if enabled else before&~8192),
   'Retained coordination request target or preserved bits differ')
  require((r['status_payload']==0) is bool(r['ack_bypassed']),
   'Retained coordinator zero-status bypass branch differs')
 words=records(delta,'gfx-poweroff-word')
 own=[r for r in words if r.get('phase')==('retained-cycle-after-second-off' if epoch==2 else 'repeat-third-after-third-off')]
 require(1<=len(own)<=101 and len(own)==final[4]['second_off_samples'] and
  [r.get('index') for r in own]==list(range(len(own))) and all(r.get('epoch')==epoch for r in own),
  'Retained physical OFF observations absent, duplicated, crossed or unbounded')
 require_fields(own[-1],dict(epoch=epoch,actual=0,target=0,auto=0,reset=0,disable=0,ps_reset=0,busy=0),
  'Retained physical OFF word not strict')
 require(own[-1]['value']&CONTRACT['off_observation_mask']==0,'Retained physical OFF mask differs')
 snapshots=[r for r in records(delta,'gfx-poweroff-snapshot') if r.get('phase')==own[-1]['phase']]
 require(len(snapshots)==len(own) and [r.get('index') for r in snapshots]==list(range(len(own))) and
  all(r.get('epoch')==epoch for r in snapshots),'Retained physical snapshots differ')
 require_fields(snapshots[-1],dict(result=0,valid=1,domain_on=0,operation_error=0,cleanup_error=0,word_valid=1),
  'Retained final physical snapshot invalid')
 # Exact raw position ties RX ACK to the new request and checked stop, followed
 # by own OFF/physical/accounting. Historical E1 markers cannot satisfy this.
 def marker(phase):return 'm4rch '+prefix+': phase='+phase+' '
 request=marker(('second' if epoch==2 else 'third')+'-pwr-gate-intent')
 stop=marker(('second' if epoch==2 else 'third')+'-cpu-stop-return')
 ack_marker='m4rch '+prefix+'-rx: epoch='+str(epoch)+' index=5 '
 require(delta.index(request)<delta.index(ack_marker)<delta.index(stop)<
  delta.index(marker(('second' if epoch==2 else 'third')+'-coordinate-off-intent'))<
  delta.index(marker(('second' if epoch==2 else 'third')+'-physical-off'))<delta.index(marker('retained-final')),
  'Retained request/own ACK/stop/OFF chronology differs')
 return dict(epoch=epoch,qualified=True,final_rows=dict(zip(families,raw_final)),
  own_ack=dict(message=ack,metadata=meta,index=5),receive_records=rx,transmit_records=tx,
  paired_coordination=coord,physical_off_words=own,physical_off_snapshot=snapshots[-1],phase_group_count=len(phases),
  application_rejoined=False,dma_retirement_verified=False)
