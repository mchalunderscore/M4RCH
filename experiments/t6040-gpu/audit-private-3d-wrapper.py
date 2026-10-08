#!/usr/bin/env python3
"""Resolve descriptor callbacks and emulate native 3D wrapper argument assembly."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c

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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0x100000,4096);m.mem_map(0x200000,0x40000)
rng=random.Random(604005);slots=[]
for name,base,specs in [('3D',0xfffffe0007eb7898,[(0x1e0,0xfffffe000895d5e4,0x210),(0x1e8,0xfffffe000895d5d8,0x218)]),('TA',0xfffffe0007eb7560,[(0x1e0,0xfffffe0008a20cb0,0x210),(0x1e8,0xfffffe0008a20ca4,0x218)]),('CL',0xfffffe0007ea4688,[(0x1b8,0xfffffe0008985c78,0x1c4),(0x1c0,0xfffffe0008985c6c,0x1cc)])]:
 for slot,target,offset in specs:
  encoded=struct.unpack('<Q',read(base+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
  code=read(target,8);m.mem_write(0x100000,code);m.ctl_remove_cache(0x100000,0x101000)
  for i in range(256):
   ptr=(rng.randrange(1<<42)<<4);m.reg_write(c.UC_ARM64_REG_X0,ptr);m.emu_start(0x100000,0x100008,count=10);assert m.reg_read(c.UC_ARM64_REG_X0)==ptr+offset
  slots.append(dict(class_name=name,slot=hex(slot),target=hex(target),descriptor_offset=hex(offset),cases=256))
start,end=0xfffffe00089db75c,0xfffffe00089db7cc
code=read(start,end-start);m.mem_write(0x100000,code);m.ctl_remove_cache(0x100000,0x101000)
for i in range(512):
 descriptor=bytearray(rng.randbytes(0x1000));direct=rng.getrandbits(64) if i&1 else 0;table_index=rng.getrandbits(32);fallback=rng.getrandbits(64)
 struct.pack_into('<Q',descriptor,0x168,direct);struct.pack_into('<Q',descriptor,0x10,0x210000);struct.pack_into('<I',descriptor,0x964,table_index)
 descriptor[0xc44]=3 if i%4==0 else rng.randrange(256)
 stack=rng.randbytes(0x70);m.mem_write(0x200000,bytes(descriptor));m.mem_write(0x210000+0xfd48+(table_index&127)*8,struct.pack('<Q',fallback));m.mem_write(0x230000,stack)
 for reg,value in [(c.UC_ARM64_REG_X19,0x200000),(c.UC_ARM64_REG_X20,0x220000),(c.UC_ARM64_REG_X21,0x221000),(c.UC_ARM64_REG_X22,0x222000),(c.UC_ARM64_REG_X23,0x200210),(c.UC_ARM64_REG_X0,0x200218),(c.UC_ARM64_REG_SP,0x230000)]:m.reg_write(reg,value)
 m.emu_start(0x100000,0x100000+len(code),count=100)
 expected=[0x220000,0x200210,0x200218,0x200820,0x200a98,direct or fallback,0x221000,0x230014]
 for j,value in enumerate(expected):assert m.reg_read(getattr(c,'UC_ARM64_REG_X'+str(j)))==value,(i,j)
 expected_stack=bytearray(stack);struct.pack_into('<Q',expected_stack,0,0x222000)
 expected_stack[8]=1 if descriptor[0xc44]==3 else descriptor[0x4c]&1;expected_stack[9]=descriptor[0xb48]&1
 assert bytes(m.mem_read(0x230000,0x70))==bytes(expected_stack)
 assert bytes(m.mem_read(0x200000,0x1000))==bytes(descriptor)
# Native SKSM caller builds a two-word payload, then a pointer/count wrapper.
caller_start,caller_end=0xfffffe000895bfc8,0xfffffe000895bfe4
caller_code=read(caller_start,caller_end-caller_start);m.mem_write(0x100000,caller_code);m.ctl_remove_cache(0x100000,0x101000);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for i in range(512):
 state=rng.getrandbits(64);work=rng.getrandbits(64);stack=rng.randbytes(0x100)
 m.mem_write(0x200080,struct.pack('<Q',state));m.mem_write(0x230000,stack)
 m.reg_write(c.UC_ARM64_REG_X19,0x200000);m.reg_write(c.UC_ARM64_REG_X25,work);m.reg_write(c.UC_ARM64_REG_SP,0x230000)
 m.emu_start(0x100000,0x100000+len(caller_code),count=50)
 expected=bytearray(stack);expected[0x80:0xa0]=bytes(32);struct.pack_into('<4Q',expected,0xa0,0x2300b0,2,work,state)
 assert bytes(m.mem_read(0x230000,0x100))==bytes(expected)
for slot,target in [(0x160,0xfffffe00089db874),(0x168,0xfffffe00089db63c),(0x170,0xfffffe00089db00c)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007eac548+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
report=dict(binary_sha256=sha,callback_cases=1536,wrapper_tail_cases=512,caller_payload_cases=512,caller_payload_range=[hex(caller_start),hex(caller_end)],caller_payload_sha256=hashlib.sha256(caller_code).hexdigest(),scheduler_3d_slot="0x168",descriptor_slots=slots,wrapper_range=[hex(start),hex(end)],wrapper_slice_sha256=hashlib.sha256(code).hexdigest(),
 argument_provenance={'x0':'scheduler','x1':'3D descriptor+0x210 event command','x2':'3D descriptor+0x218 event barrier','x3':'descriptor+0x820 RCE','x4':'descriptor+0xa98 aperture','x5':'descriptor+0x168 or table at *(descriptor+0x10)+0xfd48+(index&127)*8','x6':'original payload reference','x7':'stack+0x14 previously assembled QOS','stack0':'original notification-mask reference','stack8':'1 when descriptor byte c44 equals3, else descriptor byte4c lowbit','stack9':'descriptor byteb48 lowbit'},
 qualification='Matched vtable slots and native getters; call-free 3D wrapper tail only. Earlier external resource/QOS lookups, descriptor construction, payload identity, mapping/cache and live firmware acceptance excluded. Getter emulation stops before RET; no PAC bypass or external code executed.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1536 callback, 512 3D wrapper and 512 caller payload cases matched')
