#!/usr/bin/env python3
"""Audit complete native 3D completion scratch-value encoding, offline only."""
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
BASE=0xfffffe0000000000;START=BASE+0x895ee3c;END=BASE+0x895ef28
PAYLOAD=BASE+0x89d5cf0;VT=BASE+0x7eaa8f0;STOP=0x24f000
D,A,CH,Q,OWNER,STATUS,STACK=0x200000,0x202000,0x214000,0x216000,0x236000,0x237000,0x24e000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
for addr,n in [(BASE+0x895e000,0x1000),(BASE+0x89d5000,0x1000),(BASE+0x7eaa000,0x2000),(D,0x50000)]:m.mem_map(addr,n)
m.mem_write(START,read(START,END-START));m.mem_write(PAYLOAD,read(PAYLOAD,12))
encoded=struct.unpack('<Q',read(VT+0x220,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==PAYLOAD
m.mem_write(VT+0x220,struct.pack('<Q',PAYLOAD))
assert read(BASE+0x8998c2c,4)==bytes.fromhex('207701f9')
assert read(BASE+0x895eed0,4)==bytes.fromhex('29fddfc8')
calls=[]
def hook(m,addr,size,user):
 if addr==STOP:m.emu_stop();return
 if addr==PAYLOAD:calls.append('native_payload')
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800:m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif word&0xfffffc00==0xd73f0800:
  target=m.reg_read(c.UC_ARM64_REG_X0+((word>>5)&31));assert target==PAYLOAD
  m.reg_write(c.UC_ARM64_REG_X30,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target)
 elif word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30))
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604025);counts=dict(cases=0,positive_bank=0,negative_bank=0,zero_capacity_characterization=0)
MASK=(1<<64)-1
for i in range(4096):
 index=i%32;cap=[1,2,16,255,256,512,0,65535][i%8]
 arg=[0,1,255,256,0x7fffffff,0x80000000,0xffffffff,rng.getrandbits(32)][i//8%8]
 counters=[0,1,0xffffff,0x1000000,(1<<40)-1,rng.getrandbits(64)]
 counter=counters[i%6];previous=rng.getrandbits(64);payload=i%256
 descriptor=bytearray(rng.randbytes(0x1000));accel=bytearray(rng.randbytes(0x12000));channel=bytearray(rng.randbytes(0x1000));queues=bytearray(rng.randbytes(0x20000));owner=bytearray(rng.randbytes(0x1000));status=bytearray(rng.randbytes(0x4000))
 struct.pack_into('<Q',descriptor,0x10,A);struct.pack_into('<Q',channel,0,VT);struct.pack_into('<I',channel,0x18,index);channel[0x204]=payload
 for j in range(32):struct.pack_into('<Q',accel,0xf938+j*8,Q+j*0x1000)
 off=index*0x1000;struct.pack_into('<Q',queues,off+0x68,OWNER);struct.pack_into('<I',queues,off+0x10,cap);struct.pack_into('<Q',queues,off+0x90,previous)
 struct.pack_into('<Q',owner,0x140,STATUS);bank=0x1458 if arg<0x80000000 else 0x1460
 struct.pack_into('<Q',status,bank+index*24,counter)
 objects=[(D,descriptor),(A,accel),(CH,channel),(Q,queues),(OWNER,owner),(STATUS,status)]
 for addr,obj in objects:m.mem_write(addr,bytes(obj))
 m.reg_write(c.UC_ARM64_REG_X0,D);m.reg_write(c.UC_ARM64_REG_X1,CH);m.reg_write(c.UC_ARM64_REG_W2,arg);m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_X30,STOP);calls.clear()
 m.emu_start(START,STOP,count=256)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and calls==['native_payload']
 delta=(((counter<<24)|(arg>>8))-1)&MASK
 quotient,remainder=divmod(delta,cap) if cap else (0,delta)
 total=(previous&255)+(remainder&255)
 wraps,position=divmod(total,cap) if cap else (0,total)
 generation=((previous>>8)+(quotient&0xffffffff)+wraps)&0xffffffff
 expected=(position&255)|(generation<<8)|(payload<<40)
 assert m.reg_read(c.UC_ARM64_REG_X0)==expected,(i,hex(m.reg_read(c.UC_ARM64_REG_X0)),hex(expected))
 for addr,obj in objects:assert bytes(m.mem_read(addr,len(obj)))==bytes(obj)
 counts['cases']+=1;counts['positive_bank' if bank==0x1458 else 'negative_bank']+=1
 counts['zero_capacity_characterization']+=int(cap==0)
a.output.write_text(json.dumps(dict(binary_sha256=sha,counts=counts,function=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),caller_store=dict(address=hex(BASE+0x8998c2c),sha256=hashlib.sha256(read(BASE+0x8998c2c,4)).hexdigest()),native_payload=dict(vtable=hex(VT-16),slot='0x220',target=hex(PAYLOAD),sha256=hashlib.sha256(read(PAYLOAD,12)).hexdigest()),qualification='Complete native method including G16_SKSM payload getter executes against independent bit/arithmetic model. PAC bypassed, objects synthetic, LDAR executes in RAM. Invalid zero capacities and wide counters characterized without claiming valid hardware inputs. No firmware completion delivery/fence/live rendering proved.'),indent=2)+'\n');print(counts)
