#!/usr/bin/env python3
"""Focused native policy outcomes and intercepted immutable-capture main flows."""
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



def composed_cycle(base,helper):
 """Replace only the old policy helper; retain frozen teardown records."""
 old='m4rch gfx-cold-startup-physical: phase=idle-policy-before '
 new='m4rch gfx-cold-render-physical: phase=idle-policy-before '
 assert helper.count(old)==1
 helper=helper.replace(old,new,1)
 rows=helper.splitlines(True)
 for i,line in enumerate(rows):
  if line.startswith(new):
   assert 'operation_error=' not in line and 'cleanup_error=' not in line
   rows[i]=line.replace(' operand_samples_atomic=0',' operation_error=0 cleanup_error=0 operand_samples_atomic=0',1)
 helper=''.join(rows)
 lines=base.splitlines(True)
 start=next(i for i,line in enumerate(lines) if 'm4rch gfx-native-idle-policy: phase=intent ' in line)
 stop=next(i for i,line in enumerate(lines) if 'm4rch gfx-postdraw-native-cycle: phase=idle-policy-refresh-admission ' in line)
 assert start<stop
 return ''.join(lines[:start])+helper+''.join(lines[stop:])


def changed_row(text,prefix,phase,fields):
 lines=text.splitlines(True);matches=[i for i,line in enumerate(lines) if 'm4rch '+prefix+': phase='+phase+' ' in line]
 assert len(matches)==1,(prefix,phase)
 i=matches[0];tokens=lines[i].split()
 for key,value in fields.items():
  found=[j for j,token in enumerate(tokens) if token.startswith(key+'=')];assert len(found)==1,(key,lines[i])
  tokens[found[0]]=key+'='+str(value)
 lines[i]=' '.join(tokens)+'\n'
 return ''.join(lines)


def main():
 global cycle_fixture,cycle_fixture_token,cycle_fixture_write
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--power-assertion-qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();snapshot=a.output.with_name(a.output.stem+'.source');snapshot.mkdir(exist_ok=False)
 names=('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py','prepare-power-assertion-owner.py','test-power-assertion.py','gfx-native-idle-policy.h','README.md')
 for name in names:
  raw=(HERE/name).read_bytes();(snapshot/name).write_bytes(raw);input_paths.extend([HERE/name,snapshot/name])
 base=ROOT/'out/gfx-native-idle-policy-fender-cycle';prep_path=base/'candidate/cold-render-preparation.json'
 prep=json.loads(prep_path.read_bytes());assert contract.sha(prep_path.read_bytes())=='300e5b209856e1a20820f3c5eeac9c5fb84398e49631b53c0c28387ce066535a';input_paths.append(prep_path)
 for r in prep['inputs']:assert contract.sha(Path(r['path']).read_bytes())==r['sha256'];input_paths.append(Path(r['path']))
 old_cq=frozen_report(base/'idle-policy-qualification-v1.json','69c65fc62afd333a18be07efe94ee139d1d1dad2c1ca506c99de6b4e0a4faf6a',77)
 hq=frozen_report(base/'host-qualification-v3.json','4f96799b0d9b60799145042190b1bda0ea14f432f4f7ccdac27d68b55632e61d',28)
 cq=json.loads(a.power_assertion_qualification.read_bytes());assert cq['passed'] and cq['case_count']>0 and cq['hardware_access'] is False and cq['hardware_actions']==[] and cq['kernel_build'] is False;input_paths.append(a.power_assertion_qualification)
 assert cq['frozen_v22_qualification_sha256']==contract.sha((base/'idle-policy-qualification-v1.json').read_bytes())
 for r in cq['input_pins']:assert contract.sha(Path(r['path']).read_bytes())==r['sha256'];input_paths.append(Path(r['path']))
 log=fixture(hq['composed_pipeline_fixture']);legacy_cycle=fixture(hq['composed_cycle_fixtures']['success'])
 cycle_fixture_token=contract.rows(legacy_cycle,'gfx-postdraw-native-cycle')[0]['capture_token']
 fixture_dir=a.output.with_name(a.output.stem+'.fixtures');fixture_dir.mkdir(exist_ok=False)
 helpers={'success':cq['success_log_fixture'],**cq['clean_timeout_log_fixtures']};composed={};fixture_pins={}
 logger=a.source/'gfx-cold-runtime.h';adapter=HERE/'test-power-assertion.py';input_paths.extend([logger,adapter])
 assert 'm4rch gfx-cold-render-physical: phase=%s' in logger.read_text() and 'operation_error=%d cleanup_error=%d operand_samples_atomic=0' in logger.read_text()
 for name,spec in helpers.items():
  whole=composed_cycle(legacy_cycle,fixture(spec));path=fixture_dir/(name+'.log');path.write_text(whole);input_paths.append(path);composed[name]=whole;fixture_pins[name]=pin(path)
  checked('actual-C-native-assertion-'+name+'-full-cycle',lambda text=whole:analyzer.qualify_postdraw_cycle(text,cycle_fixture_token),True)
 outcomes={name:analyzer.observe_postdraw_cycle(text,cycle_fixture_token) for name,text in composed.items()}
 for result in outcomes.values():assert result['native_power_assertion_publication_verified'] and result['native202_request_published'] and result['strict_physical_OFF_observed'] and result['paired_PM_accounting_observed'] and not result['retirement_verified']
 assert outcomes['success']['policy_command_processing_verified'] and outcomes['success']['firmware_GPU_off_observed']
 assert outcomes['off-timeout']['policy_command_processing_verified'] and not outcomes['off-timeout']['firmware_GPU_off_observed']
 assert not outcomes['both-timeout']['policy_command_processing_verified'] and not outcomes['both-timeout']['firmware_GPU_off_observed']
 assert not outcomes['processing-timeout']['policy_command_processing_verified'] and outcomes['processing-timeout']['firmware_GPU_off_observed']
 assert not outcomes['late-processing']['policy_command_processing_verified'] and outcomes['late-processing']['firmware_GPU_off_observed']
 success=composed['success'];assertion=contract.rows(success,'gfx-native-power-assertion');baseline=next(r for r in assertion if r['phase']=='baseline');count=baseline['before']
 mutations=[('root-owner',{'root_offset':'0x18'}),('region-c-pointer',{'region_c_va':'0xfffffc2000108000'}),('arena-field',{'arena_offset':'0xce50'}),('native-field',{'field_offset':'0xe50'}),('packed-width',{'bytes':8}),('unaligned-owner',{'unaligned':0}),('missing-DMBISH',{'dmbish':0}),('uncleaned',{'cleaned':0}),('unverified-readback',{'verified':0}),('no-attempt',{'attempted':0}),('two-increments',{'current':count+2,'requested':count+2}),('current-mismatch',{'current':count}),('consumed-before-producer',{'consumed_current':count+1}),('wrap-unqualified',{'near_wrap_supported':1})]
 for label,fields in mutations:
  text=changed_row(success,'gfx-native-power-assertion','assertion-published',fields)
  checked('refuse-assertion-'+label,lambda raw=text:analyzer.qualify_postdraw_cycle(raw,cycle_fixture_token),False)
 for label,fields in [('baseline-not-consumed',{'before':count+1}),('baseline-near-wrap',{'before':2**32-2}),('baseline-already-written',{'attempted':1,'cleaned':1,'verified':1})]:
  text=changed_row(success,'gfx-native-power-assertion','baseline',fields)
  checked('refuse-assertion-'+label,lambda raw=text:analyzer.qualify_postdraw_cycle(raw,cycle_fixture_token),False)
 missing=''.join(line for line in success.splitlines(True) if 'm4rch gfx-native-power-assertion:' not in line)
 checked('refuse-policy-without-assertion-evidence',lambda:analyzer.qualify_postdraw_cycle(missing,cycle_fixture_token),False)
 publine=next(line for line in success.splitlines(True) if 'm4rch gfx-native-power-assertion: phase=assertion-published ' in line)
 checked('refuse-duplicate-assertion-publication',lambda:analyzer.qualify_postdraw_cycle(success+publine,cycle_fixture_token),False)
 moved=success.replace(publine,'');where=next(line for line in moved.splitlines(True) if 'm4rch gfx-native-idle-policy-producer: ' in line);moved=moved.replace(where,where+publine)
 checked('refuse-assertion-after-producer',lambda:analyzer.qualify_postdraw_cycle(moved,cycle_fixture_token),False)
 checked('refuse-frozen-v22-cycle-as-v23',lambda:analyzer.qualify_postdraw_cycle(legacy_cycle,cycle_fixture_token),False)
 busy=[]
 for line in success.splitlines():
  if 'gfx-postdraw-native-cycle-physical: phase=after-off ' in line:
   word=next(token for token in line.split() if token.startswith('word='));line=line.replace(word,'word='+hex(int(word[5:],16)|0x800))
  busy.append(line)
 busy='\n'.join(busy)+'\n';checked('assertion-does-not-waive-strict-OFF',lambda:analyzer.qualify_postdraw_cycle(busy,cycle_fixture_token),False)
 busy_result=analyzer.observe_postdraw_cycle(busy,cycle_fixture_token);assert busy_result['native_power_assertion_publication_verified'] and busy_result['policy_command_processing_verified'] and busy_result['firmware_GPU_off_observed'] and not busy_result['strict_physical_OFF_observed'] and busy_result['paired_PM_accounting_observed']
 checked('actual-unchanged-v23-native-descriptor-data',lambda:contract.validate_descriptor_data(a.source),True)
 elf_reader=runpy.run_path(str(HERE/'finalize-cold-render.py'),run_name='actual_v23_ELF_data_check')['actual_ELF_graph_bytes'];owner=ROOT/'out/gfx-native-power-assertion-fender-cycle/candidate/asc-graph-init/asc-graph-init.ko';input_paths.append(owner)
 checked('actual-v23-AArch64-upload-keeps-frozen-arena',lambda:elf_reader(owner.read_bytes())==(a.source/'graph-before.bin').read_bytes(),True)
 template=json.loads((base/'candidate/asc-root-envelope/build-receipt.json').read_bytes());input_paths.append(base/'candidate/asc-root-envelope/build-receipt.json')
 checked('refuse-frozen-v22-contract-as-v23',lambda:contract.validate_receipt(template),False)
 for k in list(template['graph_recovery_trial']):
  if k.endswith('_scope'):del template['graph_recovery_trial'][k]
 template['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
 checked('distinct-v23-contract',lambda:contract.validate_receipt(template),True)
 root=module('focused_v23_offline_runner',HERE/'run-cold-render.py');preflight=module('v23_preflight',HERE/'preflight-fresh.py');boot='09a48fe3-925a-46d9-b99b-b9aecc71e6f3'
 for label,obj,argv in [('cold',root,['run-cold-render.py','/tmp/unselected-v23','--graph','--run']),('preflight',preflight,['preflight-fresh.py','/tmp/unselected-v23','/tmp/unwritten-v23'])]:
  reads=[]
  def rt(path,*args,**kwargs):assert str(path)=='/proc/sys/kernel/random/boot_id';reads.append(str(path));return boot
  def rb(path,*args,**kwargs):raise AssertionError('Content before consumed-boot refusal: '+str(path))
  with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',rb),patch.object(obj.sys,'argv',argv):checked('earliest-09-'+label,obj.main,False)
  assert reads==['/proc/sys/kernel/random/boot_id'];flows.append(dict(case=label+'-09-early-refusal',boot=boot,reads=reads))
 for name in ('success','off-timeout','both-timeout'):
  cycle_fixture=composed[name];first=next(i for i,line in enumerate(cycle_fixture.splitlines(True)) if 'm4rch gfx-postdraw-native-cycle:' in line);cycle_fixture_write=''.join(cycle_fixture.splitlines(True)[first:])
  run_flow(root,a.source,template,log,'actual-'+name)
 sr=a.source/'native-power-assertion-fender-cycle-owner-source-receipt.json';input_paths.append(sr);assert cq['source_receipt_sha256']==contract.sha(sr.read_bytes())
 for loaded in list(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file and str(file).endswith('.py') and Path(file).resolve().is_relative_to(ROOT):input_paths.append(Path(file))
 report=dict(schema='m4rch.gfx-native-power-assertion-fender-cycle-host-qualification.v1',passed=True,hardware_access=False,hardware_actions=[],case_count=len(cases),cases=cases,actual_main_flows=flows,actual_main_flow_count=3,early_refusal_flow_count=2,source_receipt_sha256=contract.sha(sr.read_bytes()),power_assertion_qualification_sha256=contract.sha(a.power_assertion_qualification.read_bytes()),composed_pipeline_fixture=hq['composed_pipeline_fixture'],composed_cycle_fixtures=fixture_pins,independent_shutdown_fixture_results=outcomes,busy_is_independent_of_assertion_and_firmware_OFF=busy_result,external_C_adapter_projection=dict(before_prefix='gfx-cold-startup-physical',production_prefix='gfx-cold-render-physical',operation_error=0,cleanup_error=0,synthetic_caller_context=True,production_logger=pin(logger),actual_C_adapter=pin(adapter),actual_helper_rows_changed=False),inputs=[pin(path) for path in dict.fromkeys(input_paths)],composition=dict(frozen_v22_C_cases=77,frozen_v22_host_cases=28,frozen_v22_actual_main_flows=3,earlier_scopes=hq['composition'],unchanged_tests_repeated=False),selection='unselected-awaiting-root-review',qualification='New native assertion whole-helper outputs compose frozen full-cycle records. Exact RegionC ownership, unaligned32 extent, fresh equality, one clean/readback increment, before-producer ordering, ambiguity/near-wrap refusals, independent OFF failure and three intercepted actual-main immutable capture flows are exercised. Native assertion publication is separate from command consumption and firmware/physical OFF. Earlier whole qualifications are composed without rerun; no hardware or private instruction bytes copied.')
 with a.output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(cases=len(cases),actual_main_flows=3,early_refusals=2,output=str(a.output),sha256=contract.sha(a.output.read_bytes()))))

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
  (build/'build-receipt.json').write_text(json.dumps(fixture));(work/'cold-render-preparation.json').write_text(json.dumps(dict(schema='m4rch.gfx-native-power-assertion-fender-cycle-preparation.v1',candidate_receipt_sha256=contract.sha((build/'build-receipt.json').read_bytes()),owner_sha256=contract.sha(module_raw),inputs=[],analysis_input_pins=[],fixed_retained_RAM_samplers=list(contract.RETAINED_SAMPLERS),backing_changed_byte_count=4)))
  boot='offline-'+label;session=graph/('boot-'+boot);trace=[];cold=False;dmesg=0;sampler_present=False;active_sampler=None;post_loads=0;cycle_writes=0;cycle_token=None;cycle_log='';pre_cycle_hashes={}
  objects=bytearray((graph/'graph-before.bin').read_bytes())
  for index,offset in [(0,344064),(1,376832),(12,737280)]:
   for at in (0,8,16):struct.pack_into('<I',objects,offset+at,33 if index==12 else 1)
  owned=bytearray(174*16384);owned[112*16384:168*16384]=(graph/'backing.bin').read_bytes()
  if truncate:owned=owned[:-1]
  notifications=struct.pack('<8I4Q',0x5852474d,1,80,65536,0,0,0,0,0,0,0,0)+bytes(65536*80)
  text_path=ROOT/'out/gfx-native-fender-off-cycle/candidate/asc-graph-init/boot-09a48fe3-925a-46d9-b99b-b9aecc71e6f3/text.bin'
  raw_text=text_path.read_bytes();input_paths.append(text_path)
  assert len(raw_text)==393216 and contract.sha(raw_text)=='8e0e2b5d4d1943293f10152c326740218f610b83a7d3eef76835c0d238bd0bf3'
  # The intercepted sampler returns this immutable, already saved private
  # dump. Actual inherited TEXT checks run; no instruction bytes enter the kit.
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
   for obj,name,value in [(root.sys,'argv',['run-cold-render.py',str(work),'--graph','--run']),(root.os,'geteuid',lambda:0),(root.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),(root.os,'sync',lambda:trace.append(('sync',None,cold))),(root,'parse',lambda data:tree),(root,'qualify_linux_dt',lambda:{'composed_frozen_layout':True}),(root,'capture',capture),(root.subprocess,'run',execute),(root.subprocess,'check_output',output),(Path,'read_bytes',rb),(Path,'read_text',rt),(Path,'exists',exists)]:stack.enter_context(patch.object(obj,name,value))
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
  elif label.startswith('actual-') or cycle_failure:
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
