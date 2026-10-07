#!/usr/bin/env python3
"""Prepare guarded GPU framework on the pinned maintained Gravity baseline."""
import argparse, hashlib, json, re, shutil, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path);p.add_argument('destination',type=Path)
a=p.parse_args();kit=Path(__file__).resolve().parent;repo=kit.parents[2]
subprocess.run(['python3',str(repo/'experiments/kernel-alignment/prepare.py'),str(a.source),str(a.destination)],check=True)
t=a.destination.resolve()
patch=repo/'experiments/kernel-alignment/gravity-t6040-maintained.patch'
files=re.findall(r'^diff --git a/(\S+) b/\S+',patch.read_text(),re.M)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
protected={f:sha(t/f) for f in files}
subprocess.run(['git','apply','--check',str(kit/'guarded-identification.patch')],cwd=t,check=True)
subprocess.run(['git','apply',str(kit/'guarded-identification.patch')],cwd=t,check=True)
shutil.copy2(kit.parent/'profile.rs',t/'drivers/gpu/drm/asahi/g16_profile.rs')
shutil.copy2(kit/'trial.config',t/'.config')
subprocess.run(['make','-C',str(t),'LLVM=1','KERNELRELEASE=7.1.13-m4rch-gpu-contract','LOCALVERSION=','olddefconfig'],check=True)
receipt={'release':'7.1.13-m4rch-gpu-contract','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=t,text=True).strip(),
         'maintained_patch_sha256':sha(patch),'guard_patch_sha256':sha(kit/'guarded-identification.patch'),
         'profile_sha256':sha(kit.parent/'profile.rs'),'config_sha256':sha(t/'.config'),
         'protected_maintained_files':protected,'normal_t6040_startup_allowed':False,
         'default_probe_only':True,'gpu_node_added':False,'compiled':False}
(t.parent/'source-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Prepared isolated trial; no installation, boot edit or GPU startup')
