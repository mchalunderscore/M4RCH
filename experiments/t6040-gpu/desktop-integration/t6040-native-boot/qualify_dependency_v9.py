#!/usr/bin/env python3
"""Execute the actual native dependency store slice against typed Rust."""
import hashlib,json,random,struct,subprocess,tempfile
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
ROOT=Path(__file__).resolve().parents[4]
SOURCE=Path(__file__).with_name('g16_t6040_dependency_v9.rs')
APPLE=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X');raw=APPLE.read_bytes();segs=[];o=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,o)
 if cmd==0x19:segs.append(struct.unpack_from('<QQQQ',raw,o+24))
 o+=size
start,end=0x897f628,0x897f6c0
for vm,extent,offset,length in segs:
 if vm<=0xfffffe0000000000+start and 0xfffffe0000000000+end<=vm+length:
  code=raw[offset+0xfffffe0000000000+start-vm:offset+0xfffffe0000000000+end-vm];break
else:raise ValueError('missing native store range')
rng=random.Random(0x604048);cases=[]
for i in range(96):
 c=dict(stamp_base=rng.getrandbits(64),stamp_offset=rng.getrandbits(32),hardware_timestamp=rng.getrandbits(40),hardware_queue=rng.randrange(128),wait_value=rng.getrandbits(32),producer_event=i%24,consumer_stamp=rng.getrandbits(32),uuid=rng.getrandbits(64),selected_event=[-1,i%24,(i+1)%24][i%3])
 before=bytes(72) if i%2==0 else rng.randbytes(72)
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for addr,size in [(start&~0xfff,0x1000),(0x200000,0x1000),(0x300000,0x1000),(0x400000,0x11000),(0x500000,0x1000),(0x600000,0x1000),(0x700000,0x1000)]:u.mem_map(addr,size)
 u.mem_write(start,code);u.mem_write(0x200010,struct.pack('<Q',0x400000));u.mem_write(0x400000+0xf938+8*c['producer_event'],struct.pack('<Q',0x500000));u.mem_write(0x50000c,struct.pack('<I',c['hardware_queue']));u.mem_write(0x600000,before);u.mem_write(0x700000,struct.pack('<I',c['wait_value']))
 stack=bytearray(0x30);struct.pack_into('<Q',stack,8,c['stamp_base']);struct.pack_into('<Q',stack,0x10,c['uuid']);struct.pack_into('<I',stack,0x18,c['consumer_stamp']);struct.pack_into('<i',stack,0x1c,c['selected_event']);u.mem_write(0x300000,bytes(stack))
 for reg,value in [(UC_ARM64_REG_SP,0x300000),(UC_ARM64_REG_X0,c['stamp_offset']),(UC_ARM64_REG_X20,0x200000),(UC_ARM64_REG_X21,0x700004),(UC_ARM64_REG_X26,0x600000),(UC_ARM64_REG_X27,c['producer_event'])]:u.reg_write(reg,value)
 converted=[]
 def hook(uc,pc,size,data):
  if pc==0x897f694:
   assert uc.reg_read(UC_ARM64_REG_X0)==0x500000 and uc.reg_read(UC_ARM64_REG_X1)==c['producer_event']
   converted.append(True);uc.reg_write(UC_ARM64_REG_X0,c['hardware_timestamp']);uc.reg_write(UC_ARM64_REG_PC,pc+4)
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(start,end,count=100);assert converted==[True]
 c['before']=before.hex();c['after']=bytes(u.mem_read(0x600000,72)).hex();cases.append(c)
with tempfile.TemporaryDirectory(prefix='native-dependency-') as td:
 t=Path(td);rust='#[path='+json.dumps(str(SOURCE))+'] mod dep;\nfn main(){\n'
 for c in cases:
  fields=','.join(k+':'+str(v) for k,v in c.items() if k not in ['before','after'])
  rust+='let mut out=['+','.join(str(v) for v in bytes.fromhex(c['before']))+'];dep::write(&mut out,dep::Bindings{'+fields+'});assert_eq!(out,['+','.join(str(v) for v in bytes.fromhex(c['after']))+']);\n'
 rust+='}\n';(t/'main.rs').write_text(rust);subprocess.run(['rustc','--edition=2021','-Dwarnings',str(t/'main.rs'),'-o',str(t/'run')],check=True);subprocess.run([str(t/'run')],check=True)
out=ROOT/'out/gpu-gravity-native-dependency-v9';out.mkdir(parents=True,exist_ok=True)
def pin(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
j=dict(schema='m4rch.native-dependency-v9.v1',cases=96,native_store_range=['0x897f628','0x897f6c0'],pins=[pin(SOURCE),pin(Path(__file__).resolve()),pin(APPLE)],hardware_actions=[],runtime_enabled=False,scope='Whole72-byte actual native store-slice versus compiled Rust. Source-converted timeline is a typed provider input; conversion routine and full caller traversal are not executed. Half fresh zeroed and half poisoned records verify untouched fields. Selected-event branches and wrapping address arithmetic exercised.',untouched_offsets=['0x1c..0x24','0x38..0x3c','0x44..0x48'])
(out/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
