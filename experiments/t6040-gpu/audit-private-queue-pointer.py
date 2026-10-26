#!/usr/bin/env python3
"""Offline native pointer-publication slice; optional tracking path excluded."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_queue_pointer import publish_pointer
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
start,end=0xfffffe0008981058,0xfffffe000898111c
assert read(0xfffffe00089810ac,4)==bytes.fromhex('bf3b03d5')
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(start&~4095,4096);m.mem_write(start,read(start,end-start));m.mem_map(0x200000,0x3000)
rng=random.Random(6040);cases=0;blocked=0
for capacity in [2,3,16,256]:
 for write in range(capacity):
  for full in [False,True]:
   next_write=(write+1)%capacity;consumer=next_write if full else write
   channel=bytearray(0x100);queue=bytearray(rng.randbytes(0x80));ring=rng.randbytes(capacity*8)
   struct.pack_into('<Q',channel,0x60,0x201000);struct.pack_into('<Q',channel,0x68,0x202000);struct.pack_into('<I',channel,0x54,capacity)
   for offset,value in [(0,consumer),(0x40,write),(0x60,capacity)]:struct.pack_into('<I',queue,offset,value)
   pointer=rng.getrandbits(64)
   m.mem_write(0x200000,bytes(channel));m.mem_write(0x201000,bytes(queue));m.mem_write(0x202000,ring)
   m.reg_write(c.UC_ARM64_REG_X0,0x200000);m.reg_write(c.UC_ARM64_REG_X1,pointer);m.reg_write(c.UC_ARM64_REG_X3,0)
   m.emu_start(start,end,count=100)
   if full:
    assert m.reg_read(c.UC_ARM64_REG_PC)!=end
    assert bytes(m.mem_read(0x201000,0x80))==bytes(queue)
    assert bytes(m.mem_read(0x202000,len(ring)))==ring
    try:publish_pointer(queue,ring,pointer)
    except BlockingIOError:pass
    else:raise AssertionError('Model did not detect full queue')
    blocked+=1
   else:
    assert m.reg_read(c.UC_ARM64_REG_PC)==end
    expected_queue,expected_ring=publish_pointer(queue,ring,pointer)
    assert bytes(m.mem_read(0x201000,0x80))==expected_queue
    assert bytes(m.mem_read(0x202000,len(ring)))==expected_ring
    cases+=1
report=dict(binary_sha256=sha,slice_range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),
 successful_cases=cases,full_queue_cases=blocked,capacities=[2,3,16,256],pointer_stride=8,
 queue_fields=dict(read='0x00',host_write='0x40',capacity='0x60'),barrier_before_write_index=True,
 qualification='Actual native call-free slice with x3=0. Every producer position tested, including wrap and full condition. Full native wait bounded by emulator instruction count; numeric model reports would-block. Optional x3 tracking path, submit doorbell, cache coherency and live GPU consumption not verified.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(cases,'publication cases;',blocked,'full-queue cases matched')
