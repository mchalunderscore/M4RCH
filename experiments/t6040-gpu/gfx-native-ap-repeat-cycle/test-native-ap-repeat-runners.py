#!/usr/bin/env python3
"""Actual intercepted host paths and C-emitted retained epoch integration."""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import struct
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;KIT=HERE.parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(KIT))
import gfx_native_ap_repeat_cycle_contract as contract
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
 cases.append(dict(case=label,passed=True))
def replace_one(text,old,new):
 assert text.count(old)==1,old
 return text.replace(old,new,1)

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--owner-qualification',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
assert not args.output.exists(),'Qualification output is immutable; choose a new version'
SOURCE_RECEIPT=args.source/'native-ap-repeat-cycle-owner-source-receipt.json'
BASE_RECEIPT=ROOT/'out/gfx-coordinate-native-status/candidate/asc-root-envelope/build-receipt.json'
BASE_TEST=KIT/'gfx-native-powergate/test-powergate-runners.py'
COLD_TEST=KIT/'gfx-native-coordinate-trial/test-coordinate-runners.py'
COLD_TEST_SHA='7a9f31d8aebc953f6ab8b24b797bb8b73fec61c3e60b607e3a17a642b525a0c3'
ADT=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt'
OBSERVED_LAYOUT=ROOT/'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
OLD_Q=ROOT/'out/gfx-native-ap-retained-cycle/wrapper-qualification-v1.json'
assert sha(BASE_RECEIPT.read_bytes())=='2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
assert sha(BASE_TEST.read_bytes())=='d500624756533c9ffe73a5045773766ba93dbcd3409f8921a69540477bb47711'
assert sha(OLD_Q.read_bytes())=='44a869162bbe382302b5f7dc78a77c084a9e90d4da1ff98051a072cf376c1686'
receipt=json.loads(BASE_RECEIPT.read_text());receipt['graph_recovery_trial'].pop('gfx_native_status_execution_scope')
receipt['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
root=module('repeat_actual_cold',HERE/'run-root-powergate.py')
resident=module('repeat_actual_resident',HERE/'run-powergate.py')
preflight=module('repeat_actual_preflight',HERE/'preflight-fresh.py')
finalizer=module('repeat_actual_finalizer',HERE/'finalize-powergate.py')
check('distinct-v12-receipt',lambda:contract.validate_receipt(receipt),True)
assert resident.COMMANDS==contract.COMMANDS
for family in ('gfx_native_ap_retained_cycle_scope','gfx_native_running_cycle_scope','gfx_native_idle_cycle_scope'):
 changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][family]={}
 check('mixed-family-refused-'+family,lambda r=changed:contract.validate_receipt(r),False)
for key in contract.CONTRACT:
 changed=copy.deepcopy(receipt);changed['graph_recovery_trial'][contract.FAMILY_KEY][key]=None
 check('contract-mutation-refused-'+key,lambda r=changed:contract.validate_receipt(r),False)
check('original137-wrapper-cases-composed',lambda:finalizer.check_qualification(OLD_Q),True)

# All three actual entry points must stop after the boot-id read on a consumed
# boot, before candidate content, module inventory, notes or device-tree reads.
for boot in contract.REFUSED_BOOTS:
 for label,owner,argv in [('cold',root,['run-root-powergate.py','/tmp/unselected-ap-repeat','--graph']),
  ('resident',resident,['run-powergate.py','/tmp/unselected-ap-repeat',contract.THIRD_COMMAND]),
  ('preflight',preflight,['preflight-fresh.py','/tmp/unselected-ap-repeat','/tmp/unwritten-ap-repeat'])]:
  reads=[]
  def rt(path,*a,**kw):
   assert str(path)=='/proc/sys/kernel/random/boot_id','Read preceded boot refusal: '+str(path)
   reads.append(str(path));return boot
  def no_read(path,*a,**kw):raise AssertionError('Content read preceded boot refusal: '+str(path))
  with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',no_read),patch.object(owner.sys,'argv',argv):
   check('actual-'+label+'-earliest-refusal-'+boot,owner.main,False)
  assert reads==['/proc/sys/kernel/random/boot_id']
  (resident_flows if label=='resident' else flow_results).append(dict(case=label+'-'+boot,accepted=False,reads=reads,passed=True))

# Read only the frozen fixture/helper setup, not its tests or output writer.
saved=BASE_TEST.read_text()
setup=saved[saved.index('adt_raw = ADT.read_bytes()'):saved.index("for label, log in [('diagnostic0-status0'",saved.index('adt_raw = ADT.read_bytes()'))]
setup=setup.replace('m4rch gfx-native-powergate-session: ','m4rch gfx-native-ap-repeat-cycle-session: epoch=1 ')
exec(compile(setup,str(BASE_TEST),'exec'),globals())
COLD_AP='m4rch gfx-native-ap-repeat-cold: phase=request epoch=1 request_attempted=1 request_write_attempted=0 request_message=0xb0000000000020 request_metadata=0 reply_observed=0 reply_message=0 reply_metadata=0 ap_remote_state=0 ap_remote_known=0\n'+'m4rch gfx-native-ap-repeat-cold: phase=reply epoch=1 request_attempted=1 request_write_attempted=1 request_message=0xb0000000000020 request_metadata=0 reply_observed=1 reply_message=0xb0000000000020 reply_metadata=0 ap_remote_state=0x20 ap_remote_known=1\n'
POSITIVE=COLD_AP+POSITIVE.replace(READY+'\n','')+READY+'\n'
run_flow('repeat-cold-exact-owned-B20',POSITIVE,'positive')
for label,log in [('cold-reply-after-root',POSITIVE.replace(COLD_AP,'').replace(READY,COLD_AP+READY)),
 ('cold-old-family',POSITIVE.replace('gfx-native-ap-repeat','gfx-native-ap-retained')),
 ('cold-crossed-epoch',POSITIVE.replace('phase=reply epoch=1','phase=reply epoch=2')),
 ('cold-missing-owned-request',POSITIVE.replace('phase=reply epoch=1 request_attempted=1','phase=reply epoch=1 request_attempted=0')),
 ('cold-false-ready',POSITIVE.replace('ready=1','ready=0')),
 ('cold-unknown-with-success',POSITIVE+'m4rch gfx-native-ap-repeat-cycle-startup-retained: malformed fields\n')]:
 run_flow(label,log,'startup-outcome-unqualified')

source_profile=json.loads(SOURCE_RECEIPT.read_text())
check('actual-source-profile',lambda:finalizer.check_source_profile(source_profile),True)
for key in finalizer.PROFILE_DELTA:
 changed=copy.deepcopy(source_profile);changed['profile'][key]=None
 check('source-profile-refuses-'+key,lambda r=changed:finalizer.check_source_profile(r),False)
ownerq=finalizer.check_qualification(args.owner_qualification)
check('actual-C-owner-qualification',lambda:finalizer.check_owner_qualification(ownerq,source_profile,SOURCE_RECEIPT),True)
epoch_pins=ownerq['successful_epoch_log_pins']
assert sorted(r['epoch'] for r in epoch_pins)==[1,2,3]
EPOCH_LOGS={};C_LOG_PATHS=[]
for row in epoch_pins:
 path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
 raw=path.read_bytes();assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
 EPOCH_LOGS[row['epoch']]=raw.decode();C_LOG_PATHS.append(path)
 check('actual-C-emitted-epoch-'+str(row['epoch'])+'-qualified',lambda e=row['epoch']:contract.qualify_first_off_logs(EPOCH_LOGS[e]) if e==1 else contract.qualify_retained_off_logs(EPOCH_LOGS[e],e),True)
for epoch in (2,3):
 log=EPOCH_LOGS[epoch];prefix=contract.SECOND_COMMAND if epoch==2 else contract.THIRD_COMMAND
 number='second' if epoch==2 else 'third'
 rows=contract.records(log,prefix)
 ack=contract.records(log,prefix+'-management')[-1][number+'_ack_message']
 final_line=next(line for line in log.splitlines(keepends=True) if 'm4rch '+prefix+': phase=retained-final ' in line)
 for label,bad in [('crossed-row-epoch',log.replace('epoch='+str(epoch),'epoch='+str(5-epoch),1)),
  ('duplicate-final',log+final_line),('stale-first-final',log.replace('m4rch '+prefix+': phase=retained-final ','m4rch gfx-native-powergate-drain: phase=paired-off-return ')),
  ('missing-own-request',log.replace('phase='+number+'-pwr-gate-intent ','phase=historical-intent ')),
  ('old-ACK-only',re.sub(r'(m4rch '+re.escape(prefix)+r'-rx: epoch='+str(epoch)+r' index=5 )',r'm4rch gfx-native-powergate-drain-rx: epoch=1 index=5 ',log)),
  ('wrong-own-ACK',log.replace(number+'_ack_message='+hex(ack),number+'_ack_message=0x70000000000020')),
  ('no-cpu-stop',log.replace(number+'_cpu_stopped=1',number+'_cpu_stopped=0')),
  ('no-owned-put',log.replace(number+'_pm_put_attempted=1',number+'_pm_put_attempted=0')),
  ('bad-accounting',log.replace(number+'_accounting_ok=1',number+'_accounting_ok=0')),
  ('application-bitmap3',log.replace('packet=0x88000100000000','packet=0x88000100000003')),
  ('missing-coordinator',log.replace('m4rch gfx-native-ap-repeat-coordinate:','m4rch unrelated-coordinate:'))]:
  assert bad!=log,label
  check('epoch'+str(epoch)+'-refuses-'+label,lambda b=bad,e=epoch:contract.qualify_retained_off_logs(b,e),False)

LIVE=ROOT/'out/gfx-native-ap-retained-cycle/candidate/asc-graph-init/boot-911ae710-78af-4702-8dfc-f4145decbd38/resident-operations/20261010T101220.043342Z-gfx-powergate-3e63fc08'
NATIVE=contract.log_delta((LIVE/'dmesg-before.log').read_text(),(LIVE/'dmesg-after.log').read_text())
# Saved backing/journal captures are fixture data only. All three control-log
# deltas come from the actual new C replay, never synthesized success rows.
E1_LOG=EPOCH_LOGS[1]

def run_resident_flow(label,mutate=None,third_success=True):
 with tempfile.TemporaryDirectory(prefix='ap-repeat-host-'+label+'-') as directory:
  work=Path(directory);graph=work/'asc-graph-init';build=work/'asc-root-envelope';session=graph/'boot-offline-repeat'
  session.mkdir(parents=True);build.mkdir()
  fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(module_image)}
  fixture['graph_source_sha256']={'source.h':sha(b'boundsource')};fixture['kernel_notes_sha256']=sha(b'kernel-note')
  (graph/'source.h').write_bytes(b'boundsource');(graph/'asc-graph-init.ko').write_bytes(module_image)
  for name in ('graph-before.bin','graph-receipt.json'):(graph/name).write_bytes((ROOT/'out/gfx-coordinate-native-status/candidate/asc-graph-init'/name).read_bytes())
  (build/'build-receipt.json').write_text(json.dumps(fixture))
  before='RAM-before\n';logs=before+POSITIVE
  (session/'dmesg-before.log').write_text(before);(session/'dmesg-after.log').write_text(logs);(session/'text.bin').write_bytes(b'qualified-text')
  original=dict(boot_id='offline-repeat',diagnostic_session_active=True,resident_session_active=False,load_returncode=0,
   module_present=True,validated_build_receipt=fixture,text_sha256=sha(b'qualified-text'),dmesg_after_sha256=sha(logs.encode()),
   dmesg_before_sha256=sha(before.encode()),root_published=True,mapping_or_publication_performed=True,commands_admitted=list(contract.COMMANDS))
  original['native_powergate_startup']=contract.qualify_powergate_startup(POSITIVE,original,0,1)
  assert original['native_powergate_startup'] is not None
  (session/'attempt.json').write_text(json.dumps(original))
  real_bytes,real_text,real_exists,real_isdir=Path.read_bytes,Path.read_text,Path.exists,Path.is_dir
  bytes_map={'/sys/kernel/notes':b'kernel-note',str(resident.MODULE/'notes/.note.gnu.build-id'):build_note}
  text_map={str(resident.MODULE/'refcnt'):'1',str(resident.MODULE/'parameters/resident_session'):'Y',str(resident.MODULE/'parameters/run_gate'):'2','/proc/sys/kernel/random/boot_id':'offline-repeat'}
  exists_map={str(resident.SYSFS/n):True for n in ('command','objects','owned','notifications')};exists_map[str(resident.MODULE)]=True
  def rb(path):
   if str(path).startswith(('/sys/','/proc/')):assert str(path) in bytes_map;return bytes_map[str(path)]
   return real_bytes(path)
  def rt(path,*a,**kw):
   if str(path).startswith(('/sys/','/proc/')):assert str(path) in text_map;return text_map[str(path)]
   return real_text(path,*a,**kw)
  def ex(path):
   if str(path).startswith(('/sys/','/proc/')):assert str(path) in exists_map;return exists_map[str(path)]
   return real_exists(path)
  def isdir(path):
   if str(path).startswith(('/sys/','/proc/')):assert path==resident.MODULE;return True
   return real_isdir(path)
  operations=session/'resident-operations';calls=[]
  real_open,real_write,real_close=resident.os.open,resident.os.write,resident.os.close
  def op(path,flags,*a):
   if Path(path)!=resident.SYSFS/'command':return real_open(path,flags,*a)
   stored=json.loads((operations/'state.json').read_text());name=stored['in_flight']['command']
   saved_report=json.loads((Path(stored['in_flight']['operation_directory'])/'attempt.json').read_text())
   assert saved_report['commands'][0]['stage']=='intent-recorded'
   if name not in ('sample','gfx-snapshot'):assert stored['powergate_attempted']
   if name in (contract.SECOND_COMMAND,contract.THIRD_COMMAND):
    assert stored['retained_cycle_attempted'] and saved_report['first_off_proof']==stored['first_off_proof']
   if name==contract.THIRD_COMMAND:
    assert stored['third_cycle_attempted'] and saved_report['second_off_proof']==stored['second_off_proof']
    resident.verify_second_off_proof(saved_report['second_off_proof'],fixture,stored)
   calls.append(('open',name));return 123456
  def wr(fd,payload):
   if fd!=123456:return real_write(fd,payload)
   calls.append(('write',payload.decode().strip()));return len(payload)
  def cl(fd):
   if fd!=123456:real_close(fd)
  def capture(destination,observed,report):
   assert observed==fixture;result={}
   for key,name in [('objects','objects-after.bin'),('owned','owned-after.bin'),('notifications','notifications-after.bin')]:
    raw=(LIVE/name).read_bytes();(destination/name).write_bytes(raw);result[key]=dict(bytes=len(raw),sha256=sha(raw))
   decoded=(LIVE/'notifications-after.json').read_bytes();(destination/'notifications-after.json').write_bytes(decoded)
   journal=json.loads(decoded);result['notifications'].update(journal['header'],authoritative_records_sha256=journal['authoritative_records_sha256'])
   name=report['requested_command'];delta=E1_LOG if name=='gfx-powergate' else EPOCH_LOGS[2] if name==contract.SECOND_COMMAND else EPOCH_LOGS[3] if name==contract.THIRD_COMMAND else ''
   captured=before+delta;(destination/'dmesg-after.log').write_text(captured);result['dmesg']=dict(sha256=sha(captured.encode()))
   return result
  def main(name,accepted=True):
   prior=len(calls)
   with patch.object(resident.sys,'argv',['run-powergate.py',str(work),name]):
    if accepted:resident.main()
    else:check(label+'-actual-main-refuses-'+name+'-'+str(len(cases)),resident.main,False)
   opens=sum(x[0]=='open' for x in calls[prior:]);assert opens==int(accepted)
   resident_flows.append(dict(case=label,command=name,accepted=accepted,opens=opens,passed=True))
  with patch.object(Path,'read_bytes',rb),patch.object(Path,'read_text',rt),patch.object(Path,'exists',ex),patch.object(Path,'is_dir',isdir),patch.object(resident.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),patch.object(resident.os,'geteuid',lambda:0),patch.object(resident.os,'open',op),patch.object(resident.os,'write',wr),patch.object(resident.os,'close',cl),patch.object(resident.subprocess,'check_output',lambda *a,**kw:before),patch.object(resident,'capture',capture),contextlib.redirect_stdout(io.StringIO()):
   main(contract.THIRD_COMMAND,False);main(contract.SECOND_COMMAND,False)
   main('gfx-powergate');main('gfx-snapshot');main(contract.SECOND_COMMAND);main('gfx-snapshot')
   stored=json.loads((operations/'state.json').read_text());first=copy.deepcopy(stored['first_off_proof']);second=copy.deepcopy(stored['second_off_proof'])
   assert first['epoch']==1 and second['epoch']==2 and len(second['raw_input_pins'])==7 and second['predecessor']==first
   if label=='positive-three-epoch-once':
    # Actual save_json/fsync and command(), with faults at the write boundary.
    # Fault attempts are kept outside the simulated operation history so each
    # isolated replay receives the same immutable, qualified E2 predecessor.
    for fault in ('open','short','delivered-error','interrupt'):
     destination=work/('third-fault-'+fault);destination.mkdir();sp=destination/'state.json'
     current=copy.deepcopy(stored);report=dict(validated_build_receipt=fixture,commands=[])
     faultcalls=[]
     def faultopen(path,flags,*a):
      if Path(path)!=resident.SYSFS/'command':return real_open(path,flags,*a)
      saved_state=json.loads(sp.read_text());saved_attempt=json.loads((destination/'attempt.json').read_text())
      assert saved_state['powergate_attempted'] and saved_state['retained_cycle_attempted'] and saved_state['third_cycle_attempted']
      assert saved_state['first_off_proof']==first and saved_state['second_off_proof']==second
      assert saved_attempt['first_off_proof']==first and saved_attempt['second_off_proof']==second
      assert saved_attempt['commands'][0]['stage']=='intent-recorded'
      faultcalls.append('open')
      if fault=='open':raise OSError('RAM-third-open-fault')
      return 654321
     def faultwrite(fd,payload):
      if fd!=654321:return real_write(fd,payload)
      assert payload==(contract.THIRD_COMMAND+'\n').encode();faultcalls.append('write')
      if fault=='delivered-error':raise OSError('RAM-third-delivery-uncertain')
      if fault=='interrupt':raise KeyboardInterrupt()
      return len(payload)-int(fault=='short')
     def faultclose(fd):
      if fd!=654321:real_close(fd)
     with patch.object(resident.os,'open',faultopen),patch.object(resident.os,'write',faultwrite),patch.object(resident.os,'close',faultclose):
      try:resident.command(contract.THIRD_COMMAND,destination,report,current,sp);assert False,'Fault expected'
      except (OSError,ValueError,KeyboardInterrupt):pass
     saved_state=json.loads(sp.read_text())
     assert saved_state['third_cycle_attempted'] and saved_state['operation_uncertain'] and not saved_state['in_flight']
     assert faultcalls.count('open')==1 and faultcalls.count('write')<=1
     for name in ('gfx-powergate',contract.SECOND_COMMAND,contract.THIRD_COMMAND):
      check('durable-third-'+fault+'-refuses-'+name,lambda n=name,s=saved_state:resident.admit_command(n,fixture,s),False)
     for name in ('sample','gfx-snapshot'):
      check('durable-third-'+fault+'-admits-'+name,lambda n=name,s=saved_state:resident.admit_command(n,fixture,s),True)
     cases.append(dict(case='actual-third-durable-fault-'+fault,passed=True,calls=faultcalls))
   if mutate:mutate(operations,stored,first,second)
   main(contract.THIRD_COMMAND,third_success)
   if third_success:
    saved=json.loads((operations/'state.json').read_text());assert saved['first_off_proof']==first and saved['second_off_proof']==second and saved['third_cycle_attempted']
    main(contract.THIRD_COMMAND,False);main(contract.SECOND_COMMAND,False);main('gfx-powergate',False);main('sample')
   else:
    assert sum(x==('write',contract.THIRD_COMMAND) for x in calls)==0
    main('sample')
   return first,second

run_resident_flow('positive-three-epoch-once')
def mutate_raw(name):
 def mutate(operations,state,first,second):
  p=Path(second['operation_directory'])/name;p.write_bytes(p.read_bytes()+b'x')
 return mutate
for name in ('attempt.json','objects-after.bin','owned-after.bin','notifications-after.bin','dmesg-after.log','dmesg-before.log','notifications-after.json'):
 run_resident_flow('changed-E2-'+name,mutate_raw(name),False)
def lost_state(operations,*unused):(operations/'state.json').unlink()
run_resident_flow('lost-durable-state',lost_state,False)
def mixed_history(operations,state,first,second):
 path=Path(second['operation_directory'])/'attempt.json';r=json.loads(path.read_text());r['schema']='m4rch.gfx-native-ap-retained-cycle-operation.v1';path.write_text(json.dumps(r))
run_resident_flow('mixed-history-schema',mixed_history,False)
def substituted_first(operations,state,first,second):
 state['second_off_proof']=first;resident.save_json(operations/'state.json',state)
run_resident_flow('first-proof-substituted-for-second',substituted_first,False)
def duplicate_history(operations,state,first,second):
 import shutil
 shutil.copytree(second['operation_directory'],operations/'duplicate-second')
run_resident_flow('duplicate-second-history',duplicate_history,False)
def interrupted(operations,state,*unused):
 state['in_flight']=dict(command=contract.THIRD_COMMAND,operation_directory='unknown');resident.save_json(operations/'state.json',state)
run_resident_flow('interrupted-third-intent',interrupted,False)
def lost_history(operations,state,first,second):
 (Path(second['operation_directory'])/'attempt.json').unlink()
run_resident_flow('lost-E2-report',lost_history,False)
def stale_cumulative(operations,state,first,second):
 path=Path(second['operation_directory']);old=json.loads((path/'attempt.json').read_text())
 raw=(path/'dmesg-before.log').read_bytes();(path/'dmesg-after.log').write_bytes(raw)
 old['final_capture']['dmesg']['sha256']=sha(raw);(path/'attempt.json').write_text(json.dumps(old))
run_resident_flow('empty-E2-delta-with-historical-success',stale_cumulative,False)

with tempfile.TemporaryDirectory(prefix='ap-repeat-preflight-metadata-') as directory:
 work=Path(directory);(work/'asc-root-envelope').mkdir();(work/'asc-graph-init').mkdir()
 for name,data in [('asc-graph-init.ko',b'owner'),('source.h',b'source'),('graph-before.bin',b'graph'),('graph-receipt.json',b'layout')]:
  (work/'asc-graph-init'/name).write_bytes(data)
 fixture=copy.deepcopy(receipt);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':sha(b'owner')}
 fixture['graph_source_sha256']={'source.h':sha(b'source')};fixture['graph_fixture_sha256']=sha(b'graph');fixture['graph_receipt_sha256']=sha(b'layout')
 rpath=work/'asc-root-envelope/build-receipt.json';rpath.write_text(json.dumps(fixture))
 prep=dict(schema='m4rch.gfx-native-ap-repeat-cycle-preparation.v1',candidate_receipt_sha256=sha(rpath.read_bytes()),
  selected_next_hardware_candidate=True,hardware_actions=[],owner_sha256=sha(b'owner'),
  inputs=[dict(path=str(SOURCE_RECEIPT.resolve()),sha256=sha(SOURCE_RECEIPT.read_bytes()))],analysis_input_pins=[])
 ppath=work/'native-ap-repeat-cycle-preparation.json';ppath.write_text(json.dumps(prep))
 check('actual-v12-preflight-metadata-positive',lambda:preflight.validate_candidate(work),True)
 for key,value in [('schema','m4rch.gfx-native-ap-retained-cycle-preparation.v1'),('owner_sha256','0'*64),
  ('candidate_receipt_sha256','0'*64),('selected_next_hardware_candidate',False),('hardware_actions',['load'])]:
  ppath.write_text(json.dumps(dict(prep,**{key:value})))
  check('actual-v12-preflight-metadata-refuses-'+key,lambda:preflight.validate_candidate(work),False)
 ppath.write_text(json.dumps(prep));(work/'asc-graph-init/source.h').write_bytes(b'changed')
 check('actual-v12-preflight-source-change-refused',lambda:preflight.validate_candidate(work),False)

bound=[Path(__file__),HERE/'ap_repeat_cycle_wrapper.py',HERE/'gfx_native_ap_repeat_cycle_contract.py',
 HERE/'run-root-powergate.py',HERE/'run-powergate.py',HERE/'preflight-fresh.py',HERE/'finalize-powergate.py',
 SOURCE_RECEIPT,args.owner_qualification,BASE_RECEIPT,BASE_TEST,COLD_TEST,ADT,OBSERVED_LAYOUT,OLD_Q,*C_LOG_PATHS]
bound += [LIVE/n for n in ('attempt.json','dmesg-before.log','dmesg-after.log','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json')]
result=dict(schema='m4rch.gfx-native-ap-repeat-cycle-wrapper-qualification.v1',passed=True,hardware_access=False,
 cold_ap_startup_proof_exercised=True,actual_c_emitted_second_and_third_logs_qualified=True,
 actual_third_main_predecessor_raw_pins_exercised=True,actual_earliest_refused_boot_guard_exercised=True,
 case_count=len(cases),cases=cases,actual_main_flow_count=len(flow_results),actual_main_flows=flow_results,
 actual_resident_main_flow_count=len(resident_flows),actual_resident_main_flows=resident_flows,
 frozen_v11_wrapper_cases_composed=137,original_cases_repeated=False,
 inputs=[dict(path=str(x.resolve()),sha256=sha(x.read_bytes()),bytes=x.stat().st_size) for x in bound],
 transformed_cold_runner_sha256=sha(root.runner_source().encode()),transformed_resident_runner_sha256=sha(resident.runner_source().encode()),
 limits=['Every system read/process/write is intercepted; C logs and frozen captures are copied into temporary RAM fixtures.',
  'Host tests prove admission/persistence/raw provenance and integrate actual C-emitted rows, not hardware repeatability.',
  'No application rejoin, rendering, DMA retirement or safe unload claim.'])
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(output=str(args.output),case_count=len(cases),actual_cold_flows=len(flow_results),actual_resident_flows=len(resident_flows),hardware_access=False)))
