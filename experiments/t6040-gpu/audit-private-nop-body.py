#!/usr/bin/env python3
"""Compare NOP body and event timestamp conversion against native instruction slices."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_nop_body import patch_cached_body,convert_timestamp
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
m.mem_map(0x100000,4096);m.mem_map(0x200000,0x10000)
m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
rng=random.Random(604001)
start,end=0xfffffe00089dc0c8,0xfffffe00089dc1d4
code=read(start,end-start);m.mem_write(0x100000,code)
for i in range(512):
 record=rng.randbytes(0x200);timestamp=rng.getrandbits(64);qid=rng.getrandbits(32);priority=rng.getrandbits(32)
 previous=rng.getrandbits(64);capacity=[1,2,3,16,256][i%5]
 masks=[rng.getrandbits(64) for _ in range(4)];payload=[rng.getrandbits(64) for _ in range(2)]
 queue=bytearray(rng.randbytes(0x100))
 for off,val,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x1c,priority,'I'),(0x48,timestamp,'Q'),(0xa0,previous,'Q')]:struct.pack_into('<'+fmt,queue,off,val)
 queue[0x98]|=1
 m.mem_write(0x200000,record);m.mem_write(0x201000,bytes(queue));m.mem_write(0x202000,struct.pack('<4Q',*masks))
 m.mem_write(0x203000,struct.pack('<Q',0x204000));m.mem_write(0x204000,struct.pack('<2Q',*payload))
 for reg,val in [(c.UC_ARM64_REG_X21,0x200000),(c.UC_ARM64_REG_X19,0x201000),(c.UC_ARM64_REG_X22,0x202000),(c.UC_ARM64_REG_X20,0x203000)]:m.reg_write(reg,val)
 m.emu_start(0x100000,0x100000+len(code),count=200)
 expected,counter=patch_cached_body(record,timestamp,qid,priority,previous,masks,payload,capacity)
 assert bytes(m.mem_read(0x200000,0x200))==expected
 struct.pack_into('<Q',queue,0x48,counter)
 assert bytes(m.mem_read(0x201000,0x100))==bytes(queue)
 assert m.reg_read(c.UC_ARM64_REG_X0)==timestamp
start2,end2=0xfffffe00089ee94c,0xfffffe00089ee9b8
code2=read(start2,end2-start2);m.mem_write(0x100000,code2);m.ctl_remove_cache(0x100000,0x101000)
for i in range(1024):
 capacity=[1,2,3,16,256][i%5];initial=rng.getrandbits(64);event=rng.getrandbits(32) if i>8 else [0,1,255,256,0x7fffffff,0x80000000,0xfffffffe,0xffffffff,0x80000001][i]
 index=i%24;epoch0=rng.getrandbits(64);epoch1=rng.getrandbits(64)
 m.mem_write(0x201010,struct.pack('<I',capacity));m.mem_write(0x201068,struct.pack('<Q',0x205000));m.mem_write(0x201090,struct.pack('<Q',initial))
 m.mem_write(0x205140,struct.pack('<Q',0x206000))
 m.mem_write(0x206000+0x1458+index*24,struct.pack('<2Q',epoch0,epoch1))
 m.reg_write(c.UC_ARM64_REG_X0,0x201000);m.reg_write(c.UC_ARM64_REG_W1,index);m.reg_write(c.UC_ARM64_REG_W2,event)
 m.emu_start(0x100000,0x100000+len(code2),count=100)
 assert m.reg_read(c.UC_ARM64_REG_X0)==convert_timestamp(epoch0 if event<0x80000000 else epoch1,event,capacity,initial)
# Follow the real uncached branch and BL/RET into the already checked helper.
m.mem_map(0xfffffe00089dc000,4096);m.mem_map(0xfffffe00089ee000,4096)
m.mem_write(start,read(start,0xfffffe00089dc224-start));m.mem_write(start2,read(start2,end2+4-start2))
for i in range(512):
 record=rng.randbytes(0x200);timestamp=rng.getrandbits(64);qid=rng.getrandbits(32);priority=rng.getrandbits(32)
 capacity=[1,2,3,16,256][i%5];initial=rng.getrandbits(64);event=rng.getrandbits(32);index=i%24
 epoch0=rng.getrandbits(64);epoch1=rng.getrandbits(64)
 masks=[rng.getrandbits(64) for _ in range(4)];payload=[rng.getrandbits(64) for _ in range(2)]
 queue=bytearray(rng.randbytes(0x100))
 for off,val,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x1c,priority,'I'),(0x48,timestamp,'Q'),(0x68,0x205000,'Q'),(0x90,initial,'Q')]:struct.pack_into('<'+fmt,queue,off,val)
 queue[0x98]&=254
 m.mem_write(0x200000,record);m.mem_write(0x201000,bytes(queue));m.mem_write(0x202000,struct.pack('<4Q',*masks))
 m.mem_write(0x203000,struct.pack('<Q',0x204000));m.mem_write(0x204000,struct.pack('<2Q',*payload))
 m.mem_write(0x205140,struct.pack('<Q',0x206000));m.mem_write(0x206000+0x1458+index*24,struct.pack('<2Q',epoch0,epoch1))
 for reg,val in [(c.UC_ARM64_REG_X21,0x200000),(c.UC_ARM64_REG_X19,0x201000),(c.UC_ARM64_REG_X22,0x202000),(c.UC_ARM64_REG_X20,0x203000),(c.UC_ARM64_REG_X24,index),(c.UC_ARM64_REG_X23,event)]:m.reg_write(reg,val)
 m.emu_start(start,end,count=300)
 previous=(convert_timestamp(epoch0 if event<0x80000000 else epoch1,event,capacity,initial)-1)&((1<<64)-1)
 expected,counter=patch_cached_body(record,timestamp,qid,priority,previous,masks,payload,capacity)
 assert bytes(m.mem_read(0x200000,0x200))==expected
 struct.pack_into('<Q',queue,0x48,counter)
 assert bytes(m.mem_read(0x201000,0x100))==bytes(queue)
 assert m.reg_read(c.UC_ARM64_REG_X0)==timestamp
report=dict(binary_sha256=sha,cached_nop_body_cases=512,uncached_nop_body_cases=512,timestamp_conversion_cases=1024,
 instruction_ranges=[[hex(start),hex(end)],[hex(start2),hex(end2)]],slice_hashes=[hashlib.sha256(code).hexdigest(),hashlib.sha256(code2).hexdigest()],uncached_branch_range=[hex(0xfffffe00089dc20c),hex(0xfffffe00089dc224)],uncached_branch_sha256=hashlib.sha256(read(0xfffffe00089dc20c,24)).hexdigest(),
 findings=['NOP payload words occupy +0x10/+0x18; caller supplies command type and channel-state GPU address',
 'Dependency +0x28 uses low47 prior timestamp and queue ID OR at bit40; overlap retained as native arithmetic',
 'Four 64-bit notification words at +0x128..+0x140',
 'Descriptor low50 bits cleared at +0x150/+0x158/+0x160/+0x168',
 'Conversion chooses event-machine +0x1458 for nonnegative signed timestamp, +0x1460 otherwise; index stride24'],
 qualification='Native call-free slices in emulated RAM. Both cached and actual uncached branch/helper paths; earlier external backing initialization, atomic pending-count publication, DMA/coherency and live firmware acceptance excluded. Arbitrary input masks characterize implementation rather than valid protocol values.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('512 cached + 512 uncached NOP body patches and 1024 timestamp conversions matched native instructions')
