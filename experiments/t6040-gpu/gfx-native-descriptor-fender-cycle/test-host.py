#!/usr/bin/env python3
"""Focused descriptor candidate data check and one intercepted inherited host flow."""
import argparse,contextlib,copy,importlib.util,io,json,runpy,shutil,struct,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import cold_render_contract as contract
import analyze_cold_render as analyzer
from adt import parse
cases=[];flows=[];input_paths=[]
def checked(label,fn,accepted):
 try:ok=fn() is not False
 except (ValueError,KeyError,OSError,TypeError,struct.error,IndexError):ok=False
 assert ok is accepted,label;cases.append(dict(case=label,passed=True))
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def pin(path):return dict(path=str(path.resolve()),sha256=contract.sha(path.read_bytes()),bytes=path.stat().st_size)
def elf():
 note=struct.pack('<III',4,20,3)+b'GNU\0'+bytes(range(20));names=b'\0.note.gnu.build-id\0.shstrtab\0';raw=bytearray(512)
 struct.pack_into('<16sHHIQQQIHHHHHH',raw,0,b'\x7fELF\x02\x01\x01'+bytes(9),1,183,1,0,0,256,0,64,0,0,64,3,2)
 raw[64:100]=note;raw[128:128+len(names)]=names
 struct.pack_into('<IIQQQQIIQQ',raw,320,1,7,0,0,64,36,0,0,4,0);struct.pack_into('<IIQQQQIIQQ',raw,384,19,3,0,0,128,len(names),0,0,1,0)
 return bytes(raw),note
def frozen_report(path,digest,count):
 q=json.loads(path.read_text());assert contract.sha(path.read_bytes())==digest and q['passed'] and q['case_count']==count;assert q.get('hardware_access',False) is False and q.get('hardware_actions',[])==[];input_paths.append(path);return q
def fixture(spec):
 path=Path(spec['path']);raw=path.read_text();assert contract.sha(raw.encode())==spec['sha256'];input_paths.append(path);return raw

def main():
 global cycle_fixture,cycle_fixture_token,cycle_fixture_write
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--descriptor-qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();snapshot=a.output.with_name(a.output.stem+'.source');snapshot.mkdir(exist_ok=False)
 names=('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py','prepare-descriptor-owner.py','qualify-descriptors.py','README.md')
 for name in names:
  raw=(HERE/name).read_bytes();(snapshot/name).write_bytes(raw);input_paths.extend([HERE/name,snapshot/name])
 v20=ROOT/'out/gfx-native-fender-off-cycle'
 baseprep=v20/'candidate/cold-render-preparation.json';assert contract.sha(baseprep.read_bytes())=='933a9a7b731e341375a433f55e1a540b88f51fbe5c98f752fcff3f93c14c231b';input_paths.append(baseprep)
 cq=frozen_report(v20/'fender-off-qualification-v1.json','473c469f18401dc820a756527b1297c36bf7a4ffb0d43f63ae9ed413123e8705',65)
 hq=frozen_report(v20/'host-qualification-v1.json','2c752cb488921c5a94411f00255749543f4a53e762363b008ee1fd25ad99fa3a',27)
 for q in [cq,hq]:
  for r in q.get('input_pins',q.get('inputs',[])):assert contract.sha(Path(r['path']).read_bytes())==r['sha256'];input_paths.append(Path(r['path']))
 dq=json.loads(a.descriptor_qualification.read_bytes());assert dq['passed'] and dq['hardware_access'] is False and dq['hardware_actions']==[] and dq['changed_byte_count']==19;input_paths.append(a.descriptor_qualification)
 for r in dq['inputs']:assert contract.sha(Path(r['path']).read_bytes())==r['sha256'];input_paths.append(Path(r['path']))
 compiler_binary=Path(dq['commands'][0]['command'][-1]);elf_reader=runpy.run_path(str(HERE/'finalize-cold-render.py'),run_name='actual_ELF_data_check')['actual_ELF_graph_bytes'];input_paths.append(compiler_binary)
 checked('actual-ELF-graph-object-equals-corrected-arena',lambda:elf_reader(compiler_binary.read_bytes())==(a.source/'graph-before.bin').read_bytes(),True)
 log=fixture(hq['composed_pipeline_fixture']);cycle_fixture=fixture(hq['composed_cycle_fixture']);cycle_fixture_token=contract.rows(cycle_fixture,'gfx-postdraw-native-cycle')[0]['capture_token'];cfirst=next(i for i,line in enumerate(cycle_fixture.splitlines(True)) if 'm4rch gfx-postdraw-native-cycle:' in line);cycle_fixture_write=''.join(cycle_fixture.splitlines(True)[cfirst:])
 checked('actual-corrected-candidate-data',lambda:contract.validate_descriptor_data(a.source),True)
 with tempfile.TemporaryDirectory(prefix='descriptor-host-negative-') as tmp:
  negative=Path(tmp)
  for name in ('graph-before.bin','graph-receipt.json','graph-contract.h'):shutil.copyfile(a.source/name,negative/name)
  raw=bytearray((negative/'graph-before.bin').read_bytes());raw[0x86d8]=0;(negative/'graph-before.bin').write_bytes(raw)
  checked('candidate-refuses-uncorrected-descriptor-byte',lambda:contract.validate_descriptor_data(negative),False)
  shutil.copyfile(a.source/'graph-before.bin',negative/'graph-before.bin');header=(negative/'graph-contract.h').read_bytes().replace(b'[0x86d8]=0x2,',b'[0x86d8]=0x3,',1);(negative/'graph-contract.h').write_bytes(header)
  checked('candidate-refuses-different-compiled-upload-byte',lambda:contract.validate_descriptor_data(negative),False)
 root=module('focused_v21_offline_runner',HERE/'run-cold-render.py');preflight=module('v21_preflight',HERE/'preflight-fresh.py');boot='09a48fe3-925a-46d9-b99b-b9aecc71e6f3'
 for label,obj,argv in [('cold',root,['run-cold-render.py','/tmp/unselected-v21','--graph','--run']),('preflight',preflight,['preflight-fresh.py','/tmp/unselected-v21','/tmp/unwritten-v21'])]:
  reads=[]
  def rt(path,*args,**kwargs):assert str(path)=='/proc/sys/kernel/random/boot_id';reads.append(str(path));return boot
  def rb(path,*args,**kwargs):raise AssertionError('Content before consumed-boot refusal: '+str(path))
  with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',rb),patch.object(obj.sys,'argv',argv):checked('earliest-09-'+label,obj.main,False)
  assert reads==['/proc/sys/kernel/random/boot_id'];flows.append(dict(case=label+'-09-early-refusal',boot=boot,reads=reads))
 template=json.loads((v20/'candidate/asc-root-envelope/build-receipt.json').read_bytes());input_paths.append(v20/'candidate/asc-root-envelope/build-receipt.json')
 checked('reject-frozen-v20-contract-as-v21',lambda:contract.validate_receipt(template),False)
 for k in list(template['graph_recovery_trial']):
  if k.endswith('_scope'):del template['graph_recovery_trial'][k]
 template['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
 checked('distinct-v21-contract',lambda:contract.validate_receipt(template),True)
 run_flow(root,a.source,template,log,'actual-success')
 sr=a.source/'native-descriptor-fender-cycle-owner-source-receipt.json';input_paths.append(sr);assert dq['source_receipt_sha256']==contract.sha(sr.read_bytes())
 for loaded in list(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file and str(file).endswith('.py') and Path(file).resolve().is_relative_to(ROOT):input_paths.append(Path(file))
 report=dict(schema='m4rch.gfx-native-descriptor-fender-cycle-host-qualification.v1',passed=True,hardware_access=False,hardware_actions=[],case_count=len(cases),cases=cases,actual_main_flows=flows,actual_main_flow_count=1,early_refusal_flow_count=2,source_receipt_sha256=contract.sha(sr.read_bytes()),descriptor_qualification_sha256=contract.sha(a.descriptor_qualification.read_bytes()),composed_pipeline_fixture=hq['composed_pipeline_fixture'],composed_cycle_fixture=hq['composed_cycle_fixture'],inputs=[pin(p) for p in dict.fromkeys(input_paths)],composition=dict(frozen_v20_C_Fender_OFF_cases=65,frozen_v20_host_cases=27,frozen_v20_actual_main_flows=1,earlier_scopes=hq['composition'],unchanged_tests_repeated=False),selection='unselected-awaiting-v20-hardware-outcome',qualification='Changed graph/compiled-upload byte acceptance/refusals and contract join, inherited exact pipeline/cycle fixtures, 09 early refusal, one intercepted full capture-before-cycle main flow. All frozen v20 C65/host27/1 and earlier scopes composed without rerun. No hardware action or runtime execution proof.')
 with a.output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(cases=len(cases),actual_main_flows=1,early_refusals=2,output=str(a.output),sha256=contract.sha(a.output.read_bytes()))))
def run_flow(root,source,template,log,label,present=True,note=None,truncate=False,stale=False,rotate=False,overlap=False,diagnostic=False,incomplete=False,ram_failure=None,cycle_failure=None):
 module_raw,module_note=elf();note=module_note if note is None else note
 adt_path=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt';adt_raw=adt_path.read_bytes();tree=parse(adt_raw);input_paths.append(adt_path)
 with tempfile.TemporaryDirectory(prefix='cold-host-'+label+'-') as tmp:
  work=Path(tmp);graph=work/'asc-graph-init';build=work/'asc-root-envelope';graph.mkdir();build.mkdir();(work/'analysis-inputs').mkdir()
  for spec in contract.RETAINED_SAMPLERS:
   dest=work/spec['module'];dest.parent.mkdir(parents=True,exist_ok=True);origin=ROOT/'out/gfx-native-dispatch-contract/candidate'/spec['module'];shutil.copyfile(origin,dest);input_paths.append(origin)
  for name in ('graph-before.bin','graph-receipt.json','graph-contract.h','backing.bin'):shutil.copyfile(source/name,graph/name)
  shutil.copyfile(ROOT/'out/gfx-native-ap-repeat-cycle/candidate/analysis-inputs/target-receipt.json',work/'analysis-inputs/target-receipt.json')
  (graph/'asc-graph-init.ko').write_bytes(module_raw)
  fixture=copy.deepcopy(template);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':contract.sha(module_raw)};fixture['graph_source_sha256']={};fixture['kernel_notes_sha256']=contract.sha(b'kernel-note')
  fixture['graph_fixture_sha256']=contract.sha((graph/'graph-before.bin').read_bytes());fixture['graph_receipt_sha256']=contract.sha((graph/'graph-receipt.json').read_bytes())
  (build/'build-receipt.json').write_text(json.dumps(fixture));(work/'cold-render-preparation.json').write_text(json.dumps(dict(schema='m4rch.gfx-native-descriptor-fender-cycle-preparation.v1',candidate_receipt_sha256=contract.sha((build/'build-receipt.json').read_bytes()),owner_sha256=contract.sha(module_raw),inputs=[],analysis_input_pins=[],fixed_retained_RAM_samplers=list(contract.RETAINED_SAMPLERS),backing_changed_byte_count=4)))
  boot='offline-'+label;session=graph/('boot-'+boot);trace=[];cold=False;dmesg=0;sampler_present=False;active_sampler=None;post_loads=0;cycle_writes=0;cycle_token=None;cycle_log='';pre_cycle_hashes={}
  objects=bytearray((graph/'graph-before.bin').read_bytes())
  for index,offset in [(0,344064),(1,376832),(12,737280)]:
   for at in (0,8,16):struct.pack_into('<I',objects,offset+at,33 if index==12 else 1)
  owned=bytearray(174*16384);owned[112*16384:168*16384]=(graph/'backing.bin').read_bytes()
  if truncate:owned=owned[:-1]
  notifications=struct.pack('<8I4Q',0x5852474d,1,80,65536,0,0,0,0,0,0,0,0)+bytes(65536*80)
  raw_text=bytearray(0x5b800)
  for offset,word in {0x2f250:0xf9400109,0x2f264:0xeb0a013f,0x2f268:0x54003d61,0x2f2b4:0xb9402d29,0x2f2b8:0x34003b49,0x2fa2c:0x94004f40}.items():struct.pack_into('<I',raw_text,offset,word)
  needle=b'Host-mapped FW allocations are disabled';raw_text[0x5b768:0x5b768+len(needle)]=needle
  original_rb=Path.read_bytes;original_rt=Path.read_text;original_exists=Path.exists
  def rb(path):
   if str(path).startswith(('/sys/','/proc/')):
    assert not cycle_writes,'No hardware/sysfs data read after cycle intent'
    trace.append(('read-bytes',str(path),cold));values={'/sys/kernel/notes':b'kernel-note','/sys/module/asc_graph_init/notes/.note.gnu.build-id':note,'/sys/kernel/m4rch_gpu_graph_trial/objects':bytes(objects),'/sys/kernel/m4rch_gpu_graph_trial/owned':bytes(owned),'/sys/kernel/m4rch_gpu_graph_trial/notifications':notifications}
    if str(path)=='/sys/module/gpu_data_sample/notes/.note.gnu.build-id':
     assert sampler_present;raw=(work/next(x['module'] for x in contract.RETAINED_SAMPLERS if x['name']==active_sampler)).read_bytes()
     return bytes(36) if ram_failure=='sampler-note' else contract.module_build_note(raw)
    if str(path)=='/sys/kernel/m4rch_gpu_data_sample/data':
     assert cold and sampler_present
     if ram_failure=='read' and active_sampler=='data-retained.bin':raise OSError('offline DATA read failure')
     size=next(x['bytes'] for x in contract.RETAINED_SAMPLERS if x['name']==active_sampler)
     return bytes(size-1 if ram_failure=='extent' and active_sampler=='data-retained.bin' else size)
    assert str(path) in values,str(path);return values[str(path)]
   return original_rb(path)
  def rt(path,*args,**kwargs):
   if str(path)=='/sys/module/gpu_data_sample/refcnt':
    assert sampler_present;return '1' if ram_failure=='sampler-ref' else '0'
   if str(path).startswith(('/sys/','/proc/')):
    assert not cycle_writes,'No hardware/sysfs text read after cycle intent'
    trace.append(('read-text',str(path),cold));values={'/proc/sys/kernel/random/boot_id':boot,'/proc/modules':'','/proc/interrupts':'offline-interrupts','/sys/module/asc_graph_init/refcnt':'2' if ram_failure=='owner' and post_loads else '1'};assert str(path) in values,str(path);return values[str(path)]
   return original_rt(path,*args,**kwargs)
  def exists(path):
   if str(path)=='/sys/module/gpu_data_sample':return sampler_present
   if str(path).startswith('/sys/'):assert str(path)=='/sys/module/asc_graph_init';return present
   return original_exists(path)
  def capture(module,sysfile,destination,name):
   assert not cold,'No powered sampler after draw';trace.append(('sampler',destination.name,cold))
   data={'boot.adt':adt_raw,'pagetables.bin':bytes(0x40000),'text.bin':bytes(raw_text),'data-before.bin':bytes(16)}[destination.name];destination.write_bytes(data);return data
  def execute(command,**kwargs):
   nonlocal cold,sampler_present,active_sampler,post_loads,cycle_writes,cycle_token,cycle_log,pre_cycle_hashes
   trace.append(('subprocess',command,cold))
   if cold:
    if command[0]==sys.executable:
     import readback
     assert command[1:4]==['-c',readback.WRITE_ONCE_CODE,'/sys/kernel/m4rch_gpu_graph_trial/command']
     assert kwargs.get('timeout')==45 and cycle_writes==0
     cycle_writes+=1;cycle_token=command[4].split()[1]
     manifest=json.loads((session/'pre-cycle-attempt.json').read_text());assert contract.sha((session/'pre-cycle-attempt.json').read_bytes())==cycle_token
     assert readback.verify_pre_cycle(session,manifest)
     assert json.loads((session/'cycle-attempt.json').read_text())['command_intent']
     pre_cycle_hashes={r['relative']:contract.sha((session/r['relative']).read_bytes()) for r in manifest['capture_pins']}
     assert all((session/r['relative']).stat().st_mode&0o222==0 for r in manifest['capture_pins'])
     cycle_log=cycle_fixture_write.replace(cycle_fixture_token,cycle_token)
     if cycle_failure=='timeout':raise __import__('subprocess').TimeoutExpired(command,45)
     if cycle_failure=='write':return SimpleNamespace(returncode=1,stdout='',stderr='offline short/failedwrite')
     if cycle_failure=='OFF':cycle_log=cycle_log.replace('provider_off_observed=1','provider_off_observed=0')
     return SimpleNamespace(returncode=0,stdout='',stderr='')
    if command[0]=='insmod':
     spec=next((x for x in contract.RETAINED_SAMPLERS if command==['insmod',str(work/x['module'])]),None);assert spec and not sampler_present,command
     assert all((session/name).exists() for name in ('objects-after.bin','owned-after.bin','notifications-after.bin','target-after.png','dmesg-after.log'))
     durable=json.loads((session/'retained-ram-capture.json').read_text());assert durable['samplers'][-1]['load_intent']
     sampler_present=True;active_sampler=spec['name'];post_loads+=1
    else:
     assert command==['rmmod','gpu_data_sample'] and sampler_present,command
     assert json.loads((session/'retained-ram-capture.json').read_text())['samplers'][-1]['unload_intent']
     if ram_failure=='unload':return SimpleNamespace(returncode=1,stdout='',stderr='offline unload failure')
     sampler_present=False
   elif command[-1]=='resident_session=1':
    intent=json.loads((session/'attempt.json').read_text());assert intent['automatic_pipeline_intent'] and intent['operation_uncertain'] and intent['stage']=='cold-load-intent';cold=True
   return SimpleNamespace(returncode=0,stdout='',stderr='')
  def output(command,**kwargs):
   nonlocal dmesg
   assert command==['dmesg','--color=never'];dmesg+=1
   before='discarded\nshared exact overlap\n'+(log if stale else '')
   if cycle_failure=='tamper-before' and dmesg==4:
    import os
    target=session/'target-after.bin';os.chmod(target,0o644);raw=bytearray(target.read_bytes());raw[0]^=1;target.write_bytes(raw)
   if cycle_writes:return before+log+cycle_log
   return before if dmesg==1 else 'shared exact overlap\n'+log if overlap else 'rotated\n'+log if rotate else before if stale else before+log
  with contextlib.ExitStack() as stack:
   for obj,name,value in [(root.sys,'argv',['run-cold-render.py',str(work),'--graph','--run']),(root.os,'geteuid',lambda:0),(root.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),(root.os,'sync',lambda:trace.append(('sync',None,cold))),(root,'parse',lambda data:tree),(root,'qualify',lambda data:{'offline_fixture':True}),(root,'qualify_linux_dt',lambda:{'composed_frozen_layout':True}),(root,'capture',capture),(root.subprocess,'run',execute),(root.subprocess,'check_output',output),(Path,'read_bytes',rb),(Path,'read_text',rt),(Path,'exists',exists)]:stack.enter_context(patch.object(obj,name,value))
   stack.enter_context(contextlib.redirect_stdout(io.StringIO()));root.main()
  saved=json.loads((session/'attempt.json').read_text());cycle=json.loads((session/'cycle-attempt.json').read_text())
  if cycle_writes:
   assert cycle_writes==1 and cycle['command_intent'] and not cycle['command_replayed']
   assert all(contract.sha((session/name).read_bytes())==h for name,h in pre_cycle_hashes.items())
   if cycle_failure=='OFF':assert not cycle['management_rejoin_verified'] and cycle['command_uncertain']
   else:assert cycle['management_rejoin_verified'] and cycle['qualification']['qualified'],cycle
   if cycle_failure in ('timeout','write'):assert cycle['errors']
  else:assert cycle['stage']=='cycle-not-admitted',cycle
  if cycle_failure=='tamper-before':assert cycle_writes==0 and 'changed' in ' '.join(cycle['errors']),cycle
  if ram_failure:
   assert saved['complete'] and saved['raw_capture_complete'] and not saved['retained_RAM_complete'] and saved['retained_RAM']['errors'] and not saved.get('analysis_error'),saved
   assert (session/'owned-after.bin').exists() and (session/'target-after.png').exists()
   if ram_failure in ('read','extent'):assert (session/'pagetables-retained.bin').exists() and post_loads==2
   else:assert post_loads==1
   if ram_failure in ('owner','sampler-note','sampler-ref'):
    assert sampler_present and not any(x[0]=='subprocess' and x[1]==['rmmod','gpu_data_sample'] and x[2] for x in trace),trace
   if ram_failure in ('sampler-note','sampler-ref'):assert not (session/'data-retained.bin').exists()
  elif label in ('actual-success','actual-exact-overlap') or cycle_failure:
   assert saved['complete'] and saved['raw_capture_complete'] and saved['pipeline']['qualified'] and saved['trace_preserved']['qualified'] and not saved.get('analysis_error'),saved
   assert saved['retained_RAM_complete'] and post_loads==2
   if overlap:assert saved['log_association']['method']=='unique-exact-suffix',saved
  elif stale:assert saved['complete'] and saved['raw_capture_complete'] and not saved['pipeline']['qualified'],saved
  elif rotate:
   assert saved['complete'] and saved['raw_capture_complete'] and saved['operation_uncertain'] and not saved['log_association']['qualified'] and saved['capture_errors']==[] and not saved.get('analysis_error'),saved
   analysis=json.loads((session/'analysis/result.json').read_text());assert not analysis['publication']['qualified'] and not analysis['trace_preserved']['qualified'] and analysis['whole_image']['untouched_sentinel'],analysis
   assert saved['retained_RAM_complete'] and post_loads==2
   assert all((session/name).exists() for name in ('owned-after.bin','objects-after.bin','notifications-after.bin','target-after.bin','completion-after.bin','queues-after.bin','hardware-completions-after.bin')),saved
  elif diagnostic:
   assert saved['complete'] and saved['raw_capture_complete'] and not saved.get('analysis_error'),saved
   analysis=json.loads((session/'analysis/result.json').read_text());assert not analysis['pipeline']['qualified'] and not analysis['rendering_verified'] and not analysis['gpu_execution_verified']
   observations=analysis['raw_post_submit_observations']
   assert saved['retained_RAM_complete'] and post_loads==2,analysis
   if incomplete:assert any(s['boundary_status']=='incomplete' for s in analysis['diagnostic_provenance']['samples']),analysis
  else:assert saved['operation_uncertain'] and saved['capture_errors'],saved
  assert sum(1 for x in trace if x[0]=='subprocess' and x[1][-1]=='resident_session=1')==1
  assert not any(x[0]=='sampler' and x[2] for x in trace)
  assert all(x[1][0] in ('insmod','rmmod',sys.executable) and (x[1][0]!='rmmod' or x[1]==['rmmod','gpu_data_sample']) for x in trace if x[0]=='subprocess' and x[2]),trace
  if not present or note!=module_note:assert not any(x[0]=='read-bytes' and '/m4rch_gpu_graph_trial/' in x[1] for x in trace)
  cases.append(dict(case='actual-main-'+label,passed=True));flows.append(dict(case=label,trace=trace,stage=saved['stage'],complete=saved['complete'],cycle_stage=cycle['stage'],cycle_write_count=cycle_writes,precycle_inputs=len(pre_cycle_hashes)))
if __name__=='__main__':main()
