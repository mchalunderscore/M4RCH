#!/usr/bin/env python3
"""Execute actual concrete PM parameter-block creation success/full-ring paths."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
CREATE,END=0xfffffe00089febec,0xfffffe00089fef68;m.mem_write(CREATE,read(CREATE,END-CREATE));m.mem_map(0x220000,0x80000);m.mem_map(0xfffffe000c6e7000,4096)
GPU,B,MD,IO,SUPPORT,GART,REG,BVT,IOVT,MDVT,GARTVT,CFG,ALLOC,MVT,CTX,STATARRAY,SHARED=0x240000,*[0x260000+0x1000*i for i in range(16)]
META=0xfffffe000c6e7cb0
NEW,INIT,RETAIN,RELEASE,MAPGART,ELIGIBLE=[0x278000+8*j for j in range(6)]
def qwrite(a,v):m.mem_write(a,struct.pack('<Q',v))
qwrite(META,MVT);qwrite(MVT+0xa8,NEW)
for obj,vt in [(B,BVT),(MD,MDVT),(IO,IOVT),(GART,GARTVT)]:qwrite(obj,vt)
for vt,slot,target in [(BVT,0xa8,INIT),(BVT,0x20,RETAIN),(BVT,0x28,RELEASE),(MDVT,0x28,RELEASE),(IOVT,0x28,RELEASE),(IOVT,0x150,MAPGART),(GARTVT,0x170,ELIGIBLE)]:qwrite(vt+slot,target)
qwrite(GART+0x18,SUPPORT);events=[]
def done(address,value):m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
def block_hook(m,address,size,user):
 x0=m.reg_read(regs[0])
 if address==0xfffffe00089fec64:assert x0==CTX and m.reg_read(regs[1])==STATARRAY+current*64;events.append(('state_slot',));done(address,1);return
 if address==0xfffffe00089fece4:assert [m.reg_read(regs[j]) for j in range(4)]==[0,0x100063,0x20000,0x8000];events.append(('memory_descriptor',));done(address,MD);return
 if address==0xfffffe00089fecfc:assert [m.reg_read(regs[j]) for j in range(3)]==[GPU,0,MD];events.append(('mapping_object',));done(address,IO);return
 if address==0xfffffe00089fed08:assert x0==IO;events.append(('mapping_prepare',));done(address,0);return
 if address==0xfffffe00089fed28:assert x0==SHARED;events.append(('registration_provider',));done(address,REG);return
 if address==0xfffffe00089fee08:assert x0==SUPPORT and m.reg_read(c.UC_ARM64_REG_W1)==118;events.append(('resize_support',));m.mem_write(SUPPORT+0x78,struct.pack('<I',118));done(address,0);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==NEW:assert x0==META;value=B;events.append(('new_block',))
  elif target==INIT:assert x0==B;value=1;events.append(('inherited_init',))
  elif target in (RETAIN,RELEASE):assert x0 in (B,IO,MD);value=0;events.append(('retain' if target==RETAIN else 'release',x0))
  elif target==MAPGART:
   assert x0==IO and m.reg_read(regs[1])==REG and m.reg_read(regs[2])==(0x1100000007 if i&1 else 0x500000007);value=GART;events.append(('map_gart',))
  elif target==ELIGIBLE:assert x0==GART;value=1;events.append(('eligible',))
  else:raise AssertionError(hex(target))
  done(address,value);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,block_hook);rng=random.Random(604037);counts=dict(successes=0,ring_full=0,eligibility_checks=0,support_resizes=0)
for i in range(640):
 capacity=2+i%15;current=i%capacity;completed=(current+1)%capacity if i>=512 else current;occupied=i%capacity
 pm=bytearray(rng.randbytes(0x300));block=bytearray(rng.randbytes(0x100));config=bytearray(rng.randbytes(0x100));gpu=bytearray(0x19000);allocation=rng.randbytes(0x100)
 for off,v in [(0x10,GPU),(0x18,SHARED),(0x98,CFG),(0x198,STATARRAY),(0x248,ALLOC)]:struct.pack_into('<Q',pm,off,v)
 struct.pack_into('<I',pm,0x148,capacity);struct.pack_into('<I',pm,0x250,occupied);struct.pack_into('<I',pm,0x118,118);struct.pack_into('<III',config,0,current,0,completed);struct.pack_into('<Q',block,0,BVT);struct.pack_into('<Q',gpu,0x140,CTX);struct.pack_into('<Q',gpu,0x6d0,(i&1)<<47)
 ep=bytearray(pm);eb=bytearray(block);ec=bytearray(config);ea=bytearray(allocation)
 if i<512:struct.pack_into('<I',ep,0x250,occupied+1);struct.pack_into('<I',eb,0xc,current);struct.pack_into('<Q',eb,0x18,GART);struct.pack_into('<I',ec,0,(current+1)%capacity);struct.pack_into('<Q',ea,occupied*8,GART)
 for addr,data in [(S,pm),(B,block),(CFG,config),(GPU,gpu),(ALLOC,allocation)]:m.mem_write(addr,bytes(data))
 m.mem_write(GART+0x10,struct.pack('<H',int(bool(i&2))));m.mem_write(SUPPORT+0x78,struct.pack('<I',0 if i&4 else 118));events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,0),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(CREATE,STOP,count=1200);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_X0)==(B if i<512 else 0)
 for addr,data in [(S,ep),(B,eb),(CFG,ec),(ALLOC,ea),(GPU,gpu)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 if i>=512:assert events==[];counts['ring_full']+=1
 else:
  assert events[0][0]=='state_slot' and events[-2:]==[('retain',B),('release',B)];counts['successes']+=1;counts['eligibility_checks']+=len([e for e in events if e[0]=='eligible']);counts['support_resizes']+=len([e for e in events if e[0]=='resize_support'])
report=dict(private_binary_sha256=sha,range=[hex(CREATE),hex(END)],range_sha256=hashlib.sha256(read(CREATE,END-CREATE)).hexdigest(),counts=counts,qualification='Whole concrete createParameterBufferBlock success path512 cases and128 early full-ring returns. Full PM/block/config/allocated-list/GPU byte comparisons; capacity2..16, wrap, occupied slots, both bit47 GART flags, optional mapping eligibility and support resize. External state allocation, metaclass/init, memory descriptor/map object, registration/GART mapping and retain/release explicit services. Index assertions and deeper service-failure unwinds excluded. Ring reserves one slot: capacity1 starts full. No live allocation/cache or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
