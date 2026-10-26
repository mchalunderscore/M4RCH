#!/usr/bin/env python3
"""Offline connected native kick-offset initialization and direct writes."""
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
m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
init,initend=0xfffffe00089d9e00,0xfffffe00089d9e14
kick,kickend=0xfffffe00089dc240,0xfffffe00089dc394
const=0xfffffe000712d930
for lo,hi in [(init,initend),(kick,kickend)]:
 m.mem_map(lo&~4095,4096);m.mem_write(lo,read(lo,hi-lo))
m.mem_map(const&~4095,4096);m.mem_write(const,read(const,8))
assert read(const,8)==struct.pack('<II',0x4000,0x4008)
accel,queue,mmio=0x200000,0x220000,0x230000
m.mem_map(accel,0x24000);m.mem_map(mmio,0x5000);m.mem_map(0x240000,0x12000)
callbacks=[]
def on_code(m,address,size,data):
 if address==0x250000:m.emu_stop();return
 if address in (0x251000,0x251004):
  callbacks.append(0x58 if address==0x251000 else 0x50);events.append(("callback",callbacks[-1]))
  assert m.reg_read(c.UC_ARM64_REG_X0)==0x222000
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 word=int.from_bytes(m.mem_read(address,4),"little")
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800:
  m.reg_write(c.UC_ARM64_REG_PC,address+4)
 elif word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(getattr(c,"UC_ARM64_REG_X"+str((word>>5)&31)))
  if word&0xfffffc00==0xd73f0800:m.reg_write(c.UC_ARM64_REG_X30,address+4)
  m.reg_write(c.UC_ARM64_REG_PC,target)
 elif word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30))
m.hook_add(u.UC_HOOK_CODE,on_code)
writes=[];events=[]
def on_write(m,access,address,size,value,data):
 if mmio<=address<mmio+0x5000:
  writes.append((address-mmio,size,value));events.append(("write",address-mmio))
m.hook_add(u.UC_HOOK_MEM_WRITE,on_write)
rng=random.Random(60404090);cases=0
for qid in range(128):
 for count in [0,1,2,0x7f,0x100,0xffff,0x80000000,0xffffffff]:
  for guarded in (False,True):
   original=bytearray(rng.randbytes(0x20000))
   original[0x6d3]=(original[0x6d3]&~8)|(8 if guarded else 0)
   struct.pack_into("<Q",original,0x5b0,0x221000)
   original[0x1aed4]&=~1
   struct.pack_into('<Q',original,0x358,mmio)
   q=bytearray(rng.randbytes(0x100));struct.pack_into('<I',q,0xc,qid)
   backing=rng.randbytes(0x5000)
   m.mem_write(accel,bytes(original));m.mem_write(queue,bytes(q));m.mem_write(mmio,backing)
   m.reg_write(c.UC_ARM64_REG_X21,accel+0xec90)
   m.emu_start(init,initend,count=30)
   expected=bytearray(original);struct.pack_into('<III',expected,0xee28,0x4000,0x4008,0x10)
   assert bytes(m.mem_read(accel,len(original)))==expected
   writes.clear();callbacks.clear();events.clear()
   m.mem_write(0x221210,struct.pack("<Q",0x222000));m.mem_write(0x222000,struct.pack("<Q",0x223000))
   m.mem_write(0x223050,struct.pack("<QQ",0x251004,0x251000))
   m.reg_write(c.UC_ARM64_REG_SP,0x24f000);m.reg_write(c.UC_ARM64_REG_X30,0x250000)
   struct.pack_into("<Q",q,0x68,accel);m.mem_write(queue,bytes(q))
   m.reg_write(c.UC_ARM64_REG_X0,queue);m.reg_write(c.UC_ARM64_REG_W1,count);m.reg_write(c.UC_ARM64_REG_X2,0)
   m.emu_start(kick,0x250000,count=200)
   assert m.reg_read(c.UC_ARM64_REG_PC)==0x250000
   assert callbacks==([0x58,0x50] if guarded else [])
   control=0x0020040000021018|(qid<<43)
   assert writes==[(0x4090,8,control),(0x4098,8,count)],writes
   assert events==(([ ("callback",0x58)] if guarded else [])+[("write",0x4090),("write",0x4098)]+([( "callback",0x50)] if guarded else []))
   b=bytearray(backing);struct.pack_into('<QQ',b,0x4090,control,count)
   assert bytes(m.mem_read(mmio,len(b)))==b
   assert bytes(m.mem_read(accel,len(expected)))==expected
   assert bytes(m.mem_read(queue,len(q)))==q
   cases+=1
variant,variantend=0xfffffe00089ea4d4,0xfffffe00089ea4e4
m.mem_map(variant&~4095,4096);m.mem_write(variant,read(variant,variantend-variant))
for _ in range(1024):
 original=rng.randbytes(0x20000);flags=rng.getrandbits(64)
 m.mem_write(accel,original);m.reg_write(c.UC_ARM64_REG_X19,accel);m.reg_write(c.UC_ARM64_REG_X9,flags)
 m.emu_start(variant,variantend,count=20)
 expected=bytearray(original);struct.pack_into('<Q',expected,0x6d0,flags|0x0004000018020000)
 assert bytes(m.mem_read(accel,len(expected)))==expected
 assert m.mem_read(accel+0x6d3,1)[0]&8

report=dict(binary_sha256=sha,cases=cases,variant_flag_cases=1024,variant_flag_range=[hex(variant),hex(variantend)],variant_or_mask="0x0004000018020000",variant_sets_guarded_mode=True,queue_ids=[0,127],counts=[0,1,2,127,256,65535,2147483648,4294967295],
 initialization=dict(range=[hex(init),hex(initend)],slice_sha256=hashlib.sha256(read(init,initend-init)).hexdigest(),base_instruction='0xfffffe00089d9bbc',base='accelerator+0xec90',constant_address=hex(const),fields={'0xee28':16384,'0xee2c':16392,'0xee30':16}),
 direct_kick=dict(range=[hex(kick),hex(kickend)],slice_sha256=hashlib.sha256(read(kick,kickend-kick)).hexdigest(),base_field='accelerator+0x358',control_offset='0x4090',count_offset='0x4098',control_constant='0x0020040000021018',queue_id_shift=43,store_width=8,write_order=['control','count'],bank_index=9),
 qualification='Native initialization feeds complete native addKicks with tracing disabled, both accelerator6d3 bit3 modes, supplied mappings and synthetic slot58/50 callbacks. PAC bypassed. Entire fixtures checked. Guarded mode calls slot58 before stores and tail-calls slot50 afterward. No actual MMIO, callback implementation, provider mapping, concurrent ordering, hardware acceptance or rendering; large counts characterize encoding, not valid job ranges. Later configuration overrides not excluded.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(cases,'connected native initialization/direct-kick cases passed')
