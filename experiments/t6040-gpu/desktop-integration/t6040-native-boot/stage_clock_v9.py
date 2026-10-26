#!/usr/bin/env python3
"""Fresh offline clock-only normal v9 stage from frozen compiled v8."""
import argparse
import json
from pathlib import Path
import shutil
from stage_v4 import pin
from wire_clock_v9 import wiring
KIT=Path(__file__).resolve().parent
ROOT=KIT.parents[3]
BASE=ROOT/'out/gpu-gravity-normal-boot-v8'
CLOCK=ROOT/'out/gpu-gravity-native-architectural-clock-v9-qualification-v1/qualification.json'

def stage(destination):
    old=json.loads((BASE/'stage-receipt.json').read_text())
    clock=json.loads(CLOCK.read_text())
    for row in old['source_files']+clock['inputs']:
        if pin(row['path']) != row:
            raise ValueError('Qualified source changed: '+row['path'])
    prior=json.loads((BASE/'module-build-closure.json').read_text())
    if not prior['full_module_compiled_and_linked'] or prior['hardware_actions']:
        raise ValueError('Frozen compiled offline v8 required')
    if not clock['independent_rational_reference_agrees'] or clock['capture_function_called']:
        raise ValueError('Actual offline clock qualification required')
    source_base=BASE/'source/linux/drivers/gpu/drm/asahi'
    before={str(Path(row['path']).relative_to(source_base)):Path(row['path']).read_text()
            for row in old['source_files']}
    files=dict(before)
    wiring(files)
    changed=sorted(name for name,text in files.items() if before.get(name)!=text)
    if changed != ['asahi_m4.rs','g16.rs','g16_native_clock.rs','g16_runtime.rs']:
        raise ValueError('Unexpected clock source changes: '+repr(changed))
    destination=destination.resolve()
    destination.relative_to(ROOT/'out')
    destination.mkdir(parents=True,exist_ok=False)
    source=destination/'source/linux/drivers/gpu/drm/asahi'
    for name,text in files.items():
        path=source/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    shutil.copytree(source,destination/'build-owner')
    inputs=[pin(BASE/'stage-receipt.json'),pin(BASE/'module-build-closure.json'),
            pin(BASE/'qualification-v1/qualification.json'),pin(CLOCK),pin(__file__),
            pin(KIT/'wire_clock_v9.py'),pin(KIT/'g16_native_clock_v9.rs')]
    receipt={'schema':'m4rch.gravity-native-t6040-components.stage.v9',
             'inputs':inputs,'source_files':[pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
             'changed_files':changed,'normal_startup_enabled':False,'system_installed':False,
             'hardware_actions':[],'compiled':False,'power_complete':True,'bundle_complete':False,
             'clock_policy':'24MHz native ticks from absolute Linux physical architectural counter; Apple custom epoch offset unproven',
             'scope':'Clock-only intermediate stage; controller native render join remains separate'}
    (destination/'stage-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    qualification={'schema':'m4rch.gravity-native-t6040-components.qualification.v9',
                   'inputs':inputs+[pin(destination/'stage-receipt.json')],
                   'complete':True,'hardware_actions':[],'normal_startup_enabled':False,
                   'region_c_complete':False,'bundle_complete':False,'power_complete':True,
                   'preserved_v8_components':True,'changed_files':changed,
                   'clock_cases':336,'whole_writer_comparisons_repeated':False,
                   'module_compile_pending':True,'scope':receipt['scope']}
    q=destination/'qualification-v1'
    q.mkdir()
    (q/'qualification.json').write_text(json.dumps(qualification,indent=2)+'\n')
    print(json.dumps({'source_files':len(files),'changed_files':changed,'stage':str(destination)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    stage(parser.parse_args().destination)
