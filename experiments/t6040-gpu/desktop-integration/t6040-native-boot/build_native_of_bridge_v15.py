#!/usr/bin/env python3
"""Build metadata bridge and current-ADT capture together, offline only."""
import argparse,json,shutil,subprocess
from pathlib import Path
from native_adt_bridge_v7 import pin
KIT=Path(__file__).resolve().parent
ROOT=KIT.parents[3]
def build(kernel,out):
 out=out.resolve();out.relative_to(ROOT/'out');out.mkdir(parents=True,exist_ok=False)
 for src in (KIT/'m4rch_native_of_bridge_v15.c',ROOT/'experiments/t6040-gpu/m4rch_gpu_adt.c'):
  shutil.copy2(src,out/src.name)
 (out/'Makefile').write_text('obj-m += m4rch_native_of_bridge_v15.o m4rch_gpu_adt.o\n')
 with (out/'build.log').open('w') as log:
  result=subprocess.run(['make','-C',str(kernel.resolve()),'LLVM=1','M='+str(out),'modules'],stdout=log,stderr=subprocess.STDOUT)
 receipt={'schema':'m4rch.current-loader-bridge-build.v15','returncode':result.returncode,'kernel_release':(kernel/'include/config/kernel.release').read_text().strip(),'modules':[pin(p) for p in out.glob('*.ko')],'hardware_actions':[],'loaded':False}
 (out/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 raise SystemExit(result.returncode)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.kernel,a.out)
