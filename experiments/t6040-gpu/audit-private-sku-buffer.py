#!/usr/bin/env python3
"""Qualify native SKU buffer selection and finalization; provider calls synthetic."""
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
BASE=0xfffffe0000000000;BEGIN=BASE+0x8a16958;FINISH=BASE+0x8a16ba4;END=BASE+0x8a16cdc
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(BASE+0x8a16000,4096);m.mem_write(BEGIN,read(BEGIN,END-BEGIN));m.mem_map(0x200000,0x60000)
E,A,F,R,VT,FVT,V,B,EVENT,OUT,STOP,STACK=0x200000,0x201000,0x21d000,0x21e000,0x21f000,0x220000,0x221000,0x223000,0x230000,0x231000,0x25f000,0x25e000
m.mem_write(A+0x1aed4,b'\0');m.mem_write(A+0x5b0,struct.pack('<Q',F));m.mem_write(R,struct.pack('<Q',VT));m.mem_write(F,struct.pack('<Q',FVT));m.mem_write(VT+0x158,struct.pack('<Q',0x232000));m.mem_write(FVT+0x2d8,struct.pack('<Q',0x233000))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];seen=set();calls=[];occupancy=[];provider=0;translation=0;trap=None
TRAPS={BASE+x for x in (0x8a16ac0,0x8a16b58,0x8a16b64,0x8a16b70,0x8a16b7c)}
def hook(m,addr,size,user):
 global trap
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 if addr in TRAPS:trap=addr;m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+4*imm
  x0,x1,x2=[m.reg_read(regs[i]) for i in range(3)]
  if target==BASE+0xa7d0308:
   assert x0==0x234000 and x1>=V and (x1-V)%64==0
   idx=(x1-V)//64;assert idx<len(occupancy);calls.append(('available',idx));m.reg_write(regs[0],occupancy[idx])
  elif target==BASE+0xa7d0d18:
   assert x0==0x234000 and x1==EVENT and x2>=V and (x2-V)%64==0
   calls.append(('associate',(x2-V)//64))
  elif target==FINISH:return  # Execute native finishEncode, including its mapping stubs.
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 # Authenticated indirect call and tail branch.
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(regs[(word>>5)&31]);x0,x1,x2=[m.reg_read(regs[i]) for i in range(3)]
  if target==0x232000:assert x0==R;calls.append(('resource',));m.reg_write(regs[0],provider)
  elif target==0x233000:assert x0==F and x2==0;calls.append(('translate',x1));m.reg_write(regs[0],translation)
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_PC,addr+4 if word&0xfffffc00==0xd73f0800 else m.reg_read(c.UC_ARM64_REG_LR))
m.hook_add(u.UC_HOOK_CODE,hook)
def run(start,args):
 global trap
 trap=None;calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for i,value in enumerate(args):m.reg_write(regs[i],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(start,STOP,count=6000)
 if trap is None:assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(regs[0])
rng=random.Random(604013);counts={};examples=[]
for i in range(1024):
 n=1+i%32;previous=(i*7)%n;stride=[64,128,256,512][i%4];skip=i%n;start=(previous+1)&0xffffffff;start%=n;selected=(start+skip)%n
 occupancy=[0]*n;occupancy[selected]=1
 enc=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',enc,8,A);struct.pack_into('<Q',enc,0x20,R);struct.pack_into('<Q',enc,0x28,B);struct.pack_into('<2Q',enc,0x38,0x234000,V);struct.pack_into('<I',enc,0x48,n);struct.pack_into('<Q',enc,0x50,stride);struct.pack_into('<I',enc,0x58,n);struct.pack_into('<I',enc,0x60,previous)
 event_id=rng.getrandbits(32);m.mem_write(E,bytes(enc));backing=rng.randbytes(0x5000);m.mem_write(B,backing)
 run(BEGIN,[E,EVENT,event_id]);assert trap is None
 expected=bytearray(enc);struct.pack_into('<I',expected,0x78,event_id);struct.pack_into('<I',expected,0x60,selected);struct.pack_into('<I',expected,0x5c,stride*selected);struct.pack_into('<Q',expected,0x68,B+stride*selected)
 assert bytes(m.mem_read(E,len(enc)))==bytes(expected)
 assert calls==[('available',(start+j)%n) for j in range(skip+1)]+[('associate',selected)]
 assert bytes(m.mem_read(B,len(backing)))==backing;counts['begin']=i+1
 # Native finalization after a synthetic populated stream; no opcode semantics implied.
 length=[0,1,4,59,60,61,63,64,65,127,128][i%11];cursor=B+stride*selected+length
 struct.pack_into('<Q',expected,0x68,cursor);m.mem_write(E,bytes(expected));before=bytes(m.mem_read(B,len(backing)));out=rng.randbytes(16);m.mem_write(OUT,out)
 provider=rng.getrandbits(64);translation=rng.getrandbits(64);size_out=OUT if i%3 else 0
 result=run(FINISH,[E,size_out]);assert trap is None and result==translation
 struct.pack_into('<Q',expected,0x68,cursor+4);assert bytes(m.mem_read(E,len(enc)))==bytes(expected)
 changed=bytearray(before);struct.pack_into('<I',changed,cursor-B,0x40000002);assert bytes(m.mem_read(B,len(backing)))==bytes(changed)
 output=bytearray(out);rounded=(length+4+63)&0xffffffc0
 if size_out:struct.pack_into('<I',output,0,rounded)
 assert bytes(m.mem_read(OUT,16))==bytes(output);assert calls==[('resource',),('translate',(provider+stride*selected)&((1<<64)-1))]
 counts['finish']=i+1
 if i<12:examples.append(dict(capacity=n,previous=previous,skipped=skip,selected=selected,stride=stride,payload_bytes=length,reported_bytes=rounded,size_pointer=bool(size_out)))
# All slots unavailable: capture native failure before panic/assert external code.
for n in range(1,33):
 occupancy=[0]*n;enc=bytearray(0x100);struct.pack_into('<Q',enc,8,A);struct.pack_into('<2Q',enc,0x38,0x234000,V);struct.pack_into('<I',enc,0x48,n);struct.pack_into('<I',enc,0x58,n);m.mem_write(E,bytes(enc));run(BEGIN,[E,EVENT,3]);assert trap==BASE+0x8a16b7c
 assert calls==[('available',(1+j)%n) for j in range(n)];counts['all_unavailable']=n
# Execute the 3D caller's publication with native finishEncode, not a finish stub.
CALLER_START,CALLER_END=BASE+0x89d5980,BASE+0x89d5990
m.mem_map(BASE+0x89d5000,4096);m.mem_write(CALLER_START,read(CALLER_START,CALLER_END-CALLER_START))
CH,CMD=0x235000,0x236000
for i in range(512):
 enc=bytearray(rng.randbytes(0x100));offset=(i%16)*256;length=i%129
 struct.pack_into('<Q',enc,8,A);struct.pack_into('<Q',enc,0x20,R);struct.pack_into('<Q',enc,0x28,B);struct.pack_into('<I',enc,0x5c,offset);struct.pack_into('<Q',enc,0x68,B+offset+length)
 m.mem_write(E,bytes(enc));m.mem_write(CH+0xa8,struct.pack('<Q',E));cmd=rng.randbytes(0x100);m.mem_write(CMD,cmd)
 provider=rng.getrandbits(64);translation=rng.getrandbits(64);calls.clear()
 for reg in regs:m.reg_write(reg,0)
 m.reg_write(regs[19],CMD);m.reg_write(regs[20],CH);m.reg_write(c.UC_ARM64_REG_SP,STACK)
 m.emu_start(CALLER_START,CALLER_END,count=300);assert m.reg_read(c.UC_ARM64_REG_PC)==CALLER_END
 expected=bytearray(cmd);struct.pack_into('<Q',expected,0x14,translation);struct.pack_into('<I',expected,0x1c,(length+4+63)&0xffffffc0)
 assert bytes(m.mem_read(CMD,len(cmd)))==bytes(expected)
 assert calls==[('resource',),('translate',(provider+offset)&((1<<64)-1))]
 counts['3d_caller_native_finish']=i+1
report=dict(binary_sha256=sha,counts=counts,examples=examples,visited_instruction_count=len(seen),ranges=[dict(start=hex(CALLER_START),end=hex(CALLER_END),sha256=hashlib.sha256(read(CALLER_START,CALLER_END-CALLER_START)).hexdigest()),dict(start=hex(BEGIN),end=hex(FINISH),sha256=hashlib.sha256(read(BEGIN,FINISH-BEGIN)).hexdigest()),dict(start=hex(FINISH),end=hex(END),sha256=hashlib.sha256(read(FINISH,END-FINISH)).hexdigest())],qualification='Actual native begin/finish in RAM, PAC bypassed. Low unsigned pointers, capacities1..32, safe backing extent; trace/log bit3 clear. External availability/event association and resource/firmware mapping callbacks synthetic, no actual retirement or cache semantics. Full encoder/backing/output bytes compared. All-unavailable assertion intercepted before external failure. Synthetic arbitrary stream bytes are not valid microsequence. No live firmware execution.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
