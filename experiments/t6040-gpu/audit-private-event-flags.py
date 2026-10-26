#!/usr/bin/env python3
"""Offline type-1 event bit enumeration; external callback replaced by recorder."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
s=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:s.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(address,size):
 for vm,_,off,length in s:
  if vm<=address and address+size<=vm+length:return raw[off+address-vm:off+address-vm+size]
 raise ValueError('Not file backed')
start,end=0xfffffe00089a2e8c,0xfffffe00089a2f3c
calls=[0xfffffe00089a2ea8,0xfffffe00089a2ed4,0xfffffe00089a2f00,0xfffffe00089a2f2c]
for address in calls:
 word=struct.unpack('<I',read(address,4))[0];offset=word&0x3ffffff
 if offset&(1<<25):offset-=1<<26
 assert word>>26==0x25 and address+offset*4==0xfffffe000a7cf84c
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(start&~4095,4096)
m.mem_write(start,read(start,end-start));m.mem_map(0x200000,4096)
m.mem_write(0x200140,struct.pack('<Q',0x12345678));observed=[]
def hook(mu,address,size,unused):
 if address in calls:
  assert mu.reg_read(c.UC_ARM64_REG_X0)==0x12345678
  assert mu.reg_read(c.UC_ARM64_REG_X2)==0
  observed.append(mu.reg_read(c.UC_ARM64_REG_X1))
  mu.reg_write(c.UC_ARM64_REG_PC,address+4)
 elif not start<=address<end:raise ValueError('Unreviewed target')
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(6040);cases=[0]+[1<<i for i in range(128)]+[(1<<128)-1]+[rng.getrandbits(128) for _ in range(64)]
for bits in cases:
 observed.clear()
 for reg,value in [(c.UC_ARM64_REG_X23,bits&((1<<64)-1)),(c.UC_ARM64_REG_X25,bits>>64),(c.UC_ARM64_REG_X21,1),(c.UC_ARM64_REG_X24,0x200000)]:m.reg_write(reg,value)
 m.emu_start(start,end,count=3000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==end
 assert observed==[i for i in range(128) if bits&(1<<i)]
report=dict(binary_sha256=sha,slice_range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),cases=len(cases),
 event_type=1,mask_words=[dict(offset=4,bytes=8),dict(offset=12,bytes=8)],selector_offset=20,selector_width=2,selector_native_upper_bound=24,
 callback_target='0xfffffe000a7cf84c',callback_indices='Ascending set-bit indices 0..127, third argument zero',
 qualification='Native loop emulated, all 128 single-bit positions plus empty/full/random masks. Four external calls replaced by recorder, no service code executed. Callback effect and complete fence/job retirement not proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(len(cases),'type-1 bitmask cases matched native callback enumeration')
