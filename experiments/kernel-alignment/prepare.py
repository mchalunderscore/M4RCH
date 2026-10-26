#!/usr/bin/env python3
"""Prepare an isolated pinned Gravity kernel tree; does not build/install/select it."""
from pathlib import Path
import argparse,subprocess,json,hashlib,shutil,re
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('destination',type=Path);a=p.parse_args()
kit=Path(__file__).resolve().parent;profile=json.loads((kit/'profile.json').read_text());dst=a.destination.resolve()
assert not dst.exists(),'Destination exists; preserve current work'
assert hashlib.sha256((kit/'gravity-t6040-maintained.patch').read_bytes()).hexdigest()==profile['patch_sha256']
assert hashlib.sha256((kit/'trial.config').read_bytes()).hexdigest()==profile['config_sha256']
subprocess.run(['git','clone','--shared','--no-hardlinks',str(a.source.resolve()),str(dst)],check=True)
subprocess.run(['git','checkout','--detach',profile['revision']],cwd=dst,check=True)
subprocess.run(['git','apply','--check',str(kit/'gravity-t6040-maintained.patch')],cwd=dst,check=True)
subprocess.run(['git','apply',str(kit/'gravity-t6040-maintained.patch')],cwd=dst,check=True)
new_files=[a for a,b in re.findall(r'^diff --git a/(\S+) b/(\S+)\nnew file mode', (kit/'gravity-t6040-maintained.patch').read_text(),re.M) if a==b]
if new_files:subprocess.run(['git','add','--intent-to-add','--',*new_files],cwd=dst,check=True)
shutil.copy2(kit/'trial.config',dst/'.config')
print('Prepared',profile['release'],'from pinned Gravity source; no installation')
