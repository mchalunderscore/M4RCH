#!/usr/bin/env python3
"""Qualify native G16 RCE entries and four-phase descriptor metadata."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_rce_entry import encode_entry,decode_entry,rce_metadata
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0x100000,4096);m.mem_map(0x200000,0x10000);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
rng=random.Random(604007)
encode_start,encode_end=0xfffffe00089df714,0xfffffe00089df738
decode_start,decode_end=0xfffffe00089df6ec,0xfffffe00089df710
for mode,start,end in [('encode',encode_start,encode_end),('decode',decode_start,decode_end)]:
 code=read(start,end-start);m.mem_write(0x100000,code);m.ctl_remove_cache(0x100000,0x101000)
 for i in range(1024):
  entry=rng.randbytes(12);reg=rng.getrandbits(32);flag=rng.getrandbits(32);value=rng.getrandbits(64)
  m.mem_write(0x200000,entry);m.reg_write(c.UC_ARM64_REG_X1,0x200000)
  if mode=='encode':
   m.reg_write(c.UC_ARM64_REG_W2,reg);m.reg_write(c.UC_ARM64_REG_W3,flag);m.reg_write(c.UC_ARM64_REG_X4,value)
   m.emu_start(0x100000,0x100000+len(code),count=40);assert bytes(m.mem_read(0x200000,12))==encode_entry(entry,reg,flag,value)
  else:
   for register,address in [(c.UC_ARM64_REG_X2,0x201000),(c.UC_ARM64_REG_X3,0x201010),(c.UC_ARM64_REG_X4,0x201020)]:m.reg_write(register,address)
   m.emu_start(0x100000,0x100000+len(code),count=40)
   actual=(struct.unpack('<I',m.mem_read(0x201000,4))[0],m.mem_read(0x201010,1)[0],struct.unpack('<Q',m.mem_read(0x201020,8))[0]);assert actual==decode_entry(entry)
   assert bytes(m.mem_read(0x200000,12))==entry
# Original addresses required for ADRP constant at final metadata patch.
m.mem_map(0xfffffe00089e1000,4096);m.mem_map(0xfffffe000712d000,4096)
start,end=0xfffffe00089e1d74,0xfffffe00089e1dd4
code=read(start,end-start);m.mem_write(start,code);m.mem_write(0xfffffe000712d000,read(0xfffffe000712d000,4096))
constant=struct.unpack('<Q',read(0xfffffe000712d7d0,8))[0]
for i in range(512):
 descriptor=rng.randbytes(0x1000);command=rng.randbytes(0x3000)
 m.mem_write(0x200000,descriptor);m.mem_write(0x202000,command);m.reg_write(c.UC_ARM64_REG_X19,0x200000);m.reg_write(c.UC_ARM64_REG_X20,0x202000)
 m.emu_start(start,end,count=100);assert bytes(m.mem_read(0x200000,0x1000))==rce_metadata(descriptor,command,constant)
 assert bytes(m.mem_read(0x202000,0x3000))==command
phase_start,phase_end=0xfffffe00089df800,0xfffffe00089df824
phase_code=read(phase_start,phase_end-phase_start);m.mem_write(0x100000,phase_code);m.ctl_remove_cache(0x100000,0x101000)
for i in range(512):
 descriptor=rng.randbytes(0x1000);command=bytearray(rng.randbytes(0x3000));stack=bytearray(rng.randbytes(0x100));phase=i%4;offset=phase*0x720
 gpu=struct.unpack_from('<Q',descriptor,0x440)[0];vtable=struct.unpack_from('<Q',stack,0x48)[0]
 m.mem_write(0x200000,descriptor);m.mem_write(0x202000,bytes(command));m.mem_write(0x208000,bytes(stack))
 for reg,value in [(c.UC_ARM64_REG_X19,0x200000),(c.UC_ARM64_REG_X20,0x202000),(c.UC_ARM64_REG_X28,offset),(c.UC_ARM64_REG_SP,0x208000)]:m.reg_write(reg,value)
 m.emu_start(0x100000,0x100000+len(phase_code),count=40)
 struct.pack_into('<I',command,offset+0x7a8,0);struct.pack_into('<Q',command,offset+0x7a0,(gpu+offset+0xa0)&((1<<64)-1));struct.pack_into('<2Q',stack,0x50,vtable,0x202000+offset+0xa0)
 assert bytes(m.mem_read(0x202000,0x3000))==bytes(command);assert bytes(m.mem_read(0x208000,0x100))==bytes(stack);assert bytes(m.mem_read(0x200000,0x1000))==descriptor
bindings=[]
for slot,target in [(0,encode_start),(8,decode_start)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007ead470+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
 bindings.append(dict(slot=slot,target=hex(target)))
report=dict(binary_sha256=sha,entry_encode_cases=1024,entry_decode_cases=1024,metadata_cases=512,phase_setup_cases=512,phase_setup_range=[hex(phase_start),hex(phase_end)],phase_setup_sha256=hashlib.sha256(phase_code).hexdigest(),bindings=bindings,metadata_constant=hex(constant),
 ranges=[[hex(encode_start),hex(encode_end)],[hex(decode_start),hex(decode_end)],[hex(start),hex(end)]],slice_hashes=[hashlib.sha256(read(x,y-x)).hexdigest() for x,y in [(encode_start,encode_end),(decode_start,decode_end),(start,end)]],
 findings=['12-byte entry: header=(old&fffc0006)|(register&3fff8)|(flag&1); u64 value unaligned at4',
 'Descriptor RCE metadata820, four GPU addresses828/838/848/858 and counts830/840/850/860',
 'Source addresses command7a0+j*720; phase0 countcommand80, other counts7a8+j*720'],
 qualification='Native encoder/decoder and final four-phase metadata patch only. Full register recipe, data backing mapping, topology-dependent values, append/override services and live acceptance excluded. Internal generator ABI interpreted from actual wrappers, not nominal mangled signature.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 encodes +1024 decodes +512 metadata +512 phase setup cases matched; header',hex(constant))
