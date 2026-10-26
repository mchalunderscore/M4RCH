#!/usr/bin/env python3
"""Execute three complete SKSM transport-pool request functions in synthetic RAM."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
r=a.macho.read_bytes();sha=hashlib.sha256(r).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',r,16)[0]):
 cmd,size=struct.unpack_from('<II',r,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',r,pos+24))
 pos+=size
def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return r[off+addr-vm:off+addr-vm+n]
 raise ValueError('not file backed')
BASE=0xfffffe0000000000;FW,OUT,BITMAP,RES,OBJ,VT,STACK,STOP=0x200000,0x203000,0x204000,0x205000,0x206000,0x207000,0x20f000,0x20e000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(BASE+0x89b6000,4096);m.mem_map(0x200000,0x10000)
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
MAP=0x208000;m.mem_write(RES+0x50,struct.pack('<Q',OBJ));m.mem_write(OBJ,struct.pack('<Q',VT));m.mem_write(VT+0x158,struct.pack('<Q',MAP))
calls=[];lock=0;gpu=0
def hook(m,addr,size,user):
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4;assert target in (BASE+0xb7b13c4,BASE+0xb7b27c0)
  assert m.reg_read(regs[0])==lock;calls.append('lock' if target==BASE+0xb7b13c4 else 'unlock');m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  assert m.reg_read(regs[(word>>5)&31])==MAP and m.reg_read(regs[0])==OBJ
  calls.append('map');m.reg_write(regs[0],gpu);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604020);results=[]
for name,start,end,pool,field in [('final_fragment',0x89b687c,0x89b69a0,0x1518,0x270),('add_kicks',0x89b69a0,0x89b6ac4,0x1558,0x278),('entry_signal',0x89b6be8,0x89b6d0c,0x15d8,0x288)]:
 code=read(BASE+start,end-start);m.mem_write(BASE+start,code);stats={'success':0,'full':0,'absent':0}
 for i in range(1024):
  capacity=[0,1,2,3,16,256][i%6];cursor=rng.getrandbits(32);stride=rng.choice([24,32,64,88,0xfffffffc]);cpu=rng.getrandbits(64);gpu=rng.getrandbits(64);lock=0x209000
  bitmap=bytearray(rng.choice([0,1,255]) for _ in range(capacity));absent=i%17==0
  if i%4==0:bitmap[:]=bytes([1])*capacity
  fw=bytearray(rng.randbytes(0x1700));struct.pack_into('<Q',fw,pool+8,RES);struct.pack_into('<Q',fw,pool+0x10,cpu);struct.pack_into('<Q',fw,pool+0x18,0 if absent else BITMAP);struct.pack_into('<Q',fw,pool+0x20,stride);struct.pack_into('<I',fw,pool+0x28,capacity);struct.pack_into('<I',fw,pool+0x2c,cursor);struct.pack_into('<Q',fw,pool+0x38,lock)
  output=rng.randbytes(8);m.mem_write(FW,bytes(fw));m.mem_write(OUT,output)
  if bitmap:m.mem_write(BITMAP,bytes(bitmap))
  for reg in regs:m.reg_write(reg,0)
  m.reg_write(regs[0],FW);m.reg_write(regs[1],OUT);m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);calls.clear();m.emu_start(BASE+start,STOP,count=10000)
  assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
  selected=None
  if not absent:
   for j in range(capacity):
    slot=((cursor+j)&0xffffffff)%capacity
    if bitmap[slot]==0:selected=slot;break
  if selected is not None:
   stats['success']+=1;offset=(selected*stride)&0xffffffff;expected_return=(cpu+offset)&((1<<64)-1);expected_out=struct.pack('<Q',(gpu+offset)&((1<<64)-1));bitmap[selected]=1;struct.pack_into('<I',fw,pool+0x2c,(selected+1)%capacity);struct.pack_into('<I',fw,pool+0x30,int(expected_return==0));expected_calls=['lock','map','unlock']
  else:
   stats['absent' if absent else 'full']+=1;expected_return=0;expected_out=output;expected_calls=[] if absent else ['lock','unlock']
   if not absent:struct.pack_into('<I',fw,pool+0x30,1)
  assert m.reg_read(regs[0])==expected_return and bytes(m.mem_read(OUT,8))==expected_out
  assert bytes(m.mem_read(FW,len(fw)))==bytes(fw)
  if bitmap:assert bytes(m.mem_read(BITMAP,len(bitmap)))==bytes(bitmap)
  assert calls==expected_calls
 results.append(dict(name=name,start=hex(BASE+start),end=hex(BASE+end),pool=hex(pool),stride_source_firmware=hex(field),cases=1024,counts=stats,sha256=hashlib.sha256(code).hexdigest()))
bindings=[]
for call,cpu,gpu_field,target,init,source,dest in [(0x895e860,0x450,0x458,0x89b69a0,0x89ab4e0,0x278,0x1578),(0x895e9a4,0x480,0x488,0x89b687c,0x89ab4c0,0x270,0x1538),(0x895ea60,0x470,0x478,0x89b6be8,0x89ab51c,0x288,0x15f8)]:
 words=struct.unpack('<3I',read(BASE+call-4,12))
 assert words[0]==0x91000000|(gpu_field<<10)|(19<<5)|1
 branch=words[1];assert branch>>26==0b100101
 imm=branch&0x3ffffff
 if imm&(1<<25):imm-=1<<26
 assert call+imm*4==target
 assert words[2]==0xf9000000|((cpu//8)<<10)|(19<<5)
 initwords=struct.unpack('<2I',read(BASE+init,8))
 assert initwords==(0xf9400000|((source//8)<<10)|(19<<5)|9,0xf9000000|((dest//8)<<10)|(19<<5)|9)
 bindings.append(dict(call=hex(BASE+call),cpu_descriptor=hex(cpu),gpu_descriptor=hex(gpu_field),target=hex(BASE+target),initializer=hex(BASE+init),source=hex(source),stride=hex(dest),caller_sha256=hashlib.sha256(read(BASE+call-4,12)).hexdigest(),initializer_sha256=hashlib.sha256(read(BASE+init,8)).hexdigest()))
a.output.write_text(json.dumps(dict(binary_sha256=sha,results=results,bindings=bindings,qualification='Complete native request functions versus independent selection/address/bookkeeping model. Locks and resource slot158 map synthetic; PAC bypassed. Full/absent/zero capacity and cursor/offset wrapping covered. Fixture strides do not establish native default record sizes; release/concurrency/live GPU acceptance not tested.'),indent=2)+'\n');print(results)
