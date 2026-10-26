#!/usr/bin/env python3
"""Audit the native 3D completion pending-counter slice, not completion delivery."""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
r=a.macho.read_bytes();sha=hashlib.sha256(r).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',r,16)[0]):
 cmd,size=struct.unpack_from('<II',r,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',r,pos+24))
 pos+=size

def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return r[off+addr-vm:off+addr-vm+n]
 raise ValueError('not file backed')
BASE=0xfffffe0000000000;START=BASE+0x895e1ac;END=BASE+0x895e1f8;DIAG=BASE+0x895e324
PUB=BASE+0x89db5c0;PUBEND=BASE+0x89db5c8
D,A,Q=0x200000,0x202000,0x220000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(BASE+0x895e000,0x1000);m.mem_map(BASE+0x89db000,0x1000);m.mem_map(D,0x50000)
m.mem_write(START,read(START,END-START));m.mem_write(PUB,read(PUB,PUBEND-PUB))
assert read(BASE+0x895e1f0,4)==bytes.fromhex('2801e8b8')
assert read(BASE+0x89db5c4,4)==bytes.fromhex('2901e8b8')

def hook(m,addr,size,user):
 if addr in (END,DIAG,PUBEND):m.emu_stop()
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604024);counts=dict(zero_release=0,valid_release=0,old_zero_diagnostic=0,underflow_characterization=0,roundtrips=0,native_publication_atomics=0)

def run(index,pending,released,roundtrip=False):
 descriptor=bytearray(rng.randbytes(0x1000));accel=bytearray(rng.randbytes(0x12000));queues=bytearray(rng.randbytes(32*0x1000))
 struct.pack_into('<Q',descriptor,0x10,A);struct.pack_into('<I',descriptor,0x964,index);struct.pack_into('<I',descriptor,0x2dc,released)
 for j in range(32):struct.pack_into('<Q',accel,0xf938+j*8,Q+j*0x1000)
 offset=index*0x1000+0x44;struct.pack_into('<I',queues,offset,pending)
 m.mem_write(D,bytes(descriptor));m.mem_write(A,bytes(accel));m.mem_write(Q,bytes(queues))
 if roundtrip:
  for _ in range(released):
   m.reg_write(c.UC_ARM64_REG_X19,Q+index*0x1000);m.reg_write(c.UC_ARM64_REG_W8,1)
   m.emu_start(PUB,PUBEND,count=10);assert m.reg_read(c.UC_ARM64_REG_PC)==PUBEND
  counts['native_publication_atomics']+=released
  pending=(pending+released)&0xffffffff
 m.reg_write(c.UC_ARM64_REG_X19,D);m.emu_start(START,END,count=64)
 expected_pc=DIAG if released and pending==0 else END
 assert m.reg_read(c.UC_ARM64_REG_PC)==expected_pc
 assert m.reg_read(c.UC_ARM64_REG_X20)==Q+index*0x1000
 if released:assert m.reg_read(c.UC_ARM64_REG_W8)==pending
 struct.pack_into('<I',descriptor,0x144,0xffffffff)
 struct.pack_into('<I',queues,offset,(pending-released)&0xffffffff)
 assert bytes(m.mem_read(D,len(descriptor)))==bytes(descriptor)
 assert bytes(m.mem_read(A,len(accel)))==bytes(accel)
 assert bytes(m.mem_read(Q,len(queues)))==bytes(queues)
 if roundtrip:counts['roundtrips']+=1
 elif not released:counts['zero_release']+=1
 elif pending==0:counts['old_zero_diagnostic']+=1
 elif pending<released:counts['underflow_characterization']+=1
 else:counts['valid_release']+=1

for i in range(2048):
 mode=i%8
 if mode==0:pending,released=rng.getrandbits(32),0
 elif mode==1:pending,released=0,1+rng.randrange(0xffffffff)
 elif mode==2:pending=rng.randrange(1,65536);released=pending+1+rng.randrange(65536)
 elif mode==3:pending=released=rng.randrange(1,0x100000000)
 else:pending=rng.randrange(1,0x100000000);released=rng.randrange(1,pending+1)
 run(i%32,pending,released)
for i in range(128):run(i%32,rng.randrange(65536),1+i%32,True)
a.output.write_text(json.dumps(dict(binary_sha256=sha,counts=counts,slices=[dict(start=hex(s),end=hex(e),sha256=hashlib.sha256(read(s,e-s)).hexdigest()) for s,e in [(START,END),(PUB,PUBEND)]],qualification='Native queue selection/status invalidation and LDADDAL decrement, full synthetic object preservation; zero old-count diagnostic entry only. Roundtrips execute isolated native publish atomic plus release slice, not full submit/complete. No firmware notification routing, concurrency, DMA, fences or live job retirement proved.'),indent=2)+'\n')
print(counts)
