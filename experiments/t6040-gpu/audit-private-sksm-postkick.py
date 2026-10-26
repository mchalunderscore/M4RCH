#!/usr/bin/env python3
"""Audit native SKSM post-kick records and publication with synthetic providers."""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
raw=args.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
BASE=0xfffffe0000000000;START=BASE+0x895c1b0;END=BASE+0x895c374
for vm,_,off,length in segments:
 if vm<=START and END<=vm+length:code=raw[off+START-vm:off+END-vm];break
else:raise ValueError('not file backed')
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(BASE+0x895c000,4096);m.mem_write(START,code);m.mem_map(0x200000,0x40000)
CH,D,A,F,CVT,FVT,S,STACK,R12,R14,R16=0x200000,0x201000,0x203000,0x223000,0x224000,0x225000,0x226000,0x227000,0x228000,0x229000,0x22a000
MAP,PUBLISH=0x22b000,0x22b100
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
m.mem_write(CH,struct.pack('<Q',CVT));m.mem_write(CH+0x10,struct.pack('<Q',A));m.mem_write(CVT+0x188,struct.pack('<Q',PUBLISH))
m.mem_write(A+0x5b0,struct.pack('<Q',F));m.mem_write(A+0xee5f,b'\0');m.mem_write(F,struct.pack('<Q',FVT));m.mem_write(FVT+0x2d8,struct.pack('<Q',MAP))
calls=[];mapped=0

def hook(m,addr,size,user):
 if addr==END:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);values=[m.reg_read(regs[i]) for i in range(4)]
  if target==MAP:
   assert values[0]==F and values[2]==0;calls.append(['map',values[1]]);result=mapped
  elif target==PUBLISH:
   assert values[0]==CH and values[3]==0
   calls.append(['publish',values[1],values[2],bytes(m.mem_read(values[2],24)).hex()]);result=0
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],result);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604019);examples=[];counts={'cases':1024,'opcode14':1024,'opcode12':0,'opcode16':0}
for i in range(1024):
 d=bytearray(rng.randbytes(0x1000));q=rng.getrandbits(32);timeline=rng.getrandbits(64);mode=rng.getrandbits(32);mapped=rng.getrandbits(64)
 ptrs=[rng.getrandbits(64) for _ in range(3)];initial=[rng.randbytes(24) for _ in range(3)]
 present12=bool(i&1);present16=bool(i&2)
 for offset,value in [(0x480,R12 if present12 else 0),(0x488,ptrs[0]),(0x450,R14),(0x458,ptrs[1]),(0x470,R16 if present16 else 0),(0x478,ptrs[2])]:struct.pack_into('<Q',d,offset,value)
 m.mem_write(D,bytes(d));m.mem_write(S+0x1c,struct.pack('<I',mode));m.mem_write(STACK+0x60,struct.pack('<Q',S));m.mem_write(STACK+0x78,struct.pack('<Q',CH))
 for addr,data in zip([R12,R14,R16],initial):m.mem_write(addr,data)
 for reg in regs:m.reg_write(reg,0)
 for j,value in [(19,CH),(20,D),(22,timeline),(23,S),(25,q)]:m.reg_write(regs[j],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);calls.clear();m.emu_start(START,END,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==END
 expected=[bytearray(x) for x in initial];expected_calls=[]
 if present12:
  counts['opcode12']+=1;r=expected[0];struct.pack_into('<I',r,0,12);struct.pack_into('<H',r,4,q&0xffff);struct.pack_into('<Q',r,6,timeline);struct.pack_into('<Q',r,14,mapped)
  expected_calls.append(['map',struct.unpack_from('<Q',d,0x910)[0]])
  expected_calls.append(['publish',ptrs[0],R12,bytes(r).hex()])
 r=expected[1];struct.pack_into('<I',r,0,14);struct.pack_into('<H',r,4,q&0xffff);struct.pack_into('<H',r,6,struct.unpack_from('<I',d,0x2dc)[0]&0xffff);r[8]=mode&0xff;struct.pack_into('<Q',r,9,timeline);struct.pack_into('<I',r,17,1)
 expected_calls.append(['publish',ptrs[1],R14,bytes(r).hex()])
 if present16:
  counts['opcode16']+=1;r=expected[2];struct.pack_into('<I',r,0,16);struct.pack_into('<H',r,4,q&0xffff);struct.pack_into('<Q',r,6,timeline);struct.pack_into('<I',r,14,254)
  expected_calls.append(['publish',ptrs[2],R16,bytes(r).hex()])
 assert calls==expected_calls,(i,calls,expected_calls)
 for addr,data in zip([R12,R14,R16],expected):assert bytes(m.mem_read(addr,24))==bytes(data)
 assert bytes(m.mem_read(D,len(d)))==bytes(d)
 if i<4:examples.append(dict(case=i,calls=calls))
args.output.write_text(json.dumps(dict(binary_sha256=sha,slice=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(code).hexdigest()),counts=counts,examples=examples,qualification='Native SKSM post-kick slice with accelerator ee5f bit0 clear; complete record backing and publication arguments compared. PAC bypassed. Firmware mapping and channel pointer publication intercepted, not live providers. Timeline input is synthetic return of earlier scheduler callback. No GPU execution or job retirement proved.'),indent=2)+'\n')
print(counts)
