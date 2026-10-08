#!/usr/bin/env python3
"""Qualify fresh/reused concrete page-list mapping and actual release offline."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END,RELEASE=0xfffffe00089fe494,0xfffffe00089fea3c,0xfffffe00089fe44c
m.mem_write(RELEASE,read(RELEASE,END-RELEASE))
m.mem_map(0x220000,0x30000);m.mem_map(0xfffffe0007ea2000,4096);m.mem_map(0xfffffe000c6e7000,4096)
GPU,OBJECT,OVT,META,IVT,ARRAY,A,B,DISCARD,INNER,IV,NEW,INIT,RETAIN,REL,LENGTH=range(0x220000,0x230000,0x1000)
ALLOC,PREP,DPREP=0xfffffe000bf257d4,0xfffffe000a7c40b0,0xfffffe000a8032a8
m.mem_write(0xfffffe000c6e7d00,struct.pack('<Q',META));m.mem_write(META+0xa8,struct.pack('<Q',NEW))
m.mem_write(0xfffffe0007ea24d8,struct.pack('<Q',IVT));m.mem_write(IVT+0x150,struct.pack('<Q',INIT))
m.mem_write(OVT+0x20,struct.pack('<Q',RETAIN));m.mem_write(OVT+0x28,struct.pack('<Q',REL))
m.mem_write(IV+0x20,struct.pack('<Q',RETAIN));m.mem_write(IV+0x148,struct.pack('<Q',LENGTH))
events=[];allocation=0
def service_hook(m,address,size,user):
 global allocation
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0=m.reg_read(regs[0])
  if target==NEW:assert x0==0xfffffe000c6e7d00;value=OBJECT;events.append(('new',))
  elif target==INIT:assert x0==OBJECT and m.reg_read(regs[1])==GPU;value=1;events.append(('init',))
  elif target==RETAIN:value=0;events.append(('retain',x0))
  elif target==REL:assert x0==OBJECT;value=0;events.append(('release',x0))
  elif target==LENGTH:
   assert INNER+0x1000<=x0<INNER+0x1000*(count+1);value=lengths[(x0-INNER)//0x1000-1];events.append(('length',x0))
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfc000000==0x94000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+imm*4;x0=m.reg_read(regs[0])
  if target==ALLOC:
   assert m.reg_read(regs[1])==capacity*8;value=[A,B][allocation];allocation+=1;events.append(('alloc',value,capacity*8))
  elif target==PREP:assert x0==OBJECT;value=0;events.append(('prepare',x0))
  elif target==DPREP:assert x0==INNER;value=0;events.append(('prepare_discard',x0))
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,service_hook)
def execute(start,x0=S,x1=D):
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,x0),(c.UC_ARM64_REG_X1,x1),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(start,STOP,count=20000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(c.UC_ARM64_REG_W0)
rng=random.Random(604042);counts=dict(fresh=0,reused=0,release=0,empty_release=0,retained_resources=0)
for i in range(512):
 count=i%9;capacity=(count+63)&~63;has_discard=bool(i&1);reused=bool(i&2)
 pm=bytearray(rng.randbytes(0x300));descriptor=bytearray(rng.randbytes(0x1000));obj=bytearray(rng.randbytes(0x100));aa=bytearray(rng.randbytes(0x1000));bb=bytearray(rng.randbytes(0x1000))
 pm[0x28]=0;struct.pack_into('<I',pm,0x128,0)
 for off,value in [(0x10,GPU),(0x248,ARRAY),(0x240,DISCARD if has_discard else 0),(0x258,OBJECT if reused else 0)]:struct.pack_into('<Q',pm,off,value)
 struct.pack_into('<I',pm,0x250,count);struct.pack_into('<Q',obj,0,OVT)
 resources=[0x230000+j*0x1000 for j in range(count)];inners=[INNER+(j+1)*0x1000 for j in range(count)];lengths=[rng.randrange(1,0x100000) for j in range(count)]
 for resource,inner in zip(resources,inners):
  m.mem_write(resource,struct.pack('<Q',IV));m.mem_write(resource+0x18,struct.pack('<Q',inner));m.mem_write(inner,struct.pack('<Q',IV))
 m.mem_write(ARRAY,b''.join(struct.pack('<Q',v) for v in resources));m.mem_write(DISCARD+0x20,struct.pack('<Q',INNER));m.mem_write(INNER,struct.pack('<Q',IV))
 expected_pm=bytearray(pm);expected_d=bytearray(descriptor);expected_o=bytearray(obj);expected_a=bytearray(aa);expected_b=bytearray(bb)
 if not reused:
  struct.pack_into('<II',expected_o,0x90,capacity,count);struct.pack_into('<QQ',expected_o,0x80,A,B)
  total=(struct.unpack_from('<Q',obj,0x98)[0]+sum(lengths))&((1<<64)-1);struct.pack_into('<Q',expected_o,0x98,total)
  for j,(resource,inner) in enumerate(zip(resources,inners)):struct.pack_into('<Q',expected_a,j*8,resource);struct.pack_into('<Q',expected_b,j*8,inner)
 struct.pack_into('<Q',expected_pm,0x258,OBJECT);struct.pack_into('<Q',expected_d,0xd78,OBJECT)
 if has_discard:struct.pack_into('<Q',expected_d,0xd98,INNER)
 for addr,data in [(S,pm),(D,descriptor),(OBJECT,obj),(A,aa),(B,bb)]:m.mem_write(addr,bytes(data))
 events.clear();allocation=0;assert execute(START)==0
 for addr,data in [(S,expected_pm),(D,expected_d),(OBJECT,expected_o),(A,expected_a),(B,expected_b)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 expected_events=[]
 if not reused:
  expected_events=[('new',),('init',),('alloc',A,capacity*8),('alloc',B,capacity*8)]
  for resource,inner in zip(resources,inners):expected_events += [('retain',resource),('length',inner)]
 expected_events += [('prepare',OBJECT),('retain',OBJECT)]
 if has_discard:expected_events += [('prepare_discard',INNER),('retain',INNER)]
 assert events==expected_events,(i,events,expected_events);counts['reused' if reused else 'fresh']+=1;counts['retained_resources']+=0 if reused else count
 events.clear();execute(RELEASE);struct.pack_into('<Q',expected_pm,0x258,0)
 assert bytes(m.mem_read(S,len(pm)))==expected_pm and events==[('release',OBJECT)];counts['release']+=1
 events.clear();execute(RELEASE);assert bytes(m.mem_read(S,len(pm)))==expected_pm and events==[];counts['empty_release']+=1
report=dict(private_binary_sha256=sha,range=[hex(RELEASE),hex(END)],range_sha256=hashlib.sha256(read(RELEASE,END-RELEASE)).hexdigest(),counts=counts,qualification='Actual concrete page mapping fresh and reused success paths and actual release, whole PM/TA/mapping/array comparisons. Counts0..8; fresh capacity rounded to64; discard present/absent. Allocation, inherited initializer, retain/release, length and mapping prepare are argument/order checked external services. Fresh fixture initializer preserves randomized mapping98 and the actual method adds lengths to it; production inherited initialization must supply valid initial fields. Pending resource append, mode2 replacement and failures not qualified. No live ownership or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
