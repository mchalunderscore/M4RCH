#!/usr/bin/env python3
"""Prepare reproducible Gravity Apple9 shader candidates, without GPU submission."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('tool',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()
programs={'vertex':['vertex'],'vertex-small':['vertex-small'],'vertex-w':['vertex-w'],'fragment':['fragment'],'fragment-constant':['fragment-constant'],'fragment-alt':['fragment-alt'],'tile-store':['tile-store'],'compute-constant':['37'],'compute-gid':['gid'],'compute-mad':['mad','3','7'],'compute-dag':['dag']}
results={}
for name,args in programs.items():
 payload=None;logs=[];metadata=None
 for repeat in range(3):
  dest=a.output/(name+('.bin' if repeat==0 else '.repeat.bin'))
  run=subprocess.run([str(a.tool.resolve()),str(dest.resolve()),*args],text=True,capture_output=True,check=True)
  current=dest.read_bytes();assert current
  meta_path=Path(str(dest)+".json");current_meta=json.loads(meta_path.read_text())
  assert current_meta["binary_size"]==len(current)
  assert current_meta["apple9_preamble_offset"]+current_meta["apple9_preamble_size"]<=len(current)
  assert len(current_meta["resource_bindings"])==current_meta["apple9_resource_count"]
  assert len(current_meta["varying_mask"])==64 and len(current_meta["varying_group"])==64
  if payload is None:payload=current;metadata=current_meta
  else:
   assert current==payload and current_meta==metadata,'Non-deterministic shader '+name
   dest.unlink();meta_path.unlink()
  logs.append(run.stderr.strip())
 results[name]={'bytes':len(payload),'sha256':sha(payload),'repeats':3,'arguments':args,'compiler_output':logs[0],'metadata':metadata}
# Interior samples of the canonical vertex/fragment pair, away from raster edges.
# Screen coordinates here use y up; actual target orientation/tiling is unqualified.
verts=[(-.75,-.75),(.75,-.75),(0,.75)]
samples=[]
for x,y in [(0,0),(-.25,-.25),(.25,-.25),(0,.5)]:
 blue=(y+.75)/1.5;green=((x+.75)-.75*blue)/1.5;red=1-green-blue
 assert min(red,green,blue)>0
 samples.append({'ndc':[x,y],'barycentric':[red,green,blue],'float_rgba':[red*red,green+.125,blue*.5,1.0],'rgba8_nearest':[round(max(0,min(1,v))*255) for v in [red*red,green+.125,blue*.5,1.0]]})
report={'source_commit':commit,'tool_sha256':sha(a.tool.read_bytes()),'source_tool_sha256':sha((a.source/'src/asahi/compiler/test/apple9-tiny-tool.c').read_bytes()),'programs':results,'canonical_vertices':verts,'reference_samples':samples,'compute_expected_first_8':{'compute-constant':[37]*8,'compute-gid':list(range(8)),'compute-mad':[3*i+7 for i in range(8)],'compute-dag':[((3*i)^(i+7))+11 for i in range(8)]},'qualification':'Compiler-only candidates, three identical builds per program. No GPU execution or valid job proved. Graphics tool prints compute profile ABI0 because that profile is not populated for graphics; not a graphics ABI claim. Reference colors derive from source shader arithmetic; target orientation, raster rules, tiling, shader resource/state compatibility and quantization need hardware qualification. Keep binaries private in ignored out until source provenance reviewed.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Prepared {len(programs)} Apple9 shader candidates, {3*len(programs)} deterministic compiler runs; no GPU access')
