#!/usr/bin/env python3
"""Native type-1 firmware notification mask dispatch; provider semantics synthetic."""
import argparse,hashlib,json,random,struct,importlib.util
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
BASE=0xfffffe0000000000;START=BASE+0x89a2e50;END=BASE+0x89a2f64;INVALID=BASE+0x89a3b98;WRONG=BASE+0x89a3c48
FW,A,STACK,MACHINE=0x200000,0x201000,0x223000,0x224000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.mem_map(BASE+0x89a2000,0x2000);m.mem_map(0x200000,0x30000);m.mem_write(START,read(START,END-START))
calls=[];timevalue=0

def hook(m,addr,size,user):
 if addr in (END,INVALID,WRONG):m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  if target==BASE+0xb928a20:calls.append(['time']);m.reg_write(c.UC_ARM64_REG_X0,timevalue)
  elif target==BASE+0xa7cf84c:
   assert m.reg_read(c.UC_ARM64_REG_X0)==MACHINE and m.reg_read(c.UC_ARM64_REG_X2)==0
   calls.append(['notify',m.reg_read(c.UC_ARM64_REG_X1)])
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_PC,addr+4)
spec=importlib.util.spec_from_file_location('receive13',Path(__file__).with_name('decode-receive13.py'));decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604023);counts=dict(valid=0,invalid_metadata=0,wrong_type=0,notifications=0)
for i in range(1024):
 masks=(1<<i,0) if i<64 else (0,1<<(i-64)) if i<128 else (0,0) if i%16==0 else ((1<<64)-1,(1<<64)-1) if i%16==1 else (rng.getrandbits(64),rng.getrandbits(64))
 event=rng.randbytes(72);event=bytearray(event);struct.pack_into('<I',event,0,1);struct.pack_into('<2Q',event,4,*masks);struct.pack_into('<H',event,0x14,i%24)
 if i>=1008:struct.pack_into('<H',event,0x14,[24,25,65535][i%3])
 if i>=1020:struct.pack_into('<I',event,0,2)
 fw=bytearray(rng.randbytes(0x1000));accel=bytearray(rng.randbytes(0x20000));stack=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',fw,0x298,A);struct.pack_into('<Q',accel,0x140,MACHINE);stack[0x50:0x98]=event;timevalue=rng.getrandbits(64)
 m.mem_write(FW,bytes(fw));m.mem_write(A,bytes(accel));m.mem_write(STACK,bytes(stack));m.reg_write(c.UC_ARM64_REG_X19,FW);m.reg_write(c.UC_ARM64_REG_W21,1);m.reg_write(c.UC_ARM64_REG_SP,STACK);calls.clear();
 try:m.emu_start(START,END,count=5000)
 except u.UcError as error:raise RuntimeError((i,hex(m.reg_read(c.UC_ARM64_REG_PC)),calls)) from error
 if struct.unpack_from('<I',event)[0]!=1:counts['wrong_type']+=1;assert m.reg_read(c.UC_ARM64_REG_PC)==WRONG;assert not calls
 elif struct.unpack_from('<H',event,0x14)[0]>=24:counts['invalid_metadata']+=1;assert m.reg_read(c.UC_ARM64_REG_PC)==INVALID;assert not calls
 else:
  counts['valid']+=1;indices=[j for j in range(128) if masks[j//64]&(1<<(j%64))];counts['notifications']+=len(indices)
  assert m.reg_read(c.UC_ARM64_REG_PC)==END and calls==[['time']]+[['notify',j] for j in indices]
  struct.pack_into('<Q',accel,0x1aec0,timevalue);old=struct.unpack_from('<I',stack,0x4c)[0];struct.pack_into('<I',stack,0x4c,old|int(bool(masks[0] or masks[1])))
 state=bytearray(48);struct.pack_into('<I',state,32,1);ring=bytearray(256*72);ring[:72]=event
 decoded=decoder.decode_ring(state,ring,1)['entries'][0]
 if struct.unpack_from('<I',event)[0]==1:
  expected_indices=[j for j in range(128) if masks[j//64]&(1<<(j%64))] if struct.unpack_from('<H',event,0x14)[0]<24 else []
  assert decoded['type1_observed_fields']['native_callback_indices']==expected_indices
 assert bytes(m.mem_read(A,len(accel)))==bytes(accel) and bytes(m.mem_read(FW,len(fw)))==bytes(fw) and bytes(m.mem_read(STACK,len(stack)))==bytes(stack)
# Actual native switch table binds type1 to this reviewed path.
offset=struct.unpack('<i',read(BASE+0x89a3d38+4,4))[0];assert BASE+0x89a2bdc+offset==START
a.output.write_text(json.dumps(dict(binary_sha256=sha,counts=counts,slice=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),switch=dict(table=hex(BASE+0x89a3d38),index=1,target=hex(START)),qualification='Native type1 mask consumer against independent set-bit enumeration; all128 one-hot positions, zero/dense/random masks and invalid guard branches. External timestamp/event-machine callback synthetic. Notification is not evidence of job completion or safe cleanup; provider semantics unavailable.'),indent=2)+'\n');print(counts)
