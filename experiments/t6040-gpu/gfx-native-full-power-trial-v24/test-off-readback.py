#!/usr/bin/env python3
"""Bounded OFF-only qualifier and intercepted once-only readback checks."""
import argparse,hashlib,json,re,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
import analyze_cold_render as analyzer
import readback

def pin(path):
 path=Path(path).resolve();raw=path.read_bytes()
 return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def transform(raw):
 result=[]
 for line in raw.splitlines():
  if re.search(r'phase=(on-get-intent|on-get-return|on-coordinate-return|start-intent|start-return|autonomous-map-retained|boot-running-observed|before-get|after-get|rejoin-final) ',line) or re.search('gfx-postdraw-native-cycle-(rx|tx):',line):continue
  line=line.replace('allocations_retained=174','allocations_retained=176').replace('management_rejoin_verified=1','management_rejoin_verified=0')
  if 'gfx-postdraw-native-cycle-on:' in line:
   line=re.sub(r'\b(get_attempted|get_result|coordinate_on_complete|start_attempted|hello_replied|map_seen|endpoint_map|boot_running_observed)=[^ ]+',r'\1=0',line)
  if 'gfx-postdraw-native-cycle-management:' in line:
   line=re.sub(r'\b(boot_message|boot_metadata|hello_replies|map_replies|advertised_appmap)=[^ ]+',r'\1=0',line)
  if 'gfx-postdraw-native-cycle-state: phase=retained-final ' in line:
   for key,value in {'held':0,'usage':0,'active':0,'suspended':1,'device_access_allowed':0}.items():line=re.sub(r'\b'+key+r'=[^ ]+',key+'='+str(value),line)
  result.append(line)
 return '\n'.join(result)+'\n'

def changed(text,prefix,phase,key,value):
 lines=text.splitlines(True);found=[i for i,line in enumerate(lines) if 'm4rch '+prefix+': phase='+phase+' ' in line]
 assert len(found)==1
 i=found[0];assert re.search(r'\b'+key+r'=',lines[i]);lines[i]=re.sub(r'\b'+key+r'=[^ \n]+',key+'='+str(value),lines[i]);return ''.join(lines)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--source',type=Path,default=ROOT/'out/gfx-native-full-power-trial-v24/prepared-owner-v8');args=p.parse_args();output=args.output.resolve();output.mkdir(exist_ok=False)
 fixture=ROOT/'out/gfx-native-power-assertion-fender-cycle/host-qualification-v1.fixtures/success.log';raw=fixture.read_text();success=transform(raw);token=analyzer.rows(success,'gfx-postdraw-native-cycle')[0]['capture_token'];(output/'off-only-fixture.log').write_text(success)
 source=args.source/'gfx-postdraw-native-nmi-cycle.h';actual=source.read_text();assert 'gfx_cold_retained_pages(),0U); /* v24 never rejoins */' in actual and 'stop after bounded OFF; no wake or management rejoin' in actual
 cases=[]
 def check(name,text,accepted):
  try:q=analyzer.qualify_postdraw_cycle(text,token);ok=q['qualified'] and q['physical_OFF_verified'] and not q['management_rejoin_verified']
  except (ValueError,KeyError,TypeError,IndexError):ok=False
  assert ok==accepted,name;cases.append(dict(case=name,passed=True))
 check('OFF-terminal-success',success,True)
 mutants={
  'legacy-rejoin':success.replace('management_rejoin_verified=0','management_rejoin_verified=1'),
  'ON-get':success.replace('get_attempted=0','get_attempted=1'),
  'ON-start':success.replace('start_attempted=0','start_attempted=1'),
  'ON-intent':success+'m4rch gfx-postdraw-native-cycle: phase=on-get-intent result=0\n',
  'physical-busy':changed(success,'gfx-postdraw-native-cycle-physical','after-off','word','0x80000000'),
  'PM-held':changed(success,'gfx-postdraw-native-cycle-state','off-qualified','held',1),
  'old-174-pages':success.replace('allocations_retained=176','allocations_retained=174'),
  'wrong-token':success.replace(token,'1'*64),
  'CPU-not-stopped':changed(success,'gfx-postdraw-native-cycle-off','off-qualified','cpu_stopped',0),
  'final-error':changed(success,'gfx-postdraw-native-cycle','retained-final','result',-5),
 }
 final=next(line for line in success.splitlines(True) if 'gfx-postdraw-native-cycle: phase=retained-final ' in line);mutants['duplicate-final']=success+final
 for name,text in mutants.items():check('refuse-'+name,text,False)
 flows=[]
 for scenario in ['qualified','unknown-retained','tamper-before-write','tamper-after-write']:
  with tempfile.TemporaryDirectory(prefix='v24-off-readback-') as directory:
   session=Path(directory);writes=[];reads=[];manifest=None;boundtoken=None
   def seal(*unused):
    nonlocal manifest,boundtoken
    (session/'immutable.bin').write_bytes(b'capture-sealed');capture=pin(session/'immutable.bin');capture['relative']='immutable.bin';capture.pop('path')
    manifest=dict(schema=readback.PRE_CYCLE_SCHEMA,complete=True,capture_pins=[capture]);rawmanifest=json.dumps(manifest).encode();(session/'pre-cycle-attempt.json').write_bytes(rawmanifest);boundtoken=readback.sha(rawmanifest);return boundtoken,manifest
   def dmesg(command,**unused):
    assert command==['dmesg','--color=never'];reads.append(command)
    if len(reads)==1:
     if scenario=='tamper-before-write':(session/'immutable.bin').write_bytes(b'changed')
     return 'offline-prefix\n'
    assert len(reads)==2
    if scenario=='tamper-after-write':(session/'immutable.bin').write_bytes(b'changed-after-write')
    text=success if scenario in ('qualified','tamper-after-write') else mutants['physical-busy'];return 'offline-prefix\n'+text.replace(token,boundtoken)
   def write(command,**kwargs):
    assert len(writes)==0 and command[:3]==[sys.executable,'-c',readback.WRITE_ONCE_CODE] and command[3]=='/sys/kernel/m4rch_gpu_graph_trial/command' and command[4]=='postdraw-native-cycle '+boundtoken+'\n' and kwargs['timeout']==45
    writes.append(command);return SimpleNamespace(returncode=0,stdout='',stderr='')
   with patch.object(readback,'seal_pre_cycle',seal),patch.object(readback,'retained_owner_guard',lambda *unused:None),patch.object(readback.subprocess,'check_output',dmesg),patch.object(readback.subprocess,'run',write),patch.object(readback.os,'sync',lambda:None):
    report=readback.attempt_postdraw_cycle(session,session,session/'module.ko','offline',{})
   assert not report['management_rejoin_verified'] and not report['command_replayed'] and not report['postcycle_GPU_register_reads'] and not report['postcycle_RAM_samplers'] and not report['backing_freed'] and not report['owner_unloaded']
   if scenario=='qualified':assert report['stage']=='off-qualified' and report['physical_OFF_verified'] and len(writes)==1
   elif scenario=='unknown-retained':assert report['stage']=='off-unknown-retained' and not report['physical_OFF_verified'] and len(writes)==1 and report['independent_shutdown_observations']['paired_PM_accounting_observed']
   elif scenario=='tamper-after-write':assert report['stage']=='off-unknown-retained' and not report['physical_OFF_verified'] and report['command_uncertain'] and len(writes)==1 and report['qualification']['qualified'] is True and not report['cycle_capture_complete']
   else:assert report['stage']=='cycle-not-admitted' and not report['physical_OFF_verified'] and not writes
   flows.append(dict(case=scenario,passed=True,writes=len(writes),dmesg_reads=len(reads),stage=report['stage']))
 report=dict(schema='m4rch.native-v24-off-readback-bounded-qualification.v1',inputs=[pin(p) for p in [Path(__file__),fixture,source,HERE/'readback.py',HERE/'analyze_cold_render.py',HERE/'cold_render_contract.py',output/'off-only-fixture.log']],cases=cases,case_count=len(cases),flows=flows,passed=True,hardware_actions=[],full_writer_comparisons_repeated=False,scope='OFF-only terminal transformation of saved full-cycle fixture plus actual readback once-write/custody flow with dmesg, child write, owner admission and manifest sealing intercepted; no live source or full initial admission proof')
 (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),flows=len(flows),hardware_actions=[])))
if __name__=='__main__':main()
