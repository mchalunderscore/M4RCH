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
 p.add_argument('workspace',type=Path);p.add_argument('helper',choices=['resource-overlay','gfx-power-test'])
 a=p.parse_args();work=a.workspace.resolve();tree=work/'linux-build';target=work/a.helper
 receipt=json.loads((work/'identify-build-inputs-final.json').read_text())
 if not receipt.get('build_succeeded') or sha(tree/'.config')!=receipt['config_sha256']:
  raise ValueError('Successful matching isolated build receipt required')
 if (tree/'include/config/kernel.release').read_text().strip()!='7.1.3-m4rch-gpu-id':
  raise ValueError('Wrong kernel release')
 target.mkdir(exist_ok=True)
 for source in (REPO/'experiments/t6040-gpu'/a.helper).iterdir():
  if source.name=='Makefile' or source.suffix in ['.c','.dts']:shutil.copy2(source,target/source.name)
 if a.helper=='resource-overlay':
  subprocess.run([str(tree/'scripts/dtc/dtc'),'-@','-I','dts','-O','dtb','-o',str(target/'resource.dtb'),str(target/'resource.dts')],check=True)
  data=(target/'resource.dtb').read_bytes()
  (target/'resource-blob.h').write_text('static const unsigned char resource_dtb[] __aligned(8) = {'+','.join(hex(x) for x in data)+'};\nstatic const unsigned int resource_dtb_len = sizeof(resource_dtb);\n')
 subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE=7.1.3-m4rch-gpu-id','LOCALVERSION=','M='+str(target),'W=1','modules'],check=True)
 (target/'build-receipt.json').write_text(json.dumps({'kernel_config_sha256':sha(tree/'.config'),'module_sha256':sha(target/(a.helper+'.ko')),'loading_performed':False},indent=2)+'\n')
if __name__=='__main__':main()
