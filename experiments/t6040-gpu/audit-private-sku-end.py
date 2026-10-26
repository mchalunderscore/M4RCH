#!/usr/bin/env python3
"""Check native primary and optional secondary 3D opcode8 stream records."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_sku_end import primary,secondary
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
BASE=0xfffffe0000000000;RANGES=[(BASE+0x89d56b4,BASE+0x89d57e4),(BASE+0x89d58b8,BASE+0x89d5980)]
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
m.mem_map(BASE+0x89d5000,4096);m.mem_write(BASE+0x89d56b4,read(BASE+0x89d56b4,0x89d59d4-0x89d56b4));m.mem_map(0x200000,0x50000)
E,CH,A,D,CMD,B,STACK,FRAME=0x200000,0x201000,0x202000,0x212000,0x214000,0x218000,0x240000,0x241000
m.mem_write(CH+0x10,struct.pack('<Q',A));m.mem_write(CH+0xa8,struct.pack('<Q',E))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];seen=set()
def hook(m,addr,size,user):seen.add(addr)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(which,initial):
 for reg in regs:m.reg_write(reg,0)
 for index,value in initial.items():m.reg_write(regs[index],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_X29,FRAME)
 m.reg_write(c.UC_ARM64_REG_D8,0x100000000)
 start,end=RANGES[which];m.emu_start(start,end,count=400);assert m.reg_read(c.UC_ARM64_REG_PC)==end
rng=random.Random(604015);counts={};examples=[]
for i in range(1024):
 command=rng.randbytes(0x2300);desc=bytearray(rng.randbytes(0x1000));stack=rng.randbytes(0x100);backing=rng.randbytes(0x2000)
 pattern=i%6;vec=[0]*4
 if pattern in (1,2,3,4):vec[pattern-1]=rng.getrandbits(64) or 1
 struct.pack_into('<4Q',desc,0xa78,*vec);struct.pack_into('<I',desc,0xa70,1 if pattern==5 else 0)
 gpu=rng.getrandbits(64);payload=rng.getrandbits(64);mode=rng.getrandbits(32);config=i%256
 offset=(i%16)*64;relative=offset+(i%17)*4;cursor=B+relative
 encoder=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',encoder,0x28,B);struct.pack_into('<I',encoder,0x5c,offset);struct.pack_into('<Q',encoder,0x68,cursor)
 m.mem_write(E,bytes(encoder));m.mem_write(CMD,command);m.mem_write(D,bytes(desc));m.mem_write(STACK,stack);m.mem_write(FRAME-0x90,bytes(32));m.mem_write(B,backing);m.mem_write(A+0xf570,bytes([config]))
 run(0,{19:CMD,20:CH,22:mode,24:gpu,26:D,28:payload})
 expected=bytearray(backing);expected[relative:relative+0x200]=primary(backing[relative:relative+0x200],stack,command,desc,gpu,payload,mode,config,B,offset,cursor)
 assert bytes(m.mem_read(B,len(backing)))==bytes(expected),(i,'primary')
 struct.pack_into('<Q',encoder,0x68,cursor+0xbc);assert bytes(m.mem_read(E,len(encoder)))==bytes(encoder)
 vector=bytes(desc[0xa78:0xa98]) if pattern else bytes(32)
 assert bytes(m.mem_read(FRAME-0x90,32))==vector
 assert bytes(m.mem_read(CMD,len(command)))==command;assert bytes(m.mem_read(D,len(desc)))==bytes(desc);assert bytes(m.mem_read(STACK,len(stack)))==stack
 counts['primary_end']=i+1
 # Optional second opcode8 record slice receives saved fields/registers from earlier code.
 v=rng.randbytes(32);regvals={j:rng.getrandbits(64) for j in (21,23,24,25,26,27,28)}
 struct.pack_into('<Q',encoder,0x68,cursor);m.mem_write(E,bytes(encoder));m.mem_write(B,backing);m.mem_write(FRAME-0x90,v)
 run(1,{20:CH,**regvals})
 expected=bytearray(backing);expected[relative:relative+0x200]=secondary(backing[relative:relative+0x200],stack,regvals,v,B,offset,cursor)
 assert bytes(m.mem_read(B,len(backing)))==bytes(expected),(i,'secondary')
 struct.pack_into('<Q',encoder,0x68,cursor+0xbc);assert bytes(m.mem_read(E,len(encoder)))==bytes(encoder)
 assert bytes(m.mem_read(STACK,len(stack)))==stack;assert bytes(m.mem_read(FRAME-0x90,32))==v;counts['secondary_end']=i+1
 if i<12:examples.append(dict(notification_pattern=pattern,config=config,relative_word=hex((offset-relative)&0xffffffff),primary_mode=hex(mode)))
constant=struct.unpack('<Q',read(BASE+0x712d7f0,8))[0];assert constant==0x100000000
report=dict(binary_sha256=sha,counts=counts,examples=examples,secondary_mode_constant=hex(constant),ranges=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in RANGES],primary_zero_vector_branch=dict(start=hex(BASE+0x89d59cc),end=hex(BASE+0x89d59d4),sha256=hashlib.sha256(read(BASE+0x89d59cc,8)).hexdigest()),visited_instruction_count=len(seen),qualification='Actual native primary/secondary opcode8 record construction slices, numeric models and full backing/encoder/source byte checks. Primary notification selection executed, synthetic safe stack/frame/descriptor/resource addresses; secondary saved register inputs and d8 native constant supplied. No external callbacks or PAC bypass in slices. Full upstream construction, branch selection for secondary phase, mapping/cache, instruction completion semantics and live GPU execution remain unproved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
