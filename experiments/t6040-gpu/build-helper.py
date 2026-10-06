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
 p.add_argument('workspace',type=Path);p.add_argument('helper',choices=['resource-overlay','gfx-power-test','id-overlay'])
 p.add_argument('--reviewed-id-reads',action='store_true',help='Acknowledge the documented bounded native ID review')
 a=p.parse_args()
 if a.helper=='id-overlay' and not a.reviewed_id_reads:p.error('id-overlay requires --reviewed-id-reads')
 work=a.workspace.resolve();tree=work/'linux-build';target=work/a.helper
 receipt=json.loads((work/'identify-build-inputs-final.json').read_text())
 if not receipt.get('build_succeeded') or sha(tree/'.config')!=receipt['config_sha256']:
  raise ValueError('Successful matching isolated build receipt required')
 if (tree/'include/config/kernel.release').read_text().strip()!='7.1.3-m4rch-gpu-id':
  raise ValueError('Wrong kernel release')
 target.mkdir(exist_ok=True)
 source_name='resource-overlay' if a.helper=='id-overlay' else a.helper
 for source in (REPO/'experiments/t6040-gpu'/source_name).iterdir():
  if source.name=='Makefile' or source.suffix in ['.c','.dts']:shutil.copy2(source,target/source.name)
 if a.helper in ['resource-overlay','id-overlay']:
  if a.helper=='id-overlay':
   f=target/'resource.dts';f.write_text(f.read_text().replace('status = "okay";','status = "okay";\n                    m4rch,id-access-reviewed = <1>;'))
   f=target/'resource-overlay.c';f.write_text(f.read_text().replace('no power/reset/clock or ID-access properties','no power/reset/clock bindings; opt-in ID review flag present'))
  subprocess.run([str(tree/'scripts/dtc/dtc'),'-@','-I','dts','-O','dtb','-o',str(target/'resource.dtb'),str(target/'resource.dts')],check=True)
  data=(target/'resource.dtb').read_bytes()
  (target/'resource-blob.h').write_text('static const unsigned char resource_dtb[] __aligned(8) = {'+','.join(hex(x) for x in data)+'};\nstatic const unsigned int resource_dtb_len = sizeof(resource_dtb);\n')
 subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE=7.1.3-m4rch-gpu-id','LOCALVERSION=','M='+str(target),'W=1','modules'],check=True)
 (target/'build-receipt.json').write_text(json.dumps({'kernel_config_sha256':sha(tree/'.config'),'module_sha256':sha(target/(source_name+'.ko')),'loading_performed':False},indent=2)+'\n')
if __name__=='__main__':main()
