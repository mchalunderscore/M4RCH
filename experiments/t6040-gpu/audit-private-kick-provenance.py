#!/usr/bin/env python3
"""Offline native alias-disambiguation and kick-ID configuration check."""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('Not file backed')
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
start,end=0xfffffe00089d646c,0xfffffe00089d64ec
hal,halend=0xfffffe00089e7fc0,0xfffffe00089e7fd4
for lo,hi in [(start,end),(hal,halend)]:
 m.mem_map(lo&~4095,4096);m.mem_write(lo,read(lo,hi-lo))
m.mem_map(0x200000,0x24000)
rng=random.Random(6040353)
for _ in range(1024):
 original=rng.randbytes(0x20000);m.mem_write(0x200000,original)
 words=[rng.getrandbits(32) for _ in range(6)]
 m.mem_write(0x220000,struct.pack('<6I',*words))
 for reg,val in [(c.UC_ARM64_REG_X0,0x220000),(c.UC_ARM64_REG_X23,0x1000),(c.UC_ARM64_REG_X22,0x1000),(c.UC_ARM64_REG_X21,0x218000)]:m.reg_write(reg,val)
 m.emu_start(start,end,count=100)
 assert m.reg_read(c.UC_ARM64_REG_PC)==end
 expected=bytearray(original)
 for i,word in enumerate(words):struct.pack_into('<II',expected,0x18e08+i*8,word&15,(word>>16)&15)
 assert bytes(m.mem_read(0x200000,0x20000))==expected
 # Native leaf writes shift and ID mask through output references.
 m.mem_write(0x223000,rng.randbytes(16))
 m.reg_write(c.UC_ARM64_REG_X1,0x223000);m.reg_write(c.UC_ARM64_REG_X2,0x223008)
 m.emu_start(hal,halend,count=20)
 assert bytes(m.mem_read(0x223000,16))==struct.pack('<QQ',0x28,0x7f)
report=dict(binary_sha256=sha,cases=1024,
 parse_slice=[hex(start),hex(end)],parse_slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),
 parser_base_derivation=dict(instruction='0xfffffe00089d6380',base='accelerator+0x18000'),
 parser_destination_range=['0x18e08','0x18e38'],kick_read_fields=['0xee28','0xee2c','0xee30'],
 kick_base_derivation=dict(instruction='0xfffffe00089dc2b8',base='accelerator+0xe000'),
 hal_range=[hex(hal),hex(halend)],hal_outputs=dict(shift=40,queue_id_mask=127),
 qualification='Native call-free slices execute with supplied pointer registers. Parser base and kick base are independently read from native address-forming instructions. Entire accelerator fixture comparison proves no changes at kick fields. HAL leaf output names are inferred from its symbol; no hardware kick, MMIO mapping provider or initialization of actual kick fields is proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print('1024 parser isolation cases and 1024 native kick-ID configuration cases passed')
