#!/usr/bin/env python3
"""Execute actual concrete PM scene setup and allocation geometry."""
from pathlib import Path
from private_pm_scene_setup import scene_setup
base=Path(__file__).with_name('audit-private-pm-allocation.py');setup=base.read_text().split('rng=random.Random(604026);')[0].replace('m.hook_add(u.UC_HOOK_CODE,allocation_hook)','allocation_handle=m.hook_add(u.UC_HOOK_CODE,allocation_hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(allocation_handle)
SCENE,SCENE_END=0xfffffe00089fefb0,0xfffffe00089ff3a4;m.mem_map(0xfffffe00089ff000,4096);m.mem_write(SCENE,read(SCENE,SCENE_END-SCENE))
PVT,SCONFIG,SCENES,SCVECTOR,BLOCKVECTOR,SCALLOC,RESOURCE,DISCARD,INNER,SUPPORT,RVT,CREATE,RETAIN,ASSOC,MAP= [0x280000+0x1000*i for i in range(15)]
# Existing arena ends2a0000, all these objects fit inside it.
m.mem_write(PVT+0x1a8,struct.pack('<Q',CREATE))
for slot,target in [(0x20,RETAIN),(0x170,ASSOC),(0x160,MAP)]:m.mem_write(RVT+slot,struct.pack('<Q',target))
for obj in (RESOURCE,DISCARD,INNER):m.mem_write(obj,struct.pack('<Q',RVT))
m.mem_write(RESOURCE+0x20,struct.pack('<Q',INNER));m.mem_write(DISCARD+0x20,struct.pack('<Q',INNER));m.mem_write(INNER+0x18,struct.pack('<Q',SUPPORT))
BLOCKS=[0x290000+0x100*j for j in range(16)];events=[];created=0

def scene_hook(m,address,size,user):
 global created
 if address in (0xfffffe00089fefe0,0xfffffe00089ff27c):
  expected_arg=(struct.unpack_from('<I',pm,0x148)[0]*8) if address==0xfffffe00089fefe0 else struct.unpack_from('<I',pm,0x60)[0]
  assert m.reg_read(c.UC_ARM64_REG_X1)==expected_arg;value=BLOCKVECTOR if address==0xfffffe00089fefe0 else SCALLOC;events.append(('allocate',expected_arg));m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address in (0xfffffe00089ff1b4,0xfffffe00089ff304):
  flag=0x5000000003 if i&1 else 0x4000000003;arg_range=1 if i&1 else 5;n=request_size if address==0xfffffe00089ff1b4 else 0x8000
  assert [m.reg_read(regs[j]) for j in range(5)]==[GPU,SHARED,n,flag,arg_range]
  value=RESOURCE if address==0xfffffe00089ff1b4 else DISCARD;events.append(('new_kernel',n));m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address in (0xfffffe00089ff23c,0xfffffe00089ff388):
  assert m.reg_read(c.UC_ARM64_REG_X0)==SUPPORT and m.reg_read(c.UC_ARM64_REG_W1)==118;events.append(('resize_support',));m.mem_write(SUPPORT+0x78,struct.pack('<I',118));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0=m.reg_read(c.UC_ARM64_REG_X0)
  if target==CREATE:assert x0==S and created<len(block_ids);value=BLOCKS[created];events.append(('create_block',block_ids[created]));created+=1
  elif target==MEMORY:assert x0==GPU and m.reg_read(c.UC_ARM64_REG_W1)==0xc000000;value=memory_fallback;events.append(('memory',))
  elif target==RETAIN:assert x0 in (RESOURCE,DISCARD);value=0;events.append(('retain',x0))
  elif target==ASSOC:assert x0 in (RESOURCE,DISCARD) and m.reg_read(c.UC_ARM64_REG_X1)==SHARED;value=0;events.append(('associate',x0))
  elif target==MAP:assert x0==INNER;value=resource_map;events.append(('resource_map',))
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,scene_hook);rng=random.Random(604035);counts=dict(successes=0,blocks=0,scenes=0,support_resizes=0)
for i in range(512):
 slots=1+i%16;states=1+i%8;blocks=i%9;memory_fallback=0x40000000+i*0x8000;resource_map=rng.getrandbits(64);block_ids=list(reversed(range(blocks)));pm=bytearray(rng.randbytes(0x300));gpu=bytearray(0x1b000);config=rng.randbytes(0x100);scenes=rng.randbytes(0x1000);vector=rng.randbytes(0x1000);blockvector=rng.randbytes(0x1000)
 for off,v in [(0,PVT),(0x10,GPU),(0x18,SHARED),(0x98,SCONFIG),(0x88,SCVECTOR),(0x1a0,BLOCKVECTOR),(0x1e8,64),(0x1f0,128),(0x1f8,8),(0x200,64)]:struct.pack_into('<Q',pm,off,v)
 for off,v in [(0x60,states),(0x148,16),(0x14c,blocks//2),(0x150,blocks),(0x118,118),(0x64,(i//8)%4),(0x68,int(bool(i&16)))]:struct.pack_into('<I',pm,off,v)
 struct.pack_into('<Q',gpu,0,GVT);struct.pack_into('<Q',gpu,0x6d0,(i&1)<<47);struct.pack_into('<Q',gpu,0x11188,0 if i&2 else memory_fallback);struct.pack_into('<I',gpu,0x4e4,1+i%4);struct.pack_into('<I',gpu,0x718,slots);struct.pack_into('<I',gpu,0xf528,0 if i&8 else slots);gpu[0xed48]=int(bool(i&4))
 ep,ec,es,stride,request_size=scene_setup(pm,gpu,config,scenes,dict(block_alloc=BLOCKVECTOR,scene_alloc=SCALLOC,resource=RESOURCE,discard_resource=DISCARD),block_ids,resource_map,memory_fallback)
 for addr,data in [(S,pm),(GPU,gpu),(SCONFIG,config),(SCENES,scenes),(SCVECTOR,vector),(BLOCKVECTOR,blockvector)]:m.mem_write(addr,bytes(data))
 for j in range(slots):m.mem_write(SCVECTOR+8*j,struct.pack('<Q',SCENES+j*0x80))
 for j,b in enumerate(block_ids):m.mem_write(BLOCKS[j]+0xc,struct.pack('<I',b))
 m.mem_write(SUPPORT+0x78,struct.pack('<I',0 if i&32 else 118));events.clear();created=0
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(SCENE,STOP,count=5000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==1
 for addr,data in [(S,ep),(SCONFIG,ec),(SCENES,es),(GPU,gpu)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr),[(hex(j),m.mem_read(addr+j,1).hex(),data[j]) for j in range(len(data)) if m.mem_read(addr+j,1)[0]!=data[j]][:15])
 ev=bytearray(blockvector)
 for j,b in enumerate(block_ids):struct.pack_into('<Q',ev,b*8,BLOCKS[j])
 assert bytes(m.mem_read(BLOCKVECTOR,0x1000))==bytes(ev)
 assert created==blocks;counts['successes']+=1;counts['blocks']+=blocks;counts['scenes']+=slots;counts['support_resizes']+=len([e for e in events if e[0]=='resize_support'])
report=dict(private_binary_sha256=sha,range=[hex(SCENE),hex(SCENE_END)],range_sha256=hashlib.sha256(read(SCENE,SCENE_END-SCENE)).hexdigest(),counts=counts,qualification='Complete concrete setupSceneState success path512 cases, independent full PM/config/scenes/block vector comparisons. Both bit47 resource flags, fallback/device-memory branches, optional extra shared scene, multicore sizing branches, mapping support resize, blocks0..8 and scenes1..16/states1..8. Allocators, block creation, resource allocation/association/retain/map remain explicit services. Debug logging bit3 disabled; allocation failures excluded. Not live resources or submission readiness.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
