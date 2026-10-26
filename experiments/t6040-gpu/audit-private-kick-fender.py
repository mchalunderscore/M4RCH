#!/usr/bin/env python3
"""Offline complete native addKicks with native Fender gating methods."""
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
m.mem_map(0xfffffe00089d8000,4096);m.mem_write(0xfffffe00089d8268,read(0xfffffe00089d8268,0x1e0))
m.mem_map(0xfffffe0008a06000,4096);m.mem_map(0xfffffe0008a07000,4096)
m.mem_map(const&~4095,4096);m.mem_write(const,read(const,8))
assert read(const,8)==struct.pack('<II',0x4000,0x4008)
accel,queue,mmio=0x200000,0x220000,0x230000
m.mem_map(accel,0x24000);m.mem_map(mmio,0x5000);m.mem_map(0x240000,0x12000)
callbacks=[]
def on_code(m,address,size,data):
 if address==0x250000:m.emu_stop();return
 if address in (0xfffffe00089d8268,0xfffffe00089d8358):
  callbacks.append(0x58 if address==0xfffffe00089d8268 else 0x50);events.append(("callback",callbacks[-1]))
  assert m.reg_read(c.UC_ARM64_REG_X0)==0x222000
 if address in (0xfffffe0008a0625c,0xfffffe0008a07578):
  assert m.reg_read(c.UC_ARM64_REG_X0)==accel
  assert m.reg_read(c.UC_ARM64_REG_X1)==0xd06030
  if address==0xfffffe0008a0625c:
   events.append(("gate_read",))
   m.reg_write(c.UC_ARM64_REG_W0,int.from_bytes(m.mem_read(0x240030,4),"little"))
  else:
   value=m.reg_read(c.UC_ARM64_REG_W2)
   events.append(("gate_write",value))
   m.mem_write(0x240030,struct.pack("<I",value))
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
 if address==0x240030:
  assert size==4;events.append(("gate_write",value))
def on_read(m,access,address,size,value,data):
 if address==0x240030:
  assert size==4;events.append(("gate_read",))
m.hook_add(u.UC_HOOK_MEM_WRITE,on_write)
m.hook_add(u.UC_HOOK_MEM_READ,on_read)
rng=random.Random(60404090);cases=0
for qid in range(128):
 for count in [0,1,2,0x7f,0x100,0xffff,0x80000000,0xffffffff]:
  for mode in (0,1):
   guarded=True
   original=bytearray(rng.randbytes(0x20000))
   original[0x6d3]=(original[0x6d3]&~8)|(8 if guarded else 0)
   struct.pack_into("<Q",original,0x5b0,0x221000)
   original[0x1aed4]&=~1
   struct.pack_into("<I",original,0xc774,mode)
   struct.pack_into("<Q",original,0xc980,0xd06000)
   struct.pack_into("<Q",original,0xf8e8,0x240000)
   struct.pack_into('<Q',original,0x358,mmio)
   q=bytearray(rng.randbytes(0x100));struct.pack_into('<I',q,0xc,qid)
   backing=rng.randbytes(0x5000)
   m.mem_write(accel,bytes(original));m.mem_write(queue,bytes(q));m.mem_write(mmio,backing)
   m.reg_write(c.UC_ARM64_REG_X21,accel+0xec90)
   m.emu_start(init,initend,count=30)
   expected=bytearray(original);struct.pack_into('<III',expected,0xee28,0x4000,0x4008,0x10)
   assert bytes(m.mem_read(accel,len(original)))==expected
   gate_initial=rng.getrandbits(32);gate_backing=bytearray(rng.randbytes(4096));struct.pack_into("<I",gate_backing,0x30,gate_initial);m.mem_write(0x240000,bytes(gate_backing))
   writes.clear();callbacks.clear();events.clear()
   m.mem_write(0x221210,struct.pack("<Q",0x222000));m.mem_write(0x222000,struct.pack("<Q",0x223000))
   m.mem_write(0x223050,struct.pack("<QQ",0xfffffe00089d8358,0xfffffe00089d8268))
   m.mem_write(0x222010,struct.pack("<Q",accel))
   m.reg_write(c.UC_ARM64_REG_SP,0x24f000);m.reg_write(c.UC_ARM64_REG_X30,0x250000)
   struct.pack_into("<Q",q,0x68,accel);m.mem_write(queue,bytes(q))
   m.reg_write(c.UC_ARM64_REG_X0,queue);m.reg_write(c.UC_ARM64_REG_W1,count);m.reg_write(c.UC_ARM64_REG_X2,0)
   m.emu_start(kick,0x250000,count=500)
   assert m.reg_read(c.UC_ARM64_REG_PC)==0x250000
   assert callbacks==([0x58,0x50] if guarded else [])
   control=0x0020040000021018|(qid<<43)
   assert writes==[(0x4090,8,control),(0x4098,8,count)],writes
   assert events==[("callback",0x58),("gate_read",),("gate_write",gate_initial|4),("gate_read",),("write",0x4090),("write",0x4098),("callback",0x50),("gate_read",),("gate_write",gate_initial&~6),("gate_read",)],events
   struct.pack_into("<I",gate_backing,0x30,gate_initial&~6)
   assert bytes(m.mem_read(0x240000,4096))==gate_backing

   b=bytearray(backing);struct.pack_into('<QQ',b,0x4090,control,count)
   assert bytes(m.mem_read(mmio,len(b)))==b
   assert bytes(m.mem_read(accel,len(expected)))==expected
   assert bytes(m.mem_read(queue,len(q)))==q
   cases+=1
# The firmware initializer obtains Fender through accelerator virtualbd8.
# Verify native vtable targets without exporting table bytes.
def target(table,slot):return 0xfffffe0007004000+(int.from_bytes(read(table+16+slot,8),"little")&0xffffffff)
assert target(0xfffffe0007eae388,0xbd8)==0xfffffe00089d81cc
assert target(0xfffffe0007eabd90,0x58)==0xfffffe00089d8268
assert target(0xfffffe0007eabd90,0x50)==0xfffffe00089d8358
report=dict(binary_sha256=sha,cases=cases,queue_ids=[0,127],fender_access_modes=[0,1],
 provider_chain=dict(firmware_initialize_call='0xfffffe00089acfa8',accelerator_vtable='0xfffffe0007eae388',slot='0xbd8',factory='0xfffffe00089d81cc',factory_vtable='0xfffffe0007eabd90',firmware_store='0xfffffe00089acfac',firmware_field='0x210'),
 native_methods=dict(disable='0xfffffe00089d8268',enable='0xfffffe00089d8358',disable_slot='0x58',enable_slot='0x50'),
 gate_contract=dict(register='0xd06030',disable='old | 4',enable='old & ~6',readback_after_each_write=True,mode_field='accelerator+0xc774',mapped_base_field='accelerator+0xf8e8',mapped_offset_field='accelerator+0xc980'),
 kick_offsets=['0x4090','0x4098'],
 qualification='Complete native addKicks and complete native disable/enableDynamicFenderGating methods execute. Native vtable targets decoded and checked; firmware/factory chain statically inspected, not fully executed. PAC bypassed. Mode0 uses synthetic readGFXReg32/writeGFXReg32 providers; mode1 actual native memory accesses use supplied mapping. Entire accelerator/queue/MMIO backing checked. No real MMIO, physical mapping, concurrency, cache coherency, firmware acceptance, power handshake, shader execution or rendering.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(cases,'native kick/Fender connected cases passed')
