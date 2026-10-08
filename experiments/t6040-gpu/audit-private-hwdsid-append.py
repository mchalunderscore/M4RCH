#!/usr/bin/env python3
"""Qualify bounded HWDSID producer appends and 3D caller argument provenance."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
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
 raise ValueError('not file backed')
BASE=0xfffffe0000000000
RANGES=[(BASE+0x89945d0,BASE+0x8994618),(BASE+0x8994658,BASE+0x89946a8),
 (BASE+0x8995768,BASE+0x899577c),(BASE+0x8998cc8,BASE+0x8998cdc)]
STOPS={BASE+0x89942d8,BASE+0x89942cc,RANGES[0][1],RANGES[1][1]}
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20);m.mem_map(BASE+0x895d000,4096);m.mem_map(BASE+0x8994000,0x2000);m.mem_map(BASE+0x8998000,4096);m.mem_map(0x200000,0x20000)
for start,end in RANGES:m.mem_write(start,read(start,end-start))
D,A,STACK,FRAME,Q,DESC=0x200000,0x202000,0x210000,0x211000,0x212000,0x214000
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];seen=set()
def hook(m,addr,size,user):
 seen.add(addr)
 if addr in STOPS:m.emu_stop()
m.hook_add(u.UC_HOOK_CODE,hook)
def run(which,initial):
 for reg in regs:m.reg_write(reg,0)
 for i,value in initial.items():m.reg_write(regs[i],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_X29,FRAME)
 start,end=RANGES[which];m.emu_start(start,end,count=100)
 return m.reg_read(c.UC_ARM64_REG_PC)
def append(data,address,length,hwdsid,scale,enable):
 count=struct.unpack_from('<I',data,0x100)[0];out=bytearray(data)
 if count>15:return bytes(out),False
 off=count*16;struct.pack_into('<Q',out,off,address);struct.pack_into('<I',out,off+8,length);out[off+12]=hwdsid&255
 struct.pack_into('<H',out,off+14,scale&0xffff if enable&1 else 0);struct.pack_into('<I',out,0x100,count+1)
 return bytes(out),True
rng=random.Random(604017);counts={};examples=[]
for i in range(1024):
 data=bytearray(rng.randbytes(0x180));count=[i%17,16,17,0xffffffff][i%4];struct.pack_into('<I',data,0x100,count)
 address=rng.getrandbits(64);length=rng.getrandbits(32);scale=rng.getrandbits(32);enable=rng.getrandbits(32);hwdsid=rng.getrandbits(32)
 stack=rng.randbytes(0x100);m.mem_write(STACK,stack);m.mem_write(FRAME-0x51,bytes([hwdsid&255]));m.mem_write(A,struct.pack('<I',hwdsid));m.mem_write(D,bytes(data))
 pc=run(0,{0:address,8:A,15:enable,22:scale,24:0x100,25:D,26:length})
 expected,accepted=append(data,address,length,hwdsid,scale,enable);assert bytes(m.mem_read(D,len(data)))==expected
 assert pc==(RANGES[0][1] if accepted else BASE+0x89942d8)
 counts['direct_accepted' if accepted else 'direct_full']=counts.get('direct_accepted' if accepted else 'direct_full',0)+1
 m.mem_write(D,bytes(data));m.mem_write(STACK+0x60,struct.pack('<Q',address));provider_ok=i%3!=0
 pc=run(1,{0:int(provider_ok),14:enable,22:scale,25:D,26:length})
 expected,accepted=append(data,address,length,hwdsid,scale,enable) if provider_ok else (bytes(data),False)
 assert bytes(m.mem_read(D,len(data)))==expected;assert pc==(RANGES[1][1] if accepted else BASE+0x89942cc)
 key='resolved_accepted' if accepted else ('resolved_full' if provider_ok else 'resolved_missing');counts[key]=counts.get(key,0)+1
 assert bytes(m.mem_read(FRAME-0x51,1))==bytes([hwdsid&255])
 if i<16:examples.append(dict(initial_count=count,direct_accepted=count<=15,provider_ok=provider_ok))
# Callers supply descriptor970 and engine mask8; this is not the array capacity.
for i in range(256):
 command=rng.getrandbits(64);channel=rng.getrandbits(64);m.mem_write(Q+0x838,struct.pack('<Q',channel));m.mem_write(STACK+0x98,struct.pack('<Q',command))
 for which,initial in [(2,{19:Q,20:DESC,22:command}),(3,{19:Q,25:DESC})]:
  pc=run(which,initial);assert pc==RANGES[which][1]
  expected=[Q,command,channel,8,DESC+0x970]
  assert [m.reg_read(regs[j]) for j in range(5)]==expected
  addr=RANGES[which][1];word=struct.unpack('<I',read(addr,4))[0];imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  assert word>>26==0b100101 and addr+imm*4==BASE+0x89940f4
  key='fast_caller' if which==2 else 'ordinary_caller';counts[key]=i+1
# Native descriptor initialization clears the HWDSID array/count/notification region.
INIT_START,INIT_END=BASE+0x895db6c,BASE+0x895dbc0
m.mem_write(INIT_START,read(INIT_START,INIT_END-INIT_START))
for i in range(512):
 descriptor=rng.randbytes(0x1000);m.mem_write(DESC,descriptor);m.reg_write(regs[19],DESC)
 m.emu_start(INIT_START,INIT_END,count=100);assert m.reg_read(c.UC_ARM64_REG_PC)==INIT_END
 expected=bytearray(descriptor);expected[0x970:0xaa8]=bytes(0x138)
 assert bytes(m.mem_read(DESC,len(descriptor)))==bytes(expected);counts['descriptor_initialization']=i+1
report=dict(binary_sha256=sha,counts=counts,examples=examples,ranges=[dict(start=hex(INIT_START),end=hex(INIT_END),sha256=hashlib.sha256(read(INIT_START,INIT_END-INIT_START)).hexdigest())]+[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in RANGES],visited_instruction_count=len(seen),qualification='Actual call-free producer append slices and caller argument assembly in RAM, independent model/full destination checked. Direct identifier100 and resolved nonzero-provider paths qualified; preceding filtering/budget/resource lookup/provider execution and concurrency excluded. Both paths bound existing count<=15; callers pass descriptor970 and mask8. Does not claim every possible descriptor writer or malicious input is validated. No live GPU execution.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
