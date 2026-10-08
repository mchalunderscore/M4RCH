#!/usr/bin/env python3
"""Execute complete startup payload builder through publication, providers synthetic."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_sku_startup import build
from private_sku_records import startup
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
BASE=0xfffffe0000000000;START=BASE+0x89d5344;END=BASE+0x89d5630
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
m.mem_map(BASE+0x89d5000,4096);m.mem_write(START,read(START,END-START));m.mem_map(0x200000,0x60000)
E,CH,A,D,CMD,N,O,R1,R2,R3,VT1,VT2,VT3,F,FVT,B,STACK=0x200000,0x201000,0x202000,0x212000,0x214000,0x217000,0x218000,0x219000,0x21a000,0x21b000,0x21c000,0x21d000,0x21e000,0x21f000,0x220000,0x222000,0x250000
m.mem_write(CH+0x10,struct.pack('<Q',A));m.mem_write(CH+0xa8,struct.pack('<Q',E));m.mem_write(A+0x5b0,struct.pack('<Q',F));m.mem_write(F,struct.pack('<Q',FVT));m.mem_write(FVT+0x2d8,struct.pack('<Q',0x221000))
for r,vt,slot,target in [(R1,VT1,0x1e0,0x221100),(R2,VT2,0x158,0x221200),(R3,VT3,0x158,0x221300)]:m.mem_write(r,struct.pack('<Q',vt));m.mem_write(vt+slot,struct.pack('<Q',target))
m.mem_write(N+0x30,struct.pack('<Q',O));m.mem_write(O+0x58,struct.pack('<Q',R2))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];seen=set();resource_type=resource_map=stream_map=translated=cursor=0

def hook(m,addr,size,user):
 seen.add(addr);word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0,x1,x2=[m.reg_read(regs[i]) for i in range(3)]
  if target==0x221100:assert x0==R1;value=resource_type;calls.append(('type',))
  elif target==0x221200:assert x0==R2;value=resource_map;calls.append(('parameter_map',))
  elif target==0x221300:assert x0==R3;value=stream_map;calls.append(('stream_map',))
  elif target==0x221000:
   assert x0==F and x2==0;assert x1==(stream_map+((cursor-B)&0xffffffff)+4)&((1<<64)-1)
   value=translated;calls.append(('translate',x1))
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==BASE+0x89d562c:
  assert m.reg_read(regs[0])==cursor+4 and m.reg_read(regs[1])==STACK+0x80 and m.reg_read(regs[2])==0x1e8
  m.mem_write(cursor+4,bytes(m.mem_read(STACK+0x80,0x1e8)));calls.append(('copy',));m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604016);counts={};examples=[]
for i in range(1280):
 desc=bytearray(rng.randbytes(0x1000));command=rng.randbytes(0x2300);stack=rng.randbytes(0x300);encoder=bytearray(rng.randbytes(0x100));backing=rng.randbytes(0x4000)
 count=i%17 if i<1024 else 17+i%8;struct.pack_into('<I',desc,0xa70,count);struct.pack_into('<Q',desc,0x58,R1);struct.pack_into('<Q',desc,0x190,0x221400);struct.pack_into('<Q',desc,0xb90,N);desc[0x960]=[0,1,2,3,255][i%5]
 context=rng.getrandbits(32);resource_type=rng.getrandbits(64);resource_map=rng.getrandbits(64);stream_map=rng.getrandbits(64);translated=rng.getrandbits(64)
 config=i%256;feature=(i//2)%256;gpu=rng.getrandbits(64);pm_gpu=rng.getrandbits(64);state=rng.getrandbits(64)
 cursor=B+(i%16)*256;struct.pack_into('<Q',encoder,8,A);struct.pack_into('<Q',encoder,0x20,R3);struct.pack_into('<Q',encoder,0x28,B);struct.pack_into('<Q',encoder,0x68,cursor)
 m.mem_write(D,bytes(desc));m.mem_write(CMD,command);m.mem_write(STACK,stack);m.mem_write(E,bytes(encoder));m.mem_write(B,backing);m.mem_write(0x221408,struct.pack('<I',context));m.mem_write(A+0xed48,bytes([config]));m.mem_write(A+0x6d5,bytes([feature]))
 expected_stack,secondary=build(stack,desc,command,gpu,pm_gpu,state,resource_type,resource_map,context,config,feature)
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for j,v in {19:CMD,20:CH,21:STACK+0x80,22:state,23:0,24:gpu,25:pm_gpu,26:D}.items():m.reg_write(regs[j],v)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.emu_start(START,END,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==END
 assert bytes(m.mem_read(STACK,len(stack)))==expected_stack,(i,'payload')
 expected_backing=bytearray(backing);off=cursor-B;expected_backing[off:off+0x300]=startup(backing[off:off+0x300],expected_stack[0x80:0x268])
 assert bytes(m.mem_read(B,len(backing)))==bytes(expected_backing),(i,'published')
 struct.pack_into('<Q',encoder,0x68,cursor+0x1ec);assert bytes(m.mem_read(E,len(encoder)))==bytes(encoder)
 assert m.reg_read(regs[22])==secondary and m.reg_read(regs[28])==translated
 assert bytes(m.mem_read(D,len(desc)))==bytes(desc);assert bytes(m.mem_read(CMD,len(command)))==command
 assert calls==[('type',),('parameter_map',),('stream_map',),('translate',(stream_map+(cursor-B)+4)&((1<<64)-1)),('copy',)]
 if i<1024:counts['payload_and_publication']=i+1
 else:counts['entry_overlap_characterization']=i-1023
 if i<17:examples.append(dict(entries=count,secondary=secondary,mode=desc[0x960],feature_lowbit=feature&1))
report=dict(binary_sha256=sha,counts=counts,examples=examples,range=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),visited_instruction_count=len(seen),qualification='Actual complete startup payload builder through record7 publication, full stack/encoder/backing and source comparisons. PAC bypassed, external resource type/map/firmware translation and memcpy explicitly stubbed. Entry counts0..16 in1024 fixtures;256 additional counts17..24 characterize metadata/stack overlap, not valid jobs or allowed maximum. Pre-start w23=0; conditional wait path already separately qualified, not composed here. GPU/PM/state/firmware-map inputs synthetic; no live executable draw or allocation/cache semantics.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
