#!/usr/bin/env python3
"""Emulate three call-free native config-patch slices; callback results synthetic."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_scheduler_config import patch_config
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
descriptor_slots=[]
for name,base,target in [('CL',0xfffffe0007ea4688,0xfffffe0008985e70),('TA',0xfffffe0007eb7560,0xfffffe0008a2159c),('3D',0xfffffe0007eb7898,0xfffffe000895dc98)]:
 encoded=struct.unpack('<Q',read(base+16+0x188,8))[0]
 assert 0xfffffe0007004000+(encoded&0xffffffff)==target
 assert read(target+4,4)==bytes.fromhex('e01f8052')
 descriptor_slots.append(dict(class_name=name,slot='0x188',target=hex(target),method='getDataMaster',return_value=255))
header=struct.unpack('<Q',read(0xfffffe000712d720,8))[0];vector=read(0xfffffe000712d9b0,16)
assert header&0xffffffff==15
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for address in [0xfffffe0008987000,0xfffffe000712d000]:m.mem_map(address,4096);m.mem_write(address,read(address,4096))
m.mem_map(0x200000,0x5000);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
ranges=[(0xfffffe00089870a4,0xfffffe00089870d4),(0xfffffe0008987108,0xfffffe000898714c),(0xfffffe0008987188,0xfffffe00089871a0)]
rng=random.Random(6040)
for i in range(256):
 original=rng.randbytes(0x90);descriptor=bytearray(rng.randbytes(0x190));queue=bytearray(rng.randbytes(0x90))
 descriptor_id=struct.unpack_from('<I',descriptor,0x144)[0];queue_id=struct.unpack_from('<I',queue,0xc)[0];priority=struct.unpack_from('<I',queue,0x1c)[0];pair=struct.unpack_from('<QQ',queue,0x80)
 callbacks=[255 if i%16==0 else rng.getrandbits(32),rng.getrandbits(32)]
 m.mem_write(0x200000,original);m.mem_write(0x201000,bytes(descriptor));m.mem_write(0x202000,bytes(queue))
 for reg,value in [(c.UC_ARM64_REG_X0,0x201000),(c.UC_ARM64_REG_X1,0x200000),(c.UC_ARM64_REG_X2,0x202000),(c.UC_ARM64_REG_X19,0x200000),(c.UC_ARM64_REG_X20,0x201000),(c.UC_ARM64_REG_SP,0x204000)]:m.reg_write(reg,value)
 for k,(start,end) in enumerate(ranges):
  if k:m.reg_write(c.UC_ARM64_REG_X0,callbacks[k-1])
  m.emu_start(start,end,count=100);assert m.reg_read(c.UC_ARM64_REG_PC)==end
 expected=patch_config(original,header,vector,pair,queue_id,priority,descriptor_id,[descriptor[0x180],descriptor[0x181]],callbacks)
 assert bytes(m.mem_read(0x200000,len(original)))==expected
report=dict(binary_sha256=sha,model_cases=256,opcode=15,descriptor_slots=descriptor_slots,header_constant=hex(header),vector_constant_hex=vector.hex(),written_prefix_bytes=0x86,
 slices=[[hex(x),hex(y)] for x,y in ranges],slice_hashes=[hashlib.sha256(read(x,y-x)).hexdigest() for x,y in ranges],
 qualification='Three reviewed native patches with independently supplied callback returns; no service/PAC calls executed. Complete written 134-byte prefix matched and tail preserved. Uploaded 136-byte allocation consistent, not independently established here. Callback semantics, GPU mappings/lifetimes and live scheduler configuration unresolved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('256 configuration prefixes matched; header',hex(header),'vector',vector.hex())
