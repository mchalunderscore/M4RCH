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
import gfx_native_idle_cycle_contract as contract
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
OLD_Q=ROOT/'out/gfx-native-retained-cycle/wrapper-qualification-final-v2.json'
assert sha(BASE_RECEIPT.read_bytes())=='2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_TEST.read_bytes())=='d500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
assert sha(RETAINED_TEST.read_bytes())=='fcaedb8f010b1f62be555c0efdef28aba2809aa04e8d2dcf3c96856d72b8da9c'
assert sha(OLD_Q.read_bytes())=='bfbe8fe6be21f2588061c012c8aa25be1b494e94182dba37dd45ce5cb10e525f'
receipt=json.loads(BASE_RECEIPT.read_text());receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
root=module('native_retained_actual_cold',HERE/'run-root-powergate.py')
resident=module('native_retained_actual_resident',HERE/'run-powergate.py')
preflight=module('native_retained_actual_preflight',HERE/'preflight-fresh.py')
finalizer=module('native_retained_actual_finalizer',HERE/'finalize-powergate.py')
check('canonical-native-idle-cycle-family',lambda:contract.validate_receipt(receipt),True)
check('cold-parameters-unchanged',lambda:root.owner_parameters(receipt,graph=True)==['run_gate=2','observe_ms=5000','resident_session=1'],True)
assert resident.COMMANDS==contract.COMMANDS==('sample','gfx-snapshot','gfx-powergate','gfx-native-idle-cycle')
for family in ('gfx_native_retained_cycle_scope','gfx_retained_power_cycle_scope'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][family]={}
    check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in ('version','retained_cycle_pre_paired_on_status48_values',
    'retained_cycle_post_paired_on_status48_values','retained_cycle_idle_status_requires_own_second_on',
    'retained_cycle_pre_on_status6d_refused','retained_cycle_stage_specific_start_admission'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=None
    check('changed-native-idle-stage-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
# Exact stage sets are contractual and cannot be weakened by a source receipt.
assert contract.CONTRACT['retained_cycle_pre_paired_on_status48_values']==[106,108]
assert contract.CONTRACT['retained_cycle_post_paired_on_status48_values']==[106,108,109]
for key,value in [('retained_cycle_pre_paired_on_status48_values',[106,108,109]),
    ('retained_cycle_post_paired_on_status48_values',[106,108]),
    ('retained_cycle_idle_status_requires_own_second_on',False)]:
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=value
    check('weakened-native-idle-stage-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
old=runpy.run_path(str(KIT/'gfx-native-retained-cycle/run-powergate.py'),run_name='old_family_readonly')
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
assert oldq['case_count']==69 and oldq['actual_main_flow_count']==4 and oldq['actual_resident_main_flow_count']==10
cases.append({'case':'frozen69-native-retained-wrapper-cases-composed-without-repetition','passed':True})
# The first native OFF parser is the actual frozen function, not a reimplementation.
import gfx_native_retained_cycle_contract as original_contract
assert contract.qualify_first_off_logs is original_contract.qualify_first_off_logs
assert contract.log_delta is original_contract.log_delta
cases.append({'case':'first-off-native-predicates-and-log-join-delegate-byteexact-frozen-code','passed':True})

saved=BASE_TEST.read_text()
setup=saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index("for label, log in [('diagnostic0-status0'",saved.index('adt_raw = ADT.read_bytes()'))]
setup=setup.replace("contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else", "contract.REFUSED_BOOTS[4] if label == 'current-9626-before-any-sampler' else contract.REFUSED_BOOTS[0] if label == 'current-94cb-before-any-sampler' else")
setup=setup.replace("('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler')", "('current-9626-before-any-sampler','current-94cb-before-any-sampler','graph-receipt-pin-before-any-sampler')")
setup=setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-native-idle-cycle-session: ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
run_flow('native-retained-diagnostic0',POSITIVE,'positive')
run_flow('current-9626-before-any-sampler','',failure=True)
run_flow('native-retained-unknown-with-success-looking-text',POSITIVE+'m4rch gfx-native-idle-cycle-startup-retained: malformed fields\n','startup-outcome-unqualified')
run_flow('old-native-retained-ready-refused',POSITIVE.replace('gfx-native-idle-cycle-session','gfx-native-retained-cycle-session'),'startup-outcome-unqualified')

LIVE=ROOT/'out/gfx-native-retained-cycle/candidate/asc-graph-init/boot-96264748-b049-403f-9240-975716f71d0c/resident-operations/20261009T222016.219857Z-gfx-powergate-229fe379'
actual_before=(LIVE/'dmesg-before.log').read_text();actual_after=(LIVE/'dmesg-after.log').read_text()
NATIVE=contract.log_delta(actual_before,actual_after)

def state(**changes):
    value=dict(boot_id='offline-retained',candidate_module_sha256='unused',resident_session_active=True,
        powergate_ready=True,operation_failed=True,powergate_attempted=False,retained_cycle_attempted=False,
        submit_attempted=False,in_flight=None,family=contract.FAMILY_KEY,operation_uncertain=False,first_off_proof=None)
    value.update(changes);return value
check('old-command-name-refused',lambda:resident.admit_command('gfx-native-retained-cycle',receipt,state()),False)
check('new-cycle-before-firstOFF-refused',lambda:resident.admit_command('gfx-native-idle-cycle',receipt,state()),False)

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
block=block.replace('gfx-retained-cycle','gfx-native-idle-cycle')
exec(compile(block,str(RETAINED_TEST),'exec'),globals())

source_receipt=ROOT/'out/gfx-native-idle-cycle/prepared-owner-v1/native-idle-cycle-owner-source-receipt.json'
source_profile=json.loads(source_receipt.read_text())
check('actual-new-native-source-profile-qualified',lambda:finalizer.check_source_profile(source_profile),True)
for key in ('pre_on_known_statuses','post_on_known_statuses',
    'status6d_requires_second_on_complete_and_second_ref','pre_on_status6d_refused',
    'stage_specific_start_admission','version'):
    changed=copy.deepcopy(source_profile);changed['profile'][key]=None
    check('new-native-idle-source-profile-refuses-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
for key,value in [('pre_on_known_statuses',['0x6a','0x6c','0x6d']),
    ('post_on_known_statuses',['0x6a','0x6c']),
    ('status6d_requires_second_on_complete_and_second_ref',False)]:
    changed=copy.deepcopy(source_profile);changed['profile'][key]=value
    check('weakened-native-idle-source-stage-refused-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
owner_qualification=ROOT/'out/gfx-native-idle-cycle/owner-qualification-final-v1.json'
actual_owner=finalizer.check_qualification(owner_qualification)
check('actual-native-owner-source-and-bounded-log-qualification',lambda:finalizer.check_owner_qualification(actual_owner,source_profile,source_receipt),True)
for key,value in [('new_log_rows_bounded',False),('maximum_new_log_row_bytes',512),
    ('maximum_new_log_row_bytes',0),('maximum_new_log_row_bytes',True),
    ('actual_receive_worker',False),('source_receipt_sha256','0'*64)]:
    changed=copy.deepcopy(actual_owner);changed[key]=value
    check('native-owner-qualification-refuses-'+key+'-'+str(value),lambda c=changed:finalizer.check_owner_qualification(c,source_profile,source_receipt),False)
for key in ('stage_specific_start_guards_exercised','actual_observed_6c_to_paired_on_to_6d_sequence_simulated'):
    changed=copy.deepcopy(actual_owner);changed[key]=False
    check('native-idle-qualification-refuses-missing-actual-stage-replay-'+key,lambda c=changed:finalizer.check_owner_qualification(c,source_profile,source_receipt),False)
with tempfile.TemporaryDirectory(prefix='native-retained-preflight-candidate-') as directory:
    work=Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
    for name,data in [('asc-graph-init.ko',b'owner'),('source.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]:
        (work/'asc-graph-init'/name).write_bytes(data)
    fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')};fixture['graph_source_sha256']={'source.h':sha(b'source')}
    fixture['graph_fixture_sha256'],fixture['graph_receipt_sha256']=sha(b'graph'),sha(b'layout')
    rpath=work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
    prep={'schema':'m4rch.gfx-native-idle-cycle-preparation.v1','candidate_receipt_sha256':sha(rpath.read_bytes()),
        'selected_next_hardware_candidate':True,'hardware_actions':[],'owner_sha256':sha(b'owner'),
        'inputs':[{'path':str(source_receipt),'sha256':sha(source_receipt.read_bytes())}],'analysis_input_pins':[]}
    ppath=work/'native-idle-cycle-preparation.json';ppath.write_text(json.dumps(prep))
    check('actual-new-native-preflight-metadata-qualified',lambda:preflight.validate_candidate(work),True)
    ppath.write_text(json.dumps(dict(prep,schema='m4rch.gfx-native-retained-cycle-preparation.v1')))
    check('actual-native-preflight-prior-schema-refused',lambda:preflight.validate_candidate(work),False)

bound=[Path(__file__),HERE/'idle_cycle_wrapper.py',HERE/'gfx_native_idle_cycle_contract.py',HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',source_receipt,owner_qualification,BASE_RECEIPT,BASE_TEST,RETAINED_TEST,COLD_TEST,ADT,OBSERVED_LAYOUT,OLD_Q]
bound += [KIT/'gfx-native-retained-cycle'/name for name in ('gfx_native_retained_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','native_retained_wrapper.py','test-native-retained-runners.py')]
bound += [LIVE/name for name in ('attempt.json','dmesg-before.log','dmesg-after.log','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json')]
result=dict(schema='m4rch.gfx-native-idle-cycle-wrapper-qualification.v1',passed=True,hardware_access=False,
    case_count=len(cases),cases=cases,actual_main_flow_count=len(flow_results),actual_main_flows=flow_results,
    actual_resident_main_flow_count=len(resident_flows),actual_resident_main_flows=resident_flows,
    frozen_retained_wrapper_case_count_composed=69,frozen_retained_cold_flows_composed=4,
    frozen_retained_resident_flows_composed=10,first_off_predicates_delegate_frozen=True,
    inputs=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in bound],
    transformed_cold_runner_sha256=sha(root.runner_source().encode()),transformed_resident_runner_sha256=sha(resident.runner_source().encode()),
    limits=['All system reads/processes/command writes are intercepted in RAM; saved9626 data is copied only.',
        'The native paired-ON/START guards are qualified by the separate actual C/header replay.',
        'Mocked new command success is no HELLO/map/ACK/secondOFF or restart proof.',
        'Frozen69/4/10 wrapper qualification is composed through exact pins without repeating unchanged negative capture/syscall cases.'])
output=ROOT/'out/gfx-native-idle-cycle/wrapper-qualification-final-v2.json'
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'output':str(output.relative_to(ROOT)),'case_count':len(cases),'actual_cold_main_flows':len(flow_results),'actual_resident_main_flows':len(resident_flows),'sha256':sha(output.read_bytes()),'hardware_access':False}))
layout_directory.cleanup()
