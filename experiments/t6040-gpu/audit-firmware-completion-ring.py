#!/usr/bin/env python3
"""Execute matching firmware completion-ring helper offline with explicit services."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify
from firmware_completion import describe
p=argparse.ArgumentParser(description=__doc__);p.add_argument('text',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
text=a.text.read_bytes();identity=qualify(text)
START,END=0x15200,0x15d08
RAM,RAMSIZE=0x100000,0x100000
MAIN,HW,MMIO,RINGS,STACK,STOP=0x210000,0x214000,0x300000,0x400000,0x23f000,0x23e000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for address,size in [(0,0x90000),(RAM,RAMSIZE),(MAIN,0x30000),(MMIO,0x30000),(RINGS,0x10000)]:m.mem_map(address,size)
m.mem_write(0,text);order=struct.unpack_from('<4I',text,0x58a64);assert set(order)==set(range(4))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];current=-1
def hook(m,address,size,user):
 global current
 if address==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word in (0xd503237f,0xd50323ff):m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if address==0x15844:current=m.reg_read(regs[22])
 if address==0x15bc4:
  assert m.reg_read(regs[0])==0x82318;calls.append(('clock',current));m.reg_write(regs[0],clock);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfc000000==0x94000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+4*imm
  x0,x1,x2=[m.reg_read(regs[j]) for j in range(3)]
  if target==0x3ca80:calls.append(('cache',current,x0,x1));value=0
  elif target==0x12564:
   assert x0==current and x2==mode and RINGS+current*0x4000<=x1<RINGS+(current+1)*0x4000
   calls.append(('gate',current,x1,mode));value=gate(current,(x1-(RINGS+current*0x4000))//64)
  elif target==0x12788:
   assert x1==mode;calls.append(('process',current,x0,mode));value=0
  elif target==0x1a994:calls.append(('boundary',x0,x1,x2));value=0
  elif target in (0x28c8c,0x27e18,0x1a6d4):calls.append(('service',target));value=0
  else:raise AssertionError((hex(address),hex(target),x0,x1,x2))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604048)
counts=dict(cases=0,active_batches=0,entries=0,process_calls=0,empty_batches=0,full_batches=0,wrapped_batches=0)
examples=[]
for case in range(1024):
 capacity=[2,3,16,256][case%4];mode=2 if case&64 else 0;presence=(case//4)%16
 ram=bytearray(RAMSIZE);hw=bytearray(rng.randbytes(0x4000));mmio=bytearray(0x30000);rings=rng.randbytes(0x10000)
 struct.pack_into('<I',hw,0xeb8,0)
 def put(buf,address,fmt,value):struct.pack_into('<'+fmt,buf,address,value)
 put(ram,0x18e4c0-RAM,'Q',MAIN);put(ram,0x18f6d0-RAM,'Q',MMIO)
 put(ram,0x18f3ec-RAM,'I',capacity+1)
 for ref in (0x146888,0x1468b0,0x1468d8):put(ram,ref-RAM,'I',1)
 clock=rng.getrandbits(64);bias=rng.getrandbits(64);put(ram,0x190ba8-RAM,'Q',bias)
 m.mem_write(MAIN,struct.pack('<Q',HW));plans=[]
 for j in range(4):
  cursor=rng.randrange(capacity);head=cursor if case&128 else rng.randrange(capacity)
  count=[0,1,capacity-1,capacity][(case//16+j)%4]
  desc=struct.pack('<QQIIII',RINGS+j*0x4000 if presence&(1<<j) else 0,RINGS+j*0x4000,capacity,64,j,cursor)
  hw[0x2620+j*32:0x2640+j*32]=desc
  status=(rng.getrandbits(32)<<32)|(count<<16)|head
  put(mmio,0x21168+j*8,'Q',status);plans.append(describe(desc,status))
 m.mem_write(RAM,bytes(ram));m.mem_write(HW,bytes(hw));m.mem_write(MMIO,bytes(mmio));m.mem_write(RINGS,rings)
 # The clock service vtable is an explicit stand-in; no executable export.
 m.mem_write(0x82318,struct.pack('<Q',0x82400));m.mem_write(0x82418,struct.pack('<Q',0x82500))
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(regs[0],HW+0x2620),(regs[1],mode),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 calls.clear();current=-1
 gate=lambda j,cursor:int((j+cursor+case)%3!=0)
 try:m.emu_start(START,STOP,count=200000)
 except u.UcError as error:raise RuntimeError((case,hex(m.reg_read(c.UC_ARM64_REG_PC)),calls[-5:])) from error
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK,(case,hex(m.reg_read(c.UC_ARM64_REG_PC)))
 expected_calls=[];processed=0;active=0
 for j in order:
  plan=plans[j]
  if not plan['present'] or not plan['available']:continue
  count=plan['available'];active+=1;counts['entries']+=count;counts['full_batches']+=int(count==capacity);counts['wrapped_batches']+=int(plan['cursor']+count>capacity)
  put(ram,0x190c88-RAM,'I',active)
  expected_calls.append(('boundary',0,0,0))
  expected_calls += [('cache',j,RINGS+j*0x4000+off,length) for off,length in plan['invalidate_ranges']]
  for offset in plan['entry_offsets']:
   pointer=RINGS+j*0x4000+offset;expected_calls.append(('gate',j,pointer,mode))
   if gate(j,offset//64):expected_calls.append(('process',j,pointer,mode));processed+=1
  put(hw,0x263c+j*32,'I',plan['next_cursor'])
  expected_calls += [('boundary',0,0,1),('service',0x28c8c),('service',0x27e18),('clock',j)]
  put(ram,0x13c398-RAM,'Q',(clock+bias)&((1<<64)-1));put(mmio,0x21188+j*8,'Q',count)
  if mode!=2:expected_calls.append(('service',0x1a6d4))
 assert calls==expected_calls,(case,calls[:20],expected_calls[:20])
 assert bytes(m.mem_read(HW,len(hw)))==hw
 assert bytes(m.mem_read(RAM,RAMSIZE))==ram,(case,[(hex(RAM+i),x,y) for i,(x,y) in enumerate(zip(m.mem_read(RAM,RAMSIZE),ram)) if x!=y][:16])
 assert bytes(m.mem_read(MMIO,len(mmio)))==mmio,(case,[(hex(i),x,y) for i,(x,y) in enumerate(zip(m.mem_read(MMIO,len(mmio)),mmio)) if x!=y][:16])
 assert bytes(m.mem_read(RINGS,len(rings)))==rings
 counts['cases']+=1;counts['active_batches']+=active;counts['process_calls']+=processed;counts['empty_batches']+=sum(p.get('present',False) and not p['available'] for p in plans)
 if case<4:examples.append(dict(capacity=capacity,mode=mode,presence=presence,plans=plans))
report=dict(firmware=identity,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(text[START:END]).hexdigest(),descriptor_order=list(order),counts=counts,examples=examples,qualification='Complete firmware15200 ring helper executes in emulated RAM with already-held reference counts and optional hardware-EB8/trace/pending-notification gates off.1024 independent full descriptor/data/MMIO/ring checks: modes0/2, capacities2/3/16/256, all presence masks, empty/full/wrapping, software cursor both matching/different from hardwarehead. Cache, payload gate12564/process12788, notification flush, clock are explicit services. Hardware MMIO is ordinary RAM; cannot establish register side effects, DMA/cache or actual completion/retirement. No firmware/native code exported.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
