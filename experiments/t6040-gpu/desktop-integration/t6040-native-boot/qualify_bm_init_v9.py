#!/usr/bin/env python3
"""Compare compiled BM18 writer with actual native two-slice producer."""
from pathlib import Path
import random,struct,hashlib,json,sys,subprocess,importlib.util
R=Path(__file__).resolve().parents[4];K=Path(__file__).parent;sys.path.insert(0,str(R/'experiments/t6040-gpu'))
spec=importlib.util.spec_from_file_location('p',R/'experiments/t6040-gpu/prepare-native-sksm-registers.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
O=R/'out/gpu-gravity-native-bm-init-v9-qualification';O.mkdir(exist_ok=True)
ns=p.harness(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'),O/'setup.json','3d');m,c=ns['m'],ns['c'];BASE=0xfffffe0000000000;m.mem_map(BASE+0x8a1f000,4096);m.mem_write(BASE+0x8a1f294,ns['read'](BASE+0x8a1f294,0x8a1f2fc-0x8a1f294));D,OUT=ns['D'],0x238000
rs='''#[path="COMPONENT"]mod bm;use std::{env,fs};fn main(){let a:Vec<String>=env::args().collect();let d=fs::read(&a[1]).unwrap();let mut o=[0xa5;0x18];let b=bm::Bindings{descriptor_1274:u32::from_le_bytes(d[..4].try_into().unwrap()),descriptor_1218:u32::from_le_bytes(d[4..8].try_into().unwrap()),manager_fw:u64::from_le_bytes(d[8..16].try_into().unwrap()),caller_word_21:u32::from_le_bytes(d[16..20].try_into().unwrap())};bm::write(&mut o,b).unwrap();let before=o;let invalid=bm::Bindings{manager_fw:0,..b};assert_eq!(bm::write(&mut o,invalid),None);assert_eq!(o,before);fs::write(&a[2],o).unwrap();}
'''.replace('COMPONENT',str(K/'g16_t6040_bm_init_v9.rs'))
(O/'host.rs').write_text(rs);subprocess.run(['rustc','--edition=2021','-Dwarnings',str(O/'host.rs'),'-o',str(O/'host')],check=True)
rng=random.Random(604123);cases=[]
for i in range(96):
 a,b,fw,word=rng.getrandbits(32),rng.getrandbits(32),0xfffffc2001000000+i*0x1000,rng.getrandbits(32)
 m.mem_write(D+0x1274,struct.pack('<I',a));m.mem_write(D+0x1218,struct.pack('<I',b));m.mem_write(OUT,rng.randbytes(0x18));m.reg_write(c.UC_ARM64_REG_X20,D);m.reg_write(c.UC_ARM64_REG_X27,OUT)
 m.emu_start(BASE+0x8a1f294,BASE+0x8a1f2a8,count=8);assert m.reg_read(c.UC_ARM64_REG_PC)==BASE+0x8a1f2a8
 # Explicit owned converter result at the source-native service boundary.
 m.reg_write(c.UC_ARM64_REG_X0,fw);m.reg_write(c.UC_ARM64_REG_W21,word);m.emu_start(BASE+0x8a1f2f4,BASE+0x8a1f2fc,count=2)
 expected=bytes(m.mem_read(OUT,0x18));(O/'input.bin').write_bytes(struct.pack('<IIQI',a,b,fw,word));subprocess.run([str(O/'host'),str(O/'input.bin'),str(O/'actual.bin')],check=True);assert (O/'actual.bin').read_bytes()==expected
 cases.append(dict(case=i,sha256=hashlib.sha256(expected).hexdigest()))
files=[K/'g16_t6040_bm_init_v9.rs',Path(__file__)]
report=dict(cases=cases,count=len(cases),prewrite_refusals=len(cases),binary_sha256=ns['sha'],slices=[dict(start=hex(s),end=hex(e),sha256=hashlib.sha256(ns['read'](s,e-s)).hexdigest())for s,e in [(BASE+0x8a1f294,BASE+0x8a1f2a8),(BASE+0x8a1f2f4,BASE+0x8a1f2fc)]],inputs=[dict(path=str(f.relative_to(R)),sha256=hashlib.sha256(f.read_bytes()).hexdigest())for f in files],qualification='Actual native record stores across explicit converter boundary vs compiled Rust whole24 bytes. Context/slot are descriptor1274/1218; field14 is raw callerW21. Converter, publication and manager allocation are separate; no block-count inline, firmware acceptance or GPU proof.')
(O/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print('96 BM18 native/compiled outputs and nonzero-owner refusals matched')
