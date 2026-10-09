# SPDX-License-Identifier: GPL-2.0-only
"""One retained transport reentry after an independently captured successful OFF."""
import copy
import hashlib
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'gfx-native-powergate-drain'
BASE_SHA = '884956c2d75e6001b85453a440e28c5cbfabae10cba1b57089facd7d971c75ca'
if hashlib.sha256((BASE/'gfx_native_powergate_drain_contract.py').read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('Frozen admission-drain contract changed')
sys.path.insert(0,str(BASE))
from gfx_native_powergate_drain_contract import CONTRACT as BASE_CONTRACT
from gfx_native_powergate_drain_contract import validate_receipt as validate_base_receipt
from gfx_native_powergate_drain_contract import qualify_powergate_startup as qualify_base_startup
from gfx_native_powergate_drain_contract import (qualify_adt, qualify_linux_dt,
    qualify_startup_retention, qualify_graph_startup, record_fields)
from gfx_reset_contract import require

FAMILY_KEY = 'gfx_retained_power_cycle_scope'
COMMANDS = ('sample','gfx-snapshot','gfx-powergate','gfx-retained-cycle')
OPERATION_SCHEMA = 'm4rch.gfx-retained-power-cycle-operation.v1'
REFUSED_BOOTS = ('94cb4163-fc21-43ec-9489-07c54e549885',
    'd841b8bf-bf1f-4499-9508-caf275909695','16868560-efd7-4c98-b58d-45cb88280d46')
CONTRACT = copy.deepcopy(BASE_CONTRACT)
CONTRACT.update({'version':7,'commands':list(COMMANDS),
    'after_attempt':['sample','gfx-snapshot','gfx-retained-cycle'],
    'after_powergate_intent':['sample','gfx-snapshot','gfx-retained-cycle'],
    'retained_cycle_command':'gfx-retained-cycle','maximum_retained_cycle_intents':1,
    'maximum_retained_cycle_pm_gets':1,'maximum_retained_cycle_starts':1,
    'retained_cycle_requires_saved_successful_first_off':True,
    'retained_cycle_requires_strict_first_off':True,
    'retained_cycle_preserves_first_coordination_epoch':True,
    'retained_cycle_separate_pm_reference':True,
    'retained_cycle_separate_coordination_epoch':True,
    'retained_cycle_pre_start_status48':0x6a,
    'retained_cycle_pre_start_start_clear':True,
    'retained_cycle_pre_start_rx_empty':True,
    'retained_cycle_protocol':'autonomous HELLO12 and endpoint map only',
    'retained_cycle_maximum_protocol_records':16,
    'retained_cycle_maximum_protocol_polls':4001,
    'retained_cycle_nominal_protocol_timeout_ms':4000,
    'retained_cycle_autonomous_hello_versions':[12,12],
    'retained_cycle_autonomous_map_shape':[{'base':0,'bitmap':3,'last':False},
                                          {'base':1,'bitmap':3,'last':True}],
    'retained_cycle_sends_init220':False,
    'retained_cycle_publishes_root_or_context':False,
    'retained_cycle_resets_app_queues':False,
    'retained_cycle_application_rejoined':False,
    'retained_cycle_powercycle_complete_verified':False,
    'retained_cycle_after_intent':['sample','gfx-snapshot'],
    'restart_allowed':False,'maximum_triangle_publications':0,
    'retained_transport_only':False,
    'retained_management_roundtrip_admitted':True,
    'maximum_retained_cycle_powergate_requests':1,
    'maximum_retained_cycle_pm_puts':1,
    'maximum_total_pm_puts':2,
    'retained_cycle_second_powergate_request':0x0060000000000202,
    'retained_cycle_second_off_requires_own_ack_and_checked_cpu_stop':True})


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial',{})
    selected = trial.get(FAMILY_KEY)
    if selected is None:return False
    require(selected == CONTRACT and not any(key in trial for key in
        ('gfx_native_powergate_drain_scope','gfx_native_powergate_scope',
         'gfx_native_status_execution_scope','gfx_coordinated_execution_scope',
         'gfx_coordinated_power_off_scope','gfx_power_off_scope','gfx_reset_scope')),
        'Unknown or mixed retained-cycle contract')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_native_powergate_drain_scope'] = BASE_CONTRACT
    return validate_base_receipt(view)


def qualify_powergate_startup(delta,report,returncode,refcount):
    for marker in ('m4rch gfx-native-powergate-session: ',
                   'm4rch gfx-native-powergate-startup-retained: ',
                   'm4rch gfx-native-powergate-drain-session: ',
                   'm4rch gfx-native-powergate-drain-startup-retained: '):
        if marker in delta:return None
    translated = delta.replace('m4rch gfx-retained-power-cycle-session: ',
        'm4rch gfx-native-powergate-drain-session: ').replace(
        'm4rch gfx-retained-power-cycle-startup-retained: ',
        'm4rch gfx-native-powergate-drain-startup-retained: ')
    proof = qualify_base_startup(translated,report,returncode,refcount)
    if proof is not None:
        proof['ready_record'] = proof['ready_record'].replace(
            'gfx-native-powergate-drain-session','gfx-retained-power-cycle-session')
        proof['commands_admitted'] = list(COMMANDS)
    return proof


def log_delta(before,after):
    """Join exact log suffix/prefix even when dmesg rotates its oldest lines."""
    require(bool(before) and before.endswith('\n') and after.endswith('\n'),
        'Incomplete first OFF log line boundary')
    if after.startswith(before):return after[len(before):]
    anchor=before.splitlines(keepends=True)[-1]
    offsets=[match.start() for match in re.finditer(re.escape(anchor),after)]
    require(len(offsets)==1,'First OFF log boundary is missing or ambiguous')
    end=offsets[0]+len(anchor)
    require(before.endswith(after[:end]),'First OFF rotated log overlap differs')
    return after[end:]


def records(logs,kind):
    rows=[]
    for line in logs.splitlines():
        marker = 'm4rch '+kind+': '
        if marker not in line:continue
        tail=line.split(marker,1)[1]
        tokens=tail.split()
        require(tokens and all(re.fullmatch(r'[a-z][a-z0-9_]*=[^\s=]+',token) for token in tokens),
            'Malformed retained first OFF record')
        fields=dict(token.split('=',1) for token in tokens)
        require(len(fields)==len(tokens),'Duplicate retained first OFF field')
        row={}
        for key,value in fields.items():
            require(re.fullmatch(r'-?(0|[1-9]\d*)|0x[0-9a-f]+',value) or
                (key in ('phase','command','refused_condition') and re.fullmatch(r'[a-z][a-z0-9_-]*',value)),
                'Malformed retained first OFF operand')
            try:row[key]=int(value,0)
            except ValueError:row[key]=value
        rows.append(row)
    return rows


def one_record(logs,kind,**wanted):
    rows=[row for row in records(logs,kind) if all(row.get(k)==v for k,v in wanted.items())]
    require(len(rows)==1,'Missing or ambiguous first OFF record: '+kind+str(wanted))
    return rows[0]


def require_fields(row,expected,description):
    require(all(row.get(k)==v for k,v in expected.items()),description)


def qualify_first_off_logs(logs):
    """Typed native predicates, never infer physical success from syscall success."""
    result=one_record(logs,'gfx-poweroff-result',command='gfx-powergate')
    require_fields(result,dict(result=0,gate_consumed=1,pm_attempted=1,pm_result=0,
        snapshot_result=0,provider_off_observed=1,accounting_ok=1,held=0,
        host_stopped=1,sealed=1,allocations_retained=174,restart_allowed=0,
        dma_retirement_verified=0),'First OFF result does not establish the retained boundary')
    require(1 <= result.get('snapshot_count',0) <= 101,'First OFF snapshot count invalid')
    paired=one_record(logs,'gfx-native-powergate-drain',phase='paired-off-return')
    require_fields(paired,dict(result=0,intent=1,request_attempted=1,
        request=0x0060000000000202,ack_observed=1,rx_empty_after_ack=1,
        rx_empty_before_cpu=1,idle_observed=1,clear10_attempted=1,
        clear20_attempted=1,control_after10=0,control_after20=0,cpu_stopped=1,
        off_delegated=1,held=0,allocations_retained=174,restart_allowed=0,
        dma_retirement_verified=0),'First management/CPU/OFF chain incomplete')
    require(((paired.get('ack_message',0)>>52)&15)==7 and
        (paired['ack_message']&255) in (1,2) and
        (paired.get('ack_metadata',-1)&255)==0 and
        (paired.get('idle_status',0)&3)!=0,'First native ACK/idle boundary invalid')
    words=[row for row in records(logs,'gfx-poweroff-word') if row.get('phase')=='after-off']
    require(1 <= len(words) <= 101 and len(words)==result['snapshot_count'] and
        [row.get('index') for row in words]==list(range(len(words))),
        'First physical OFF words missing, inconsistent or excessive')
    last=words[-1]
    require((last.get('value',-1)&CONTRACT['off_observation_mask'])==0 and
        all(last.get(k)==0 for k in ('actual','target','reset','disable','ps_reset','busy')),
        'First physical OFF word failed strict predicate')
    snapshot=one_record(logs,'gfx-poweroff-snapshot',phase='after-off',index=len(words)-1)
    require_fields(snapshot,dict(result=0,valid=1,domain_on=0,operation_error=0,
        cleanup_error=0,word_valid=1),'First physical OFF snapshot invalid')
    pm=one_record(logs,'gfx-poweroff-pm',phase='poweroff-final')
    require_fields(pm,dict(available=1,usage_count=0,runtime_status=2,runtime_error=0,
        active=0,suspended=1,held=0,pm_attempted=1),'First PM accounting invalid')
    owner=one_record(logs,'gfx-coordinate-owner',phase='before-target-zero-off')
    require_fields(owner,dict(result=0,startup_retained=1,module_pinned=1,
        on_attempted=1,on_complete=1,off_attempted=1,off_complete=1,
        held=1,retirement_verified=0),'First paired coordination incomplete')
    return dict(result=result,paired_off=paired,physical_words=words,
        physical_snapshot=snapshot,pm_final=pm,coordination_owner=owner)
