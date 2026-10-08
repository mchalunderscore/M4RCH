#!/usr/bin/env python3
"""Common work dependency, RCE, QOS, notification, counter and publication audit."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_work_body import patch_work_body
from private_nop_body import convert_timestamp
from private_scheduler_publish import publish_nop
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(0xfffffe00089db000,4096);m.mem_map(0xfffffe00089ee000,4096);m.mem_map(0x200000,0x20000)
start,end=0xfffffe00089db370,0xfffffe00089db5dc
m.mem_write(start,read(start,0xfffffe00089db620-start));m.mem_write(0xfffffe00089ee94c,read(0xfffffe00089ee94c,0x70))
rng=random.Random(604004)
for i in range(1024):
 record=rng.randbytes(0x200);queue=bytearray(rng.randbytes(0x100));capacity=[1,2,3,16,256][i%5]
 timestamp=rng.getrandbits(64);initial=rng.getrandbits(64);qid=rng.getrandbits(32);cached=bool(i&1);previous=rng.getrandbits(64)
 n=i%9;entries=[];dep=bytearray(4+n*12);struct.pack_into('<I',dep,0,n)
 epochs={}
 for idx in range(24):
  epochs[idx]=(rng.getrandbits(64),rng.getrandbits(64))
  m.mem_write(0x20a000+0x1458+idx*24,struct.pack('<2Q',*epochs[idx]))
 for j in range(n):
  event=rng.getrandbits(32);idx=rng.randrange(24);epoch=epochs[idx][event>>31]
  entries.append((event,idx,epoch));struct.pack_into('<3I',dep,4+j*12,event,idx,rng.getrandbits(32))
 event=rng.getrandbits(32);idx=rng.randrange(24)
 m.mem_write(0x20c000,struct.pack('<2I',event,idx))
 if not cached:previous=(convert_timestamp(epochs[idx][event>>31],event,capacity,initial)-1)&((1<<64)-1)
 qos=[rng.getrandbits(32) for _ in range(3)];kind=rng.getrandbits(32);reglists=[(rng.getrandbits(64),rng.getrandbits(16)) for _ in range(4)]
 rce=bytearray(rng.randbytes(0x48));struct.pack_into('<I',rce,0,kind)
 for j,(address,count) in enumerate(reglists):struct.pack_into('<QH',rce,8+j*16,address,count)
 masks=[rng.getrandbits(64) for _ in range(4)];aux=rng.getrandbits(64)
 for off,val,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x44,max(0,capacity-1),'I'),(0x48,timestamp,'Q'),(0x68,0x209000,'Q'),(0x90,initial,'Q'),(0xa0,previous,'Q')]:struct.pack_into('<'+fmt,queue,off,val)
 queue[0x98]=(queue[0x98]&254)|cached
 m.mem_write(0x200000,record);m.mem_write(0x201000,bytes(queue));m.mem_write(0x202000,bytes(dep));m.mem_write(0x203000,struct.pack('<3I',*qos));m.mem_write(0x204000,bytes(rce));m.mem_write(0x205000,struct.pack('<4Q',*masks));m.mem_write(0x206018,struct.pack('<Q',0x20c000));m.mem_write(0x209140,struct.pack('<Q',0x20a000))
 for reg,val in [(c.UC_ARM64_REG_X21,0x200000),(c.UC_ARM64_REG_X19,0x201000),(c.UC_ARM64_REG_X25,0x202000),(c.UC_ARM64_REG_X23,0x203000),(c.UC_ARM64_REG_X22,0x204000),(c.UC_ARM64_REG_X27,0x205000),(c.UC_ARM64_REG_X20,aux),(c.UC_ARM64_REG_SP,0x206000)]:m.reg_write(reg,val)
 m.emu_start(start,end,count=1500)
 expected,counter=patch_work_body(record,timestamp,capacity,initial,qid,entries,previous,qos,kind,reglists,masks,aux)
 assert bytes(m.mem_read(0x200000,0x200))==expected,(i,'record')
 struct.pack_into('<Q',queue,0x48,counter);queue,overflow=publish_nop(queue,timestamp);assert not overflow
 assert bytes(m.mem_read(0x201000,0x100))==queue,(i,'queue')
 assert m.reg_read(c.UC_ARM64_REG_X0)==timestamp
report=dict(binary_sha256=sha,work_body_cases=1024,cached_cases=512,uncached_cases=512,dependency_counts=list(range(9)),
 instruction_range=[hex(start),hex(end)],extra_branch_range=['0xfffffe00089db5fc','0xfffffe00089db620'],helper_range=['0xfffffe00089ee94c','0xfffffe00089ee9bc'],
 slice_sha256=hashlib.sha256(read(start,0xfffffe00089db620-start)).hexdigest(),
 findings=['Explicit dependencies use 12-byte input stride, timestamp at entry0 and event index at entry4; third word not read in this slice',
 'Event index also supplies low7 queue ID bits at dependency bit40; implicit prior added after explicit dependencies',
 'QOS byte0 at bits32..39, u32+8 low5 at bits40..44, u32+4 low16 at bits48..63 of word20',
 'Four reglists encode address>>5 low38 and count low7 at bit43, preserve high14; bits38..42 cleared',
 'RCE kind low2 replaces whole byte148; auxiliary caller x5 stored at178'],
 qualification='Actual body, uncached helper and LSE publication run in single-thread emulated RAM. Earlier external zero/init, full-input allocation/protocol bounds, live memory coherency, capacity diagnostic path and real rendering workloads excluded. Tested dependency counts0..8, not asserted maximum.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 ordinary work bodies including dependencies, RCE/QOS and native publication matched')
