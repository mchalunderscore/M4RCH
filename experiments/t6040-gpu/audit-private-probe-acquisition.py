#!/usr/bin/env python3
"""Offline native probe mapping acquisition and pointer setup."""
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


for slot,target in [(0xb98,0xfffffe00089e9fa0),(0xb30,0xfffffe00089ea17c)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007eae388+16+slot,8))[0]
 assert 0xfffffe0007004000+(encoded&0xffffffff)==target

m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
start,end=0xfffffe00089a1bc4,0xfffffe00089a1edc
m.mem_map(start&~4095,4096);m.mem_write(start,read(start,end-start))
for page in [0xfffffe000c6e7000,0xfffffe000712d000,0xfffffe00089e9000,0xfffffe00089ea000]:m.mem_map(page,4096)
m.mem_write(0xfffffe000712d7c0,read(0xfffffe000712d7c0,8))
m.mem_map(0x200000,0x30000)
m.mem_write(0xfffffe00089e9fa0,read(0xfffffe00089e9fa0,12));m.mem_write(0xfffffe00089ea17c,read(0xfffffe00089ea17c,16))
accel=0x200000;avt=0x220000;mainmap=0x221000;fendermap=0x222000;mvt=0x223000;fvt=0x224000
m.mem_write(mainmap,struct.pack('<Q',mvt));m.mem_write(fendermap,struct.pack('<Q',fvt))
m.mem_write(mvt+0x138,struct.pack('<Q',0x225000));m.mem_write(fvt+0x138,struct.pack('<Q',0x225004));m.mem_write(fvt+0x148,struct.pack('<Q',0x225010))
m.mem_write(avt+0xb98,struct.pack('<Q',0xfffffe00089e9fa0));m.mem_write(avt+0xb30,struct.pack('<Q',0xfffffe00089ea17c))
service=0x226000;svt=0x227000;m.mem_write(service,struct.pack('<Q',svt));m.mem_write(svt+0x710,struct.pack('<Q',0x225014))
# Mapping object globals are filled by the executed native acquisition code.
events=[]
def hook(m,addr,size,data):
 if addr==0xfffffe00089e9fa0:events.append('offset')
 if addr==0xfffffe00089ea17c:events.append('physical(1)');assert m.reg_read(c.UC_ARM64_REG_W1)==1
 if 0x225000<=addr<=0x225014:
  obj=m.reg_read(c.UC_ARM64_REG_X0);arg=m.reg_read(c.UC_ARM64_REG_W1)
  if addr==0x225000:assert obj==mainmap;val=mainva;events.append('main.address')
  elif addr==0x225004:assert obj==fendermap;val=fenderva;events.append('fender.address')
  elif addr==0x225010:assert obj==fendermap;val=extent;events.append('fender.length')
  else:
   assert obj==service and m.reg_read(c.UC_ARM64_REG_W2)==0
   if arg==mainidx:val=mainmap;events.append('map.main')
   else:assert arg==fenderidx;val=fendermap;events.append('map.fender')
  m.reg_write(c.UC_ARM64_REG_X0,val);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 word=int.from_bytes(m.mem_read(addr,4),'little')
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif word&0xfffffc00==0xd73f0800:
  target=m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)));m.reg_write(c.UC_ARM64_REG_X30,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604045358)
for case in range(1024):
 mainva=0xffff000000000000+(rng.getrandbits(20)<<16);fenderva=0xffff100000000000+(rng.getrandbits(20)<<16)
 offset=0xd00000;physical=0x280000000+rng.randrange(0x10000000);extent=rng.randrange(1,0x100000)
 original=bytearray(rng.randbytes(0x20000));struct.pack_into('<Q',original,0,avt);m.mem_write(accel,bytes(original))
 globals_before=bytearray(rng.randbytes(4096));mainidx,fenderidx=((0,1) if case%2==0 else (1,2))
 struct.pack_into('<Q',globals_before,0x908,service);struct.pack_into('<Q',globals_before,0x920,physical)
 globals_before[0x914]=mainidx;globals_before[0x915]=fenderidx;globals_before[0x917]=1;globals_before[0x919]=5
 m.mem_write(0xfffffe000c6e7000,bytes(globals_before))
 m.reg_write(c.UC_ARM64_REG_X20,accel);m.reg_write(c.UC_ARM64_REG_X25,0xfffffe000c6e7908);m.reg_write(c.UC_ARM64_REG_X24,0xfffffe000c6e7000)
 events.clear();m.emu_start(start,end,count=500)
 assert m.reg_read(c.UC_ARM64_REG_PC)==end
 assert events==['map.main','map.fender','main.address','fender.address','offset','physical(1)','fender.length']
 expected=bytearray(original)
 for off,val in [(0x358,mainva),(0xf808,mainva),(0xf8e8,fenderva),(0xc778,physical+offset),(0xc980,offset)]:struct.pack_into('<Q',expected,off,val)
 expected[0xc770:0xc778]=read(0xfffffe000712d7c0,8)
 expected[0xc780:0xc978]=bytes(0x1f8)
 struct.pack_into('<II',expected,0xc978,extent,0)
 assert bytes(m.mem_read(accel,0x20000))==expected
 globals_expected=bytearray(globals_before);struct.pack_into('<QQ',globals_expected,0x938,mainmap,fendermap)
 assert bytes(m.mem_read(0xfffffe000c6e7000,4096))==globals_expected
report=dict(binary_sha256=sha,cases=1024,range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),descriptor_header=list(struct.unpack('<II',read(0xfffffe000712d7c0,8))),mapping_objects=['global c6e7938 -> accelerator358 and f808','global c6e7940 -> acceleratorf8e8'],fender_descriptor=dict(base='c770',physical='physical(1) + u32(offset)',extent='mapping.length truncated u32',logical_offset='u32(offset)'),qualification='Continuous native map acquisition and setup slice with native G16X offset and physical getters; synthetic service.map(index,0), mapping.address and length providers. Both register index pairs 0/1 and 1/2 tested. Entire accelerator and global page compared. PAC bypassed; flags choose direct mapping and skip optional provider enable calls. Physical global input is synthetic. Real provider implementations, earlier probe flags/count selection, final virtual11e8, hardware mapping and rendering not proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 continuous native map acquisition/setup cases passed')
