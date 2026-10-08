#!/usr/bin/env python3
"""Native call-free NOP header/counter models and method-slot checks."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_nop_header import patch_header,advance_timestamp
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
encoded=struct.unpack('<Q',read(0xfffffe0007eac548+16+0x148,8))[0]
assert 0xfffffe0007004000+(encoded&0xffffffff)==0xfffffe00089dc07c
# Confirm return-value load, stored counter update, and unmodified x0 before epilogue.
for address,word in [(0xfffffe00089dc198,0xf9402660),(0xfffffe00089dc1d0,0xf9002668),(0xfffffe000897f028,0xaa0003fb)]:
 assert struct.unpack('<I',read(address,4))[0]==word
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0x100000,4096);m.mem_map(0x200000,0x3000)
rng=random.Random(6040)
start,end=0xfffffe00089dc0c8,0xfffffe00089dc10c
code=read(start,end-start);m.mem_write(0x100000,code)
for i in range(1024):
 old=rng.getrandbits(64);timestamp=rng.getrandbits(64);queue=rng.getrandbits(32);priority=rng.getrandbits(32)
 m.mem_write(0x200000,struct.pack('<Q',old));m.mem_write(0x20100c,struct.pack('<I',queue));m.mem_write(0x20101c,struct.pack('<I',priority));m.mem_write(0x201048,struct.pack('<Q',timestamp))
 m.reg_write(c.UC_ARM64_REG_X21,0x200000);m.reg_write(c.UC_ARM64_REG_X19,0x201000)
 m.emu_start(0x100000,0x100000+len(code),count=100)
 assert struct.unpack('<Q',m.mem_read(0x200000,8))[0]==patch_header(old,timestamp,queue,priority)
start2,end2=0xfffffe00089dc198,0xfffffe00089dc1d4
code2=read(start2,end2-start2);m.mem_write(0x100000,code2);m.ctl_remove_cache(0x100000,0x101000)
n=0
for capacity in [1,2,3,16,256]:
 for index in range(capacity):
  for high in [0,0x1234560000000000,0xffffffffffffff00]:
   old=high|index
   m.mem_write(0x201048,struct.pack('<Q',old));m.mem_write(0x201010,struct.pack('<I',capacity));m.reg_write(c.UC_ARM64_REG_X19,0x201000)
   m.emu_start(0x100000,0x100000+len(code2),count=100)
   assert m.reg_read(c.UC_ARM64_REG_X0)==old
   assert struct.unpack('<Q',m.mem_read(0x201048,8))[0]==advance_timestamp(old,capacity)
   n+=1
report=dict(binary_sha256=sha,header_cases=1024,counter_cases=n,header_kind_bits=2,
 header_ranges=[[hex(start),hex(end)],[hex(start2),hex(end2)]],slice_hashes=[hashlib.sha256(code).hexdigest(),hashlib.sha256(code2).hexdigest()],
 nop_vtable_slot='0x148',nop_target='0xfffffe00089dc07c',return_value='Previous queue object +0x48 counter, not record address',
 qualification='Actual header/counter arithmetic slices only. Arbitrary-width inputs characterize masks/overlap, not valid protocol timestamps. Return links pinned; external conversion, allocation, full encoding, atomic pending-count increment and hardware execution excluded.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 header cases and',n,'counter cases matched; NOP return is prior counter')
