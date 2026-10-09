#!/usr/bin/env python3
"""Targeted new-family actual main paths; frozen first-proof behavior is composed."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;KIT=HERE.parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(KIT))
import gfx_native_retained_cycle_contract as contract
from adt import parse
from linux_dt_contract import encoded_layout

def sha(raw):return hashlib.sha256(raw).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
cases=[];flow_results=[];resident_flows=[]
def check(label,function,accepted):
    try:actual=function() is not False
    except (ValueError,KeyError,OSError,TypeError):actual=False
    assert actual is accepted,label
    cases.append({'case':label,'passed':True})
def replace_one(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new,1)

BASE_RECEIPT=ROOT/'out/gfx-coordinate-native-status/candidate/asc-root-envelope/build-receipt.json'
BASE_TEST=KIT/'gfx-native-powergate/test-powergate-runners.py'
RETAINED_TEST=KIT/'gfx-retained-power-cycle/test-powergate-runners.py'
COLD_TEST=KIT/'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA='7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
OBSERVED_LAYOUT=ROOT/'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
OLD_Q=ROOT/'out/gfx-retained-power-cycle/wrapper-qualification-final-v3.json'
assert sha(BASE_RECEIPT.read_bytes())=='2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_TEST.read_bytes())=='d500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
assert sha(RETAINED_TEST.read_bytes())=='fcaedb8f010b1f62be555c0efdef28aba2809aa04e8d2dcf3c96856d72b8da9c'
assert sha(OLD_Q.read_bytes())=='4c2b2d272e80df4c42a5db8d57e75df17303d9f32300224dcca6d89eea1a9856'
receipt=json.loads(BASE_RECEIPT.read_text());receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
root=module('native_retained_actual_cold',HERE/'run-root-powergate.py')
resident=module('native_retained_actual_resident',HERE/'run-powergate.py')
preflight=module('native_retained_actual_preflight',HERE/'preflight-fresh.py')
finalizer=module('native_retained_actual_finalizer',HERE/'finalize-powergate.py')
check('canonical-native-retained-cycle-family',lambda:contract.validate_receipt(receipt),True)
check('cold-parameters-unchanged',lambda:root.owner_parameters(receipt,graph=True)==['run_gate=2','observe_ms=5000','resident_session=1'],True)
assert resident.COMMANDS==contract.COMMANDS==('sample','gfx-snapshot','gfx-powergate','gfx-native-retained-cycle')
for family in ('gfx_retained_power_cycle_scope','gfx_native_powergate_drain_scope'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][family]={}
    check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in ('retained_cycle_pre_start_status48_values','retained_cycle_fresh_guard_before_paired_on',
    'retained_cycle_separate_paired_on_before_start','retained_cycle_refresh_guards_after_paired_on',
    'retained_cycle_refresh_guards_after_start_intent_log','retained_cycle_immediate_start_fresh_ctrl_rmw',
    'retained_cycle_maximum_log_row_bytes','maximum_triangle_publications'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=None
    check('changed-native-operand-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
old=runpy.run_path(str(KIT/'gfx-retained-power-cycle/run-powergate.py'),run_name='old_family_readonly')
for name in contract.COMMANDS:
    check('old-retained-wrapper-refuses-new-family-'+name,lambda n=name:old['admit_command'](n,receipt,{}),False)
for boot in contract.REFUSED_BOOTS:
    check('fresh-old-boot-refused-'+boot,lambda b=boot:preflight.qualify_fresh_boot(b,''),False)
    check('resident-old-boot-before-sysfs-'+boot,lambda b=boot:resident.validate(Path('/tmp/unselected-native-retained'),b),False)
    reads=[];real_read=Path.read_text
    def native_text(path,*args,**kwargs):
        if str(path).startswith(('/proc/','/sys/')):
            reads.append(str(path));assert str(path) in ('/proc/sys/kernel/random/boot_id','/proc/modules')
            return boot if str(path).endswith('boot_id') else ''
        return real_read(path,*args,**kwargs)
    with patch.object(Path,'read_text',native_text),patch.object(preflight.sys,'argv',['preflight-fresh.py','/tmp/unselected-native-retained','/tmp/unwritten-native-retained']),patch.object(preflight,'validate_candidate',lambda p:(_ for _ in ()).throw(AssertionError('Candidate validation preceded boot refusal'))):
        check('actual-preflight-main-old-boot-before-candidate-'+boot,preflight.main,False)
    assert reads==['/proc/sys/kernel/random/boot_id','/proc/modules']
oldq=finalizer.check_qualification(OLD_Q)
assert oldq['case_count']==101 and oldq['actual_main_flow_count']==6 and oldq['actual_resident_main_flow_count']==10
cases.append({'case':'frozen101-retained-wrapper-cases-composed-without-repetition','passed':True})
# The first native OFF parser is the actual frozen function, not a reimplementation.
import gfx_retained_power_cycle_contract as original_contract
assert contract.qualify_first_off_logs is original_contract.qualify_first_off_logs
assert contract.log_delta is original_contract.log_delta
cases.append({'case':'first-off-native-predicates-and-log-join-delegate-byteexact-frozen-code','passed':True})

saved=BASE_TEST.read_text()
setup=saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index("for label, log in [('diagnostic0-status0'",saved.index('adt_raw = ADT.read_bytes()'))]
setup=setup.replace("contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else", "contract.REFUSED_BOOTS[3] if label == 'current-5bf0-before-any-sampler' else contract.REFUSED_BOOTS[0] if label == 'current-94cb-before-any-sampler' else")
setup=setup.replace("('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler')", "('current-5bf0-before-any-sampler','current-94cb-before-any-sampler','graph-receipt-pin-before-any-sampler')")
setup=setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-native-retained-cycle-session: ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
run_flow('native-retained-diagnostic0',POSITIVE,'positive')
run_flow('current-5bf0-before-any-sampler','',failure=True)
run_flow('native-retained-unknown-with-success-looking-text',POSITIVE+'m4rch gfx-native-retained-cycle-startup-retained: malformed fields\n','startup-outcome-unqualified')
run_flow('old-retained-ready-refused',POSITIVE.replace('gfx-native-retained-cycle-session','gfx-retained-power-cycle-session'),'startup-outcome-unqualified')

LIVE=ROOT/'out/gfx-retained-power-cycle/candidate/asc-graph-init/boot-5bf0a178-e6d8-4def-8088-74ad7ea87727/resident-operations/20261009T214748.089738Z-gfx-powergate-5cbfd01e'
actual_before=(LIVE/'dmesg-before.log').read_text();actual_after=(LIVE/'dmesg-after.log').read_text()
NATIVE=contract.log_delta(actual_before,actual_after)

def state(**changes):
    value=dict(boot_id='offline-retained',candidate_module_sha256='unused',resident_session_active=True,
        powergate_ready=True,operation_failed=True,powergate_attempted=False,retained_cycle_attempted=False,
        submit_attempted=False,in_flight=None,family=contract.FAMILY_KEY,operation_uncertain=False,first_off_proof=None)
    value.update(changes);return value
check('old-command-name-refused',lambda:resident.admit_command('gfx-retained-cycle',receipt,state()),False)
check('new-cycle-before-firstOFF-refused',lambda:resident.admit_command('gfx-native-retained-cycle',receipt,state()),False)

# Reuse only the frozen actual resident fixture/main block. Its native reads,
# command writes and subprocesses remain intercepted; fixture data is current
# saved first-OFF data. Unchanged raw mutation and syscall-fault loops compose.
retained=RETAINED_TEST.read_text()
block=retained[retained.index("with tempfile.TemporaryDirectory(prefix='retained-resident-main-')"):retained.index('\nsource_receipt=ROOT/')]
start=block.index('        for key,value in [(\'complete\'')
end=block.index('        # Loss of host state before the new intent',start)
block=block[:start]+block[end:]
start=block.index('        # Direct command failure coverage')
block=block[:start]
block=block.replace('gfx-retained-cycle','gfx-native-retained-cycle')
exec(compile(block,str(RETAINED_TEST),'exec'),globals())

source_receipt=ROOT/'out/gfx-native-retained-cycle/prepared-owner-v1/native-retained-cycle-owner-source-receipt.json'
source_profile=json.loads(source_receipt.read_text())
check('actual-new-native-source-profile-qualified',lambda:finalizer.check_source_profile(source_profile),True)
for key in ('known_native_reentry_statuses','reentry_four_operands_before_and_after_second_paired_on',
    'reentry_four_operands_after_start_intent_log','immediate_start_fresh_ctrl_rmw',
    'maximum_log_row_bytes','complete_newline_structured_state_rows','first_epoch_evidence_immutable',
    'version','native_ordered_start_is_experimental_hypothesis','second_log_row_prefixes'):
    changed=copy.deepcopy(source_profile);changed['profile'][key]=None
    check('new-native-source-profile-refuses-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
owner_qualification=ROOT/'out/gfx-native-retained-cycle/owner-qualification-final-v1.json'
actual_owner=finalizer.check_qualification(owner_qualification)
check('actual-native-owner-source-and-bounded-log-qualification',lambda:finalizer.check_owner_qualification(actual_owner,source_profile,source_receipt),True)
for key,value in [('new_log_rows_bounded',False),('maximum_new_log_row_bytes',512),
    ('maximum_new_log_row_bytes',0),('maximum_new_log_row_bytes',True),
    ('actual_receive_worker',False),('source_receipt_sha256','0'*64)]:
    changed=copy.deepcopy(actual_owner);changed[key]=value
    check('native-owner-qualification-refuses-'+key+'-'+str(value),lambda c=changed:finalizer.check_owner_qualification(c,source_profile,source_receipt),False)
with tempfile.TemporaryDirectory(prefix='native-retained-preflight-candidate-') as directory:
    work=Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
    for name,data in [('asc-graph-init.ko',b'owner'),('source.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]:
        (work/'asc-graph-init'/name).write_bytes(data)
    fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')};fixture['graph_source_sha256']={'source.h':sha(b'source')}
    fixture['graph_fixture_sha256'],fixture['graph_receipt_sha256']=sha(b'graph'),sha(b'layout')
    rpath=work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
    prep={'schema':'m4rch.gfx-native-retained-cycle-preparation.v1','candidate_receipt_sha256':sha(rpath.read_bytes()),
        'selected_next_hardware_candidate':True,'hardware_actions':[],'owner_sha256':sha(b'owner'),
        'inputs':[{'path':str(source_receipt),'sha256':sha(source_receipt.read_bytes())}],'analysis_input_pins':[]}
    ppath=work/'native-retained-cycle-preparation.json';ppath.write_text(json.dumps(prep))
    check('actual-new-native-preflight-metadata-qualified',lambda:preflight.validate_candidate(work),True)
    ppath.write_text(json.dumps(dict(prep,schema='m4rch.gfx-retained-power-cycle-preparation.v1')))
    check('actual-native-preflight-prior-schema-refused',lambda:preflight.validate_candidate(work),False)

bound=[Path(__file__),HERE/'native_retained_wrapper.py',HERE/'gfx_native_retained_cycle_contract.py',HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',source_receipt,owner_qualification,BASE_RECEIPT,BASE_TEST,RETAINED_TEST,COLD_TEST,ADT,OBSERVED_LAYOUT,OLD_Q]
bound += [KIT/'gfx-retained-power-cycle'/name for name in ('gfx_retained_power_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py')]
bound += [LIVE/name for name in ('attempt.json','dmesg-before.log','dmesg-after.log','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json')]
result=dict(schema='m4rch.gfx-native-retained-cycle-wrapper-qualification.v1',passed=True,hardware_access=False,
    case_count=len(cases),cases=cases,actual_main_flow_count=len(flow_results),actual_main_flows=flow_results,
    actual_resident_main_flow_count=len(resident_flows),actual_resident_main_flows=resident_flows,
    frozen_retained_wrapper_case_count_composed=101,frozen_retained_cold_flows_composed=6,
    frozen_retained_resident_flows_composed=10,first_off_predicates_delegate_frozen=True,
    inputs=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in bound],
    transformed_cold_runner_sha256=sha(root.runner_source().encode()),transformed_resident_runner_sha256=sha(resident.runner_source().encode()),
    limits=['All system reads/processes/command writes are intercepted in RAM; saved5bf0 data is copied only.',
        'The native paired-ON/START guards are qualified by the separate actual C/header replay.',
        'Mocked new command success is no HELLO/map/ACK/secondOFF or restart proof.',
        'Frozen101/6/10 wrapper qualification is composed through exact pins without repeating unchanged negative capture/syscall cases.'])
output=ROOT/'out/gfx-native-retained-cycle/wrapper-qualification-final-v2.json'
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'output':str(output.relative_to(ROOT)),'case_count':len(cases),'actual_cold_main_flows':len(flow_results),'actual_resident_main_flows':len(resident_flows),'sha256':sha(output.read_bytes()),'hardware_access':False}))
layout_directory.cleanup()
