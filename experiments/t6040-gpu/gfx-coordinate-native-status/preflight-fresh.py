#!/usr/bin/env python3
"""Read-only fresh-boot kernel/USB/resource/candidate preflight, no GPU operation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from gfx_native_status_contract import validate_receipt,qualify_linux_dt


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();candidate=a.candidate.resolve();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert boot!='493814fd-b859-42b5-b257-c0ac4960e8a1','Current owner retained: normal fresh boot required'
 rpath=candidate/'asc-root-envelope/build-receipt.json';r=json.loads(rpath.read_text());assert validate_receipt(r)
 ppath=candidate/'native-status-preparation.json';prep=json.loads(ppath.read_text())
 assert sha(rpath)==prep['candidate_receipt_sha256'] and prep['selected_next_hardware_candidate'] is True
 assert os.uname().release==r['kernel_release'] and sha(Path('/sys/kernel/notes'))==r['kernel_notes_sha256']
 for n,s in r['artifact_sha256'].items():assert sha(candidate/n)==s,n
 for n,s in r['graph_source_sha256'].items():assert sha(candidate/'asc-graph-init'/n)==s,n
 for pin in prep['inputs']:assert sha(Path(pin['path']))==pin['sha256'],pin['path']
 for pin in prep['analysis_tool_pins']:assert sha(Path(pin['path']))==pin['sha256'],pin['path']
 for pin in prep['analysis_input_pins']:assert sha(candidate/pin['relative'])==pin['sha256'],pin['relative']
 assert not (candidate/'asc-graph-init'/('boot-'+boot)/'attempt.json').exists()
 conflicts=[]
 for line in Path('/proc/modules').read_text().splitlines():
  name=line.split()[0]
  if name.startswith('asc_') or name in ['asahi_m4','resource_overlay','gfx_power_test','gpu_data_sample','m4rch_gpu_adt']:conflicts.append(name)
 assert not conflicts,conflicts
 bindings=[]
 for dev in ['0-0a','0-0c','2-0c']:
  driver=(Path('/sys/bus/spmi/devices')/dev/'driver').resolve(strict=True)
  assert str(driver)=='/sys/bus/spmi/drivers/tps6598x-spmi';bindings.append({'device':dev,'driver':str(driver)})
 roles=sorted(p.name for p in Path('/sys/class/usb_role').iterdir())
 assert roles==['382280000.usb-role-switch','38a280000.usb-role-switch','392280000.usb-role-switch'],roles
 usb=Path('/usr/lib/modules')/r['kernel_release']/'kernel/drivers/usb/dwc3/dwc3-apple.ko'
 assert sha(usb)=='0c52d7c40156465674ba0fec752e6d137d4bf38354b415770cb62db3748a647e'
 reader=runpy.run_path(str(HERE/'run-native-status.py'))['module_build_note']
 assert Path('/sys/module/dwc3_apple/notes/.note.gnu.build-id').read_bytes()==reader(usb.read_bytes())
 layout=qualify_linux_dt()
 result={'schema':'m4rch.gfx-native-status-fresh-preflight.v1','boot_id':boot,
  'kernel_release':os.uname().release,'kernel_notes_sha256':r['kernel_notes_sha256'],
  'candidate_receipt_sha256':sha(rpath),'owner_sha256':prep['owner_sha256'],
  'artifact_pins_checked':len(r['artifact_sha256']),'source_pins_checked':len(r['graph_source_sha256']),
  'preparation_input_pins_checked':len(prep['inputs']),'conflicting_modules':conflicts,
  'pd_bindings':bindings,'usb_role_providers':roles,'dwc3_file_sha256':sha(usb),
  'loaded_dwc3_note_matches_file':True,'linux_dt_resource_layout':layout,
  'cmdline':Path('/proc/cmdline').read_text().strip(),'uptime':Path('/proc/uptime').read_text().strip(),
  'helper_sha256':sha(Path(__file__)),'gpu_operation_performed':False}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result))


if __name__=='__main__':main()
