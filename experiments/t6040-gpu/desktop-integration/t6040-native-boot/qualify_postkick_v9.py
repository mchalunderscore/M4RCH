#!/usr/bin/env python3
"""Compare typed opcode14 transport against both actual native store slices."""
import hashlib,json,random,struct,subprocess,tempfile
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
ROOT=Path(__file__).resolve().parents[4]
SRC=Path(__file__).with_name('g16_t6040_postkick_v9.rs')
BIN=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
raw=BIN.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
BASE=0xfffffe0000000000
def extract(start,end):
 for vm,_,off,length in segments:
  if vm<=start and end<=vm+length:return raw[off+start-vm:off+end-vm]
 raise ValueError('unbacked native slice')
code='#[path='+json.dumps(str(SRC))+'] mod kick;\nfn main(){assert_eq!(kick::BACKING_BYTES,24);assert_eq!(kick::WRITTEN_BYTES,21);\n'
rng=random.Random(60402414);pins=[];cases=0
for kind,lo,hi,offset,countoff in [('Tiling',0x8a1fe9c,0x8a1fecc,0xfb0,0xe38),('Fragment',0x895c2bc,0x895c2ec,0x450,0x2dc)]:
 start,end=BASE+lo,BASE+hi;native=extract(start,end)
 m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(start&~4095,4096);m.mem_write(start,native)
 m.mem_map(0x200000,0x10000);D,S,STACK,RECORD=0x200000,0x202000,0x204000,0x206000
 for i in range(128):
  q,count,mode=[rng.getrandbits(32) for _ in range(3)];timeline=rng.getrandbits(64);initial=rng.randbytes(32)
  m.mem_write(D+offset,struct.pack('<Q',RECORD));m.mem_write(D+countoff,struct.pack('<I',count));m.mem_write(S+0x1c,struct.pack('<I',mode))
  m.mem_write(STACK+0x5c,struct.pack('<I',q));m.mem_write(RECORD,initial)
  m.reg_write(c.UC_ARM64_REG_SP,STACK)
  for reg,val in [(c.UC_ARM64_REG_X20,D),(c.UC_ARM64_REG_X23,S),(c.UC_ARM64_REG_X22,timeline),(c.UC_ARM64_REG_X25,q)]:m.reg_write(reg,val)
  m.emu_start(start,end,count=64);assert m.reg_read(c.UC_ARM64_REG_PC)==end
  expected=bytes(m.mem_read(RECORD,32));assert expected[21:]==initial[21:]
  b='kick::Bindings{kind:kick::Kind::'+kind+',firmware_queue_id:'+str(q)+',descriptor_count:'+str(count)+',scheduler_mode:'+str(mode)+',submitted_timeline:'+str(timeline)+'}'
  code+='let b='+b+';let mut out='+repr(list(initial))+';kick::write(&mut out,&b).unwrap();assert_eq!(out,'+repr(list(expected))+');\n'
  code+='let mut short=[0xa5u8;23];assert!(kick::write(&mut short,&b).is_none());assert_eq!(short,[0xa5;23]);\n'
  cases+=1
 pins.append(dict(kind=kind,start=hex(start),end=hex(end),sha256=hashlib.sha256(native).hexdigest()))
code+='}\n'
with tempfile.TemporaryDirectory(prefix='native-postkick-') as td:
 p=Path(td);(p/'main.rs').write_text(code)
 subprocess.run(['rustc','--edition=2021','-Dwarnings',str(p/'main.rs'),'-o',str(p/'run')],check=True)
 subprocess.run([str(p/'run')],check=True)
def pin(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
report=dict(schema='m4rch.native-postkick-v9.v1',cases=cases,prewrite_refusals=cases,native_slices=pins,pins=[pin(SRC),pin(Path(__file__).resolve()),pin(BIN)],hardware_actions=[],runtime_enabled=False,scope='Actual TA and 3D opcode14 store slices versus compiled Rust, complete32byte backing including preserved tails. Inputs are supplied scheduler identities; no caller timestamp/count update, queue allocation, optional opcode12/16, ring publication or firmware acceptance proved.')
out=ROOT/'docs/evidence/2026-10-11-native-postkick-v9.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
