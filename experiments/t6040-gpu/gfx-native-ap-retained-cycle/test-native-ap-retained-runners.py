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
import gfx_native_ap_retained_cycle_contract as contract
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
OLD_Q=ROOT/'out/gfx-native-running-cycle/wrapper-qualification-final-v2.json'
assert sha(BASE_RECEIPT.read_bytes())=='2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_TEST.read_bytes())=='d500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
assert sha(RETAINED_TEST.read_bytes())=='fcaedb8f010b1f62be555c0efdef28aba2809aa04e8d2dcf3c96856d72b8da9c'
assert sha(OLD_Q.read_bytes())=='bc0a8396c901708854a9036573e54ed52d72d6e21490933170078e3276716d60'
receipt=json.loads(BASE_RECEIPT.read_text());receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
root=module('native_retained_actual_cold',HERE/'run-root-powergate.py')
resident=module('native_retained_actual_resident',HERE/'run-powergate.py')
preflight=module('native_retained_actual_preflight',HERE/'preflight-fresh.py')
finalizer=module('native_retained_actual_finalizer',HERE/'finalize-powergate.py')
check('canonical-native-idle-cycle-family',lambda:contract.validate_receipt(receipt),True)
check('cold-parameters-unchanged',lambda:root.owner_parameters(receipt,graph=True)==['run_gate=2','observe_ms=5000','resident_session=1'],True)
assert resident.COMMANDS==contract.COMMANDS==('sample','gfx-snapshot','gfx-powergate','gfx-native-ap-retained-cycle')
for family in ('gfx_native_running_cycle_scope','gfx_native_idle_cycle_scope','gfx_native_retained_cycle_scope'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][family]={}
    check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in ('version','retained_cycle_boot_running_message','retained_cycle_host_power_requests_maximum',
 'cold_ap_power_request','cold_ap_power_reply','cold_ap_exact_owned_reply_required_before_root_publication',
 'retained_ap_state_required_before_second_pm_get','retained_ap_state_preserved_across_management202',
 'retained_ap_unknown_state_refused','retained_ap_skip_intent_maximum','retained_ap_skip_requires_exact_fresh_running',
 'retained_ap_skip_guarded_before_and_after_logging','retained_ap_skip_is_fresh_reply',
 'retained_ap_skip_and_cold_proof_required_before_second202','retained_ap_skip_reserved_ack_journal_slots',
 'retained_ap_native_runtime_flags_observed','retained_ap_b201_or_b0_admitted'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=None
    check('changed-ap-retained-policy-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
assert contract.CONTRACT['retained_cycle_pre_paired_on_status48_values']==[106,108]
assert contract.CONTRACT['retained_cycle_post_paired_on_status48_values']==[106,108,109]
assert contract.CONTRACT['retained_cycle_maximum_protocol_records']==16
for key,value in [('retained_cycle_host_power_requests_maximum',1),('retained_ap_skip_is_fresh_reply',True),
 ('retained_ap_skip_and_cold_proof_required_before_second202',False),('retained_ap_b201_or_b0_admitted',True)]:
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=value
    check('weakened-ap-retained-policy-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
old=runpy.run_path(str(KIT/'gfx-native-running-cycle/run-powergate.py'),run_name='old_family_readonly')
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
assert oldq['case_count']==102 and oldq['actual_main_flow_count']==4 and oldq['actual_resident_main_flow_count']==10
cases.append({'case':'frozen102-native-running-wrapper-cases-composed-without-repetition','passed':True})
# The first native OFF parser is the actual frozen function, not a reimplementation.
import gfx_native_idle_cycle_contract as original_contract
assert contract.qualify_first_off_logs is original_contract.qualify_first_off_logs
assert contract.log_delta is original_contract.log_delta
cases.append({'case':'first-off-native-predicates-and-log-join-delegate-byteexact-frozen-code','passed':True})

saved=BASE_TEST.read_text()
setup=saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index("for label, log in [('diagnostic0-status0'",saved.index('adt_raw = ADT.read_bytes()'))]
setup=setup.replace("contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else", "contract.REFUSED_BOOTS[5] if label == 'current-54e2-before-any-sampler' else contract.REFUSED_BOOTS[0] if label == 'current-94cb-before-any-sampler' else")
setup=setup.replace("('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler')", "('current-54e2-before-any-sampler','current-94cb-before-any-sampler','graph-receipt-pin-before-any-sampler')")
setup=setup.replace("contract.REFUSED_BOOTS[5] if label == 'current-54e2-before-any-sampler' else", "contract.REFUSED_BOOTS[-1] if label == 'current-df540-before-any-sampler' else contract.REFUSED_BOOTS[5] if label == 'current-54e2-before-any-sampler' else")
setup=setup.replace("('current-54e2-before-any-sampler','current-94cb-before-any-sampler',","('current-df540-before-any-sampler','current-54e2-before-any-sampler','current-94cb-before-any-sampler',")
setup=setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-native-ap-retained-cycle-session: ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
COLD_AP='m4rch gfx-native-ap-retained-cold: phase=request request_attempted=1 request_write_attempted=0 request_message=0xb0000000000020 request_metadata=0 reply_observed=0 reply_message=0 reply_metadata=0 ap_remote_state=0 ap_remote_known=0\n'+'m4rch gfx-native-ap-retained-cold: phase=reply request_attempted=1 request_write_attempted=1 request_message=0xb0000000000020 request_metadata=0 reply_observed=1 reply_message=0xb0000000000020 reply_metadata=0x0010110000000000 ap_remote_state=0x20 ap_remote_known=1\n'
POSITIVE=COLD_AP+POSITIVE.replace(READY+'\n','')+READY+'\n'
run_flow('native-retained-diagnostic0',POSITIVE,'positive')
run_flow('current-54e2-before-any-sampler','',failure=True)
run_flow('current-df540-before-any-sampler','',failure=True)
run_flow('native-retained-unknown-with-success-looking-text',POSITIVE+'m4rch gfx-native-ap-retained-cycle-startup-retained: malformed fields\n','startup-outcome-unqualified')
run_flow('old-native-retained-ready-refused',POSITIVE.replace('gfx-native-ap-retained-cycle-session','gfx-native-idle-cycle-session'),'startup-outcome-unqualified')
run_flow('immediate-v10-ready-refused',POSITIVE.replace('gfx-native-ap-retained-cycle-session','gfx-native-running-cycle-session'),'startup-outcome-unqualified')
run_flow('cold-reply-after-root-refused',POSITIVE.replace(COLD_AP,'').replace(READY,COLD_AP+READY),'startup-outcome-unqualified')
for label,cold in [('missing', ''),('duplicate',COLD_AP+COLD_AP),
 ('wrong-reply-fullword',COLD_AP.replace('reply_message=0xb0000000000020','reply_message=0xb0000000000120')),
 ('invalid-metadata',COLD_AP.replace('reply_metadata=0x0010110000000000','reply_metadata=0xffffffffffffffff')),
 ('extra-field',COLD_AP.replace('phase=reply ','phase=reply invented=1 ')),
 ('wrong-endpoint',COLD_AP.replace('reply_metadata=0x0010110000000000','reply_metadata=0x0010110000000001')),
 ('unowned-reply',COLD_AP.replace('phase=reply request_attempted=1','phase=reply request_attempted=0')),
 ('not-written',COLD_AP.replace('request_write_attempted=1','request_write_attempted=0')),
 ('unknown-mirror',COLD_AP.replace('ap_remote_known=1','ap_remote_known=0')),
 ('wrong-state',COLD_AP.replace('ap_remote_state=0x20','ap_remote_state=0x21')),
 ('reversed', '\n'.join(reversed(COLD_AP.strip().splitlines()))+'\n')]:
 run_flow('cold-ap-'+label,POSITIVE.replace(COLD_AP,cold),'startup-outcome-unqualified')


LIVE=ROOT/'out/gfx-native-running-cycle/candidate/asc-graph-init/boot-df540c1c-5ec4-44f5-894c-37be6c2f3527/resident-operations/20261010T071532.196651Z-gfx-powergate-b454aab3'
actual_before=(LIVE/'dmesg-before.log').read_text();actual_after=(LIVE/'dmesg-after.log').read_text()
NATIVE=contract.log_delta(actual_before,actual_after)

def state(**changes):
    value=dict(boot_id='offline-retained',candidate_module_sha256='unused',resident_session_active=True,
        powergate_ready=True,operation_failed=True,powergate_attempted=False,retained_cycle_attempted=False,
        submit_attempted=False,in_flight=None,family=contract.FAMILY_KEY,operation_uncertain=False,first_off_proof=None)
    value.update(changes);return value
check('old-command-name-refused',lambda:resident.admit_command('gfx-native-idle-cycle',receipt,state()),False)
check('new-cycle-before-firstOFF-refused',lambda:resident.admit_command('gfx-native-ap-retained-cycle',receipt,state()),False)

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
block=block.replace('gfx-retained-cycle','gfx-native-ap-retained-cycle')
exec(compile(block,str(RETAINED_TEST),'exec'),globals())

source_receipt=ROOT/'out/gfx-native-ap-retained-cycle/prepared-owner-v2/native-ap-retained-cycle-owner-source-receipt.json'
source_profile=json.loads(source_receipt.read_text())
check('actual-new-native-source-profile-qualified',lambda:finalizer.check_source_profile(source_profile),True)
profile_keys=('cold_owned_ap_on_request','cold_exact_ap_on_reply','cold_ap_state_wire',
 'maximum_cold_ap_polls','nominal_cold_ap_timeout_ms','cold_ap_on_exact_request_reply_required_before_root_publication',
 'cold_ap_on_fresh_rx_empty_tx_available_before_and_after_intent','cold_ap_on_late_or_pending_reply_refused',
 'cold_ap_mirror_required_before_second_pm_get','cold_ap_mirror_preserved_through_management_only_202',
 'retained_ap_unknown_state_refused','second_host_on_requests_maximum','second_host_on_fallback_forbidden',
 'retained_host_on_skip_intent_required','retained_host_on_skip_requires_cold_exact_ap20_and_fresh_running',
 'retained_host_on_skip_fresh_gates_after_intent_log','retained_host_on_skip_does_not_fabricate_fresh_reply',
 'second202_fresh_gates_after_intent_log','retained_ap_skip_is_experimental_management_hypothesis',
 'second_ack_reserved_journal_slots','no_ap_b201_or_b0','second_log_row_count','second_log_row_prefixes',
 'cold_ap_log_prefix','cold_ap_log_phases','version','exact_boot_running_message')
for key in profile_keys:
    changed=copy.deepcopy(source_profile);changed['profile'][key]=None
    check('new-ap-retained-source-profile-refuses-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
changed=copy.deepcopy(source_profile);changed['profile']['host_on_reply_required_before_second_202']=True
check('obsolete-fresh-HOST-profile-refused',lambda:finalizer.check_source_profile(changed),False)
for key in ('restart_allowed','dma_retirement_verified','fresh_cpu_stop_rmw_masks','no_init220_request'):
 changed=copy.deepcopy(source_profile);changed['profile'][key]=None
 check('frozen-policy-mutation-refused-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
changed=copy.deepcopy(source_profile);changed['profile']['invented_relaxation']=True
check('unknown-profile-field-refused',lambda:finalizer.check_source_profile(changed),False)
owner_qualification=ROOT/'out/gfx-native-ap-retained-cycle/owner-qualification-v2.json'
actual_owner=finalizer.check_qualification(owner_qualification)
check('actual-native-owner-source-and-bounded-log-qualification',lambda:finalizer.check_owner_qualification(actual_owner,source_profile,source_receipt),True)
for key,value in [('new_log_rows_bounded',False),('maximum_new_log_row_bytes',512),
    ('maximum_new_log_row_bytes',0),('maximum_new_log_row_bytes',True),
    ('actual_receive_worker',False),('source_receipt_sha256','0'*64)]:
    changed=copy.deepcopy(actual_owner);changed[key]=value
    check('native-owner-qualification-refuses-'+key+'-'+str(value),lambda c=changed:finalizer.check_owner_qualification(c,source_profile,source_receipt),False)
for key in ('actual_retained_ap20_skip_before202','actual_cold_power_ack','duplicate_B20_panics_in_firmware_model','actual_cold_root_publication_condition',
 'no_second_B20_path','post_skip_and_second202_intent_fresh_guards_exercised','actual_complete_six_row_groups'):
    changed=copy.deepcopy(actual_owner);changed[key]=False
    check('native-idle-qualification-refuses-missing-actual-stage-replay-'+key,lambda c=changed:finalizer.check_owner_qualification(c,source_profile,source_receipt),False)
changed=copy.deepcopy(actual_owner);changed['second_log_row_count']=5
check('native-running-qualification-refuses-incomplete-phase-row-count',lambda:finalizer.check_owner_qualification(changed,source_profile,source_receipt),False)
with tempfile.TemporaryDirectory(prefix='native-retained-preflight-candidate-') as directory:
    work=Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
    for name,data in [('asc-graph-init.ko',b'owner'),('source.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]:
        (work/'asc-graph-init'/name).write_bytes(data)
    fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')};fixture['graph_source_sha256']={'source.h':sha(b'source')}
    fixture['graph_fixture_sha256'],fixture['graph_receipt_sha256']=sha(b'graph'),sha(b'layout')
    rpath=work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
    prep={'schema':'m4rch.gfx-native-ap-retained-cycle-preparation.v1','candidate_receipt_sha256':sha(rpath.read_bytes()),
        'selected_next_hardware_candidate':True,'hardware_actions':[],'owner_sha256':sha(b'owner'),
        'inputs':[{'path':str(source_receipt),'sha256':sha(source_receipt.read_bytes())}],'analysis_input_pins':[]}
    ppath=work/'native-ap-retained-cycle-preparation.json';ppath.write_text(json.dumps(prep))
    check('actual-new-native-preflight-metadata-qualified',lambda:preflight.validate_candidate(work),True)
    ppath.write_text(json.dumps(dict(prep,schema='m4rch.gfx-native-idle-cycle-preparation.v1')))
    check('actual-native-preflight-prior-schema-refused',lambda:preflight.validate_candidate(work),False)

bound=[Path(__file__),HERE/'ap_retained_cycle_wrapper.py',HERE/'gfx_native_ap_retained_cycle_contract.py',HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',source_receipt,owner_qualification,BASE_RECEIPT,BASE_TEST,RETAINED_TEST,COLD_TEST,ADT,OBSERVED_LAYOUT,OLD_Q]
bound += [KIT/'gfx-native-idle-cycle'/name for name in ('gfx_native_idle_cycle_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py','idle_cycle_wrapper.py','test-native-idle-runners.py')]
bound += [LIVE/name for name in ('attempt.json','dmesg-before.log','dmesg-after.log','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json')]
result=dict(schema='m4rch.gfx-native-ap-retained-cycle-wrapper-qualification.v1',passed=True,hardware_access=False,cold_ap_startup_proof_exercised=True,
    case_count=len(cases),cases=cases,actual_main_flow_count=len(flow_results),actual_main_flows=flow_results,
    actual_resident_main_flow_count=len(resident_flows),actual_resident_main_flows=resident_flows,
    frozen_retained_wrapper_case_count_composed=102,frozen_retained_cold_flows_composed=4,
    frozen_retained_resident_flows_composed=10,first_off_predicates_delegate_frozen=True,
    inputs=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in bound],
    transformed_cold_runner_sha256=sha(root.runner_source().encode()),transformed_resident_runner_sha256=sha(resident.runner_source().encode()),
    limits=['All system reads/processes/command writes are intercepted in RAM; saveddf540 data is copied only.',
        'The native paired-ON/START guards are qualified by the separate actual C/header replay.',
        'Mocked new command success is no HELLO/map/ACK/secondOFF or restart proof.',
        'Frozen102/4/10 wrapper qualification is composed through exact pins without repeating unchanged negative capture/syscall cases.'])
output=ROOT/'out/gfx-native-ap-retained-cycle/wrapper-qualification-v1.json'
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'output':str(output.relative_to(ROOT)),'case_count':len(cases),'actual_cold_main_flows':len(flow_results),'actual_resident_main_flows':len(resident_flows),'sha256':sha(output.read_bytes()),'hardware_access':False}))
layout_directory.cleanup()
