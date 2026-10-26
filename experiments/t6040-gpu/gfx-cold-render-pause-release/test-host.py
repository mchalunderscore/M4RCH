#!/usr/bin/env python3
"""Narrow v14 release/log-rotation qualifications; no hardware or unchanged reruns."""
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
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--owner-qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();snapshot=a.output.with_name(a.output.stem+'.source');snapshot.mkdir(exist_ok=False)
 names=('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')
 for name in names:
  raw=(HERE/name).read_bytes();(snapshot/name).write_bytes(raw);input_paths.extend([HERE/name,snapshot/name])
 cq=json.loads(a.owner_qualification.read_text());fixture=cq['success_log_fixture'];fpath=Path(fixture['path']);log=fpath.read_text();assert contract.sha(log.encode())==fixture['sha256']
 input_paths.extend([a.owner_qualification,fpath,a.source/'cold-render-pause-release-owner-source-receipt.json',*[a.source/name for name in ('graph-before.bin','graph-receipt.json','backing.bin')]])
 checked('actual-C-base-pipeline-join',lambda:analyzer.qualify_pipeline(log),True);checked('actual-C-typed-release-join',lambda:analyzer.qualify_release(log),True)
 for phase in ('eligible','intent','write-intent','readback','released','retained-final'):
  line=next(x for x in log.splitlines(True) if 'gfx-cold-pause-release: phase='+phase+' ' in x)
  checked('missing-release-'+phase,lambda l=log.replace(line,''):analyzer.qualify_release(l),False)
  checked('duplicate-release-'+phase,lambda l=log+line:analyzer.qualify_release(l),False)
 eligible=next(x for x in log.splitlines(True) if 'gfx-cold-pause-release: phase=eligible ' in x)
 mutations={'clear-bit1':('written=0x2','written=0'),'wrong-initial-ack':('ack=0x2','ack=0x3'),'wrong-initial-request':('before=0x3','before=0x1'),'wrong-sample':('sample_index=2','sample_index=1'),'wrong-enabled-mask':('offset21038=0x3','offset21038=0'),'wrong-second-enable':('offset21040=0','offset21040=1'),'output-already-progressed':('target_changed=0','target_changed=1'),'software-already-progressed':('completion_changed=0','completion_changed=1'),'hardware-already-progressed':('changed=0','changed=1'),'fault-address':('fault_addr=0','fault_addr=0x4000'),'different-config':('config=0x400010000d8001','config=0x400010000d8000')}
 for label,(before,after) in mutations.items():
  assert before in log;checked('release-refuses-'+label,lambda l=log.replace(before,after):analyzer.qualify_release(l),False)
 release_lines=[x for x in log.splitlines(True) if 'gfx-cold-pause-release:' in x and any('phase='+p+' ' in x for p in ('eligible','intent','write-intent','readback','released'))]
 removed=log
 for line in release_lines:removed=removed.replace(line,'',1)
 checked('relocated-release-before-own-sample',lambda:analyzer.qualify_release(''.join(release_lines)+removed),False)
 checked('relocated-release-after-sample3',lambda:analyzer.qualify_release(removed+''.join(release_lines)),False)
 for label,before,after,accepted in [('strict-prefix','before\n','before\n'+log,True),('unique-overlap','discard\nshared\n','shared\n'+log,True),('no-overlap','before\n','different\n'+log,False),('ambiguous-overlap','discard\nshared\nshared\n','shared\nshared\n'+log,False),('empty-no-overlap','before\n','',False)]:
  checked('association-'+label,lambda b=before,z=after:contract.associate_logs(b,z),accepted)
 root=module('pause_actual_launcher',HERE/'run-cold-render.py');preflight=module('pause_actual_preflight',HERE/'preflight-fresh.py');boot='1241f6b5-f2c5-4678-9078-dce0ed367d60'
 for label,obj,argv in [('cold',root,['run-cold-render.py','/tmp/unselected-pause','--graph','--run']),('preflight',preflight,['preflight-fresh.py','/tmp/unselected-pause','/tmp/unwritten-pause'])]:
  reads=[]
  def rt(path,*args,**kwargs):assert str(path)=='/proc/sys/kernel/random/boot_id';reads.append(str(path));return boot
  def rb(path,*args,**kwargs):raise AssertionError('Content before1241refusal: '+str(path))
  with patch.object(Path,'read_text',rt),patch.object(Path,'read_bytes',rb),patch.object(obj.sys,'argv',argv):checked('earliest1241-'+label,obj.main,False)
  assert reads==['/proc/sys/kernel/random/boot_id'];flows.append(dict(case=label+'-1241-early-refusal',boot=boot,reads=reads))
 template=json.loads((ROOT/'out/gfx-cold-render/candidate-v2/asc-root-envelope/build-receipt.json').read_text())
 for k in list(template['graph_recovery_trial']):
  if k.endswith('_scope'):del template['graph_recovery_trial'][k]
 template['graph_recovery_trial'].update(cycles=0,work_submitted=False);template['graph_recovery_trial'][contract.FAMILY_KEY]=copy.deepcopy(contract.CONTRACT)
 checked('distinct-v14-contract',lambda:contract.validate_receipt(template),True)
 run_flow(root,a.source,template,log,'actual-success');run_flow(root,a.source,template,log,'actual-exact-overlap',overlap=True);run_flow(root,a.source,template,log,'actual-no-overlap',rotate=True)
 run_flow(root,a.source,template,log,'missing-module',present=False);run_flow(root,a.source,template,log,'wrong-loaded-owner',note=bytes(36))
 for cf in cq['actual_log_fixtures']:
  if cf['case'] not in ('later-reasserted','later-otherbits','ack-zero','request-two','write-dropped','readback-reasserted','ack-timeout'):continue
  path=Path(cf['path']);data=path.read_bytes();assert contract.sha(data)==cf['sha256'];input_paths.append(path);text=data.decode()
  accepted=cf['case'] in ('later-reasserted','later-otherbits','ack-zero');checked('actual-C-release-'+cf['case'],lambda l=text:analyzer.qualify_release(l),accepted)
  if not accepted:run_flow(root,a.source,template,text,'diagnostic-'+cf['case'],diagnostic=True)
 for name in ('run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','frozen_source.py','cold_render_contract.py','finalize-cold-render.py'):input_paths.append(HERE.parent/'gfx-cold-render'/name)
 for name in ('prepare-apple9-shaders.py','prepare-apple9-target.py','decode-receive-journal.py'):input_paths.append(HERE.parent/name)
 for loaded in list(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file and str(file).endswith('.py') and Path(file).resolve().is_relative_to(ROOT):input_paths.append(Path(file))
 frozen=ROOT/'out/gfx-cold-render/wrapper-qualification-v4.json';assert contract.sha(frozen.read_bytes())=='ce085fb9c4cd5c89cc908ab7e2c726053cb00ee7e57ad788ce712cdb795923ce';input_paths.append(frozen)
 report=dict(schema='m4rch.gfx-cold-render-pause-release-host-qualification.v1',passed=True,hardware_access=False,case_count=len(cases),cases=cases,actual_main_flows=flows,actual_main_flow_count=len(flows),actual_C_success_log_qualified=True,actual_C_typed_release_qualified=True,actual_C_success_log_sha256=fixture['sha256'],source_receipt_sha256=contract.sha((a.source/'cold-render-pause-release-owner-source-receipt.json').read_bytes()),inputs=[pin(path) for path in dict.fromkeys(input_paths)],frozen_v13_C_cases=56,frozen_v13_host_cases=74,unchanged_cases_repeated=False,qualification='Newtyped one-write/source-sample joins and intercepted raw-first launcher/log-rotation paths only. Frozen v13 readback/native/capture tests compose without rerun. No module build/load, MMIO, GPU access or rendered pixels.')
 with a.output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(cases=len(cases),actual_main_flows=len(flows),output=str(a.output),sha256=contract.sha(a.output.read_bytes()))))
def run_flow(root,source,template,log,label,present=True,note=None,truncate=False,stale=False,rotate=False,overlap=False,diagnostic=False,incomplete=False):
 module_raw,module_note=elf();note=module_note if note is None else note
 adt_path=ROOT/'out/gfx-native-reset-owner/candidate/asc-graph-init/boot-a1f61d61-b0ec-4475-948b-e3de2741e60b/boot.adt';adt_raw=adt_path.read_bytes();tree=parse(adt_raw);input_paths.append(adt_path)
 with tempfile.TemporaryDirectory(prefix='cold-host-'+label+'-') as tmp:
  work=Path(tmp);graph=work/'asc-graph-init';build=work/'asc-root-envelope';graph.mkdir();build.mkdir();(work/'analysis-inputs').mkdir()
  for name in ('graph-before.bin','graph-receipt.json','backing.bin'):shutil.copyfile(source/name,graph/name)
  shutil.copyfile(ROOT/'out/gfx-native-ap-repeat-cycle/candidate/analysis-inputs/target-receipt.json',work/'analysis-inputs/target-receipt.json')
  (graph/'asc-graph-init.ko').write_bytes(module_raw)
  fixture=copy.deepcopy(template);fixture['artifact_sha256']={'asc-graph-init/asc-graph-init.ko':contract.sha(module_raw)};fixture['graph_source_sha256']={};fixture['kernel_notes_sha256']=contract.sha(b'kernel-note')
  fixture['graph_fixture_sha256']=contract.sha((graph/'graph-before.bin').read_bytes());fixture['graph_receipt_sha256']=contract.sha((graph/'graph-receipt.json').read_bytes())
  (build/'build-receipt.json').write_text(json.dumps(fixture));(work/'cold-render-preparation.json').write_text(json.dumps(dict(schema='m4rch.gfx-cold-render-pause-release-preparation.v1',candidate_receipt_sha256=contract.sha((build/'build-receipt.json').read_bytes()),owner_sha256=contract.sha(module_raw),inputs=[],analysis_input_pins=[])))
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
   before='discarded\nshared exact overlap\n'+(log if stale else '')
   return before if dmesg==1 else 'shared exact overlap\n'+log if overlap else 'rotated\n'+log if rotate else before if stale else before+log
  with contextlib.ExitStack() as stack:
   for obj,name,value in [(root.sys,'argv',['run-cold-render.py',str(work),'--graph','--run']),(root.os,'geteuid',lambda:0),(root.os,'uname',lambda:SimpleNamespace(release=fixture['kernel_release'])),(root.os,'sync',lambda:trace.append(('sync',None,cold))),(root,'parse',lambda data:tree),(root,'qualify',lambda data:{'offline_fixture':True}),(root,'qualify_linux_dt',lambda:{'composed_frozen_layout':True}),(root,'capture',capture),(root.subprocess,'run',execute),(root.subprocess,'check_output',output),(Path,'read_bytes',rb),(Path,'read_text',rt),(Path,'exists',exists)]:stack.enter_context(patch.object(obj,name,value))
   stack.enter_context(contextlib.redirect_stdout(io.StringIO()));root.main()
  saved=json.loads((session/'attempt.json').read_text())
  if label in ('actual-success','actual-exact-overlap'):
   assert saved['complete'] and saved['raw_capture_complete'] and saved['pipeline']['qualified'] and saved['release']['qualified'] and not saved.get('analysis_error'),saved
   if overlap:assert saved['log_association']['method']=='unique-exact-suffix',saved
  elif stale:assert saved['complete'] and saved['raw_capture_complete'] and not saved['pipeline']['qualified'],saved
  elif rotate:
   assert saved['complete'] and saved['raw_capture_complete'] and saved['operation_uncertain'] and not saved['log_association']['qualified'] and saved['capture_errors']==[] and not saved.get('analysis_error'),saved
   analysis=json.loads((session/'analysis/result.json').read_text());assert not analysis['publication']['qualified'] and not analysis['release']['qualified'] and analysis['whole_image']['untouched_sentinel'],analysis
   assert all((session/name).exists() for name in ('owned-after.bin','objects-after.bin','notifications-after.bin','target-after.bin','completion-after.bin','queues-after.bin','hardware-completions-after.bin')),saved
  elif diagnostic:
   assert saved['complete'] and saved['raw_capture_complete'] and not saved['release']['qualified'] and not saved.get('analysis_error'),saved
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
