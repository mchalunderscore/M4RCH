#!/usr/bin/env python3
"""ONE first OFF, then two independently proved retained management epochs."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
BASE_KIT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(BASE_KIT))
from ap_repeat_cycle_wrapper import source,replace_once,translate
from gfx_native_ap_repeat_cycle_contract import (COMMANDS,FAMILY_KEY,OPERATION_SCHEMA,
 SECOND_COMMAND,THIRD_COMMAND,REFUSED_BOOTS,validate_receipt,qualify_first_off_logs,
 qualify_retained_off_logs,log_delta)
from gfx_reset_contract import require

def _closed_capture(directory,receipt,state,name):
 """Exactly seven saved raw inputs; no live access and no fallback log join."""
 directory=directory.resolve()
 require(directory.parent.name=='resident-operations' and
  directory.parent.parent.name=='boot-'+state['boot_id'] and
  str(directory.parent.parent)==state.get('session_directory'),'Proof escapes exact resident session')
 path=directory/'attempt.json';report=json.loads(path.read_text())
 require(report.get('schema')==OPERATION_SCHEMA and report.get('boot_id')==state['boot_id'] and
  report.get('validated_build_receipt')==receipt and report.get('requested_command')==name and
  report.get('epoch')=={'gfx-powergate':1,SECOND_COMMAND:2,THIRD_COMMAND:3}[name] and
  report.get('initial_session')==str(directory.parent.parent),'Closed capture identity differs')
 require(report.get('complete') is True and not report.get('capture_errors') and not report.get('error') and
  report.get('module_present') is True and report.get('allocations_retained') is True and
  report.get('powergate_attempted') is True and report.get('submit_attempted') is False and
  report.get('operation_uncertain') is False,'Closed capture is incomplete or quarantined')
 commands=report.get('commands')
 require(isinstance(commands,list) and len(commands)==1 and commands[0].get('command')==name and
  commands[0].get('stage')=='returned' and commands[0].get('result')=='success',
  'Closed host command did not complete exactly once')
 require(type(commands[0].get('started_monotonic')) in (int,float) and
  type(commands[0].get('finished_monotonic')) in (int,float) and
  0<=commands[0]['started_monotonic']<=commands[0]['finished_monotonic'],'Host chronology invalid')
 pins=[]
 def bind(p):
  raw=p.read_bytes();pins.append(dict(path=str(p.resolve()),sha256=sha(raw),bytes=len(raw)));return raw
 bind(path);captures={}
 for key,name,extent in (('objects','objects-after.bin',receipt['graph_object_pages']*PAGE_SIZE),
  ('owned','owned-after.bin',receipt['joined_owned_pages']*PAGE_SIZE),
  ('notifications','notifications-after.bin',None),('dmesg','dmesg-after.log',None)):
  raw=bind(directory/name);info=report['final_capture'][key]
  require(info.get('sha256')==sha(raw),'Raw capture changed: '+key)
  if extent is not None:require(len(raw)==extent and info.get('bytes')==extent,'Raw extent differs: '+key)
  captures[key]=raw
 journal=runpy.run_path(str(BASE_KIT/'decode-receive-journal.py'))['decode'](captures['notifications'])
 require(journal['header']['status_flags']==0 and journal['header']['used']<journal['header']['capacity'] and
  journal['authoritative_records_sha256']==report['final_capture']['notifications'].get('authoritative_records_sha256'),
  'Receive journal invalid or full')
 require(json.loads(bind(directory/'notifications-after.json'))==journal,'Decoded journal differs')
 before=bind(directory/'dmesg-before.log').decode();after=captures['dmesg'].decode()
 # The frozen helper rejects truncation/ambiguous joins; there is no whole-log fallback.
 delta=log_delta(before,after)
 return report,pins,journal,delta

def _proof(directory,receipt,state,epoch):
 name='gfx-powergate' if epoch==1 else SECOND_COMMAND if epoch==2 else THIRD_COMMAND
 report,pins,journal,delta=_closed_capture(directory,receipt,state,name)
 if epoch==1:
  require(not report.get('retained_cycle_attempted') and not report.get('third_cycle_attempted'),
   'First OFF capture contains later epoch intent')
  native=qualify_first_off_logs(delta);predecessor=None
  require(all(r.get('epoch')==1 for k,v in native.items() for r in (v if isinstance(v,list) else [v])),
   'First OFF native epoch is missing or crossed')
 else:
  require(report.get('retained_cycle_attempted') is True and
   report.get('third_cycle_attempted') is (epoch==3),'Retained command intent provenance differs')
  first=state.get('first_off_proof');verify_first_off_proof(first,receipt,state)
  require(report.get('first_off_proof')==first,'Retained operation lost immutable first epoch link')
  native=qualify_retained_off_logs(delta,epoch)
  cold=state['cold_ap_power']
  on=native['final_rows'][(SECOND_COMMAND if epoch==2 else THIRD_COMMAND)+'-on']
  require(on['cold_ap_reply_metadata']==cold['reply']['reply_metadata'] and
   on['cold_ap_reply_message']==cold['reply']['reply_message'] and cold['wire_state']==0x20,
   'Retained cold AP chain differs from exact original reply')
  predecessor=first if epoch==2 else state.get('second_off_proof')
  if epoch==3:
   verify_second_off_proof(predecessor,receipt,state)
   require(report.get('second_off_proof')==predecessor,'Third operation lost exact second predecessor link')
  else:require(report.get('second_off_proof') is None,'Second capture uses a stale predecessor')
  previous=json.loads((Path(predecessor['operation_directory'])/'attempt.json').read_text())
  require(report['commands'][0]['started_monotonic']>=previous['commands'][0]['finished_monotonic'] and
   predecessor['operation_directory']!=str(directory.resolve()),'Retained predecessor chronology differs')
 return dict(schema='m4rch.gfx-ap-repeat-'+('first' if epoch==1 else 'second' if epoch==2 else 'third')+'-off-proof.v1',
  qualified=True,epoch=epoch,boot_id=state['boot_id'],owner_sha256=receipt['artifact_sha256'][MODULE_ARTIFACT],
  operation_directory=str(directory.resolve()),native=native,owned_pages=receipt['joined_owned_pages'],
  journal_used=journal['header']['used'],raw_input_pins=pins,predecessor=predecessor,snapshots_atomic=False,
  cold_ap_power=state['cold_ap_power'],
  qualification='Saved own management OFF/accounting only; fresh kernel identity/physical/transport gates still required. No application rejoin or retirement claim.')

def first_off_proof(directory,receipt,state):return _proof(directory,receipt,state,1)
def second_off_proof(directory,receipt,state):return _proof(directory,receipt,state,2)
def third_off_proof(directory,receipt,state):return _proof(directory,receipt,state,3)

def _verify(proof,receipt,state,epoch):
 require(isinstance(proof,dict) and proof.get('qualified') is True and proof.get('epoch')==epoch and
  proof.get('boot_id')==state['boot_id'] and proof.get('owner_sha256')==receipt['artifact_sha256'][MODULE_ARTIFACT],
  'Missing or mismatched saved epoch proof')
 require(_proof(Path(proof['operation_directory']),receipt,state,epoch)==proof,'Saved epoch raw proof changed')
def verify_first_off_proof(proof,receipt,state):_verify(proof,receipt,state,1)
def verify_second_off_proof(proof,receipt,state):_verify(proof,receipt,state,2)

def execution_admission(name,receipt,state):
 require(validate_receipt(receipt),'Distinct repeat scope missing')
 require(name in COMMANDS,'Unknown repeat command')
 if name in ('sample','gfx-snapshot'):return
 require(state.get('powergate_ready') is True,'Qualified repeat startup required')
 require(not any(state.get(k) for k in ('submit_attempted','in_flight','interrupted_operation',
  'operation_uncertain','power_off_attempted','host_stop_requested','gfx_reset_attempted',
  'state_created_with_existing_history')),'Unknown or incompatible intent admits diagnostics only')
 require(not state.get('third_cycle_attempted'),'Third epoch intent is consumed; diagnostics only')
 if name=='gfx-powergate':
  require(not state.get('powergate_attempted') and not state.get('retained_cycle_attempted'),
   'First OFF intent is consumed');return
 require(state.get('powergate_attempted') is True,'First OFF has not been attempted')
 verify_first_off_proof(state.get('first_off_proof'),receipt,state)
 if name==SECOND_COMMAND:
  require(not state.get('retained_cycle_attempted'),'Second epoch intent is consumed');return
 require(state.get('retained_cycle_attempted') is True,'Second epoch has not been attempted')
 verify_second_off_proof(state.get('second_off_proof'),receipt,state)

def quarantine_operation_history(operations,receipt,state,state_path):
 """Every prior operation and predecessor is rebuilt; unknown history seals controls."""
 changed=False;epochs={1:[],2:[],3:[]}
 try:
  for directory in sorted(operations.iterdir()):
   if not directory.is_dir():continue
   report=json.loads((directory/'attempt.json').read_text());name=report.get('requested_command')
   require(report.get('schema')==OPERATION_SCHEMA and report.get('boot_id')==state['boot_id'] and
    report.get('validated_build_receipt')==receipt and name in COMMANDS and
    report.get('initial_session')==str(operations.parent),'Operation history identity differs')
   commands=report.get('commands')
   require(isinstance(commands,list) and len(commands)==1 and commands[0].get('command')==name and
    commands[0].get('stage')=='returned' and commands[0].get('result')=='success',
    'Unknown, mixed or interrupted operation history')
   for epoch,command_name,flag in ((1,'gfx-powergate','powergate_attempted'),
    (2,SECOND_COMMAND,'retained_cycle_attempted'),(3,THIRD_COMMAND,'third_cycle_attempted')):
    if name==command_name:
     epochs[epoch].append(directory)
     if not state.get(flag):state[flag]=True;changed=True
   require(report.get('complete') is True and not report.get('error') and not report.get('capture_errors') and
    report.get('operation_uncertain') is False and report.get('allocations_retained') is True and
    report.get('submit_attempted') is False,'Incomplete or unrelated earlier operation')
  require(all(len(v)<=1 for v in epochs.values()),'Duplicate epoch intents in operation history')
  require(not epochs[2] or epochs[1],'Second epoch has no first predecessor')
  require(not epochs[3] or epochs[2],'Third epoch has no second predecessor')
  for epoch,key,flag in ((1,'first_off_proof','powergate_attempted'),(2,'second_off_proof','retained_cycle_attempted')):
   if epochs[epoch]:
    proof=_proof(epochs[epoch][0],receipt,state,epoch);old=state.get(key)
    require(old is None or old==proof,'Saved predecessor proof differs')
    if old is None:state[key]=proof;changed=True
   else:require(state.get(key) is None and not state.get(flag),'Saved epoch history is missing')
  if epochs[3]:third_off_proof(epochs[3][0],receipt,state)
  else:require(not state.get('third_cycle_attempted'),'Third intent history is missing')
 except (ValueError,KeyError,OSError,TypeError,AttributeError):
  if not state.get('operation_uncertain'):state['operation_uncertain']=True;changed=True
 if changed:
  state['operation_failed']=True;save_json(state_path,state)

def runner_source():
 text=translate(source('run-powergate.py'))
 text=replace_once(text,"COMMANDS = ('sample', 'gfx-snapshot', 'gfx-powergate', 'gfx-native-ap-repeat-cycle')",
  'COMMANDS = '+repr(COMMANDS))
 text=replace_once(text,"    require(os.geteuid() == 0, 'Native sudo required')\n    work = args.workspace.resolve()\n    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()",
  "    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n    require(bool(boot) and boot not in REFUSED_BOOTS, 'Consumed boot refused before candidate or live reads')\n    require(os.geteuid() == 0, 'Native sudo required')\n    work = args.workspace.resolve()")
 text=replace_once(text,"    delta = logs[len(prior):] if logs.startswith(prior) else logs",'    delta = log_delta(prior, logs)')
 text=replace_once(text,"            'retained_cycle_attempted': False, 'first_off_proof': None}",
  "            'retained_cycle_attempted': False, 'first_off_proof': None,\n            'third_cycle_attempted': False, 'second_off_proof': None,\n            'state_created_with_existing_history': any(p.is_dir() for p in operations.iterdir())}")
 text=replace_once(text,"            'boot_id': boot, 'candidate_module_sha256': receipt['artifact_sha256'][MODULE_ARTIFACT],",
  "            'boot_id': boot, 'session_directory': str(session.resolve()),\n            'candidate_module_sha256': receipt['artifact_sha256'][MODULE_ARTIFACT],")
 text=replace_once(text,"            'trace_disabled': False, 'powergate_attempted': False,",
  "            'trace_disabled': False, 'powergate_attempted': False,\n            'cold_ap_power': original['native_powergate_startup']['cold_ap_power'],")
 text=replace_once(text,"        require(state.get('family') == 'gfx_native_ap_repeat_cycle_scope', 'Operation state family differs')",
  "        require(state.get('family') == 'gfx_native_ap_repeat_cycle_scope' and state.get('session_directory') == str(session.resolve()) and state.get('cold_ap_power') == original['native_powergate_startup']['cold_ap_power'], 'Operation state family/session/original cold AP proof differs')")
 text=replace_once(text,"        report['first_off_proof'] = state['first_off_proof']\n    save_json(output / 'attempt.json', report)",
  "        report['first_off_proof'] = state['first_off_proof']\n    if name == 'gfx-native-ap-repeat-third':\n        state['third_cycle_attempted'] = True\n        state['operation_failed'] = True\n        report['reboot_required'] = True\n        report['first_off_proof'] = state['first_off_proof']\n        report['second_off_proof'] = state['second_off_proof']\n    save_json(output / 'attempt.json', report)")
 text=replace_once(text,"            report['first_off_proof'] = state.get('first_off_proof')",
  "            report['first_off_proof'] = state.get('first_off_proof')\n            report['third_cycle_attempted'] = state.get('third_cycle_attempted', False)\n            report['second_off_proof'] = state.get('second_off_proof')")
 text=replace_once(text,"                  'requested_command': args.command, 'initial_session': str(session),",
  "                  'requested_command': args.command, 'initial_session': str(session),\n                  'epoch': {'gfx-powergate':1,'gfx-native-ap-repeat-cycle':2,'gfx-native-ap-repeat-third':3}.get(args.command,0),")
 return text

exec(compile(runner_source(),str(HERE/'run-powergate.py'),'exec'),globals())
