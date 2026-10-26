#!/usr/bin/env python3
"""Eager-load packaged Mesa against the real target's dependency libraries."""
from pathlib import Path
import json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/packages';TARGET=Path('/Volumes/ARCHROOT');VM='m4rch-arch-packages'
def guest(code):return subprocess.check_output(['container','exec',VM,'python3','-c',code],text=True)
def source(name):
 p=TARGET/'usr/lib'/name
 for _ in range(12):
  if not p.is_symlink():return p
  q=Path(os.readlink(p));p=TARGET/str(q).lstrip('/') if q.is_absolute() else p.parent/q
 raise RuntimeError(name)
def main():
 dest=OUT/'target-abi-libs';dest.mkdir(exist_ok=True)
 owned=set(guest("import subprocess;print('\\n'.join(subprocess.check_output(['pacman','-Qlq','mesa-m4rch'],text=True).splitlines()))").splitlines())
 new={Path(n).name for n in owned if '.so' in n}
 needed=set(guest("import subprocess,re;print('\\n'.join(re.findall(r'=> /usr/lib/([^ ]+)',subprocess.check_output(['ldd','/usr/lib/libvulkan_asahi.so','/usr/lib/libEGL_mesa.so.0','/usr/lib/libGLX_mesa.so.0','/usr/lib/libgbm.so.1'],text=True))))").splitlines())
 copied=set()
 for _ in range(8):
  for name in needed-copied-new:
   p=source(name);assert p.is_file(),name;shutil.copyfile(p,dest/name);copied.add(name)
  raw=guest("from pathlib import Path;import subprocess,re,json;names=set();\nfor p in Path('/project/out/packages/target-abi-libs').iterdir():\n names.update(re.findall(r'\\(NEEDED\\).*\\[([^]]+)\\]',subprocess.check_output(['readelf','-d',str(p)],text=True)))\nprint(json.dumps(sorted(names)))")
  more=set(json.loads(raw))-copied-new
  if not more:break
  needed=more
 else:raise RuntimeError('Unbounded dependency closure')
 code="import ctypes,os;\nfor name in ['libvulkan_asahi.so','libEGL_mesa.so.0','libGLX_mesa.so.0','libgbm.so.1']:\n ctypes.CDLL('/usr/lib/'+name,mode=os.RTLD_NOW);print('PASS target libraries:',name)"
 result=subprocess.check_output(['container','exec',VM,'env','LD_LIBRARY_PATH=/project/out/packages/target-abi-libs','python3','-c',code],text=True)
 (OUT/'target-abi-validation.log').write_text(result+'Native dependency libraries checked: '+str(len(copied))+'\n');print(result,end='')
if __name__=='__main__':main()
