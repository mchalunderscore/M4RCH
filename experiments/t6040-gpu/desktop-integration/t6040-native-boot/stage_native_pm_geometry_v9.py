#!/usr/bin/env python3
"""Apply the complete native PM geometry wiring to a private Gravity stage."""
import argparse,hashlib,json,shutil
from pathlib import Path
from wire_pm_geometry_v9 import wiring
p=argparse.ArgumentParser(description=__doc__);p.add_argument('base',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
assert not a.output.exists();shutil.copytree(a.base,a.output)
r=a.output/'source/linux/drivers/gpu/drm/asahi'
names=['g16_runtime.rs','g16_t6040_pm_owned_v9.rs','g16_t6040_pm_v9.rs'];files={n:(r/n).read_text()for n in names};wiring(files)
for n in names:(r/n).write_text(files[n])
receipt={'schema':'m4rch.native-pm-geometry-stage.v9','base':str(a.base.resolve()),'output':str(a.output.resolve()),'hardware_actions':[],
 'native_geometry':{'scene_count':80,'state_count':36,'page_factor':4,'registration_stride':4,'scene_budget':[6144,8,8,16],'group_shift':0,'group_allowance':False,'extra_scene_stride':False},
 'linux_allocation_policy':{'initial_blocks':11,'maximum':'tvb_max_blocks','capacity':'maximum+1','support_extent':'actual mapped page-list allocation'},
 'unresolved':'PM1d4 explicit fresh Linux zero; DevicePMConfig is separate1d8 and not substituted.',
 'files':{n:hashlib.sha256((r/n).read_bytes()).hexdigest()for n in names}}
(a.output/'pm-geometry-stage.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
