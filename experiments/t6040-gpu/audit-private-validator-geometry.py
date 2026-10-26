#!/usr/bin/env python3
"""Emulate reviewed, call-free native validator initialization in RAM."""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X19, UC_ARM64_REG_CPACR_EL1, UC_ARM64_REG_PC
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
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
u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
for address in [0xfffffe00089ad000,0xfffffe000712d000]:
 u.mem_map(address,4096);u.mem_write(address,read(address,4096))
host=0x200000;u.mem_map(host,0x2000)
values={0x298:0x333000,0x8c0:0x400000,0x8c8:0x500000,0x8d0:0x600000,0x8d8:0x700000,0x8e0:0x800000,0x8e8:0x900000,0x8f0:0xa00000,0x8f8:0xb00000}
for offset,value in values.items():u.mem_write(host+offset,struct.pack('<Q',value))
u.reg_write(UC_ARM64_REG_X19,host);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
u.emu_start(0xfffffe00089ad000,0xfffffe00089ad160,count=100)
assert u.reg_read(UC_ARM64_REG_PC)==0xfffffe00089ad160
validators=[]
for i in range(9):
 offset=0x5f0+i*48
 owner,state,ring,_,mask,capacity=struct.unpack('<QQQQQQ',u.mem_read(host+offset,48))
 assert (owner,state,ring,mask,capacity)==(values[0x298],values[0x8c8]+i*48,values[0x8e8]+i*0x4800,0x4,256)
 validators.append(dict(host_offset=hex(offset),state_resource_field='0x8c8',state_byte_offset=i*48,ring_resource_field='0x8e8',ring_byte_offset=i*0x4800,allowed_mask=hex(mask),capacity=capacity))
owner,state,ring,_,mask,capacity=struct.unpack('<QQQQQQ',u.mem_read(host+0x800,48))
assert (owner,state,ring,mask,capacity)==(values[0x298],values[0x8c0],values[0x8e0],0x2000ffd3,256)
result=dict(binary_sha256=sha,initialization_range=['0xfffffe00089ad000','0xfffffe00089ad160'],
 event=dict(host_offset='0x800',state_resource_field='0x8c0',mapped_state_field='0x900',main_pointer_offset='0x1c0',ring_resource_field='0x8e0',mapped_ring_field='0x920',main_ring_pointer_offset='0x1c8',capacity=256,allowed_mask=hex(mask)),
 nine_type2_validators=validators,qualification='Actual call-free initialization slice with synthetic resource pointers. Mapping fields/main offsets corroborated by existing receive-layout audit. Nine validators allow type 2 only; richer log semantics and live message production unresolved.')
a.output.write_text(json.dumps(result,indent=2)+'\n');print('Native setup verified: 9 type-2 validators and 1 general event validator')
