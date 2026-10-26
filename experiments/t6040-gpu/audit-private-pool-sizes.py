#!/usr/bin/env python3
"""Native configurePoolElementSizes and caller/stride copies versus explicit sizes."""
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
BASE=0xfffffe0000000000;FN=BASE+0x89a2a78;CALL=BASE+0x89ab0b0;END=BASE+0x89ab0e0;FW,VT=0x200000,0x203000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(BASE+0x89a2000,4096),(BASE+0x89ab000,4096),(BASE+0x712d000,4096),(0x200000,0x10000)]:m.mem_map(addr,n)
for addr,n in [(FN,0x54),(CALL,END-CALL),(BASE+0x712d000,4096)]:m.mem_write(addr,read(addr,n))
m.mem_write(VT+0x8a0,struct.pack('<Q',FN))
def hook(m,addr,size,user):
 if addr==END:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  assert m.reg_read(c.UC_ARM64_REG_X8)==FN and m.reg_read(c.UC_ARM64_REG_X0)==FW
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,FN)
m.hook_add(u.UC_HOOK_CODE,hook)
sizes={0x218:0x9c0,0x220:0x2240,0x228:0xa00,0x230:0x1040,0x238:0x80,0x248:0x40,0x250:0x40,0x258:0x80,0x268:0x80,0x270:0x40,0x278:0x40,0x280:0xc0,0x288:0x40,0x290:0x40}
copies=[(0x89ab3a4,0x220,0x1338),(0x89ab3c4,0x228,0x1378),(0x89ab3e4,0x230,0x13b8),(0x89ab4c0,0x270,0x1538),(0x89ab4e0,0x278,0x1578),(0x89ab51c,0x288,0x15f8)]
for addr,_,_ in copies:m.mem_write(BASE+addr,read(BASE+addr,8))
rng=random.Random(604021)
for i in range(128):
 fw=bytearray(rng.randbytes(0x1700));struct.pack_into('<Q',fw,0,VT);m.mem_write(FW,bytes(fw));m.reg_write(c.UC_ARM64_REG_X19,FW);m.emu_start(CALL,END,count=100)
 for off,value in sizes.items():struct.pack_into('<Q',fw,off,value)
 struct.pack_into('<Q',fw,0x12f8,0x9c0)
 assert bytes(m.mem_read(FW,len(fw)))==bytes(fw)
 for addr,source,dest in copies:
  m.emu_start(BASE+addr,BASE+addr+8,count=10);struct.pack_into('<Q',fw,dest,sizes[source]);assert bytes(m.mem_read(FW,len(fw)))==bytes(fw)
bindings=[]
for table in [BASE+0x7ea7860,BASE+0x7ea8668]:
 encoded=struct.unpack('<Q',read(table+16+0x8a0,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==FN;bindings.append(dict(vtable=hex(table),slot='0x8a0',target=hex(FN)))
a.output.write_text(json.dumps(dict(binary_sha256=sha,cases=128,bindings=bindings,sizes={hex(k):hex(v) for k,v in sizes.items()},function=dict(start=hex(FN),end=hex(FN+0x54),sha256=hashlib.sha256(read(FN,0x54)).hexdigest()),caller=dict(start=hex(CALL),end=hex(END),sha256=hashlib.sha256(read(CALL,END-CALL)).hexdigest()),copies=[dict(start=hex(BASE+addr),source=hex(source),destination=hex(dest),sha256=hashlib.sha256(read(BASE+addr,8)).hexdigest()) for addr,source,dest in copies],qualification='Native caller virtual dispatch, complete constant size initializer and six downstream stride copies versus explicit independent size table; full firmware fixture preservation checked. PAC bypassed. Values describe host allocation strides, not necessarily wire payload extents; allocation/firmware execution absent.'),indent=2)+'\n');print({hex(k):hex(v) for k,v in sizes.items()})
