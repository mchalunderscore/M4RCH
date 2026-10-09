#!/usr/bin/env python3
"""Targeted actual four-command family and saved first-OFF admission in RAM."""
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
import gfx_retained_power_cycle_contract as contract
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
COLD_TEST=KIT/'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA='7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
OBSERVED_LAYOUT=ROOT/'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
OLD_Q=ROOT/'out/gfx-native-powergate-drain/wrapper-qualification.json'
assert sha(BASE_RECEIPT.read_bytes())=='2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_TEST.read_bytes())=='d500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
assert sha(OLD_Q.read_bytes())=='af990df129fdb30dcf93c5a5d66fc78f688af9fb43399d37324d63bff1ac24ca'
receipt=json.loads(BASE_RECEIPT.read_text());receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
root=module('retained_actual_cold',HERE/'run-root-powergate.py')
resident=module('retained_actual_resident',HERE/'run-powergate.py')
preflight=module('retained_actual_preflight',HERE/'preflight-fresh.py')
finalizer=module('retained_actual_finalizer',HERE/'finalize-powergate.py')
check('canonical-retained-cycle-family',lambda:contract.validate_receipt(receipt),True)
assert resident.COMMANDS==contract.COMMANDS==('sample','gfx-snapshot','gfx-powergate','gfx-retained-cycle')
check('same-cold-only-owner-parameters',lambda:root.owner_parameters(receipt,graph=True)==['run_gate=2','observe_ms=5000','resident_session=1'],True)
for family in ('gfx_native_powergate_drain_scope','gfx_native_powergate_scope'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][family]={}
    check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in ('maximum_retained_cycle_intents','maximum_retained_cycle_pm_gets','retained_cycle_pre_start_status48',
            'retained_cycle_sends_init220','retained_cycle_publishes_root_or_context','maximum_triangle_publications'):
    changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=None
    check('changed-new-contract-operand-'+key,lambda r=changed:contract.validate_receipt(r),False)
old=runpy.run_path(str(KIT/'gfx-native-powergate-drain/run-powergate.py'),run_name='old_readonly')
for name in contract.COMMANDS:
    check('old-drain-wrapper-refuses-new-family-'+name,lambda n=name:old['admit_command'](n,receipt,{}),False)
for boot in contract.REFUSED_BOOTS:
    check('fresh-old-boot-refused-'+boot,lambda b=boot:preflight.qualify_fresh_boot(b,''),False)
    check('resident-old-boot-before-sysfs-'+boot,lambda b=boot:resident.validate(Path('/tmp/unselected-retained'),b),False)
    reads=[];real_read=Path.read_text
    def native_text(path,*args,**kwargs):
        if str(path).startswith(('/proc/','/sys/')):
            reads.append(str(path));assert str(path) in ('/proc/sys/kernel/random/boot_id','/proc/modules')
            return boot if str(path).endswith('boot_id') else ''
        return real_read(path,*args,**kwargs)
    with patch.object(Path,'read_text',native_text),patch.object(preflight.sys,'argv',['preflight-fresh.py','/tmp/unselected-retained','/tmp/unwritten-retained']),patch.object(preflight,'validate_candidate',lambda p:(_ for _ in ()).throw(AssertionError('Candidate validation preceded boot refusal'))):
        check('actual-preflight-main-old-boot-before-candidate-'+boot,preflight.main,False)
    assert reads==['/proc/sys/kernel/random/boot_id','/proc/modules']
oldq=finalizer.check_qualification(OLD_Q)
assert oldq['case_count']==94 and oldq['actual_main_flow_count']==9
cases.append({'case':'frozen94-drain-wrapper-cases-bound-without-repetition','passed':True})

# Only frozen cold fixture construction is reused; changed family/markers/boot
# and essential identity gates run through the actual new cold main.
saved=BASE_TEST.read_text()
setup=saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index("for label, log in [('diagnostic0-status0'",saved.index('adt_raw = ADT.read_bytes()'))]
setup=setup.replace("contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else", "contract.REFUSED_BOOTS[0] if label == 'current-94cb-before-any-sampler' else contract.REFUSED_BOOTS[1] if label == 'current-d841-before-any-sampler' else contract.REFUSED_BOOTS[2] if label == 'current-1686-before-any-sampler' else")
setup=setup.replace("('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler')", "('current-94cb-before-any-sampler','current-d841-before-any-sampler','current-1686-before-any-sampler','graph-receipt-pin-before-any-sampler')")
setup=setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-retained-power-cycle-session: ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
run_flow('retained-diagnostic0',POSITIVE,'positive')
run_flow('retained-healthy2',positive(cycles=2,failed=0),'positive')
run_flow('current-1686-before-any-sampler','',failure=True)
run_flow('retained-unknown-with-success-looking-text',POSITIVE+'m4rch gfx-retained-power-cycle-startup-retained: malformed fields\n','startup-outcome-unqualified')
run_flow('prior-drain-ready-refused',POSITIVE.replace('gfx-retained-power-cycle-session','gfx-native-powergate-drain-session'),'startup-outcome-unqualified')
run_flow('retained-loaded-note-mismatch',POSITIVE,failure=True,note=b'changed')

LIVE=ROOT/'out/gfx-native-powergate-drain/candidate/asc-graph-init/boot-16868560-efd7-4c98-b58d-45cb88280d46/resident-operations/20261009T204650.706839Z-gfx-powergate-2ff34a77'
actual_before=(LIVE/'dmesg-before.log').read_text();actual_after=(LIVE/'dmesg-after.log').read_text()
NATIVE=contract.log_delta(actual_before,actual_after)
check('actual-saved-first-OFF-native-predicates',lambda:contract.qualify_first_off_logs(NATIVE),True)
for label,old,new in [('busy','value=0xf000300','value=0xf000b00'),
    ('kernel-result','command=gfx-powergate operation=2 result=0','command=gfx-powergate operation=2 result=-110'),
    ('accounting','accounting_ok=1','accounting_ok=0'),('held','host_stopped=1 sealed=1','host_stopped=0 sealed=1'),
    ('ack-kind','ack_message=0x70000000000201','ack_message=0x60000000000201'),
    ('ack-endpoint','ack_metadata=0x10ef0000000000','ack_metadata=0x10ef0000000020'),
    ('cpu','cpu_stopped=1','cpu_stopped=0'),('first-on','on_complete=1','on_complete=0')]:
    assert old in NATIVE,label
    check('native-first-OFF-refuses-'+label,lambda t=NATIVE.replace(old,new):contract.qualify_first_off_logs(t),False)


def state(**changes):
    value=dict(boot_id='offline-retained',candidate_module_sha256='unused',resident_session_active=True,
        powergate_ready=True,operation_failed=True,powergate_attempted=False,retained_cycle_attempted=False,
        submit_attempted=False,in_flight=None,family=contract.FAMILY_KEY,operation_uncertain=False,first_off_proof=None)
    value.update(changes);return value
for name in ('stop','recover','control','trace-off','submit','gfx-poweroff','restart'):
    check('no-alternate-command-'+name,lambda n=name:resident.admit_command(n,receipt,state()),False)
check('cycle-before-firstOFF-refused',lambda:resident.admit_command('gfx-retained-cycle',receipt,state()),False)

with tempfile.TemporaryDirectory(prefix='retained-resident-main-') as directory:
    work=Path(directory);graph=work/'asc-graph-init';build=work/'asc-root-envelope';session=graph/'boot-offline-retained'
    session.mkdir(parents=True);build.mkdir()
    fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(module_image)}
    fixture['graph_source_sha256']={'source.h':sha(b'boundsource')};fixture['kernel_notes_sha256']=sha(b'kernel-note')
    (graph/'source.h').write_bytes(b'boundsource');(graph/'asc-graph-init.ko').write_bytes(module_image)
    for name in ('graph-before.bin','graph-receipt.json'):(graph/name).write_bytes((ROOT/'out/gfx-coordinate-native-status/candidate/asc-graph-init'/name).read_bytes())
    (build/'build-receipt.json').write_text(json.dumps(fixture))
    before='RAM-before\n';logs=before+POSITIVE
    (session/'dmesg-before.log').write_text(before);(session/'dmesg-after.log').write_text(logs);(session/'text.bin').write_bytes(b'qualified-text')
    original=dict(boot_id='offline-retained',diagnostic_session_active=True,resident_session_active=False,load_returncode=0,
        module_present=True,validated_build_receipt=fixture,text_sha256=sha(b'qualified-text'),dmesg_after_sha256=sha(logs.encode()),
        dmesg_before_sha256=sha(before.encode()),root_published=True,mapping_or_publication_performed=True,commands_admitted=list(contract.COMMANDS))
    original['native_powergate_startup']=contract.qualify_powergate_startup(POSITIVE,original,0,1)
    assert original['native_powergate_startup'] is not None
    (session/'attempt.json').write_text(json.dumps(original))
    real_bytes,real_text,real_exists,real_isdir=Path.read_bytes,Path.read_text,Path.exists,Path.is_dir
    bytes_map={'/sys/kernel/notes':b'kernel-note',str(resident.MODULE/'notes/.note.gnu.build-id'):build_note}
    text_map={str(resident.MODULE/'refcnt'):'1',str(resident.MODULE/'parameters/resident_session'):'Y',str(resident.MODULE/'parameters/run_gate'):'2','/proc/sys/kernel/random/boot_id':'offline-retained'}
    exists_map={str(resident.SYSFS/name):True for name in ('command','objects','owned','notifications')};exists_map[str(resident.MODULE)]=True
    def rb(path):
        if str(path).startswith(('/sys/','/proc/')):assert str(path) in bytes_map;return bytes_map[str(path)]
        return real_bytes(path)
    def rt(path,*args,**kwargs):
        if str(path).startswith(('/sys/','/proc/')):assert str(path) in text_map;return text_map[str(path)]
        return real_text(path,*args,**kwargs)
    def ex(path):
        if str(path).startswith(('/sys/','/proc/')):assert str(path) in exists_map;return exists_map[str(path)]
        return real_exists(path)
    def isdir(path):
        if str(path).startswith(('/sys/','/proc/')):assert path==resident.MODULE;return True
        return real_isdir(path)
    operations=session/'resident-operations';calls=[];failure=None;capture_mode='success'
    real_open,real_write,real_close=resident.os.open,resident.os.write,resident.os.close
    def op(path,flags,*args):
        if Path(path)!=resident.SYSFS/'command':return real_open(path,flags,*args)
        stored=json.loads((operations/'state.json').read_text());name=stored['in_flight']['command']
        assert stored['powergate_attempted']
        if name=='gfx-retained-cycle':
            assert stored['retained_cycle_attempted'] and stored['first_off_proof']['qualified']
            saved_report=json.loads((Path(stored['in_flight']['operation_directory'])/'attempt.json').read_text())
            assert saved_report['first_off_proof']==stored['first_off_proof']
        calls.append(('open',name))
        if failure=='open':raise OSError('RAM-open-failure')
        return 123456
    def wr(fd,payload):
        if fd!=123456:return real_write(fd,payload)
        calls.append(('write',payload.decode().strip()))
        if failure=='delivered':raise OSError('RAM-delivered-error')
        if failure=='interrupt':raise KeyboardInterrupt()
        return len(payload)-(failure=='short')
    def cl(fd):
        if fd!=123456:real_close(fd)
    def capture(destination,observed,report):
        assert observed==fixture
        result={}
        for key,name in [('objects','objects-after.bin'),('owned','owned-after.bin'),('notifications','notifications-after.bin')]:
            raw=(LIVE/name).read_bytes();(destination/name).write_bytes(raw);result[key]={'bytes':len(raw),'sha256':sha(raw)}
        decoded=(LIVE/'notifications-after.json').read_bytes();(destination/'notifications-after.json').write_bytes(decoded)
        journal=json.loads(decoded);result['notifications'].update(journal['header'],authoritative_records_sha256=journal['authoritative_records_sha256'])
        captured=before+NATIVE if report['requested_command']=='gfx-powergate' else before
        (destination/'dmesg-after.log').write_text(captured);result['dmesg']={'sha256':sha(captured.encode())}
        if capture_mode=='error':report['capture_errors'].append('RAM-only missing capture')
        return result
    def main(name,accepted=True):
        prior=len(calls)
        with patch.object(resident.sys,'argv',['run-powergate.py',str(work),name]):
            if accepted:resident.main()
            else:check('actual-resident-main-refusal-'+name+'-'+str(len(cases)),resident.main,False)
        resident_flows.append({'command':name,'accepted':accepted,'opens':sum(x[0]=='open' for x in calls[prior:]),'passed':True})
    with patch.object(Path,'read_bytes',rb),patch.object(Path,'read_text',rt),patch.object(Path,'exists',ex),patch.object(Path,'is_dir',isdir),patch.object(resident.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),patch.object(resident.os,'geteuid',lambda:0),patch.object(resident.os,'open',op),patch.object(resident.os,'write',wr),patch.object(resident.os,'close',cl),patch.object(resident.subprocess,'check_output',lambda *a,**kw:before),patch.object(resident,'capture',capture),contextlib.redirect_stdout(io.StringIO()):
        check('actual-resident-validation-positive',lambda:resident.validate(work,'offline-retained'),True)
        main('gfx-retained-cycle',False);assert not calls
        main('gfx-powergate');assert calls==[('open','gfx-powergate'),('write','gfx-powergate')]
        main('gfx-powergate',False);assert len(calls)==2
        main('gfx-snapshot')
        stored=json.loads((operations/'state.json').read_text());proof=stored['first_off_proof'];assert proof['qualified']
        assert stored['powergate_attempted'] and not stored['retained_cycle_attempted'] and not stored['operation_uncertain']
        check('actual-first-off-raw-proof-qualified',lambda:resident.verify_first_off_proof(proof,fixture,stored),True)
        firstdir=Path(proof['operation_directory']);firstreport=(firstdir/'attempt.json').read_bytes()
        for key,value in [('complete',False),('capture_errors',['missing']),('module_present',False),('operation_uncertain',True),('submit_attempted',True)]:
            changed=json.loads(firstreport);changed[key]=value;(firstdir/'attempt.json').write_text(json.dumps(changed))
            check('first-off-report-refuses-'+key,lambda:resident.first_off_proof(firstdir,fixture,stored),False)
        (firstdir/'attempt.json').write_bytes(firstreport)
        for name in ('objects-after.bin','owned-after.bin','notifications-after.bin','dmesg-after.log','dmesg-before.log','notifications-after.json'):
            path=firstdir/name;raw=path.read_bytes();path.write_bytes(raw+b'x')
            check('first-off-raw-pin-refuses-'+name,lambda:resident.verify_first_off_proof(proof,fixture,stored),False)
            path.write_bytes(raw)
        # Loss of host state before the new intent rebuilds the immutable first
        # proof; the kernel's independent once flag still controls publication.
        (operations/'state.json').unlink();main('gfx-snapshot')
        stored=json.loads((operations/'state.json').read_text());assert stored['first_off_proof']==proof and stored['powergate_attempted']
        # Actual second command is one sysfs write; synthetic terminal records
        # are not produced for it and no hardware success claim follows.
        main('gfx-retained-cycle');stored=json.loads((operations/'state.json').read_text())
        assert stored['powergate_attempted'] and stored['retained_cycle_attempted'] and stored['first_off_proof']==proof
        main('gfx-retained-cycle',False);main('gfx-powergate',False)
        (operations/'state.json').unlink();main('sample')
        rebuilt=json.loads((operations/'state.json').read_text());assert rebuilt['retained_cycle_attempted'] and rebuilt['first_off_proof']==proof
        main('gfx-retained-cycle',False)
        assert sum(x==('write','gfx-retained-cycle') for x in calls)==1
        cases.append({'case':'actual-main-lost-state-preserves-both-epoch-intents','passed':True})
        # Direct command failure coverage shares the qualified immutable first
        # proof, with distinct RAM report/state for each intent.
        for failure in ('open','short','delivered','interrupt'):
            destination=operations/('fault-'+failure);destination.mkdir();sp=destination/'state.json'
            current=state(powergate_attempted=True,first_off_proof=proof)
            current['candidate_module_sha256']=fixture['artifact_sha256'][resident.MODULE_ARTIFACT]
            report={'validated_build_receipt':fixture,'commands':[]};prior=len(calls)
            # op() reads the main state file, so bind this command's state there
            # and keep its own durable state location as the true target.
            def fault_open(path,flags,*args):
                if Path(path)!=resident.SYSFS/'command':return real_open(path,flags,*args)
                saved_state=json.loads(sp.read_text());saved_attempt=json.loads((destination/'attempt.json').read_text())
                assert saved_state['powergate_attempted'] and saved_state['retained_cycle_attempted']
                assert saved_state['first_off_proof']==proof and saved_attempt['first_off_proof']==proof
                calls.append(('open','gfx-retained-cycle'))
                if failure=='open':raise OSError('RAM-fault-open')
                return 123456
            with patch.object(resident.os,'open',fault_open):
                try:resident.command('gfx-retained-cycle',destination,report,current,sp);assert False,'Fault expected'
                except (OSError,ValueError,KeyboardInterrupt):pass
            saved_state=json.loads(sp.read_text());assert saved_state['retained_cycle_attempted'] and saved_state['powergate_attempted'] and saved_state['first_off_proof']==proof and saved_state['operation_uncertain']
            assert sum(x[0]=='open' for x in calls[prior:])==1
            check('durable-second-fault-refuses-retry-'+failure,lambda s=saved_state:resident.admit_command('gfx-retained-cycle',fixture,s),False)
            for diagnostic in ('sample','gfx-snapshot'):check('durable-second-fault-diagnostic-'+failure+'-'+diagnostic,lambda n=diagnostic,s=saved_state:resident.admit_command(n,fixture,s),True)
        failure=None

source_receipt=ROOT/'out/gfx-retained-power-cycle/prepared-owner-v4/retained-power-cycle-owner-source-receipt.json'
source_profile=json.loads(source_receipt.read_text())
check('actual-new-source-profile-qualified',lambda:finalizer.check_source_profile(source_profile),True)
for key in ('maximum_retained_cycle_pm_gets','maximum_retained_cycle_requests','exact_cold_reentry_status',
    'autonomous_endpoint_map_shape','first_epoch_evidence_immutable','no_init220_request',
    'no_application_root_publication','no_context_reattach','second_intent_seals_all_controls'):
    changed=copy.deepcopy(source_profile);changed['profile'][key]=None
    check('actual-new-source-profile-refuses-'+key,lambda c=changed:finalizer.check_source_profile(c),False)
check('first-OFF-snapshot-count-consistency',lambda:contract.qualify_first_off_logs(NATIVE.replace('snapshot_count=1','snapshot_count=2')),False)
for label,before_log,after_log in [('missing','a\nb\n','c\nd\n'),
    ('ambiguous','a\nb\n','b\nb\n'),('changed-overlap','a\nb\n','changed\nb\nc\n'),
    ('partial-line','a\nb','b\nc\n')]:
    check('exact-log-overlap-refuses-'+label,lambda b=before_log,a=after_log:contract.log_delta(b,a),False)
with tempfile.TemporaryDirectory(prefix='retained-preflight-candidate-') as directory:
    work=Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
    for name,data in [('asc-graph-init.ko',b'owner'),('source.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]:
        (work/'asc-graph-init'/name).write_bytes(data)
    fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')};fixture['graph_source_sha256']={'source.h':sha(b'source')}
    fixture['graph_fixture_sha256'],fixture['graph_receipt_sha256']=sha(b'graph'),sha(b'layout')
    rpath=work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
    prep={'schema':'m4rch.gfx-retained-power-cycle-preparation.v1','candidate_receipt_sha256':sha(rpath.read_bytes()),
        'selected_next_hardware_candidate':True,'hardware_actions':[],'owner_sha256':sha(b'owner'),
        'inputs':[{'path':str(source_receipt),'sha256':sha(source_receipt.read_bytes())}],'analysis_input_pins':[]}
    ppath=work/'retained-power-cycle-preparation.json';ppath.write_text(json.dumps(prep))
    check('actual-new-preflight-metadata-qualified',lambda:preflight.validate_candidate(work),True)
    ppath.write_text(json.dumps(dict(prep,schema='m4rch.gfx-native-powergate-drain-preparation.v1')))
    check('actual-new-preflight-old-schema-refused',lambda:preflight.validate_candidate(work),False)
    ppath.write_text(json.dumps(prep));changed=copy.deepcopy(fixture);changed['graph_recovery_trial'][contract.FAMILY_KEY]['maximum_retained_cycle_starts']=2;rpath.write_text(json.dumps(changed))
    check('actual-new-preflight-changed-contract-refused',lambda:preflight.validate_candidate(work),False)

bound=[source_receipt,Path(__file__),HERE/'retained_wrapper.py',HERE/'gfx_retained_power_cycle_contract.py',HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',BASE_RECEIPT,BASE_TEST,COLD_TEST,ADT,OBSERVED_LAYOUT,OLD_Q]
bound += [KIT/'gfx-native-powergate-drain'/name for name in ('gfx_native_powergate_drain_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py')]
bound += [LIVE/name for name in ('attempt.json','dmesg-before.log','dmesg-after.log','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json')]
result=dict(schema='m4rch.gfx-retained-power-cycle-wrapper-qualification.v1',passed=True,hardware_access=False,
    case_count=len(cases),cases=cases,actual_main_flow_count=len(flow_results),actual_main_flows=flow_results,
    actual_resident_main_flow_count=len(resident_flows),actual_resident_main_flows=resident_flows,
    frozen_drain_wrapper_case_count_composed=94,frozen_drain_full_cold_flows_composed=9,
    inputs=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in bound],
    transformed_cold_runner_sha256=sha(root.runner_source().encode()),transformed_resident_runner_sha256=sha(resident.runner_source().encode()),
    limits=['All system reads/processes/command writes are intercepted in RAM; saved1686 data is copied only.',
        'Mocked second sysfs return is no second HELLO/map/ACK/OFF proof.','Saved first OFF has separate non-atomic raw reads; current kernel identity and physical gates remain mandatory.',
        'Prior94/9 wrapper and original196/45 qualifications are composed via immutable pins.'])
output=ROOT/'out/gfx-retained-power-cycle/wrapper-qualification-final-v3.json'
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'output':str(output.relative_to(ROOT)),'case_count':len(cases),'actual_cold_main_flows':len(flow_results),'actual_resident_main_flows':len(resident_flows),'sha256':sha(output.read_bytes()),'hardware_access':False}))
layout_directory.cleanup()
