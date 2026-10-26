#!/usr/bin/env python3
"""Targeted actual drain-family wrappers in RAM; compose frozen prior coverage."""
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

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(KIT))
import gfx_native_powergate_drain_contract as contract
from adt import parse
from linux_dt_contract import encoded_layout

def sha(data): return hashlib.sha256(data).hexdigest()
def module(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
def check(label,function,accepted):
    try: actual = function() is not False
    except (ValueError,KeyError,OSError): actual = False
    assert actual is accepted,label
    cases.append({'case':label,'passed':True})
def replace_one(source,old,new):
    assert source.count(old) == 1,old
    return source.replace(old,new,1)

BASE_RECEIPT = ROOT/'out/gfx-coordinate-native-status/candidate/asc-root-envelope/build-receipt.json'
BASE_WRAPPER_Q = ROOT/'out/gfx-native-powergate/wrapper-qualification.json'
BASE_TEST = KIT/'gfx-native-powergate/test-powergate-runners.py'
COLD_TEST = KIT/'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA = '7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT = ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
OBSERVED_LAYOUT = ROOT/'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
assert sha(BASE_RECEIPT.read_bytes()) == '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_WRAPPER_Q.read_bytes()) == 'd0f27bceb4ccc535b1126ca895b66ac9536d8c0a24dde43623db6c2d9c4515ab'
assert sha(BASE_TEST.read_bytes()) == 'd500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
receipt = json.loads(BASE_RECEIPT.read_text())
receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY] = copy.deepcopy(contract.CONTRACT)
root = module('drain_actual_cold',HERE/'run-root-powergate.py')
resident = module('drain_actual_resident',HERE/'run-powergate.py')
preflight = module('drain_actual_preflight',HERE/'preflight-fresh.py')
finalizer = module('drain_actual_finalizer',HERE/'finalize-powergate.py')
cases,flow_results = [],[]
check('canonical-drain-family',lambda:contract.validate_receipt(receipt),True)
check('same-cold-only-parameters',lambda:root.owner_parameters(receipt,graph=True) == ['run_gate=2','observe_ms=5000','resident_session=1'],True)
assert resident.COMMANDS == contract.COMMANDS == ('sample','gfx-snapshot','gfx-powergate')
for family in ('gfx_native_powergate_scope','gfx_native_status_execution_scope'):
    changed = copy.deepcopy(receipt); changed['graph_recovery_trial'][family] = {}
    check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in ('nominal_admission_deadline_ms','maximum_admission_wait_polls','maximum_admission_rx_messages',
            'maximum_successful_admission_rx_messages','stale_ep0_refused'):
    changed = copy.deepcopy(receipt); changed['graph_recovery_trial'][contract.FAMILY_KEY][key] = None
    check('changed-drain-operand-'+key,lambda r=changed:contract.validate_receipt(r),False)
for path,function in [('run-root-powergate.py','owner_parameters'),('run-powergate.py','admit_command')]:
    old = runpy.run_path(str(KIT/'gfx-native-powergate'/path))
    check('old-powergate-refuses-'+function,
          (lambda:old[function](receipt,graph=True)) if function == 'owner_parameters' else
          (lambda:old[function]('sample',receipt,{})),False)
for boot in contract.REFUSED_BOOTS:
    check('fresh-boot-refused-'+boot,lambda b=boot:preflight.qualify_fresh_boot(b,''),False)
    check('resident-validation-refused-before-native-'+boot,lambda b=boot:resident.validate(Path('/tmp/nonexistent-drain-fixture'),b),False)
    reads = []
    real_text = Path.read_text
    def native_text(path,*args,**kwargs):
        if str(path).startswith(('/proc/','/sys/')):
            reads.append(str(path))
            assert str(path) in ('/proc/sys/kernel/random/boot_id','/proc/modules')
            return boot if str(path).endswith('boot_id') else ''
        return real_text(path,*args,**kwargs)
    with patch.object(Path,'read_text',native_text), patch.object(preflight.sys,'argv',['preflight-fresh.py','/tmp/drain-unselected','/tmp/no-drain-output']), patch.object(preflight,'validate_candidate',lambda p:(_ for _ in ()).throw(AssertionError('Candidate validation before boot refusal'))):
        check('actual-preflight-main-refuses-before-candidate-'+boot,preflight.main,False)
    assert reads == ['/proc/sys/kernel/random/boot_id','/proc/modules']
check('fresh-boot-without-owner-admitted',lambda:preflight.qualify_fresh_boot('offline-drain-new',''),True)
check('fresh-boot-owner-conflict-refused',lambda:preflight.qualify_fresh_boot('offline-drain-new','asc_graph_init 0 1 - Live 0\n'),False)

# Compose the previously bound196 wrapper cases; do not replay all unchanged cases.
original_wrapper = finalizer.check_qualification(BASE_WRAPPER_Q)
assert original_wrapper['case_count'] == 196 and original_wrapper['actual_main_flow_count'] == 45
cases.append({'case':'frozen196-wrapper-cases-bound-without-repetition','passed':True})

# Reuse only the frozen full cold-main fixture construction, then exercise changed
# family/boot/prefix boundaries and a small set of unchanged critical gates.
saved = BASE_TEST.read_text()
setup = saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index('for label, log in [(\'diagnostic0-status0\'',saved.index('adt_raw = ADT.read_bytes()'))]
setup = setup.replace("contract.REFUSED_BOOT if label == 'current-94cb-before-any-sampler' else", "contract.REFUSED_BOOTS[0] if label == 'current-94cb-before-any-sampler' else contract.REFUSED_BOOTS[1] if label == 'current-d841-before-any-sampler' else")
setup = setup.replace("('current-94cb-before-any-sampler', 'graph-receipt-pin-before-any-sampler')", "('current-94cb-before-any-sampler', 'current-d841-before-any-sampler', 'graph-receipt-pin-before-any-sampler')")
setup = setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-native-powergate-drain-session: ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
for label,log in [('drain-diagnostic0',POSITIVE),('drain-healthy2',positive(cycles=2,failed=0))]: run_flow(label,log,'positive')
run_flow('current-94cb-before-any-sampler','',failure=True)
run_flow('current-d841-before-any-sampler','',failure=True)
run_flow('drain-unknown-with-success-looking-text',POSITIVE+'m4rch gfx-native-powergate-drain-startup-retained: malformed fields\n','startup-outcome-unqualified')
run_flow('old-marker-refused',POSITIVE.replace('gfx-native-powergate-drain-session','gfx-native-powergate-session'),'startup-outcome-unqualified')
run_flow('drain-work-marker-refused',POSITIVE.replace('startup_work_submitted=0','startup_work_submitted=1'),'startup-outcome-unqualified')
run_flow('drain-owner-note-mismatch',POSITIVE,failure=True,note=b'changed')
run_flow('drain-graph-metadata-before-any-sampler','',failure=True,mutate_linux=True)

def state(**changes):
    value = dict(resident_session_active=True,powergate_ready=True,operation_failed=True,
                 powergate_attempted=False,submit_attempted=False,in_flight=None,
                 family=contract.FAMILY_KEY,operation_uncertain=False)
    value.update(changes);return value
for name in ('stop','gfx-poweroff','recover','control','trace-off','submit','gfx-reset','restart'):
    check('no-alternate-command-'+name,lambda c=name:resident.admit_command(c,receipt,state()),False)
for failure in (None,'open','short','delivered-error','interrupt'):
    with tempfile.TemporaryDirectory(prefix='drain-durable-intent-') as directory:
        out = Path(directory); sp = out/'state.json'; current = state(); report = {'validated_build_receipt':receipt,'commands':[]}; calls = []
        real_open,real_write,real_close = resident.os.open,resident.os.write,resident.os.close
        def fake_open(path,flags,*args):
            if Path(path) != resident.SYSFS/'command': return real_open(path,flags,*args)
            saved_state = json.loads(sp.read_text()); saved_report = json.loads((out/'attempt.json').read_text())
            assert saved_state['powergate_attempted'] and saved_state['in_flight']['command'] == 'gfx-powergate'
            assert saved_report['commands'][0]['stage'] == 'intent-recorded' and saved_report['reboot_required']
            calls.append('open')
            if failure == 'open': raise OSError('RAM open failure')
            return 123456
        def fake_write(fd,payload):
            if fd != 123456: return real_write(fd,payload)
            assert payload == b'gfx-powergate\n';calls.append('write')
            if failure == 'delivered-error': raise OSError('RAM possibly delivered failure')
            if failure == 'interrupt': raise KeyboardInterrupt()
            return len(payload)-(failure == 'short')
        def fake_close(fd):
            if fd != 123456: real_close(fd)
        with patch.object(resident.os,'open',fake_open),patch.object(resident.os,'write',fake_write),patch.object(resident.os,'close',fake_close):
            try:
                resident.command('gfx-powergate',out,report,current,sp); assert failure is None
            except (OSError,ValueError,KeyboardInterrupt): assert failure is not None
        stored = json.loads(sp.read_text());assert stored['powergate_attempted'] and stored['in_flight'] is None
        assert calls.count('open') == 1 and calls.count('write') <= 1
        check('durable-terminal-never-repeat-'+str(failure),lambda:resident.admit_command('gfx-powergate',receipt,stored),False)
        for name in ('sample','gfx-snapshot'):check('durable-diagnostics-'+str(failure)+'-'+name,lambda c=name:resident.admit_command(c,receipt,stored),True)

# Actual resident validate/main flows remain intercepted. Select the established
# fixture block; it validates notes/pins and exercises durable main/history/capture.
resident_setup = saved[saved.index("with tempfile.TemporaryDirectory(prefix='powergate-resident-validation-')"):saved.index('# Actual candidate metadata and qualification readers reject changed pins.')]
resident_setup = resident_setup.replace("prefix='powergate-resident-validation-'","prefix='drain-resident-validation-'")
exec(compile(resident_setup,str(BASE_TEST),'exec'),globals())

# Metadata family and exact source-profile binding are newly qualified here.
source_receipt = ROOT/'out/gfx-native-powergate-drain/prepared-owner-v2/powergate-drain-owner-source-receipt.json'
source = json.loads(source_receipt.read_text())
check('actual-new-source-profile-bound',lambda:finalizer.check_source_profile(source),True)
for key in ('nominal_admission_deadline_ms','maximum_admission_wait_polls','maximum_admission_rx_messages','maximum_successful_admission_rx_messages','stale_ep0_refused'):
    changed = copy.deepcopy(source);changed['profile'][key] = None
    check('source-profile-refuses-'+key,lambda s=changed:finalizer.check_source_profile(s),False)
with tempfile.TemporaryDirectory(prefix='drain-preflight-candidate-') as directory:
    work = Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
    for name,data in [('asc-graph-init.ko',b'owner'),('test.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]: (work/'asc-graph-init'/name).write_bytes(data)
    fixture = copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')};fixture['graph_source_sha256']={'test.h':sha(b'source')}
    fixture['graph_fixture_sha256'],fixture['graph_receipt_sha256'] = sha(b'graph'),sha(b'layout')
    rpath = work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
    prep = {'schema':'m4rch.gfx-native-powergate-drain-preparation.v1','candidate_receipt_sha256':sha(rpath.read_bytes()),'selected_next_hardware_candidate':True,'hardware_actions':[],'owner_sha256':sha(b'owner'),'inputs':[{'path':str(source_receipt),'sha256':sha(source_receipt.read_bytes())}],'analysis_input_pins':[]}
    ppath = work/'powergate-drain-preparation.json';ppath.write_text(json.dumps(prep))
    check('actual-new-preflight-candidate-admitted',lambda:preflight.validate_candidate(work),True)
    ppath.write_text(json.dumps(dict(prep,schema='m4rch.gfx-native-powergate-preparation.v1')))
    check('old-preparation-schema-refused',lambda:preflight.validate_candidate(work),False)
    ppath.write_text(json.dumps(prep));changed=copy.deepcopy(fixture);changed['graph_recovery_trial'][contract.FAMILY_KEY]['nominal_admission_deadline_ms']=12;rpath.write_text(json.dumps(changed))
    check('changed-final-receipt-drain-bound-refused',lambda:preflight.validate_candidate(work),False)

bound = [Path(__file__),HERE/'frozen_wrapper.py',HERE/'gfx_native_powergate_drain_contract.py',HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',HERE/'gfx-native-powergate-drain.h',HERE/'prepare-powergate-drain-owner.py',source_receipt,BASE_WRAPPER_Q,BASE_TEST,BASE_RECEIPT,COLD_TEST,ADT,OBSERVED_LAYOUT] + [KIT/'gfx-native-powergate'/name for name in ('gfx_native_powergate_contract.py','run-root-powergate.py','run-powergate.py','preflight-fresh.py')]
result = {'schema':'m4rch.gfx-native-powergate-drain-wrapper-qualification.v1','passed':True,'hardware_access':False,'case_count':len(cases),'cases':cases,
    'actual_main_flow_count':len(flow_results),'actual_main_flows':flow_results,'frozen_wrapper_case_count_composed':196,'frozen_full_cold_main_flows_composed':45,
    'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in bound],
    'transformed_cold_runner_sha256':sha(root.runner_source().encode()),'transformed_resident_runner_sha256':sha(resident.runner_source().encode()),
    'transformed_selected_cold_mock_sha256':sha(flow_source.encode()),
    'limits':['All system reads/processes/command writes intercepted in RAM; no GPU operation.','Prior196/45 flow qualification is composed through exact pins rather than exhaustively repeated.','The cold fixture elides optional raw owned/journal decoding.','Host syscall success is no native ACK, CPU stop, OFF, retirement or restart proof.']}
output = ROOT/'out/gfx-native-powergate-drain/wrapper-qualification.json';output.parent.mkdir(parents=True,exist_ok=True)
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'output':str(output.relative_to(ROOT)),'sha256':sha(output.read_bytes()),'case_count':len(cases),'actual_main_flow_count':len(flow_results),'hardware_access':False}))
layout_directory.cleanup()
