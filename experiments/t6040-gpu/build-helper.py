#!/usr/bin/env python3
"""Build metadata/power-test helpers against the isolated maintained trial tree.
No loading or hardware access. Generated artifacts remain in the supplied workspace.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
REPO=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('workspace',type=Path);p.add_argument('helper',choices=['resource-overlay','gfx-power-test','id-overlay','guard-overlay'])
 p.add_argument('--reviewed-id-reads',action='store_true',help='Acknowledge the documented bounded native ID review')
 a=p.parse_args()
 if a.helper=='id-overlay' and not a.reviewed_id_reads:p.error('id-overlay requires --reviewed-id-reads')
 work=a.workspace.resolve();tree=work/'linux-build';target=work/a.helper
 is_port=a.helper=='guard-overlay' or (a.helper=='gfx-power-test' and (work/'port-source.json').exists())
 receipt=json.loads((work/('port-source.json' if is_port else 'identify-build-inputs-final.json')).read_text())
 release='7.1.3-m4rch-gpu-port' if is_port else '7.1.3-m4rch-gpu-id'
 if not receipt.get('compiled' if is_port else 'build_succeeded') or sha(tree/'.config')!=receipt['config_sha256']:
  raise ValueError('Successful matching isolated build receipt required')
 if (tree/'include/config/kernel.release').read_text().strip()!=release:
  raise ValueError('Wrong kernel release')
 target.mkdir(exist_ok=True)
 source_name='resource-overlay' if a.helper in ['id-overlay','guard-overlay'] else a.helper
 for source in (REPO/'experiments/t6040-gpu'/source_name).iterdir():
  if source.name=='Makefile' or source.suffix in ['.c','.dts']:shutil.copy2(source,target/source.name)
 if a.helper in ['resource-overlay','id-overlay','guard-overlay']:
  if a.helper=='guard-overlay':
   if receipt.get('t6040_firmware_startup_allowed') is not False:raise ValueError('T6040 startup guard required')
   for name in ['drivers/gpu/drm/asahi/asahi_m4.rs','drivers/gpu/drm/asahi/g16_profile.rs']:
    if sha(tree/name)!=receipt['files'][name]['after']:raise ValueError('Guard source mismatch')
   f=target/'resource.dts';f.write_text(f.read_text().replace('m4rch,t6040-gpu-identify','apple,agx-t6040'))
  if a.helper=='id-overlay':
   f=target/'resource.dts';f.write_text(f.read_text().replace('status = "okay";','status = "okay";\n                    m4rch,id-access-reviewed = <1>;'))
   f=target/'resource-overlay.c';f.write_text(f.read_text().replace('no power/reset/clock or ID-access properties','no power/reset/clock bindings; opt-in ID review flag present'))
  subprocess.run([str(tree/'scripts/dtc/dtc'),'-@','-I','dts','-O','dtb','-o',str(target/'resource.dtb'),str(target/'resource.dts')],check=True)
  data=(target/'resource.dtb').read_bytes()
  (target/'resource-blob.h').write_text('static const unsigned char resource_dtb[] __aligned(8) = {'+','.join(hex(x) for x in data)+'};\nstatic const unsigned int resource_dtb_len = sizeof(resource_dtb);\n')
 subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE='+release,'LOCALVERSION=','M='+str(target),'W=1','modules'],check=True)
 (target/'build-receipt.json').write_text(json.dumps({'kernel_config_sha256':sha(tree/'.config'),'module_sha256':sha(target/(source_name+'.ko')),'loading_performed':False,'kernel_release':release,'expected_probe_only':0 if a.helper=='guard-overlay' else None},indent=2)+'\n')
if __name__=='__main__':main()
