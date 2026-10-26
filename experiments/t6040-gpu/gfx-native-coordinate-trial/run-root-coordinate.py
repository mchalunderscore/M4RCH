#!/usr/bin/env python3
"""Exact cold runner with paired coordination and an early retained-failure path.
Never load this future candidate over the retained owner on the current boot.
"""
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
BASE = HERE.parent / 'gfx-poweroff-trial/run-root-poweroff.py'
BASE_SHA = 'b166fc4560d45f2a40b62ea45efc11e02857f49b2259cacb5348a38347de92e7'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Cold runner insertion point changed: ' + old[:90])
    return source.replace(old, new, 1)


def runner_source():
    raw = BASE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError('Frozen cold power-off runner changed')
    source = replace_once(raw.decode(),
        'from gfx_poweroff_contract import validate_receipt',
        'from gfx_coordinate_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup')
    source = replace_once(source, '    tree = parse(raw)\n',
                          '    tree = parse(raw)\n    qualify_adt(tree)\n')
    source = replace_once(source,
        "    require(sha(Path('/sys/kernel/notes').read_bytes()) == receipt['kernel_notes_sha256'], 'Kernel identity mismatch')\n",
        "    require(sha(Path('/sys/kernel/notes').read_bytes()) == receipt['kernel_notes_sha256'], 'Kernel identity mismatch')\n"
        "    qualify_linux_dt()\n")
    source = replace_once(source,
        "    try:\n        result = subprocess.run(['insmod',str(selected)]+parameters,capture_output=True,text=True)",
        "    try:\n"
        "        report.update(stage='cold-load-intent', selected_module=str(selected), cold_parameters=parameters)\n"
        "        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n')\n"
        "        os.sync()\n"
        "        result = subprocess.run(['insmod',str(selected)]+parameters,capture_output=True,text=True)")
    source = replace_once(source,
        "    if args.graph and receipt.get('graph_recovery_trial'):\n        resident=",
        "    if args.graph and power_off_scope and not present:\n"
        "        report.update(stage='cold-load-module-absent-unqualified',resident_session_active=False,diagnostic_session_active=False,commands_admitted=[],unloaded=False,reboot_required=True,startup_outcome_unknown=True)\n"
        "        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n')\n"
        "        os.sync()\n"
        "        print('Module absent after cold-load intent; hardware outcome and retirement are unqualified. Preserve this attempt; no cleanup, powered sampling or retry.')\n"
        "        return\n"
        "    if args.graph and power_off_scope and present:\n"
        "        from runpy import run_path\n"
        "        note_reader=run_path(str(Path(__file__).resolve().parent/'run-coordinate.py'))['module_build_note']\n"
        "        pinned=Path('/sys/module/asc_graph_init')\n"
        "        require((pinned/'notes/.note.gnu.build-id').read_bytes()==note_reader(selected.read_bytes()),'Wrong loaded coordinator module')\n"
        "        module_refcount=int((pinned/'refcnt').read_text())\n"
        "        marker='m4rch gfx-native-coordinate: startup-retained result='\n"
        "        matches=[line for line in delta.splitlines() if marker in line]\n"
        "        if matches:\n"
        "            from gfx_coordinate_contract import qualify_startup_retention\n"
        "            early=qualify_startup_retention(matches, result.returncode, module_refcount, report)\n"
        "            report.update(early,stage='startup-retained-before-firmware',resident_session_active=False,diagnostic_session_active=False,commands_admitted=[],unloaded=False)\n"
        "            (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n')\n"
        "            os.sync()\n"
        "            print('Startup coordination refused; owner, PM reference and acquired resources retained. No firmware START or graph publication. No typed commands, cleanup or retry.')\n"
        "            return\n"
        "        on_records=[line for line in delta.splitlines() if 'm4rch gfx-coordinate-observation: ' in line]\n"
        "        on_owner=[line for line in delta.splitlines() if 'm4rch gfx-coordinate-owner: phase=post-active-on' in line]\n"
        "        retained_graph=('m4rch recovery-session: resident=1 control_ready=1' in delta or 'm4rch recovery-session: diagnostic=1 sealed=1' in delta)\n"
        "        if not retained_graph or not qualify_graph_startup(on_records,on_owner,result.returncode,module_refcount,report):\n"
        "            report.update(stage='startup-outcome-unqualified',resident_session_active=False,diagnostic_session_active=False,commands_admitted=[],unloaded=False,reboot_required=True,startup_outcome_unknown=True,on_records=on_records,on_owner_records=on_owner,module_refcount=int(Path('/sys/module/asc_graph_init/refcnt').read_text()))\n"
        "            (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n')\n"
        "            os.sync()\n"
        "            print('Coordinator startup outcome is unqualified; preserve the owner and all resources. No graph reads, powered samplers, cleanup or retry.')\n"
        "            return\n"
        "    if args.graph and receipt.get('graph_recovery_trial'):\n        resident=")
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
