#!/usr/bin/env python3
"""Read-only fresh boot admission for the distinct automatic cold-render owner."""
import argparse,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from cold_render_contract import REFUSED_BOOTS,require,sha,validate_candidate,module_build_note,qualify_linux_dt
def early_boot():
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 require(bool(boot) and boot not in REFUSED_BOOTS,'Consumed boot refused before candidate or live reads')
 return boot
def fresh_modules(modules):
 for line in modules.splitlines():
  words=line.split();require(words,'Malformed module inventory');name=words[0]
  require(not(name.startswith('asc_') or name in ('asahi_m4','resource_overlay','gfx_power_test','gpu_data_sample','m4rch_gpu_adt')),'Conflicting module: '+name)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
 boot=early_boot();fresh_modules(Path('/proc/modules').read_text())
 candidate=args.candidate.resolve();receipt=validate_candidate(candidate)
 require(os.uname().release==receipt['kernel_release'] and sha(Path('/sys/kernel/notes').read_bytes())==receipt['kernel_notes_sha256'],'Kernel identity differs')
 require(not (candidate/'asc-graph-init'/('boot-'+boot)).exists(),'An existing session forbids another cold load')
 bindings=[]
 for name in ('0-0a','0-0c','2-0c'):
  driver=(Path('/sys/bus/spmi/devices')/name/'driver').resolve(strict=True)
  require(str(driver)=='/sys/bus/spmi/drivers/tps6598x-spmi','PD provider differs');bindings.append(dict(device=name,driver=str(driver)))
 roles=sorted(p.name for p in Path('/sys/class/usb_role').iterdir())
 require(roles==['382280000.usb-role-switch','38a280000.usb-role-switch','392280000.usb-role-switch'],'USB role providers differ')
 usb=Path('/usr/lib/modules')/receipt['kernel_release']/'kernel/drivers/usb/dwc3/dwc3-apple.ko';raw=usb.read_bytes()
 require(sha(raw)=='0c52d7c40156465674ba0fec752e6d137d4bf38354b415770cb62db3748a647e','USB driver differs')
 require(Path('/sys/module/dwc3_apple/notes/.note.gnu.build-id').read_bytes()==module_build_note(raw),'Loaded USB note differs')
 layout=qualify_linux_dt()
 result=dict(schema='m4rch.gfx-native-dispatch-contract-fresh-preflight.v1',boot_id=boot,candidate_receipt_sha256=sha((candidate/'asc-root-envelope/build-receipt.json').read_bytes()),owner_sha256=receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],kernel_release=receipt['kernel_release'],kernel_notes_sha256=receipt['kernel_notes_sha256'],artifact_pins_checked=len(receipt['artifact_sha256']),source_pins_checked=len(receipt['graph_source_sha256']),pd_bindings=bindings,usb_role_providers=roles,linux_dt_resource_layout=layout,gpu_operation_performed=False)
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
