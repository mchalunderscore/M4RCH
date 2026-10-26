#!/usr/bin/env python3
"""One automatic cold startup/control/draw/capture; no reboot or resident mutation."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from frozen_source import source,replace_once
TAIL='''    present = Path('/sys/module/asc_graph_init').exists()
    before_log=(out/'dmesg-before.log').read_text()
    report.update(schema=ATTEMPT_SCHEMA,boot_id=boot,session=str(out),candidate=str(work),
      selected_module=str(selected),owner_sha256=sha(selected.read_bytes()),
      candidate_receipt_sha256=sha((work/'asc-root-envelope/build-receipt.json').read_bytes()),
      dmesg_before_sha256=sha(before_log.encode()),dmesg_after_sha256=sha(logs.encode()),
      load_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,module_present=present,
      complete=False,operation_uncertain=True,capture_errors=[],capture_pins=[],
      allocations_retained=True,pm_retained=True,unloaded=False,commands_admitted=[],
      interpretation='Automatic cold-render attempt; retained resources and PM, no work reuse or teardown.')
    (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n');os.sync()
    try:
        if not present:raise ValueError('Owner absent after load; outcome and retirement unknown')
        pinned=Path('/sys/module/asc_graph_init')
        note=(pinned/'notes/.note.gnu.build-id').read_bytes()
        require(note==module_build_note(selected.read_bytes()),'Loaded owner GNU note differs')
        require(int((pinned/'refcnt').read_text())==1,'Owner refcount differs from retained1')
        report['loaded_owner_note_hex']=note.hex()
        for name,sysfile,size in [('objects-after.bin','objects',receipt['graph_object_pages']*0x4000),
           ('owned-after.bin','owned',receipt['joined_owned_pages']*0x4000),
           ('notifications-after.bin','notifications',None)]:
            raw=Path('/sys/kernel/m4rch_gpu_graph_trial',sysfile).read_bytes()
            if size is not None:require(len(raw)==size,'Captured extent differs: '+name)
            (out/name).write_bytes(raw)
        decoded=runpy.run_path(str(BASE_KIT/'decode-receive-journal.py'))['decode']((out/'notifications-after.bin').read_bytes())
        (out/'notifications-after.json').write_text(json.dumps(decoded,indent=2)+'\\n')
        owned=(out/'owned-after.bin').read_bytes()
        for name,first,count in [('target-after.bin',132,1),('completion-after.bin',159,1),('queues-after.bin',160,4),('hardware-completions-after.bin',164,4)]:
            (out/name).write_bytes(owned[first*0x4000:(first+count)*0x4000])
        from readback import png
        (out/'target-after.png').write_bytes(png((out/'target-after.bin').read_bytes()))
        from readback import capture_retained_ram
        report['retained_RAM']=capture_retained_ram(work,out,selected,boot,receipt)
        report['retained_RAM_complete']=report['retained_RAM']['complete']
        (out/'dmesg-after-samplers.log').write_text(subprocess.check_output(['dmesg','--color=never'],text=True))
        from cold_render_contract import associate_logs
        from analyze_cold_render import qualify_pipeline,qualify_trace_preserved,qualify_publication
        try:
            association,delta=associate_logs(before_log,logs)
            report['log_association']=association
            (out/'operation-delta.log').write_text(delta)
            for key,qualifier in [('pipeline',qualify_pipeline),('publication',qualify_publication),('trace_preserved',qualify_trace_preserved)]:
                try:report[key]=qualifier(delta)
                except ValueError as error:report[key]={'qualified':False,'error':str(error)}
        except ValueError as error:
            report['log_association']={'qualified':False,'error':str(error)}
            for key in ('pipeline','publication','trace_preserved'):report[key]={'qualified':False,'error':'Saved logs have no exact association'}
        report.update(complete=True,raw_capture_complete=True,operation_uncertain=not report['log_association']['qualified'],stage='capture-closed')
    except Exception as error:
        report['capture_errors'].append(str(error));report['stage']='capture-unknown-retained'
    for name in ('objects-before.bin','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json','target-after.bin','completion-after.bin','queues-after.bin','hardware-completions-after.bin','target-after.png','dmesg-before.log','dmesg-after.log','operation-delta.log','text.bin','data-retained.bin','pagetables-retained.bin','retained-ram-capture.json','dmesg-after-samplers.log'):
        path=out/name
        if path.exists():raw=path.read_bytes();report['capture_pins'].append(dict(name=name,bytes=len(raw),sha256=sha(raw)))
    (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n');os.sync()
    if report['complete']:
        from analyze_cold_render import analyze
        try:analyze(out,work,out/'analysis')
        except Exception as error:
            report['analysis_error']=str(error);(out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n');os.sync()
    from readback import attempt_postdraw_cycle
    cycle=attempt_postdraw_cycle(work,out,selected,boot,receipt)
    print('Draw capture saved; postdraw native cycle outcome: '+cycle['stage'])
'''
def runner_source():
 text=source('run-root-powergate.py')
 text=replace_once(text,'from gfx_native_ap_repeat_cycle_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup, qualify_powergate_startup, REFUSED_BOOTS','from cold_render_contract import validate_receipt, validate_candidate, qualify_adt, qualify_linux_dt, REFUSED_BOOTS, ATTEMPT_SCHEMA, module_build_note, log_delta')
 begin=text.index('def owner_parameters(');end=text.index('\n\ndef sha(',begin)
 text=text[:begin]+'''def owner_parameters(receipt, *, graph=False, arena=False, warm_restart=False):
    require(validate_receipt(receipt) and graph and not arena and not warm_restart,'Only cold graph mode is admitted')
    return ['run_gate=2','observe_ms=5000','resident_session=1']
'''+text[end:]
 text=replace_once(text,"    receipt = json.loads((build/'build-receipt.json').read_text())","    receipt = validate_candidate(work)")
 text=replace_once(text,"    out.mkdir(parents=True,exist_ok=True)","    require(not out.exists(), 'An existing cold session forbids another load')\n    out.mkdir(parents=True,exist_ok=False)")
 text=replace_once(text,"        report.update(stage='cold-load-intent', selected_module=str(selected), cold_parameters=parameters)","        report.update(schema=ATTEMPT_SCHEMA, boot_id=boot, session=str(out), stage='cold-load-intent', automatic_pipeline_intent=True, complete=False, operation_uncertain=True, selected_module=str(selected), cold_parameters=parameters, owner_sha256=sha(selected.read_bytes()), candidate_receipt_sha256=sha((work/'asc-root-envelope/build-receipt.json').read_bytes()))")
 boundary="    present = Path('/sys/module/asc_graph_init' if args.graph else '/sys/module/asc_root_envelope').exists()"
 require_count=text.count(boundary)
 if require_count!=1:raise ValueError('Frozen capture boundary differs')
 return text[:text.index(boundary)]+TAIL+"\nif __name__ == '__main__':\n    main()\n"
exec(compile(runner_source(),str(HERE/'run-cold-render.py'),'exec'),globals())
