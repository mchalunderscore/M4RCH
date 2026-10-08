#!/usr/bin/env python3
"""Native G16 completion descriptor construction and allocation-size arithmetic."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
r=a.macho.read_bytes();sha=hashlib.sha256(r).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',r,16)[0]):
 cmd,size=struct.unpack_from('<II',r,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',r,pos+24))
 pos+=size
def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return r[off+addr-vm:off+addr-vm+n]
 raise ValueError('not file backed')
BASE=0xfffffe0000000000;FN=BASE+0x89d76c0;END=BASE+0x89d7948;A,OUT,STACK,STOP=0x200000,0x221000,0x222000,0x223000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(BASE+0x89d7000,4096),(BASE+0x712d000,4096),(0x200000,0x40000)]:m.mem_map(addr,n)
m.mem_write(FN,read(FN,END-FN));m.mem_write(BASE+0x712d000,read(BASE+0x712d000,4096))
values={};calls=[]
def hook(m,addr,size,user):
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)));assert target==0x239000
  obj=m.reg_read(c.UC_ARM64_REG_X0);assert obj in values;calls.append(obj);m.reg_write(c.UC_ARM64_REG_X0,values[obj]);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604024);counts=dict(cases=512,present_descriptors=0,absent_descriptors=0)
for i in range(512):
 accel=bytearray(rng.randbytes(0x20000));capacity=rng.getrandbits(32);struct.pack_into('<I',accel,0xee58,capacity);initial=rng.randbytes(0x80);expected=bytearray(initial);expected_calls=[];values.clear()
 for j in range(4):
  resource=0x224000+j*0x1000;obj58=0x228000+j*0x1000;obj50=0x22c000+j*0x1000;vt58=0x230000+j*0x1000;vt50=0x234000+j*0x1000
  present=bool(i&(1<<j));struct.pack_into('<Q',accel,0x1af70+j*8,resource if present else 0)
  m.mem_write(resource+0x58,struct.pack('<Q',obj58));m.mem_write(resource+0x50,struct.pack('<Q',obj50))
  for obj,vt in [(obj58,vt58),(obj50,vt50)]:m.mem_write(obj,struct.pack('<Q',vt));m.mem_write(vt+0x158,struct.pack('<Q',0x239000));values[obj]=rng.getrandbits(64)
  off=j*32;struct.pack_into('<Q',expected,off,0)
  if present:
   counts['present_descriptors']+=1;struct.pack_into('<2Q4I',expected,off,values[obj58],values[obj50],capacity,64,j,0);expected_calls.extend([obj58,obj50])
  else:counts['absent_descriptors']+=1
 m.mem_write(A,bytes(accel));m.mem_write(OUT,initial);m.reg_write(c.UC_ARM64_REG_X0,A);m.reg_write(c.UC_ARM64_REG_X1,OUT);m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);calls.clear();m.emu_start(FN,STOP,count=1000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and calls==expected_calls
 assert bytes(m.mem_read(OUT,128))==bytes(expected) and bytes(m.mem_read(A,len(accel)))==bytes(accel)
# Independently check native capacity*64 rounded to256 allocation argument.
size_start=BASE+0x89d713c;size_mid=BASE+0x89d7154;size_arg=BASE+0x89d7178
m.mem_write(size_start,read(size_start,size_mid-size_start));m.mem_write(size_arg,read(size_arg,4))
for capacity in [0,1,3,4,5,255,256,0xffffffff]+[rng.getrandbits(32) for _ in range(248)]:
 m.mem_write(A+0xee58,struct.pack('<I',capacity));m.reg_write(c.UC_ARM64_REG_X0,A);m.emu_start(size_start,size_mid,count=20);m.emu_start(size_arg,size_arg+4,count=5)
 assert m.reg_read(c.UC_ARM64_REG_X2)==(capacity*64+255)&~255
report=dict(binary_sha256=sha,counts=counts,allocation_geometry_cases=256,descriptor_size='0x20',entry_stride='0x40',resource_array='accelerator+0x1af70',capacity_source='accelerator+0xee58',function=dict(start=hex(FN),end=hex(END),sha256=hashlib.sha256(read(FN,END-FN)).hexdigest()),allocation_slices=[dict(start=hex(addr),size=n,sha256=hashlib.sha256(read(addr,n)).hexdigest()) for addr,n in [(size_start,size_mid-size_start),(size_arg,4)]],qualification='Complete native completion descriptor builder, all16 optional-resource combinations; independent full-output and call-order checks. PAC bypassed; resource50/58 virtual mapping getters synthetic. Capacity/stride/ordinal observed without naming pointer roles or entry payload. Allocation rounding slice only; no actual allocation, completion cursor, retirement or live GPU access.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
