#!/usr/bin/env python3
"""Offline complete native single-region CPU PIO mapping."""
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
start,end=0xfffffe0008977fd8,0xfffffe0008978284
m.mem_map(start&~4095,0x3000);m.mem_write(start,read(start,end-start))
m.mem_map(0xfffffe0007ea2000,4096)
m.mem_map(0xfffffe000bfa4000,0x1000)
m.mem_map(0x200000,0x20000);m.mem_map(0x230000,0x22000)
accel=0x200000;mem=0x230000;memvt=0x231000;mapping=0x232000;mapvt=0x233000;shiftptr=0x234000;stop=0x250000
m.mem_write(0xfffffe0007ea2388,struct.pack('<Q',shiftptr))
m.mem_write(mem,struct.pack('<Q',memvt));m.mem_write(memvt+0x228,struct.pack('<Q',0x251000));m.mem_write(memvt+0x28,struct.pack('<Q',0x251008))
m.mem_write(mapping,struct.pack('<Q',mapvt));m.mem_write(mapvt+0x138,struct.pack('<Q',0x251004))
calls=[];failure="none"
def hook(m,address,size,data):
 if address==stop:m.emu_stop();return
 if address==0xfffffe000bfa4df4:
  calls.append(('factory',m.reg_read(c.UC_ARM64_REG_X0),m.reg_read(c.UC_ARM64_REG_X1),m.reg_read(c.UC_ARM64_REG_W2)))
  m.reg_write(c.UC_ARM64_REG_X0,0 if failure=="factory" else mem);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 if address in (0x251000,0x251004,0x251008):
  obj=m.reg_read(c.UC_ARM64_REG_X0)
  if address==0x251000:
   assert obj==mem;calls.append(('map',m.reg_read(c.UC_ARM64_REG_X1)));m.reg_write(c.UC_ARM64_REG_X0,0 if failure=="map" else mapping)
  elif address==0x251004:
   assert obj==mapping;calls.append(('address',));m.reg_write(c.UC_ARM64_REG_X0,0 if failure=="address" else virtual)
  else:assert obj==mem;calls.append(('release',))
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 word=int.from_bytes(m.mem_read(address,4),'little')
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800:m.reg_write(c.UC_ARM64_REG_PC,address+4)
 elif word&0xfffffc00==0xd73f0800:
  target=m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)))
  m.reg_write(c.UC_ARM64_REG_X30,address+4);m.reg_write(c.UC_ARM64_REG_PC,target)
 elif word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30))
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604045);cases=0
for shift in [12,14,16]:
 for region in [0,3,17,26,45,48]:
  for flags in [0,2]:
   for _ in range(32):
    physical=0x288000000+rng.randrange(0x2000000);span=rng.randrange(1,0x10000);options=rng.getrandbits(32)
    virtual=0xffff000000000000+(rng.getrandbits(24)<<16)
    original=bytearray(rng.randbytes(0x20000));descriptor=0x998+region*0x438
    struct.pack_into('<IIQ',original,descriptor,flags,1,physical);struct.pack_into('<I',original,descriptor+0x208,span)
    m.mem_write(accel,bytes(original));m.mem_write(shiftptr,struct.pack('<I',shift))
    m.reg_write(c.UC_ARM64_REG_X0,accel);m.reg_write(c.UC_ARM64_REG_W1,region);m.reg_write(c.UC_ARM64_REG_W2,options)
    m.reg_write(c.UC_ARM64_REG_SP,0x24f000);m.reg_write(c.UC_ARM64_REG_X30,stop);calls.clear()
    m.emu_start(start,stop,count=500)
    assert m.reg_read(c.UC_ARM64_REG_PC)==stop
    assert m.reg_read(c.UC_ARM64_REG_W0)==1
    page=1<<shift;lo=physical&~(page-1);hi=(physical+span+page-1)&~(page-1)
    assert calls==[('factory',lo,hi-lo,(flags&2)|1),('map',options),('address',),('release',)],calls
    expected=bytearray(original);struct.pack_into('<Q',expected,0xf780+region*8,virtual);struct.pack_into('<Q',expected,0xf5d8+region*8,mapping)
    assert bytes(m.mem_read(accel,len(expected)))==expected
    cases+=1
failure_cases={}
for failure in ['empty','factory','map','address']:
 for _ in range(256):
  region=45;options=rng.getrandbits(32);virtual=0xffff000000100000
  original=bytearray(rng.randbytes(0x20000));descriptor=0x998+region*0x438
  struct.pack_into('<IIQ',original,descriptor,0,0 if failure=='empty' else 1,0x288d06000)
  struct.pack_into('<I',original,descriptor+0x208,0x1000)
  m.mem_write(accel,bytes(original));m.mem_write(shiftptr,struct.pack('<I',14))
  for reg,val in [(c.UC_ARM64_REG_X0,accel),(c.UC_ARM64_REG_W1,region),(c.UC_ARM64_REG_W2,options),(c.UC_ARM64_REG_SP,0x24f000),(c.UC_ARM64_REG_X30,stop)]:m.reg_write(reg,val)
  calls.clear();m.emu_start(start,stop,count=500)
  assert m.reg_read(c.UC_ARM64_REG_PC)==stop
  expected=bytearray(original)
  factory=('factory',0x288d04000,0x4000,1)
  if failure=='empty':assert calls==[]
  elif failure=='factory':assert calls==[factory]
  elif failure=='map':assert calls==[factory,('map',options),('release',)]
  else:
   assert calls==[factory,('map',options),('address',),('release',)]
   struct.pack_into('<Q',expected,0xf780+region*8,0);struct.pack_into('<Q',expected,0xf5d8+region*8,mapping)
  assert m.reg_read(c.UC_ARM64_REG_W0)==(1 if failure=='address' else 0)
  assert bytes(m.mem_read(accel,len(expected)))==expected
 failure_cases[failure]=256
report=dict(binary_sha256=sha,cases=cases,failure_cases=failure_cases,range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),
 region_indices=[0,3,17,26,45,48],page_shifts=[12,14,16],single_segment=True,descriptor_base='0x998',descriptor_stride='0x438',address_cache='0xf780',map_cache='0xf5d8',fender_region=45,fender_address_field='0xf8e8',fender_descriptor='0xc770',
 contract='factory(page_aligned_physical, rounded_span, (flags & 2) | 1); memory.map(options); map.address(); cache virtual and mapping; release descriptor',
 qualification='Complete native single-segment success path executes with synthetic descriptor/map/address/release providers and PAC bypassed. Entire accelerator fixture compared. Physical addresses are supplied test inputs, not observations from macOS or Linux. Empty/factory/map failures preserve existing caches; successful map with zero returned address stores zero and still returns1. No multi-segment path, real MMIO, physical base358 provenance, cache/coherency behavior or rendering proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(cases,'complete native single-region CPU mapping cases passed')
