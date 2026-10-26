#!/usr/bin/env python3
"""Check native ordinary/FastBlit headers, 3D state copies and tail in RAM."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_3d_command import header,body,tail,BODY_COPIES
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
RANGES=[(BASE+0x895af28,BASE+0x895af8c),(BASE+0x895b388,BASE+0x895b410),
 (BASE+0x895b604,BASE+0x895b8f8),(BASE+0x895b92c,BASE+0x895b9d8)]
EXTERNAL=BASE+0xbeaf410
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
m.mem_map(BASE+0x895a000,0x2000);m.mem_map(0x200000,0x40000)
for start,end in RANGES:m.mem_write(start,read(start,end-start))
D,C,S,CH,O,STACK,FRAME=0x200000,0x204000,0x208000,0x20a000,0x20b000,0x220000,0x221000
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];seen=set()
def hook(m,addr,size,user):
 seen.add(addr)
 if addr in (BASE+0x895af44,BASE+0x895b3a8):
  word=struct.unpack('<I',m.mem_read(addr,4))[0];imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  assert addr+4*imm==EXTERNAL
  assert m.reg_read(c.UC_ARM64_REG_X0)==struct.unpack('<Q',m.mem_read(D+0x60,8))[0]
  assert m.reg_read(c.UC_ARM64_REG_X1)==BASE+0xc6e6298
  calls.append(addr);m.reg_write(c.UC_ARM64_REG_X0,O);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(which,initial):
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for index,value in initial.items():m.reg_write(regs[index],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK)
 start,end=RANGES[which];m.emu_start(start,end,count=600);assert m.reg_read(c.UC_ARM64_REG_PC)==end
rng=random.Random(604012);counts={};examples=[]
for i in range(1024):
 command=rng.randbytes(0x2300);desc=bytearray(rng.randbytes(0x1000));source=rng.randbytes(0x400);stack=rng.randbytes(0x100);frame_data=rng.randbytes(24)
 serial=[0,1,(1<<64)-1,rng.getrandbits(64)][i%4]
 desc[0x960]=[0,1,2,3,255][i%5]
 struct.pack_into('<Q',desc,0x420,C);struct.pack_into('<Q',desc,0x438,C)
 m.mem_write(D,bytes(desc));m.mem_write(S,source);m.mem_write(STACK,stack);m.mem_write(FRAME-0xb8,frame_data)
 for which,fast in [(0,True),(1,False)]:
  m.mem_write(C,command);object_data=bytearray(rng.randbytes(0x700));struct.pack_into('<Q',object_data,0x5e8,serial);m.mem_write(O,bytes(object_data))
  run(which,{20:D,29:FRAME})
  assert bytes(m.mem_read(C,len(command)))==header(command,desc,serial,frame_data,fast),(i,'header',fast)
  struct.pack_into('<Q',object_data,0x5e8,(serial+1)&((1<<64)-1))
  assert bytes(m.mem_read(O,len(object_data)))==bytes(object_data);assert len(calls)==1
  counts['fast_header' if fast else 'ordinary_header']=i+1
 channel=bytearray(rng.randbytes(0x300));counter=[0,0xffffffff,rng.getrandbits(32)][i%3];struct.pack_into('<I',channel,0x204,counter)
 m.mem_write(CH,bytes(channel));m.mem_write(C,command);m.mem_write(STACK+0x60,struct.pack('<Q',S))
 run(2,{19:CH,20:D,24:C,28:C+0x1f38})
 assert bytes(m.mem_read(C,len(command)))==body(command,desc,source),(i,'body')
 struct.pack_into('<I',channel,0x204,(counter+1)&0xffffffff);assert bytes(m.mem_read(CH,len(channel)))==bytes(channel)
 counts['ordinary_body']=i+1
 m.mem_write(C,command);m.mem_write(STACK,stack);w21,w22=rng.getrandbits(32),rng.getrandbits(32);callback=rng.getrandbits(64)
 run(3,{0:callback,20:D,21:w21,22:w22,24:C,28:C+0x1f38})
 assert bytes(m.mem_read(C,len(command)))==tail(command,desc,stack,w21,w22,callback),(i,'tail')
 counts['ordinary_tail']=i+1
 assert bytes(m.mem_read(D,len(desc)))==bytes(desc);assert bytes(m.mem_read(S,len(source)))==source
 if i<5:examples.append(dict(serial=hex(serial),counter=hex(counter),mode=desc[0x960]))
report=dict(binary_sha256=sha,counts=counts,functions=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in RANGES],descriptor_body_copies=BODY_COPIES,examples=examples,visited_instruction_count=len(seen),qualification='Actual SKSM construction slices in emulated RAM; full command destination and counter object compared, source unchanged. External descriptor60 lookup explicitly intercepted, synthetic object returned; lookup semantics, locks and serial concurrency excluded. Tail callback return is synthetic; frame/stack/resource-state inputs synthetic. No full submit, pointer mappings, microsequence, live firmware or valid draw proved. Destination fixture2300 bytes is not proof of allocation stride.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
