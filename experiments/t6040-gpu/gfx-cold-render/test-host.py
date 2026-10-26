#!/usr/bin/env python3
"""Offline actual launcher/parser/readback flows using the actual C-emitted log."""
import argparse,contextlib,copy,importlib.util,io,json,runpy,shutil,struct,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import cold_render_contract as contract
import analyze_cold_render as analyzer
import readback
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
 struct.pack_into('<IIQQQQIIQQ',raw,320,1,7,0,0,64,36,0,0,4,0)
 struct.pack_into('<IIQQQQIIQQ',raw,384,19,3,0,0,128,len(names),0,0,1,0)
 return bytes(raw),note
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--owner-qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists(),'Qualification output must be new'
 snapshot=a.output.with_name(a.output.stem+'.source');snapshot.mkdir(exist_ok=False)
 for name in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py'):
  path=snapshot/name;path.write_bytes((HERE/name).read_bytes());input_paths.append(path)
 cq=json.loads(a.owner_qualification.read_text());fixture=cq['success_log_fixture'];fpath=Path(fixture['path']);raw=fpath.read_bytes();assert contract.sha(raw)==fixture['sha256'];log=raw.decode()
 input_paths.extend([a.owner_qualification,fpath,a.source/'cold-render-owner-source-receipt.json',*[a.source/name for name in ('graph-before.bin','graph-receipt.json','backing.bin')]])
 checked('actual-C-success-log',lambda:analyzer.qualify_pipeline(log),True)
 for phase in ('pipeline-intent','control-intent','control-ready','draw-intent','draw-published','retained-final'):
  line=next(line for line in log.splitlines(True) if 'm4rch gfx-cold-render: phase='+phase+' ' in line)
  checked('missing-own-stage-'+phase,lambda l=log.replace(line,''):analyzer.qualify_pipeline(l),False)
  checked('duplicate-own-stage-'+phase,lambda l=log+line:analyzer.qualify_pipeline(l),False)
 mutations={'stale32-proof':('ready_cursors=33/33/33','ready_cursors=32/32/32'),
  'unverified-producer':('producer1_verified=1','producer1_verified=0'),
  'unclean-record':('record1_cleaned=1','record1_cleaned=0'),
  'lost-PM':('held=1','held=0'),'phase-inherited':('recovery_phase=0','recovery_phase=2'),
  'unknown-journal':('journal_status=0','journal_status=0x2'),
  'no-own-root':('gfx-cold-render-root:','historical-root:'),
  'wrong-control-packet':('packet=0x84000000000000','packet=0x83000000000000'),
  'extra-draw':('gfx-cold-render-tx:','gfx-cold-render-tx:'),
  'wrong-cold-endpoint':('remote_state=0x20','remote_state=0x10')}
 for label,(old,new) in mutations.items():
  if label=='extra-draw':bad=log+next(line for line in log.splitlines(True) if 'gfx-cold-render-tx:' in line and 'sent=1 ' in line)
  else:assert old in log,label;bad=log.replace(old,new)
  checked('actual-parser-refuses-'+label,lambda l=bad:analyzer.qualify_pipeline(l),False)
 checked('rotated-log-refuses',lambda:contract.log_delta('old\n','new\n'),False)
 checked('stale-startup-only-refuses',lambda:analyzer.qualify_pipeline(''),False)
 # Preserve every pixel and catch corruption beyond the historic eight points.
 target_path=ROOT/'out/gfx-native-ap-repeat-cycle/candidate/analysis-inputs/target-receipt.json';target=json.loads(target_path.read_text());input_paths.append(target_path)
 image=b''.join(readback.pixel_model(x,y)[0] for y in range(64) for x in range(64))
 expected=readback.check_full(target,image);assert expected['conditional_candidate_pattern_matches'] and expected['rendering_verified'] is False
 cases.append(dict(case='synthetic-full-reference-never-rendering-proof',passed=True))
 bad=bytearray(image);bad[30*256+30*4]^=128
 checked('off-eight-point-corruption-detected',lambda:readback.check_full(target,bytes(bad))['conditional_candidate_pattern_matches'],False)
 checked('untouched-full-target-detected',lambda:readback.check_full(target,bytes([165])*16384)['untouched_sentinel'],True)
 for size in (0,16383,16385):checked('full-image-extent-'+str(size),lambda n=size:readback.check_full(target,bytes(n)),False)
 png=readback.png(image);assert png.startswith(b'\x89PNG\r\n\x1a\n') and b'IHDR' in png;cases.append(dict(case='standalone-full-image-PNG',passed=True))
 root=module('cold_actual_launcher',HERE/'run-cold-render.py');preflight=module('cold_actual_preflight',HERE/'preflight-fresh.py')
 for boot in contract.REFUSED_BOOTS:
  for label,obj,argv in [('cold',root,['run-cold-render.py','/tmp/unselected-cold','--graph','--run']),('preflight',preflight,['preflight-fresh.py','/tmp/unselected-cold','/tmp/unwritten-cold'])]:
   reads=[]
   def rt(path,*args,**kwargs):assert str(path)=='/proc/sys/kernel/random/boot_id';reads.append(str(path));return boot
   def rb(path,*args,**kwargs):raise AssertionError('Content before refusal: '+str(path))
   with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',rb),patch.object(obj.sys,'argv',argv):checked('earliest-'+label+'-'+boot,obj.main,False)
   assert reads==['/proc/sys/kernel/random/boot_id'];flows.append(dict(case=label+'-early-refusal',boot=boot,reads=reads))
 template=json.loads((ROOT/'out/gfx-native-ap-repeat-cycle/candidate/asc-root-envelope/build-receipt.json').read_text())
 for k in list(template['graph_recovery_trial']):
  if k.endswith('_scope'):del template['graph_recovery_trial'][k]
 template['graph_recovery_trial'].update(cycles=0,work_submitted=False);template['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
 checked('distinct-v13-contract',lambda:contract.validate_receipt(template),True)
 for family in ('gfx_native_ap_repeat_cycle_scope','gfx_native_ap_retained_cycle_scope'):
  bad=copy.deepcopy(template);bad['graph_recovery_trial'][family]={};checked('mixed-family-'+family,lambda d=bad:contract.validate_receipt(d),False)
 run_flow(root,a.source,template,log,'actual-success')
 run_flow(root,a.source,template,log,'missing-module',present=False)
 run_flow(root,a.source,template,log,'wrong-loaded-owner',note=bytes(36))
 run_flow(root,a.source,template,log,'truncated-owned',truncate=True)
 run_flow(root,a.source,template,log,'stale-before-log',stale=True)
 run_flow(root,a.source,template,log,'rotated-after-log',rotate=True)
 for diagnostic_fixture in cq['actual_log_fixtures']:
  if diagnostic_fixture['case'] not in ('post-device-fault','post-rx-crash','post-journal-full','post-KSM-map-missing','post-fault-map-missing'):continue
  path=Path(diagnostic_fixture['path']);data=path.read_bytes();assert contract.sha(data)==diagnostic_fixture['sha256'];input_paths.append(path)
  bad=data.decode();checked('actual-C-diagnostic-rejects-'+diagnostic_fixture['case'],lambda l=bad:analyzer.qualify_pipeline(l),False)
  run_flow(root,a.source,template,bad,'diagnostic-'+diagnostic_fixture['case'],diagnostic=True)
 # Incomplete source boundary keeps preceding raw rows but cannot qualify a draw.
 boundary=next(line for line in log.splitlines(True) if 'gfx-cold-render-sample: phase=post-submit sample_index=3 ' in line and 'begin=0 ' in line)
 early=log[:log.index(boundary)]
 run_flow(root,a.source,template,early,'diagnostic-incomplete-sample',diagnostic=True,incomplete=True)
 # A failed health word alone must not make bound raw diagnostics disappear.
 bad=log.replace(boundary,boundary.replace('fault_info=0 ','fault_info=0x40 '))
 run_flow(root,a.source,template,bad,'diagnostic-modified-fault',diagnostic=True)
 address_fault=log.replace(boundary,boundary.replace('fault_addr=0 ','fault_addr=0x4000 '))
 checked('address-only-fault-parser-refuses',lambda:analyzer.qualify_pipeline(address_fault),False)
 address_observations=analyzer.diagnostic_observations(address_fault)
 assert not next(s for s in address_observations['samples'] if s['identity']['sample_index']==3)['health_verified'];cases.append(dict(case='address-only-fault-not-healthy',passed=True))
 run_flow(root,a.source,template,address_fault,'diagnostic-address-only-fault',diagnostic=True)
 observations=analyzer.diagnostic_observations(log)
 assert observations['complete_post_submit_window'] and not observations['errors'];cases.append(dict(case='raw-complete-sample-tuple-association',passed=True))
 duplicated=analyzer.diagnostic_observations(log+boundary)
 unbound=next(s for s in duplicated['samples'] if s['identity']['sample_index']==3)
 assert unbound['boundary_status']=='unbound' and not unbound['health_verified'];cases.append(dict(case='duplicate-healthy-boundary-not-verified',passed=True))
 assert not any(r['sample_index']==3 for values in duplicated['raw_post_submit_observations'].values() for r in values);cases.append(dict(case='duplicate-boundary-raw-rows-unassociated',passed=True))
 orphan=next(line for line in log.splitlines(True) if 'ksm-fault: phase=post-submit sample_index=2 ' in line)
 observations=analyzer.diagnostic_observations(orphan+log)
 assert len(observations['unassociated_post_submit_observations']['ksm-fault'])==1;cases.append(dict(case='raw-row-outside-source-boundary-unassociated',passed=True))
 for name in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py'):input_paths.append(HERE/name)
 for name in readback.RECIPE_HASHES:input_paths.append(HERE.parent/name)
 input_paths.extend([HERE.parent/'gfx-native-ap-repeat-cycle/run-root-powergate.py',HERE.parent/'decode-receive-journal.py'])
 for loaded in list(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file and str(file).endswith('.py') and Path(file).resolve().is_relative_to(ROOT):input_paths.append(Path(file))
 report=dict(schema='m4rch.gfx-cold-render-host-qualification.v1',passed=True,hardware_access=False,case_count=len(cases),cases=cases,actual_main_flows=flows,actual_main_flow_count=len(flows),actual_C_success_log_qualified=True,actual_C_success_log_sha256=fixture['sha256'],source_receipt_sha256=contract.sha((a.source/'cold-render-owner-source-receipt.json').read_bytes()),inputs=[pin(path) for path in dict.fromkeys(input_paths)],frozen_v12_C_cases=172,frozen_v12_host_cases=378,unchanged_cases_repeated=False,qualification='Intercepted actual launcher entry points, actual C-emitted log parser and synthetic full-image/capture negative tests only. No build, module load, hardware execution or rendering.')
 with a.output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(cases=len(cases),actual_main_flows=len(flows),output=str(a.output),sha256=contract.sha(a.output.read_bytes()))))
def run_flow(root,source,template,log,label,present=True,note=None,truncate=False,stale=False,rotate=False,diagnostic=False,incomplete=False):
 module_raw,module_note=elf();note=module_note if note is None else note
 adt_path=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt';adt_raw=adt_path.read_bytes();tree=parse(adt_raw);input_paths.append(adt_path)
 with tempfile.TemporaryDirectory(prefix='cold-host-'+label+'-') as tmp:
  work=Path(tmp);graph=work/'asc-graph-init';build=work/'asc-root-envelope';graph.mkdir();build.mkdir();(work/'analysis-inputs').mkdir()
  for name in ('graph-before.bin','graph-receipt.json','backing.bin'):shutil.copyfile(source/name,graph/name)
  shutil.copyfile(ROOT/'out/gfx-native-ap-repeat-cycle/candidate/analysis-inputs/target-receipt.json',work/'analysis-inputs/target-receipt.json')
  (graph/'asc-graph-init.ko').write_bytes(module_raw)
  fixture=copy.deepcopy(template);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':contract.sha(module_raw)};fixture['graph_source_sha256']={};fixture['kernel_notes_sha256']=contract.sha(b'kernel-note')
  fixture['graph_fixture_sha256']=contract.sha((graph/'graph-before.bin').read_bytes());fixture['graph_receipt_sha256']=contract.sha((graph/'graph-receipt.json').read_bytes())
  (build/'build-receipt.json').write_text(json.dumps(fixture));(work/'cold-render-preparation.json').write_text(json.dumps(dict(schema='m4rch.gfx-cold-render-preparation.v1',candidate_receipt_sha256=contract.sha((build/'build-receipt.json').read_bytes()),owner_sha256=contract.sha(module_raw),inputs=[],analysis_input_pins=[])))
  boot='offline-'+label;session=graph/('boot-'+boot);trace=[];cold=False;dmesg=0
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
    trace.append(('read-bytes',str(path),cold));values={'/sys/kernel/notes':b'kernel-note','/sys/module/asc_graph_init/notes/.note.gnu.build-id':note,'/sys/kernel/m4rch_gpu_graph_trial/objects':bytes(objects),'/sys/kernel/m4rch_gpu_graph_trial/owned':bytes(owned),'/sys/kernel/m4rch_gpu_graph_trial/notifications':notifications}
    assert str(path) in values,str(path);return values[str(path)]
   return original_rb(path)
  def rt(path,*args,**kwargs):
   if str(path).startswith(('/sys/','/proc/')):
    trace.append(('read-text',str(path),cold));values={'/proc/sys/kernel/random/boot_id':boot,'/proc/modules':'','/proc/interrupts':'offline-interrupts','/sys/module/asc_graph_init/refcnt':'1'};assert str(path) in values,str(path);return values[str(path)]
   return original_rt(path,*args,**kwargs)
  def exists(path):
   if str(path).startswith('/sys/'):assert str(path)=='/sys/module/asc_graph_init';return present
   return original_exists(path)
  def capture(module,sysfile,destination,name):
   assert not cold,'No powered sampler after draw';trace.append(('sampler',destination.name,cold))
   data={'boot.adt':adt_raw,'pagetables.bin':bytes(0x40000),'text.bin':bytes(raw_text),'data-before.bin':bytes(16)}[destination.name];destination.write_bytes(data);return data
  def execute(command,**kwargs):
   nonlocal cold
   assert not cold,'No cleanup/reload after cold attempt';trace.append(('subprocess',command,cold))
   if command[-1]=='resident_session=1':
    intent=json.loads((session/'attempt.json').read_text());assert intent['automatic_pipeline_intent'] and intent['operation_uncertain'] and intent['stage']=='cold-load-intent';cold=True
   return SimpleNamespace(returncode=0,stdout='',stderr='')
  def output(command,**kwargs):
   nonlocal dmesg
   assert command==['dmesg','--color=never'];dmesg+=1
   before='before\n'+(log if stale else '')
   return before if dmesg==1 else 'rotated\n'+log if rotate else before if stale else before+log
  with contextlib.ExitStack() as stack:
   for obj,name,value in [(root.sys,'argv',['run-cold-render.py',str(work),'--graph','--run']),(root.os,'geteuid',lambda:0),(root.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),(root.os,'sync',lambda:trace.append(('sync',None,cold))),(root,'parse',lambda data:tree),(root,'qualify',lambda data:{'offline_fixture':True}),(root,'qualify_linux_dt',lambda:{'composed_frozen_layout':True}),(root,'capture',capture),(root.subprocess,'run',execute),(root.subprocess,'check_output',output),(Path,'read_bytes',rb),(Path,'read_text',rt),(Path,'exists',exists)]:stack.enter_context(patch.object(obj,name,value))
   stack.enter_context(contextlib.redirect_stdout(io.StringIO()));root.main()
  saved=json.loads((session/'attempt.json').read_text())
  if label=='actual-success':assert saved['complete'] and saved['pipeline']['qualified'] and not saved.get('analysis_error'),saved
  elif stale:assert saved['complete'] and not saved['pipeline']['qualified'],saved
  elif diagnostic:
   assert saved['complete'] and not saved['pipeline']['qualified'] and not saved.get('analysis_error'),saved
   analysis=json.loads((session/'analysis/result.json').read_text());assert not analysis['pipeline']['qualified'] and not analysis['rendering_verified'] and not analysis['gpu_execution_verified']
   observations=analysis['raw_post_submit_observations']
   expected=sum(len([r for r in contract.rows(log,name) if r.get('phase')=='post-submit']) for name in analyzer.OBSERVATION_FAMILIES)
   assert sum(map(len,observations.values()))==expected,analysis
   if incomplete:assert any(s['boundary_status']=='incomplete' for s in analysis['diagnostic_provenance']['samples']),analysis
  else:assert saved['operation_uncertain'] and saved['capture_errors'],saved
  assert sum(1 for x in trace if x[0]=='subprocess' and x[1][-1]=='resident_session=1')==1
  assert not any(x[0]=='sampler' and x[2] for x in trace)
  if not present or note!=module_note:assert not any(x[0]=='read-bytes' and '/m4rch_gpu_graph_trial/' in x[1] for x in trace)
  cases.append(dict(case='actual-main-'+label,passed=True));flows.append(dict(case=label,trace=trace,stage=saved['stage'],complete=saved['complete']))
if __name__=='__main__':main()
