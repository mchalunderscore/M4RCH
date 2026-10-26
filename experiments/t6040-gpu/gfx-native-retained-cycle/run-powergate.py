#!/usr/bin/env python3
"""ONE first OFF and ONE evidence-gated retained management roundtrip."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
BASE_KIT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(BASE_KIT))
from native_retained_wrapper import source,replace_once
from gfx_native_retained_cycle_contract import (COMMANDS,FAMILY_KEY,OPERATION_SCHEMA,
    CONTRACT,validate_receipt,qualify_first_off_logs,log_delta)
from gfx_reset_contract import require


def first_off_proof(directory,receipt,state):
    """Read and hash complete captured first-OFF evidence; no native access."""
    path=directory/'attempt.json'
    report=json.loads(path.read_text())
    require(report.get('schema')==OPERATION_SCHEMA and report.get('boot_id')==state['boot_id'] and
        report.get('validated_build_receipt')==receipt and
        report.get('requested_command')=='gfx-powergate' and
        report.get('initial_session')==str(directory.parent.parent),
        'First OFF capture identity differs')
    require(report.get('complete') is True and not report.get('capture_errors') and
        not report.get('error') and report.get('module_present') is True and
        report.get('allocations_retained') is True and report.get('powergate_attempted') is True and
        report.get('submit_attempted') is False and report.get('operation_uncertain') is False,
        'First OFF capture is incomplete or quarantined')
    commands=report.get('commands')
    require(isinstance(commands,list) and len(commands)==1 and
        commands[0].get('command')=='gfx-powergate' and
        commands[0].get('stage')=='returned' and commands[0].get('result')=='success',
        'First OFF host command did not complete')
    require(0 <= commands[0]['started_monotonic'] <= commands[0]['finished_monotonic'],
        'First OFF host chronology invalid')
    pins=[]
    def bind(p):
        raw=p.read_bytes()
        pins.append({'path':str(p.resolve()),'sha256':sha(raw),'bytes':len(raw)})
        return raw
    bind(path)
    captures={}
    for key,name,extent in (('objects','objects-after.bin',receipt['graph_object_pages']*PAGE_SIZE),
        ('owned','owned-after.bin',receipt['joined_owned_pages']*PAGE_SIZE),
        ('notifications','notifications-after.bin',None),('dmesg','dmesg-after.log',None)):
        raw=bind(directory/name);info=report['final_capture'][key]
        require(info.get('sha256')==sha(raw),'First OFF raw capture changed: '+key)
        if extent is not None:
            require(len(raw)==extent and info.get('bytes')==extent,'First OFF raw extent differs: '+key)
        captures[key]=raw
    journal=runpy.run_path(str(BASE_KIT/'decode-receive-journal.py'))['decode'](captures['notifications'])
    require(journal['header']['status_flags']==0 and journal['header']['used']<journal['header']['capacity'] and
        journal['authoritative_records_sha256']==report['final_capture']['notifications'].get('authoritative_records_sha256'),
        'First OFF receive journal is invalid or full')
    decoded=bind(directory/'notifications-after.json')
    require(json.loads(decoded)==journal,'First OFF decoded receive journal differs')
    before=bind(directory/'dmesg-before.log').decode()
    after=captures['dmesg'].decode()
    native=qualify_first_off_logs(log_delta(before,after))
    return {'schema':'m4rch.gfx-retained-first-off-proof.v1','qualified':True,
        'boot_id':state['boot_id'],'owner_sha256':receipt['artifact_sha256'][MODULE_ARTIFACT],
        'operation_directory':str(directory.resolve()),'native':native,
        'owned_pages':receipt['joined_owned_pages'],'journal_used':journal['header']['used'],
        'raw_input_pins':pins,'snapshots_atomic':False,
        'qualification':'Saved first physical OFF and accounting only; current identity/physical/transport gates remain mandatory in the kernel.'}


def verify_first_off_proof(proof,receipt,state):
    require(isinstance(proof,dict) and proof.get('qualified') is True and
        proof.get('boot_id')==state['boot_id'] and proof.get('owner_sha256')==
        receipt['artifact_sha256'][MODULE_ARTIFACT],'Missing or mismatched saved first OFF proof')
    directory=Path(proof['operation_directory'])
    require(directory.parent.name=='resident-operations' and
        directory.parent.parent.name=='boot-'+state['boot_id'],'First OFF proof escapes session')
    rebuilt=first_off_proof(directory,receipt,state)
    require(rebuilt==proof,'First OFF proof changed since admission')


def execution_admission(name,receipt,state):
    require(validate_receipt(receipt),'Distinct retained-cycle scope missing')
    require(name in COMMANDS,'Unknown retained-cycle command')
    if name in ('sample','gfx-snapshot'):return
    require(state.get('powergate_ready') is True,'Qualified retained-cycle startup required')
    require(not any(state.get(key) for key in ('submit_attempted','in_flight',
        'interrupted_operation','operation_uncertain','power_off_attempted',
        'host_stop_requested','gfx_reset_attempted')),'Unknown or incompatible intent admits diagnostics only')
    require(not state.get('retained_cycle_attempted'),'Retained cycle intent is consumed')
    if name=='gfx-powergate':
        require(not state.get('powergate_attempted'),'First powergate intent is consumed')
        return
    require(state.get('powergate_attempted') is True,'First powergate has not been attempted')
    verify_first_off_proof(state.get('first_off_proof'),receipt,state)


def quarantine_operation_history(operations,receipt,state,state_path):
    """Lost state cannot erase either epoch; every raw first-OFF proof is rechecked."""
    changed=False;first=[];cycle=[]
    for directory in sorted(operations.iterdir()):
        if not directory.is_dir():continue
        try:
            report=json.loads((directory/'attempt.json').read_text())
            require(report.get('schema')==OPERATION_SCHEMA and report.get('boot_id')==state['boot_id'] and
                report.get('validated_build_receipt')==receipt,'Operation history identity differs')
            name=report.get('requested_command');commands=report.get('commands')
            require(name in COMMANDS and isinstance(commands,list),'Operation history command differs')
            observed={name}|{item.get('command') for item in commands}
            if 'gfx-powergate' in observed:
                first.append(directory)
                if not state.get('powergate_attempted'):state['powergate_attempted']=True;changed=True
            if 'gfx-native-retained-cycle' in observed:
                cycle.append(directory)
                if not state.get('retained_cycle_attempted'):state['retained_cycle_attempted']=True;changed=True
            require(report.get('complete') is True and not report.get('error') and
                not report.get('capture_errors') and not report.get('operation_uncertain'),
                'Incomplete earlier operation')
        except (ValueError,KeyError,OSError,TypeError,AttributeError):
            if not state.get('operation_uncertain'):state['operation_uncertain']=True;changed=True
    try:
        require(len(first)<=1 and len(cycle)<=1,'Duplicate epoch intents in operation history')
        if first:
            proof=first_off_proof(first[0],receipt,state)
            old=state.get('first_off_proof')
            require(old is None or old==proof,'Saved first epoch proof differs')
            if old is None:state['first_off_proof']=proof;changed=True
        else:
            require(state.get('first_off_proof') is None,'Saved first epoch evidence is missing')
    except (ValueError,KeyError,OSError,TypeError,AttributeError):
        if not state.get('operation_uncertain'):state['operation_uncertain']=True;changed=True
    if changed:
        state['operation_failed']=True
        save_json(state_path,state)


def runner_source():
    text=source('run-powergate.py')
    text=text.replace('gfx_retained_power_cycle_contract','gfx_native_retained_cycle_contract')
    text=text.replace('gfx_retained_power_cycle_scope',FAMILY_KEY)
    text=text.replace('m4rch.gfx-retained-power-cycle-operation.v1',OPERATION_SCHEMA)
    text=text.replace('gfx-retained-cycle','gfx-native-retained-cycle')
    return text


exec(compile(runner_source(),str(HERE/'run-powergate.py'),'exec'),globals())
