#!/usr/bin/env python3
"""Build the isolated prepared GPU trial and record completed artifact hashes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);p.add_argument('--jobs',type=int,default=8)
a=p.parse_args();assert a.jobs>0;w=a.workspace.resolve();t=w/'linux';file=w/'source-receipt.json';r=json.loads(file.read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=t,text=True).strip()==r['source_revision']
assert sha(t/'.config')==r['config_sha256']
for f,h in r['protected_maintained_files'].items():assert sha(t/f)==h,f
kit=Path(__file__).resolve().parent
assert sha(t/'drivers/gpu/drm/asahi/g16_profile.rs')==r['profile_sha256']
assert sha(kit/'guarded-identification.patch')==r['guard_patch_sha256']
subprocess.run(['git','apply','--reverse','--check',str(kit/'guarded-identification.patch')],cwd=t,check=True)
subprocess.run(['make','-C',str(t),'LLVM=1','KERNELRELEASE='+r['release'],'LOCALVERSION=','-j'+str(a.jobs),'Image','modules'],check=True)
r['compiled']=True;r['artifacts']={f:sha(t/f) for f in ['arch/arm64/boot/Image','drivers/gpu/drm/asahi/asahi_m4.ko','Module.symvers']}
file.write_text(json.dumps(r,indent=2)+'\n')
