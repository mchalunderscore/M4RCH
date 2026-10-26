#!/usr/bin/env python3
"""Qualify common work-kick header, aperture and payload against native instructions."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_work_prefix import patch_work_prefix
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0x100000,4096);m.mem_map(0x200000,0x10000)
rng=random.Random(604003)
start,end=0xfffffe00089db298,0xfffffe00089db370
code=read(start,end-start);m.mem_write(0x100000,code)
for i in range(1024):
 record=rng.randbytes(0x200);timestamp=rng.getrandbits(64);qid=rng.getrandbits(32);priority=rng.getrandbits(32)
 address=rng.getrandbits(64);index=rng.getrandbits(32);count=[0,1,2,64,65,0xffffffff][i%6]
 flag0=bool(i&1);flag1=bool(i&2);payload=[rng.getrandbits(64),rng.getrandbits(64)]
 m.mem_write(0x200000,record);m.mem_write(0x20100c,struct.pack('<I',qid));m.mem_write(0x20101c,struct.pack('<I',priority));m.mem_write(0x201048,struct.pack('<Q',timestamp))
 m.mem_write(0x202000,struct.pack('<Q2I',address,index,count));m.mem_write(0x203000,struct.pack('<Q',0x204000));m.mem_write(0x204000,struct.pack('<2Q',*payload));m.mem_write(0x205010,struct.pack('<Q',0))
 for reg,val in [(c.UC_ARM64_REG_X21,0x200000),(c.UC_ARM64_REG_X19,0x201000),(c.UC_ARM64_REG_X27,0x202000),(c.UC_ARM64_REG_X26,0x203000),(c.UC_ARM64_REG_X29,0x205000),(c.UC_ARM64_REG_W24,flag0),(c.UC_ARM64_REG_W28,flag1)]:m.reg_write(reg,int(val))
 m.emu_start(0x100000,0x100000+len(code),count=100)
 assert bytes(m.mem_read(0x200000,0x200))==patch_work_prefix(record,timestamp,qid,priority,address,index,count,flag0,flag1,payload)
report=dict(binary_sha256=sha,work_prefix_cases=1024,instruction_range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(code).hexdigest(),
 findings=['Optional aperture descriptor modifies +0x8 only when count nonzero; 38-bit address>>5 at bit6, six-bit index and count-minus1 fields',
 'Work header differs from NOP final mask: 0xc401fffffffffffe, aperture bit58 and caller flag bit61',
 'Two payload words copied at +0x10/+0x18; their meanings depend on caller'],
 qualification='Actual call-free common work encoder prefix in emulated RAM. External record initialization, dependency body, QOS, shader/TA/3D work structures, publication and live firmware acceptance excluded. Count65/all-ones and unaligned address inputs characterize masking, not valid submissions.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 ordinary work-kick prefix cases matched native instructions')
