#!/usr/bin/env python3
"""Check retained native layouts against actual Gravity allocation geometry."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
SRC=Path(__file__).with_name('g16_t6040_work_layout_v9.rs')
RUNTIME=ROOT/'out/gpu-gravity-normal-boot-v9-clock/source/linux/drivers/gpu/drm/asahi/g16_runtime.rs'
txt=RUNTIME.read_text()
for required in ['if render { 0x1c000 }','if render { 0x10000 }','va + 0x10000, 0xc000','work_page = va + stage * 0x8000','register_page = alias + stage * 0x4000']:
 assert required in txt,required
code='#[path='+json.dumps(str(SRC))+'] mod layout;\nfn main(){\n'
code+='assert_eq!(layout::STRIDE,0x1c000);assert_eq!(layout::PAGE_BYTES,0x4000);assert_eq!(layout::RCE_BYTES,0x3000);assert_eq!(layout::SKU_CAPACITY,0x2000);\n'
intervals=[]
for i in range(256):
 base=0xfffffc2201000000+i*0x1c000;device=0x7201000000+i*0x1c000
 code+='let l=layout::Layout::new('+str(base)+').unwrap();assert_eq!(l.base,'+str(base)+');assert_eq!(l.bm_fw,'+str(base+0x3200)+');\n'
 extents=[(base+0x3200,0x18,'bm')]
 for stage in range(2):
  fw=base+stage*0x8000;dv=device+stage*0x4000
  fields=dict(dependency_fw=fw+0x3240,sku_fw=fw+0x4000,shared_state_fw=base+0x10000+stage*0x4000,driver_stamp_fw=base+0x18000+stage*0x40)
  code+='assert_eq!(l.pages['+str(stage)+'],layout::Page{firmware:'+str(fw)+',device:'+str(dv)+'});\n'
  code+='assert_eq!(l.stages['+str(stage)+'].command,l.pages['+str(stage)+']);assert_eq!(l.stages['+str(stage)+'].ksm,layout::Page{firmware:'+str(fw+0x3000)+',device:'+str(dv+0x3000)+'});\n'
  for k,v in fields.items():code+='assert_eq!(l.stages['+str(stage)+'].'+k+','+str(v)+');\n'
  extents += [(fw,0x3000,'rce'),(fw+0x3000,0x200,'ksm'),(fw+0x3240,0x48,'dependency'),(fw+0x4000,0x2000,'sku'),(base+0x10000+stage*0x4000,0x4000,'state'),(base+0x18000+stage*0x40,0x40,'stamp')]
 extents.sort()
 for a,n,name in extents:assert base<=a<a+n<=base+0x1c000
 for (a,n,_),(b,_,_) in zip(extents,extents[1:]):assert a+n<=b
 intervals.extend(extents)
for base in [0,0xfffffc21ffffc000,0xfffffc2200000001,0xfffffc22ffffc000,0xfffffffffffffffc]:code+='assert!(layout::Layout::new('+str(base)+').is_none());\n'
# Exact last two-page alias extent is admitted; the following page is refused.
code+='assert!(layout::Layout::new(0xfffffc22ffff8000).is_some());\n}\n'
with tempfile.TemporaryDirectory(prefix='native-layout-') as td:
 t=Path(td);(t/'main.rs').write_text(code);subprocess.run(['rustc','--edition=2021','-Dwarnings',str(t/'main.rs'),'-o',str(t/'run')],check=True);subprocess.run([str(t/'run')],check=True)
for (a,n,_),(b,_,_) in zip(sorted(intervals),sorted(intervals)[1:]):assert a+n<=b
out=ROOT/'out/gpu-gravity-native-work-layout-v9';out.mkdir(parents=True,exist_ok=True)
def pin(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
j=dict(schema='m4rch.native-work-layout-v9.v1',leases=256,stages=512,disjoint_extents=len(intervals),boundary_refusals=5,pins=[pin(SRC),pin(Path(__file__).resolve()),pin(RUNTIME)],hardware_actions=[],runtime_enabled=False,scope='Compiled typed addresses and nonoverlap across256retained leases, matching actual Gravity16KiBpage/1c000lease geometry. Requires caller to map both address views to same physical backing and keep leases until retirement; no page or lifetime proof from this address plan.')
(out/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
