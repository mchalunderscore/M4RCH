#!/usr/bin/env python3
"""Build the pinned maintained Gravity kernel; does not install or change boot selection."""
from pathlib import Path
import argparse,subprocess,json,hashlib
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,default=Path('out/gravity-kernel-alignment'));p.add_argument('--package',action='store_true');p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
assert a.jobs>0
kit=Path(__file__).resolve().parent;profile=json.loads((kit/'profile.json').read_text());w=a.workspace.resolve();t=w/'linux';w.mkdir(parents=True,exist_ok=True)
if not t.exists():
 source=w/'upstream'
 assert not source.exists(),'Inspect existing upstream checkout before preparing'
 subprocess.run(['git','clone','--filter=blob:none','--no-checkout',profile['url'],str(source)],check=True)
 subprocess.run(['python3',str(kit/'prepare.py'),str(source),str(t)],check=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=t,text=True).strip()==profile['revision']
assert hashlib.sha256(subprocess.check_output(['git','diff','--binary'],cwd=t)).hexdigest()==profile['patch_sha256'],'Source patch differs from qualified profile'
args=['make','-C',str(t),'KERNELRELEASE='+profile['release'],'LOCALVERSION=']
subprocess.run(args+['olddefconfig'],check=True)
subprocess.run(args+['-j'+str(a.jobs),'Image','modules'],check=True)
if a.package:subprocess.run(['python3',str(kit/'package-trial.py'),str(w),'--maintained'],check=True)
