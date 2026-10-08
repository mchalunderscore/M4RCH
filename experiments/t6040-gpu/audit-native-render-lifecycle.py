#!/usr/bin/env python3
"""Offline native render-target initialization and event scrub, with opaque services."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,n=struct.unpack_from('<II',raw,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=n
B=0xfffffe0000000000

def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return raw[off+addr-vm:off+addr-vm+n]
 raise ValueError(hex(addr))
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(B+0x8a0b000,4096),(B+0x7ea2000,4096),(0x200000,0x80000)]:
 m.mem_map(addr,n)
 if addr>B:m.mem_write(addr,read(addr,n))
O,A,SH,VT,BVT,ARRAY,R0,R1,STACK,STOP=0x200000,0x220000,0x240000,0x250000,0x251000,0x260000,0x270000,0x270100,0x27e000,0x27f000
m.mem_write(B+0x7ea2580,struct.pack('<Q',BVT));m.mem_write(BVT+0xb8,struct.pack('<Q',0x253000));m.mem_write(SH,struct.pack('<Q',VT));m.mem_write(VT+0x20,struct.pack('<Q',0x253100));m.mem_write(VT+0x1a8,struct.pack('<Q',0x253200))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];seen=set();base_success=1

def hook(m,addr,size,user):
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==B+0x8a0b47c:
  calls.append(('allocate_records',[m.reg_read(regs[0])]));m.reg_write(regs[0],ARRAY);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==B+0x8a0b49c:
  calls.append(('event_initialize',[m.reg_read(regs[0])]));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==B+0x8a0b338:
  calls.append(('event_scrub',[m.reg_read(regs[0]),m.reg_read(regs[1])]));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(regs[(word>>5)&31]);arg=m.reg_read(regs[0]);tail=word&0xfffffc00==0xd71f0800
  if target==0x253000:
   assert arg==O;calls.append(('base_init',[arg]));m.reg_write(regs[0],base_success)
  elif target==0x253100:
   assert arg==SH;calls.append(('shared_retain',[arg]))
  elif target==0x253200:
   assert arg in (R0,R1);calls.append(('resource_1a8',[arg]));m.reg_write(regs[0],0)
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR) if tail else addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(addr,**values):
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for name,value in values.items():m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);m.emu_start(B+addr,STOP,count=12000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(regs[0])
def put(b,off,value,size=8):struct.pack_into('<Q' if size==8 else '<I',b,off,value)
rng=random.Random(604023);counts={'init_success':0,'base_init_failure':0,'scrub_events':0,'event_init_calls':0,'event_scrub_calls':0};examples=[]
for i in range(1024):
 original=bytearray(rng.randbytes(0x400));record=bytes(rng.randbytes(0x2000));m.mem_write(ARRAY,record)
 override=[0,1,2,16,31,64][i%6];fallback=[0,1,4,16,32][i%5];count=override or fallback;config=i%3;argument=rng.getrandbits(64);base_success=int(i%7!=0)
 m.mem_write(A+0xf528,struct.pack('<I',override));m.mem_write(A+0x718,struct.pack('<I',fallback));m.mem_write(A+0xecd4,struct.pack('<I',config));m.mem_write(O,bytes(original))
 expected=bytearray(original);want=[('base_init',[O])]
 if base_success:
  put(expected,0x120,A);put(expected,0x128,SH);put(expected,0x280,count,4);put(expected,0x284,0);put(expected,0x278,count*0x58);put(expected,0x290,ARRAY)
  put(expected,0x18,0,4);put(expected,0x30,0);put(expected,0x260,0);expected[0x140:0x1c0]=bytes(0x80);expected[0x2c0]=int(config!=0)
  put(expected,0x130,0);put(expected,0x138,argument);expected[0x1c0:0x1d0]=bytes(16);put(expected,0x258,argument)
  want += [('shared_retain',[SH]),('allocate_records',[count*0x58])]+[('event_initialize',[ARRAY+0x18+j*0x58]) for j in range(count)]
 value=run(0x8a0b3e0,x0=O,x1=A,x2=SH,x3=argument)
 assert value==base_success and bytes(m.mem_read(O,0x400))==expected and bytes(m.mem_read(ARRAY,0x2000))==record
 assert calls==want,(i,calls,want)
 counts['init_success' if base_success else 'base_init_failure']+=1;counts['event_init_calls']+=count if base_success else 0
 # Complete scrub method, including resource tail-call. Event service remains opaque.
 original=bytearray(rng.randbytes(0x400));record=bytes(rng.randbytes(0x2000));manager=0x274000
 put(original,0x120,A);put(original,0x290,ARRAY);put(original,0x280,count,4);put(original,0x1c0,R0 if i&1 else 0);put(original,0x130,R1 if i&2 else 0)
 m.mem_write(A+0x140,struct.pack('<Q',manager));m.mem_write(R0,struct.pack('<Q',VT));m.mem_write(R1,struct.pack('<Q',VT));m.mem_write(O,bytes(original));m.mem_write(ARRAY,record)
 run(0x8a0b300,x0=O)
 want=[('event_scrub',[manager,ARRAY+0x18+j*0x58]) for j in range(count)]
 if i&1:want.append(('resource_1a8',[R0]))
 if i&2:want.append(('resource_1a8',[R1]))
 assert calls==want and bytes(m.mem_read(O,0x400))==original and bytes(m.mem_read(ARRAY,0x2000))==record
 counts['scrub_events']+=1;counts['event_scrub_calls']+=count
 if i<6:examples.append({'override_f528':override,'fallback_718':fallback,'selected_records':count,'array_bytes':count*0x58,'extra_storage_flag':bool(config),'base_success':bool(base_success)})
ranges=[(0x8a0b3e0,0x8a0b514),(0x8a0b300,0x8a0b3e0)]
report={'private_binary_sha256':sha,'counts':counts,'examples':examples,'native_ranges':[{'start':hex(B+x),'end':hex(B+y),'sha256':hashlib.sha256(read(B+x,y-x)).hexdigest()} for x,y in ranges],'visited_instructions':len(seen),'qualification':'Full native init and scrub functions with whole object/record byte comparison. Base initialization, shared retain, record allocation, event initialize/scrub and resource slot1a8 are argument-checked supplied opaque services. Services do not write record bytes: this is deliberately not proof of event contents/zero initialization. Positive allocator return supplied; actual allocation failure behavior not tested. Accelerator overrides/configuration are fixtures, not live topology reads. PAC auth/return bypassed; no hardware.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
