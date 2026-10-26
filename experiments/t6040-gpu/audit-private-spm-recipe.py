#!/usr/bin/env python3
"""Emulate the full SPM helper with native entry encoder and a synthetic map callback."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_spm_recipe import spm_entries,append_spm
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size

def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('address not file-backed')
start,end=0xfffffe00089e1df4,0xfffffe00089e2948
encode=0xfffffe00089df714
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(start&~4095,0x2000);m.mem_write(start,read(start,end-start))
m.mem_map(encode&~4095,4096);m.mem_write(encode,read(encode,0x28))
m.mem_map(0x200000,0x20000)
A,C,D,E,B,V,R1,R2,R3,RV=0x200000,0x202000,0x205000,0x207000,0x208000,0x209000,0x20a000,0x20b000,0x20c000,0x20d000
STOP=0x21f000;STACK=0x21e000
m.mem_write(V,struct.pack('<Q',encode));m.mem_write(RV+0x158,struct.pack('<Q',0x210000))
trace=[];mapped=0;callback_count=0;seen=set()
xregs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)]

def hook(m,address,size,user):
 global callback_count
 seen.add(address)
 if address==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd65f0fff: # retab: authenticate excluded, return to unsigned fixture LR
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  if address==0xfffffe00089e1edc:
   assert m.reg_read(c.UC_ARM64_REG_X0)==R3
   assert m.reg_read(xregs[(word>>5)&31])==0x210000
   callback_count+=1;m.reg_write(c.UC_ARM64_REG_X0,mapped);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
  target=m.reg_read(xregs[(word>>5)&31]);assert target==encode,(hex(address),hex(target))
  trace.append(tuple(m.reg_read(r) for r in [c.UC_ARM64_REG_W2,c.UC_ARM64_REG_W3,c.UC_ARM64_REG_X4]))
  m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,encode)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604008);hist={};examples={};cases=1024
for i in range(cases):
 accel=bytearray(rng.randbytes(0x1000));command=rng.randbytes(0x3000);descriptor=bytearray(rng.randbytes(0x1000));backing=bytearray(rng.randbytes(0x800))
 phase=i%4;enabled=(i//4)%2;special=(i//8)%2
 descriptor[0x897]=(descriptor[0x897]&~1)|special
 for off in (0x4e0,0x678,0x688,0x690,0x6f8,0x720,0x668,0x680):
  if rng.randrange(2):struct.pack_into('<Q',descriptor,off,0)
 struct.pack_into('<Q',descriptor,0xb90,R1)
 m.mem_write(R1+0x30,struct.pack('<Q',R2));m.mem_write(R2+0x58,struct.pack('<Q',R3));m.mem_write(R3,struct.pack('<Q',RV))
 struct.pack_into('<HH',backing,0x708,rng.randrange(0,16),12*rng.randrange(0,8))
 mapped=rng.getrandbits(64);trace.clear();callback_count=0
 expected=spm_entries(accel,command,descriptor,phase,enabled,mapped);expected_backing=append_spm(backing,expected)
 for addr,data in [(A,bytes(accel)),(C,command),(D,bytes(descriptor)),(E,struct.pack('<QQ',V,B)),(B,bytes(backing))]:m.mem_write(addr,data)
 for reg in xregs:m.reg_write(reg,0)
 for reg,value in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_X3,E),(c.UC_ARM64_REG_X4,phase),(c.UC_ARM64_REG_X5,enabled),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,value)
 m.emu_start(start,STOP,count=5000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP,'instruction budget exhausted'
 assert trace==expected,(i,phase,enabled,special,trace,expected)
 assert bytes(m.mem_read(B,len(backing)))==expected_backing,(i,'backing mismatch')
 assert callback_count==int(bool(enabled and phase!=1))
 for addr,data in [(A,bytes(accel)),(C,command),(D,bytes(descriptor)),(E,struct.pack('<QQ',V,B))]:assert bytes(m.mem_read(addr,len(data)))==data
 key=f'phase{phase}/enabled{enabled}/special{special}'
 hist.setdefault(key,set()).add(len(trace));examples.setdefault(key,[dict(register=hex(r),flag=f,value=hex(v)) for r,f,v in trace])
report=dict(binary_sha256=sha,cases=cases,range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),entry_encoder_sha256=hashlib.sha256(read(encode,0x28)).hexdigest(),entry_counts={k:sorted(v) for k,v in hist.items()},examples=examples,visited_instruction_count=len(seen),
 qualification='Whole SPM helper and native entry encoder executed in emulated RAM. PAC authentication bypassed for unsigned fixture pointers. Exactly one external mapping callback returns a synthetic address; its implementation, map attributes, descriptor construction, register semantics, override stage and live firmware/GPU acceptance are not qualified.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(cases,'full SPM recipes matched; entry counts',sorted(set(n for vals in hist.values() for n in vals)))
