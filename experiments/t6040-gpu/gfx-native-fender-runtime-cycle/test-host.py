#!/usr/bin/env python3
"""Changed runtime-state policy/order parser and one capture-before-cycle flow."""
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
 q=json.loads(path.read_text());assert contract.sha(path.read_bytes())==digest and q['passed'] and q['hardware_access'] is False and q['case_count']==count;input_paths.append(path);return q
def fixture(spec):
 path=Path(spec['path']);raw=path.read_text();assert contract.sha(raw.encode())==spec['sha256'];input_paths.append(path);return raw

def main():
 global cycle_fixture,cycle_fixture_token,cycle_fixture_write
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--runtime-qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();snapshot=a.output.with_name(a.output.stem+'.source');snapshot.mkdir(exist_ok=False)
 names=('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')
 for name in names:
  raw=(HERE/name).read_bytes();(snapshot/name).write_bytes(raw);input_paths.extend([HERE/name,snapshot/name])
 v17=ROOT/'out/gfx-postdraw-native-nmi-cycle';v18=ROOT/'out/gfx-native-fender-draw-cycle'
 baseprep=v18/'candidate/cold-render-preparation.json';assert contract.sha(baseprep.read_bytes())=='c85cdc4d9f2f42f9452df3e23f6a638bfdf5806ca6408210db2f6e7e9efc6ee6';input_paths.append(baseprep)
 # Compose authoritative prior receipts. Never repeat unchanged C/host cases.
 cq=frozen_report(v17/'owner-qualification-v3.json','066f25f9c608865b73c453a1d85edac49db7df8ad24d678dea184715b1b499d1',64)
 sq=frozen_report(v17/'preasc-qualification-v1.json','286f47a9cfadfe3d9317f42b6d7e2c1423a9db006a677e6118e87721b0991e61',39)
 hq=frozen_report(v17/'host-qualification-v2.json','6d37d82fc657216feb85c327d92ac572fe7ad2af198a852fcfef3b4e7b199486',41)
 fq=frozen_report(v18/'fender-qualification-v1.json','5de3331a735e667f586946585607271165720101b5da45cf936fa744366f2505',45)
 vh=frozen_report(v18/'host-qualification-v2.json','abea47f3b4a3f0643a84a46dee1c8ba87def836cb2d2318dd412b803823c9aef',21)
 rq=json.loads(a.runtime_qualification.read_text());assert rq['passed'] and rq['hardware_actions']==[] and rq['case_count']==829 and rq['compiler_returncode']==0 and contract.sha(a.runtime_qualification.read_bytes())=='e12421602d0b41e42120e5235527fd1686c1ccf4047d6167037e3f0595a2d2a8'
 assert rq['helper_sha256']==contract.sha((a.source/'gfx-native-runtime-state.h').read_bytes())
 for row in rq['input_pins']:assert contract.sha(Path(row['path']).read_bytes())==row['sha256'];input_paths.append(Path(row['path']))
 fixtures=rq['success_log_fixtures'];strict=fixture(fixtures['strict-ff']);dyn4=fixture(fixtures['dynamic-auto-4']);dyn0=fixture(fixtures['dynamic-auto-0']);dynf=fixture(fixtures['dynamic-auto-f'])
 for raw,fc in [(strict,False),(dyn4,True),(dyn0,True),(dynf,True)]:
  rr=contract.rows(raw,'gfx-runtime-active');assert len(rr)==1 and len(raw.splitlines())==1;analyzer.qualify_runtime_active_row(rr[0],rr[0]['phase'],fc)
 input_paths.append(a.runtime_qualification)
 log=compose_pipeline(fixture(vh['composed_pipeline_fixture']),fixture(vh['actual_C_fender_first_operation']),strict,dyn4)
 composed=a.output.with_name(a.output.stem+'.composed-pipeline.log');composed.write_text(log);input_paths.append(composed)
 cycle_fixture=compose_cycle(fixture(cq['cycle_nmi_success_log_fixture']),dyn4)
 composed_cycle=a.output.with_name(a.output.stem+'.composed-cycle.log');composed_cycle.write_text(cycle_fixture);input_paths.append(composed_cycle)
 cycle_fixture_token=contract.rows(cycle_fixture,'gfx-postdraw-native-cycle')[0]['capture_token'];cfirst=next(i for i,line in enumerate(cycle_fixture.splitlines(True)) if 'm4rch gfx-postdraw-native-cycle:' in line);cycle_fixture_write=''.join(cycle_fixture.splitlines(True)[cfirst:])
 checked('actual-C-runtime-ordered-pipeline-composition',lambda:analyzer.qualify_pipeline(log),True)
 checked('actual-C-runtime-ordered-publication-composition',lambda:analyzer.qualify_publication(log),True)
 checked('actual-C-runtime-NMI-cycle-composition',lambda:analyzer.qualify_postdraw_cycle(cycle_fixture_write,cycle_fixture_token),True)
 base=contract.rows(dyn4,'gfx-runtime-active')[0]
 def word_row(word,**overrides):
  row=dict(base,word=word,actual=(word>>4)&15,target=word&15,auto=(word>>28)&1,auto_state=(word>>24)&15,min_state=(word>>16)&15,blocked=word&0x80001c00);row.update(overrides);return row
 for label,word in [('actual-off-with-AUTO',0x1400030f),('clock-gated-with-AUTO',0x1400034f),('active-without-AUTO',0x040003ff),('active-with-AUTO',0x140003ff)]:checked('runtime-admits-'+label,lambda w=word:analyzer.qualify_runtime_active_row(word_row(w),base['phase'],True),True)
 for label,word in [('all-ones',0xffffffff),('clock-gated-no-AUTO',0x0400034f),('off-no-AUTO',0x0400030f),('unknown-actual',0x1400038f),('target-not-active',0x14000340),('RESET',0x9400034f),('DEV_DISABLE',0x1400074f),('BUSY',0x14000b4f),('PS_RESET',0x1400134f)]:checked('runtime-refuses-'+label,lambda w=word:analyzer.qualify_runtime_active_row(word_row(w),base['phase'],True),False)
 for label,overrides in [('before-invalid',dict(valid=0)),('domain-OFF',dict(domain_on=0)),('unknown-Fender-policy',dict(policy_known=0)),('unaccepted',dict(accepted=0)),('wrong-decode',dict(actual=15)),('before-Fender-dynamic',dict(fender_complete=0)),('atomic-claim',dict(operand_samples_atomic=1))]:checked('runtime-refuses-'+label,lambda changes=overrides:analyzer.qualify_runtime_active_row(word_row(base['word'],**changes),base['phase'],True),False)
 for label,text in [('missing-dynamic',log.replace(runtime_line(dyn4,'cold-guard'),' ',1)),('duplicate-row',log+runtime_line(dyn4,'cold-guard')),('Fender-completion-not-yet',log.replace('fender_complete=1 policy_known=1 policy=dynamic-auto','fender_complete=0 policy_known=1 policy=strict-ff',1)),('fresh-snapshot-word',log.replace('word=0x1400034f operation_error=0','word=0x1f0003ff operation_error=0',1)),('guard-refusal',log+'m4rch gfx-runtime-guard-refused: condition=control\n')]:checked('runtime-pipeline-refuses-'+label,lambda raw=text:analyzer.qualify_runtime_active(raw),False)
 cycle=cycle_fixture_write
 for label,needle,replacement in [('strict-OFF-busy','word=0xf000300 state_mask=0x90001cff expected_on=0','word=0xf000b00 state_mask=0x90001cff expected_on=0'),('strict-fresh-ON-gated','phase=after-get index=0 result=0 valid=0x1 domain_on=1 word=0x1f0003ff','phase=after-get index=0 result=0 valid=0x1 domain_on=1 word=0x1400034f')]:
  assert needle in cycle,label;checked(label,lambda raw=cycle.replace(needle,replacement):analyzer.qualify_postdraw_cycle(raw,cycle_fixture_token),False)
 root=module('focused_v19_offline_runner',HERE/'run-cold-render.py');preflight=module('v19_preflight',HERE/'preflight-fresh.py')
 for boot in ['2529a76a-a0ac-4de7-95f8-71b42181042b','e7288eeb-bc71-46e3-a0c5-831b77bebb1d']:
  for label,obj,argv in [('cold',root,['run-cold-render.py','/tmp/unselected-v19','--graph','--run']),('preflight',preflight,['preflight-fresh.py','/tmp/unselected-v19','/tmp/unwritten-v19'])]:
   reads=[]
   def rt(path,*args,**kwargs):assert str(path)=='/proc/sys/kernel/random/boot_id';reads.append(str(path));return boot
   def rb(path,*args,**kwargs):raise AssertionError('Content before consumed-boot refusal: '+str(path))
   with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',rb),patch.object(obj.sys,'argv',argv):checked('earliest-'+boot[:4]+'-'+label,obj.main,False)
   assert reads==['/proc/sys/kernel/random/boot_id'];flows.append(dict(case=label+'-'+boot[:4]+'-early-refusal',boot=boot,reads=reads))
 template=json.loads((v18/'candidate/asc-root-envelope/build-receipt.json').read_text())
 for k in list(template['graph_recovery_trial']):
  if k.endswith('_scope'):del template['graph_recovery_trial'][k]
 template['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
 checked('distinct-v19-contract',lambda:contract.validate_receipt(template),True)
 run_flow(root,a.source,template,log,'actual-success')
 source_receipt=a.source/'native-fender-runtime-cycle-owner-source-receipt.json';input_paths.extend([source_receipt,*[a.source/name for name in ('graph-before.bin','graph-receipt.json','backing.bin','gfx-native-runtime-state.h')]])
 for loaded in list(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file and str(file).endswith('.py') and Path(file).resolve().is_relative_to(ROOT):input_paths.append(Path(file))
 composition=dict(frozen_v17_C_cases=64,frozen_v17_preasc_C_cases=39,frozen_v17_host_cases=41,frozen_v17_actual_main_flows=10,frozen_v18_Fender_C_cases=45,frozen_v18_host_cases=21,frozen_v18_actual_main_flows=1,new_C_runtime_cases=rq['case_count'],unchanged_tests_repeated=False,ordered_fixture_is_composition=True,actual_caller_order_not_proved_by_fixture=True)
 report=dict(schema='m4rch.gfx-native-fender-runtime-cycle-host-qualification.v1',passed=True,hardware_access=False,case_count=len(cases),cases=cases,actual_main_flows=flows,actual_main_flow_count=1,early_refusal_flow_count=4,source_receipt_sha256=contract.sha(source_receipt.read_bytes()),runtime_qualification_sha256=contract.sha(a.runtime_qualification.read_bytes()),actual_C_runtime_success_fixtures=[pin(Path(spec['path'])) for spec in fixtures.values()],composed_pipeline_fixture=pin(composed),composed_cycle_fixture=pin(composed_cycle),actual_C_runtime_parser_qualified=True,inputs=[pin(path) for path in dict.fromkeys(input_paths)],composition=composition,qualification='Changed read-only runtime predicate policy/decode/order cases, strict physicalOFF/freshON negatives, consumed-boot early refusals, and one intercepted full capture-before-native-cycle flow. Frozen v18 Fender45/host21/1 and v17 C64/preASC39/host41/10 compose unchanged. Actual helper row outputs are composed with prior C pipeline/NMI fixtures; caller insertion is bound separately. No hardware, MMIO, power, GPU/DRM operation or real execution proof.')
 with a.output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(cases=len(cases),actual_main_flows=1,early_refusals=4,output=str(a.output),sha256=contract.sha(a.output.read_bytes()))))

def runtime_line(raw,phase):
 row=contract.rows(raw,'gfx-runtime-active')[0]
 assert len(raw.splitlines())==1
 return raw.replace('phase='+str(row['phase'])+' ','phase='+phase+' ',1)
def snapshot_line(word,index=33,phase='cold-guard'):
 return f'm4rch gfx-cold-render-physical: phase={phase} index={index} result=0 valid=0x1 domain_on=1 word={word:#x} operation_error=0 cleanup_error=0 operand_samples_atomic=0\n'
def compose_pipeline(log,fender,strict,dynamic):
 # The earlier independent Fender fixture was inserted at draw-intent.
 # Relocate it to its production caller, then append actual helper row output
 # after each saved physical guard. This remains explicit fixture composition.
 lines=[line for line in log.splitlines(True) if 'm4rch gfx-native-fender-enable' not in line]
 frows=fender.splitlines(True);assert len(frows)==3
 ready=next(i for i,line in enumerate(lines) if 'm4rch gfx-cold-render: phase=control-ready ' in line)
 first_draw_guard=next(i for i in range(ready+1,len(lines)) if 'm4rch gfx-cold-render-physical: phase=cold-guard ' in lines[i])
 inserted=frows[:1]+[snapshot_line(contract.rows(strict,'gfx-runtime-active')[0]['word'])]+frows[1:]
 lines[first_draw_guard:first_draw_guard]=inserted
 out=[];guard=0
 for line in lines:
  if 'm4rch gfx-cold-render-physical: phase=cold-guard ' in line:
   raw=strict if guard<4 else dynamic;word=contract.rows(raw,'gfx-runtime-active')[0]['word']
   previous=contract.rows(line,'gfx-cold-render-physical')[0]['word'];line=line.replace('word='+hex(previous)+' ','word='+hex(word)+' ',1)
   out.extend([line,runtime_line(raw,'cold-guard')]);guard+=1
  else:out.append(line)
 assert guard==6
 return ''.join(out)
def compose_cycle(log,dynamic):
 out=[];word=contract.rows(dynamic,'gfx-runtime-active')[0]['word'];selected=0
 for line in log.splitlines(True):
  target=None
  for phase in ('admission-before','before-off'):
   if ('m4rch gfx-cold-render-physical: phase='+phase+' ') in line or ('m4rch gfx-postdraw-native-cycle-physical: phase='+phase+' ') in line:
    prefix='gfx-postdraw-native-cycle-physical' if 'm4rch gfx-postdraw-native-cycle-physical: ' in line else 'gfx-cold-render-physical'
    before=contract.rows(line,prefix)[0]['word'];line=line.replace('word='+hex(before)+' ','word='+hex(word)+' ',1)
    if prefix=='gfx-postdraw-native-cycle-physical':target=phase
  out.append(line)
  if target:out.append(runtime_line(dynamic,target));selected+=1
 assert selected==2
 return ''.join(out)
def run_flow(root,source,template,log,label,present=True,note=None,truncate=False,stale=False,rotate=False,overlap=False,diagnostic=False,incomplete=False,ram_failure=None,cycle_failure=None):
 module_raw,module_note=elf();note=module_note if note is None else note
 adt_path=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt';adt_raw=adt_path.read_bytes();tree=parse(adt_raw);input_paths.append(adt_path)
 with tempfile.TemporaryDirectory(prefix='cold-host-'+label+'-') as tmp:
  work=Path(tmp);graph=work/'asc-graph-init';build=work/'asc-root-envelope';graph.mkdir();build.mkdir();(work/'analysis-inputs').mkdir()
  for spec in contract.RETAINED_SAMPLERS:
   dest=work/spec['module'];dest.parent.mkdir(parents=True,exist_ok=True);origin=ROOT/'out/gfx-native-dispatch-contract/candidate'/spec['module'];shutil.copyfile(origin,dest);input_paths.append(origin)
  for name in ('graph-before.bin','graph-receipt.json','backing.bin'):shutil.copyfile(source/name,graph/name)
  shutil.copyfile(ROOT/'out/gfx-native-ap-repeat-cycle/candidate/analysis-inputs/target-receipt.json',work/'analysis-inputs/target-receipt.json')
  (graph/'asc-graph-init.ko').write_bytes(module_raw)
  fixture=copy.deepcopy(template);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':contract.sha(module_raw)};fixture['graph_source_sha256']={};fixture['kernel_notes_sha256']=contract.sha(b'kernel-note')
  fixture['graph_fixture_sha256']=contract.sha((graph/'graph-before.bin').read_bytes());fixture['graph_receipt_sha256']=contract.sha((graph/'graph-receipt.json').read_bytes())
  (build/'build-receipt.json').write_text(json.dumps(fixture));(work/'cold-render-preparation.json').write_text(json.dumps(dict(schema='m4rch.gfx-native-fender-runtime-cycle-preparation.v1',candidate_receipt_sha256=contract.sha((build/'build-receipt.json').read_bytes()),owner_sha256=contract.sha(module_raw),inputs=[],analysis_input_pins=[],fixed_retained_RAM_samplers=list(contract.RETAINED_SAMPLERS),backing_changed_byte_count=4)))
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
