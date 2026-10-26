#!/usr/bin/env python3
"""Native SKSM control-slot cleanup versus independent bookkeeping/call model."""
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
BASE=0xfffffe0000000000;START=BASE+0x895df04;END=BASE+0x895e054
D,A,FW=0x200000,0x202000,0x203000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(BASE+0x895d000,0x2000);m.mem_map(0x200000,0x10000)
code=read(START,END-START);wake=read(BASE+0x895e360,0x40);m.mem_write(START,code);m.mem_write(BASE+0x895e360,wake);m.mem_write(A+0x5b0,struct.pack('<Q',FW))
pools=[(0x480,0x1518,0x40),(0x450,0x1558,0x40),(0x460,0x1598,0xc0),(0x470,0x15d8,0x40)]
calls=[];STOP=0x21f000;mapping_value=0
def hook(m,addr,size,user):
 if addr in (END,STOP):m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00==0xd73f0800:
  assert m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)))==0x21d000
  calls.append(['map',m.reg_read(c.UC_ARM64_REG_X0)]);m.reg_write(c.UC_ARM64_REG_X0,mapping_value);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  names={BASE+0xb7b13c4:'lock',BASE+0xb7b27c0:'unlock',BASE+0xa7e51c8:'resource_callback'}
  assert target in names;calls.append([names[target],m.reg_read(c.UC_ARM64_REG_X0)]);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604022);counts=dict(cases=1024,released=0,zero_occupancy=0,resource_callback=0,absent=0)
for i in range(1024):
 descriptor=bytearray(rng.randbytes(0x1000));struct.pack_into('<Q',descriptor,0x10,A);fw=bytearray(rng.randbytes(0x1700));expected_calls=[];bitmaps=[];original_pointers=[]
 for j,(field,pool,stride) in enumerate(pools):
  bitmap_addr=0x205000+j*0x1000;resource=0x209000+j*0x1000;lock=0x20d000+j*16;callback=0x20e000+j*16
  # Valid slot geometry; CPU pointer low32 subtraction also wraps over 4GiB.
  slot=rng.randrange(256);cpu=(0xfffffff0 if i&16 else 0x80000000)+rng.randrange(16);cpu|=rng.getrandbits(16)<<32
  pointer=(cpu+slot*stride)&((1<<64)-1);present=bool(i&(1<<j));flag=(i>>(4+j))&1
  bitmap=bytearray(rng.randbytes(256));bitmap[slot]=[0,1,2,255][(i//16+j)%4]
  original_pointers.append(pointer if present else 0);struct.pack_into('<Q',descriptor,field,pointer if present else 0)
  struct.pack_into('<Q',fw,pool,resource);struct.pack_into('<Q',fw,pool+0x10,cpu);struct.pack_into('<Q',fw,pool+0x18,bitmap_addr);struct.pack_into('<Q',fw,pool+0x20,stride);struct.pack_into('<I',fw,pool+0x30,flag);struct.pack_into('<Q',fw,pool+0x38,lock)
  m.mem_write(bitmap_addr,bytes(bitmap));m.mem_write(resource+0x158,struct.pack('<Q',callback))
  if present:
   counts['released']+=1;expected_calls.append(['lock',lock])
   if bitmap[slot]:bitmap[slot]-=1
   else:counts['zero_occupancy']+=1
   if flag:counts['resource_callback']+=1;expected_calls.append(['resource_callback',callback])
   expected_calls.append(['unlock',lock]);struct.pack_into('<Q',descriptor,field,0)
  else:counts['absent']+=1
  bitmaps.append((bitmap_addr,bytes(bitmap)))
 original=bytearray(descriptor)
 for (field,_,_),pointer in zip(pools,original_pointers):struct.pack_into('<Q',original,field,pointer)
 m.mem_write(D,bytes(original));m.mem_write(FW,bytes(fw));m.reg_write(c.UC_ARM64_REG_X19,D);m.reg_write(c.UC_ARM64_REG_SP,0x20f000);calls.clear();m.emu_start(START,END,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==END and calls==expected_calls,(i,calls,expected_calls)
 assert bytes(m.mem_read(D,len(descriptor)))==bytes(descriptor)
 assert bytes(m.mem_read(FW,len(fw)))==bytes(fw)
 for addr,expected in bitmaps:assert bytes(m.mem_read(addr,len(expected)))==expected
# Actual request and cleanup sequences repeated across all four slots.
m.mem_map(BASE+0x89b6000,4096);m.mem_write(BASE+0x89b687c,read(BASE+0x89b687c,0x490));m.mem_map(0x210000,0x10000)
request_functions=[0x89b687c,0x89b69a0,0x89b6ac4,0x89b6be8]
fw=bytearray(rng.randbytes(0x1700));descriptor=bytearray(rng.randbytes(0x1000));struct.pack_into('<Q',descriptor,0x10,A)
for j,(field,pool,stride) in enumerate(pools):
 bitmap_addr=0x205000+j*0x1000;resource=0x209000+j*0x1000;lock=0x20d000+j*16;obj=0x210000+j*0x1000;vt=0x214000+j*0x1000
 struct.pack_into('<Q',fw,pool,resource);struct.pack_into('<Q',fw,pool+8,resource);struct.pack_into('<Q',fw,pool+0x10,0x500000+j*0x10000);struct.pack_into('<Q',fw,pool+0x18,bitmap_addr);struct.pack_into('<Q',fw,pool+0x20,stride);struct.pack_into('<I',fw,pool+0x28,4);struct.pack_into('<I',fw,pool+0x2c,0);struct.pack_into('<I',fw,pool+0x30,0);struct.pack_into('<Q',fw,pool+0x38,lock)
 m.mem_write(bitmap_addr,bytes(4));m.mem_write(resource+0x50,struct.pack('<Q',obj));m.mem_write(obj,struct.pack('<Q',vt));m.mem_write(vt+0x158,struct.pack('<Q',0x21d000));struct.pack_into('<Q',descriptor,field,0)
m.mem_write(FW,bytes(fw));m.mem_write(D,bytes(descriptor))
for iteration in range(64):
 slot=iteration%4;expected_calls=[];calls.clear()
 for j,((field,pool,stride),fn) in enumerate(zip(pools,request_functions)):
  mapping_value=0x900000+j*0x10000;lock=0x20d000+j*16;obj=0x210000+j*0x1000
  m.reg_write(c.UC_ARM64_REG_X0,FW);m.reg_write(c.UC_ARM64_REG_X1,D+field+8);m.reg_write(c.UC_ARM64_REG_SP,0x21e000);m.reg_write(c.UC_ARM64_REG_LR,STOP);m.emu_start(BASE+fn,STOP,count=1000)
  pointer=0x500000+j*0x10000+slot*stride;assert m.reg_read(c.UC_ARM64_REG_X0)==pointer
  m.mem_write(D+field,struct.pack('<Q',pointer));struct.pack_into('<Q',descriptor,field,pointer);struct.pack_into('<Q',descriptor,field+8,mapping_value+slot*stride);struct.pack_into('<I',fw,pool+0x2c,(slot+1)%4)
  expected_calls.extend([['lock',lock],['map',obj],['unlock',lock]])
 assert calls==expected_calls and bytes(m.mem_read(D,len(descriptor)))==bytes(descriptor) and bytes(m.mem_read(FW,len(fw)))==bytes(fw)
 for j in range(4):assert bytes(m.mem_read(0x205000+j*0x1000,4))==bytes(int(k==slot) for k in range(4))
 m.reg_write(c.UC_ARM64_REG_X19,D);calls.clear();m.emu_start(START,END,count=1000)
 expected_calls=[]
 for j,(field,pool,stride) in enumerate(pools):
  struct.pack_into('<Q',descriptor,field,0);lock=0x20d000+j*16;expected_calls.extend([['lock',lock],['unlock',lock]])
 assert calls==expected_calls and bytes(m.mem_read(D,len(descriptor)))==bytes(descriptor) and bytes(m.mem_read(FW,len(fw)))==bytes(fw)
 for j in range(4):assert bytes(m.mem_read(0x205000+j*0x1000,4))==bytes(4)
counts['native_allocate_release_cycles']=64;counts['native_roundtrip_slot_releases']=256
report=dict(binary_sha256=sha,counts=counts,request_functions=dict(start=hex(BASE+0x89b687c),end=hex(BASE+0x89b6d0c),sha256=hashlib.sha256(read(BASE+0x89b687c,0x490)).hexdigest()),slice=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(code).hexdigest()),callback_tail=dict(start=hex(BASE+0x895e360),size='0x40',sha256=hashlib.sha256(wake).hexdigest()),qualification='Native descriptor complete control-slot cleanup slice, not full complete function. All four optional control pools, zero/nonzero occupancy, failure-flag callback and low32 CPU address subtraction covered. Lock/unlock/resource callback synthetic. No completion trigger, actual fence, ownership/concurrency or hardware retirement established.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
