#!/usr/bin/env python3
"""Native 3D command pool selection and mapped-address/bookkeeping slices."""
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(0xfffffe00089a6000,4096);m.mem_map(0x200000,0x10000)
rng=random.Random(604006)
start,end=0xfffffe00089a6658,0xfffffe00089a66a4
m.mem_write(start,read(start,0xfffffe00089a6778-start))
full_stop=0xfffffe00089a6768
m.hook_add(u.UC_HOOK_CODE,lambda uc,addr,size,user:uc.emu_stop() if addr==full_stop else None)
found_cases=full_cases=0
for i in range(1024):
 capacity=[1,2,3,16,256][i%5];cursor=rng.getrandbits(32);slots=bytearray(rng.choice([0,1,255]) for _ in range(capacity))
 if i%4==0:slots[:]=bytes([1])*capacity
 expected=None
 for n in range(capacity):
  index=((cursor+n)&0xffffffff)%capacity
  if slots[index]==0:expected=index;break
 fw=bytearray(rng.randbytes(0x1400));struct.pack_into('<Q',fw,0x1330,0x202000);struct.pack_into('<I',fw,0x1340,capacity);struct.pack_into('<I',fw,0x1344,cursor)
 m.mem_write(0x200000,bytes(fw));m.mem_write(0x202000,bytes(slots));m.reg_write(c.UC_ARM64_REG_X19,0x200000);m.reg_write(c.UC_ARM64_REG_X20,0x203000)
 m.emu_start(start,end,count=capacity*20+100)
 assert bytes(m.mem_read(0x200000,0x1400))==bytes(fw);assert bytes(m.mem_read(0x202000,capacity))==bytes(slots)
 if expected is None:
  assert m.reg_read(c.UC_ARM64_REG_PC)==full_stop;assert m.reg_read(c.UC_ARM64_REG_X20)==0;full_cases+=1;continue
 found_cases+=1;assert m.reg_read(c.UC_ARM64_REG_W22)==expected;assert m.reg_read(c.UC_ARM64_REG_PC)==end
 stride=rng.getrandbits(32);offset=(expected*stride)&0xffffffff;cpu=rng.getrandbits(64);map50=rng.getrandbits(64);map58=rng.getrandbits(64)
 struct.pack_into('<Q',fw,0x1328,cpu);m.mem_write(0x200000,bytes(fw))
 m.reg_write(c.UC_ARM64_REG_X23,offset);m.reg_write(c.UC_ARM64_REG_X21,0x203008);m.reg_write(c.UC_ARM64_REG_X0,map50)
 m.emu_start(0xfffffe00089a66d8,0xfffffe00089a66e0,count=10)
 m.reg_write(c.UC_ARM64_REG_X0,map58);m.reg_write(c.UC_ARM64_REG_X20,0x203000)
 m.emu_start(0xfffffe00089a6720,full_stop,count=100)
 assert struct.unpack('<2Q',m.mem_read(0x203000,16))==((map58+offset)&((1<<64)-1),(map50+offset)&((1<<64)-1))
 assert m.reg_read(c.UC_ARM64_REG_X20)==(cpu+offset)&((1<<64)-1)
 struct.pack_into('<I',fw,0x1344,(expected+1)%capacity);slots[expected]+=1
 assert bytes(m.mem_read(0x200000,0x1400))==bytes(fw);assert bytes(m.mem_read(0x202000,capacity))==bytes(slots)
# Bind the descriptor's actual pool callbacks, rather than infer by shared offsets.
bindings=[]
base=0xfffffe0007ea7860
for slot,target,name in [(0x2a0,0xfffffe00089a6624,'3D'),(0x2a8,0xfffffe00089a64ac,'FastBlit')]:
 encoded=struct.unpack('<Q',read(base+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
 bindings.append(dict(vtable=hex(base),slot=hex(slot),target=hex(target),pool=name))
# Page-rounded backing size and capacity are qualified separately from mapping calls.
m.mem_map(0x100000,4096)
round_start,round_end=0xfffffe00089abe58,0xfffffe00089abe78
round_code=read(round_start,round_end-round_start);capacity_code=read(0xfffffe00089ac0c0,12)
for i in range(512):
 requested=rng.randrange(1,501);stride=rng.randrange(1,0x2401);shift=[12,14,16][i%3]
 m.mem_write(0x100000,round_code);m.ctl_remove_cache(0x100000,0x101000)
 m.reg_write(c.UC_ARM64_REG_X21,requested);m.reg_write(c.UC_ARM64_REG_X23,stride);m.reg_write(c.UC_ARM64_REG_W24,shift)
 m.emu_start(0x100000,0x100000+len(round_code),count=30)
 size=((requested*stride)+(1<<shift)-1)&- (1<<shift)
 assert m.reg_read(c.UC_ARM64_REG_X21)==size
 m.mem_write(0x200020,struct.pack('<Q',stride));m.reg_write(c.UC_ARM64_REG_X19,0x200000)
 m.mem_write(0x100000,capacity_code);m.ctl_remove_cache(0x100000,0x101000);m.emu_start(0x100000,0x10000c,count=20)
 assert struct.unpack('<I',m.mem_read(0x200028,4))[0]==size//stride
for slot,target in [(0x2a0,0xfffffe00089a6624),(0x2a8,0xfffffe00089a64ac)]:
 base=0xfffffe0007ea8668;encoded=struct.unpack('<Q',read(base+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
 bindings.append(dict(vtable=hex(base),slot=hex(slot),target=hex(target),pool='3D' if slot==0x2a0 else 'FastBlit'))
report=dict(binary_sha256=sha,selection_cases=1024,backing_geometry_cases=512,geometry_ranges=[[hex(round_start),hex(round_end)],["0xfffffe00089ac0c0","0xfffffe00089ac0cc"]],geometry_slice_sha256=[hashlib.sha256(round_code).hexdigest(),hashlib.sha256(capacity_code).hexdigest()],found_cases=found_cases,full_cases=full_cases,address_bookkeeping_cases=found_cases,bindings=bindings,
 selection_range=[hex(start),hex(end)],patch_ranges=[['0xfffffe00089a66d8','0xfffffe00089a66e0'],['0xfffffe00089a6720','0xfffffe00089a6768']],
 code_sha256=hashlib.sha256(read(start,0xfffffe00089a6778-start)).hexdigest(),
 findings=['Pool bitmap +1330, capacity1340, scan cursor1344, stride1338, CPU base1328, resource1320',
 'Return CPU base+slot*stride; second output resource50 map+offset; first output resource58 map+offset',
 '3D descriptor438 CPU,440 resource58 address,448 resource50 address; FastBlit420/428/430'],
 qualification='Native selection and post-callback store/bookkeeping slices only. External lock and mapping getters excluded; mapping return values supplied independently, attributes unqualified. Allocation rounding/capacity qualified for supplied stride/page shift; live stride initialization, release and live firmware execution not established.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 selections,',found_cases,'address patches and 512 backing-geometry cases matched')
