#!/usr/bin/env python3
"""Emulate two packed record patches in the matched native NOP path."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_kick_records import patch_add_kicks,patch_alternate_kick
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
slots=[]
for name,base in [('3D',0xfffffe0007eaa560),('CL',0xfffffe0007eabe88),('TA',0xfffffe0007eadc98)]:
 encoded=struct.unpack('<Q',read(base+16+0x188,8))[0]
 target=0xfffffe0007004000+(encoded&0xffffffff)
 slots.append(dict(channel=name,vtable=hex(base),slot='0x188',target=hex(target)))
 assert target==0xfffffe0008981048, 'Unexpected channel pointer writer'
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0x100000,4096);m.mem_map(0x200000,0x4000)
rng=random.Random(6040);ranges=[(0xfffffe000897f084,0xfffffe000897f0b0),(0xfffffe000897f05c,0xfffffe000897f078)]
for mode,(start,end) in enumerate(ranges):
 code=read(start,end-start);m.mem_write(0x100000,code);m.ctl_remove_cache(0x100000,0x101000)
 for i in range(256):
  original=rng.randbytes(64);queue=rng.getrandbits(32);scheduler_id=rng.getrandbits(32);pointer=rng.getrandbits(64);value=rng.getrandbits(32)
  m.mem_write(0x200000,original);m.mem_write(0x20101c,struct.pack('<I',scheduler_id));m.mem_write(0x202020,struct.pack('<II',value,queue))
  for reg,v in [(c.UC_ARM64_REG_X24,0x200000),(c.UC_ARM64_REG_X25,0x200000),(c.UC_ARM64_REG_X26,0x201000),(c.UC_ARM64_REG_X27,pointer),(c.UC_ARM64_REG_SP,0x202000)]:m.reg_write(reg,v)
  m.emu_start(0x100000,0x100000+len(code),count=100)
  assert m.reg_read(c.UC_ARM64_REG_PC)==0x100000+len(code)
  expected=patch_add_kicks(original,queue,scheduler_id,pointer,value) if mode==0 else patch_alternate_kick(original,queue,pointer)
  assert bytes(m.mem_read(0x200000,64))==expected
report=dict(binary_sha256=sha,cases_per_variant=256,channel_slots=slots,ranges=[[hex(x),hex(y)] for x,y in ranges],
 slices_sha256=[hashlib.sha256(read(x,y-x)).hexdigest() for x,y in ranges],
 add_kicks_prefix=dict(opcode=14,queue_offset=4,count_offset=6,count=1,scheduler_id_offset=8,timestamp_offset=9,value_offset=17,minimum_bytes=21),
 alternate_prefix=dict(opcode=16,queue_offset=4,timestamp_offset=6,constant_offset=14,constant=254,minimum_bytes=18),
 qualification='Call-free patches only, all unused bytes preserved. Mode choice depends on native accelerator flag +0xee5f bit0; allocation extents, pointer roles, earlier/later commands and full NOP lifecycle unresolved. No hardware execution.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('256 cases per packed variant matched; unknown tails preserved')
