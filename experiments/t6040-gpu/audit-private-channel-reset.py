#!/usr/bin/env python3
"""Compare numeric reset model with call-free matched AGX reset instructions."""
import argparse, hashlib, json, random, struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_CPACR_EL1, UC_ARM64_REG_PC
from private_channel_reset import reset_prefix
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
s=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:s.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
start,end=0xfffffe000897dea8,0xfffffe000897df50
for vm,_,off,length in s:
 if vm<=start and end<=vm+length:code=raw[off+start-vm:off+end-vm];break
else:raise ValueError('Not file backed')
u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
u.mem_map(0x100000,4096);u.mem_write(0x100000,code)
u.mem_map(0x200000,0x3000);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
rng=random.Random(6040)
for i in range(256):
 channel=bytearray(rng.randbytes(0x200));queue=rng.randbytes(0x80)
 pointers=[rng.getrandbits(64) for _ in range(3)]
 capacity=[0,1,16,256,0xffffffff][i%5];identifier=rng.getrandbits(32);context=rng.getrandbits(64)
 struct.pack_into('<QQ',channel,0x58,0x201000,0x202000)
 struct.pack_into('<QQQ',channel,0x88,*pointers)
 struct.pack_into('<I',channel,0x54,capacity);struct.pack_into('<I',channel,0x4c,identifier)
 struct.pack_into('<Q',channel,0xf8,context)
 u.mem_write(0x200000,bytes(channel));u.mem_write(0x201000,b'\xa5'*0xd0);u.mem_write(0x202000,queue)
 u.reg_write(UC_ARM64_REG_X0,0x200000)
 u.emu_start(0x100000,0x100000+len(code),count=100)
 assert u.reg_read(UC_ARM64_REG_PC)==0x100000+len(code)
 expected_state,expected_queue=reset_prefix(queue,pointers,capacity,identifier,context)
 assert bytes(u.mem_read(0x201000,0xc0))==expected_state
 assert bytes(u.mem_read(0x202000,0x80))==expected_queue
 assert bytes(u.mem_read(0x2010c0,16))==b'\xa5'*16
 expected_channel=bytearray(channel)
 struct.pack_into('<I',expected_channel,0x70,0);struct.pack_into('<Q',expected_channel,0xd8,0)
 assert bytes(u.mem_read(0x200000,0x200))==bytes(expected_channel)
report=dict(binary_sha256=sha,slice_range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(code).hexdigest(),model_cases=256,
 state_bytes=192,queue_minimum_observed_bytes=100,state_sentinels=['0x24','0x44'],queue_sentinel='0x50',
 qualification='Reviewed call-free reset prefix only. Randomized inputs and prefilled output detect missing/preserved writes. Capacity boundary cases characterize native copying, not protocol-valid capacities. No hardware or complete job constructor verified.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('256 reset-prefix cases matched native instructions, including sentinels and preserved bytes')
