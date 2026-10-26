#!/usr/bin/env python3
"""Run ordinary PM resource-retention and staged-update success path."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END=0xfffffe00089fa7a8,0xfffffe00089fb0d4
m.mem_map(0xfffffe00089fa000,0x2000);m.mem_write(START,read(START,END-START));m.mem_map(0x220000,0x40000)
M,CFG,WRAP,VECTOR,PENDING,PVT,RVT,STAGED=0x220000,0x221000,0x222000,0x223000,0x224000,0x225000,0x226000,0x227000
RES=[0x228000+0x100*i for i in range(9)];SUP=[0x229000+0x100*i for i in range(6)];BLOCK=[0x22a000+0x100*i for i in range(8)]
RETAIN,READY,GEN,PREPARE,CHANGE,DRAIN=0x22b000,0x22b008,0x22b010,0x22b018,0x22b020,0x22b028
for slot,target in [(0x1f0,READY),(0x200,GEN),(0x1c0,PREPARE),(0x1c8,CHANGE)]:m.mem_write(PVT+slot,struct.pack('<Q',target))
DIRTY=0x22b030;m.mem_write(RVT+0x138,struct.pack('<Q',DIRTY))
m.mem_write(RVT+0x20,struct.pack('<Q',RETAIN));m.mem_write(RVT+0x150,struct.pack('<Q',DRAIN))
for obj in RES+BLOCK:m.mem_write(obj,struct.pack('<Q',RVT))
for j,obj in enumerate([RES[7],RES[1],RES[4],RES[3],RES[6]]):m.mem_write(obj+0x28 if obj in (RES[7],RES[6]) else obj+0x48,struct.pack('<Q',SUP[j]))
m.mem_write(RES[7]+0x20,struct.pack('<Q',RES[8]));m.mem_write(WRAP+0x20,struct.pack('<Q',RES[6]));m.mem_write(WRAP+0x28,struct.pack('<Q',SUP[4]))
for j,obj in enumerate(BLOCK):m.mem_write(VECTOR+8*j,struct.pack('<Q',obj));m.mem_write(PENDING+8*j,struct.pack('<Q',obj))
events=[];generations={}
def done(address,value):m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
prep_calls={0xfffffe00089fa7ec:RES[0],0xfffffe00089fa810:RES[2],0xfffffe00089fa8d8:RES[1],0xfffffe00089fa930:RES[4],0xfffffe00089fa990:RES[3],0xfffffe00089faa40:RES[5]}
lock_calls={0xfffffe00089fa834:RES[8],0xfffffe00089fa89c:RES[8],0xfffffe00089fa9e8:RES[6]}
gen_calls={0xfffffe00089fa84c:SUP[0],0xfffffe00089fa8e8:SUP[1],0xfffffe00089fa944:SUP[2],0xfffffe00089fa9a0:SUP[3],0xfffffe00089fa9f8:SUP[4]}
def retain_hook(m,address,size,user):
 x0=m.reg_read(c.UC_ARM64_REG_X0)
 if address in prep_calls:assert x0==prep_calls[address];events.append(('prepare_mapping',x0));done(address,0);return
 if address in lock_calls:assert x0==lock_calls[address];events.append(('prepare_support',x0));done(address,0);return
 if address in gen_calls:assert x0==gen_calls[address];events.append(('generation',x0));done(address,generations[x0]);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==RETAIN:assert x0 in RES;events.append(('retain',x0));value=0
  elif target==READY:assert x0==S and m.reg_read(regs[1])==D;events.append(('prepare_pages',));value=0
  elif target==GEN:assert x0==S;events.append(('generation_other',));value=gen_other
  elif target==DRAIN:assert x0 in BLOCK;events.append(('drain_pending',x0));value=0
  elif target==DIRTY:assert x0 in BLOCK and m.reg_read(regs[1])==2;events.append(('dirty_block',x0));value=0
  elif target==PREPARE:assert x0==S;assert m.reg_read(regs[1]) in BLOCK;events.append(('prepare_block',m.reg_read(regs[1])));value=0
  elif target==CHANGE:assert x0==S and m.reg_read(regs[1])==STAGED;events.append(('stage_update',));value=stage_result
  else:raise AssertionError(hex(target))
  done(address,value);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,retain_hook);rng=random.Random(604034);counts=dict(successes=0,block_calls=0,stage_calls=0,pending_drains=0,dirty_blocks=0)
for i in range(512):
 capacity=8;readidx=i%8;writeidx=(i//8)%8;doneidx=(i//64)%8;pending=i%4;stage_result=int(bool(i&1));gen_other=rng.getrandbits(64)
 pm=bytearray(rng.randbytes(0x300));manager=bytearray(rng.randbytes(0x100));descriptor=rng.randbytes(0x1000);config=rng.randbytes(0x100);staged=rng.randbytes(0x40)
 for off,val in [(0,PVT),(0x20,M),(0x30,RES[3]),(0x38,RES[0]),(0x40,RES[1]),(0x50,RES[5]),(0x58,WRAP),(0x98,CFG),(0x1a0,VECTOR),(0x120,PENDING)]:struct.pack_into('<Q',pm,off,val)
 for off,val in [(0x148,capacity),(0x128,pending),(0x1d0,0 if i&2 else 1)]:struct.pack_into('<I',pm,off,val)
 pm[0x1a8]=int(bool(i&32))
 for off,val in [(0x20,RES[7]),(0x28,RES[8]),(0x88,RES[2]),(0x90,RES[4])]:struct.pack_into('<Q',manager,off,val)
 struct.pack_into('<I',manager,0x80,0 if i&4 else 1);struct.pack_into('<I',manager,0x30,0 if i&8 else 2)
 cfg=bytearray(config);struct.pack_into('<3I',cfg,0,writeidx,readidx,doneidx)
 generations={obj:rng.getrandbits(64) for obj in SUP[:5]};struct.pack_into('<Q',pm,0x1c0,gen_other if i&16 else gen_other^1)
 ep=bytearray(pm);ep[0x1a8]=0;em=bytearray(manager);ed=bytearray(descriptor);est=bytearray(staged)
 # Prepare/retain mapping services do not mutate fixture objects.
 if struct.unpack_from('<I',pm,0x1d0)[0]==0:struct.pack_into('<I',ep,0x1d0,1)
 if struct.unpack_from('<I',manager,0x80)[0]==0:struct.pack_into('<I',em,0x80,1)
 struct.pack_into('<Q',em,0x70,generations[SUP[0]]);struct.pack_into('<Q',em,0x78,generations[SUP[2]])
 for off,obj in [(0x1b0,SUP[1]),(0x1c8,SUP[3]),(0x1b8,SUP[4])]:struct.pack_into('<Q',ep,off,generations[obj])
 struct.pack_into('<Q',ep,0x1c0,gen_other);struct.pack_into('<I',ep,0x128,0)
 for off,obj in [(0xd88,RES[8]),(0xd90,RES[8]),(0xda8,RES[1]),(0xda0,RES[4]),(0xdc0,RES[3]),(0xdb0,RES[6]),(0xdb8,RES[5])]:struct.pack_into('<Q',ed,off,obj)
 # Ring loops: first completed->read only if generation changed; then read->write.
 block_indices=[]
 if not i&16:
  j=doneidx
  while j!=readidx:block_indices.append(j);j=(j+1)%capacity
 j=readidx
 while j!=writeidx:block_indices.append(j);j=(j+1)%capacity
 struct.pack_into('<I',est,0,writeidx);ep[0x28]=1;struct.pack_into('<I',ep,0x140,doneidx)
 do_stage=struct.unpack_from('<I',manager,0x30)[0]==0
 if do_stage and stage_result:ep[0x28]=3;struct.pack_into('<I',ep,0x144,writeidx)
 struct.pack_into('<I',ep,0x6c,1)
 for addr,data in [(S,pm),(M,manager),(D,descriptor),(CFG,cfg),(STAGED,staged)]:m.mem_write(addr,bytes(data))
 initial_pending=b''.join(struct.pack('<Q',obj) for obj in BLOCK);m.mem_write(PENDING,initial_pending);events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,D),(c.UC_ARM64_REG_X2,STAGED),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=5000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==0
 for addr,data in [(S,ep),(M,em),(D,ed),(CFG,cfg),(STAGED,est),(PENDING,bytes(pending*8)+initial_pending[pending*8:])]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr),[(hex(j),m.mem_read(addr+j,1).hex(),data[j]) for j in range(len(data)) if m.mem_read(addr+j,1)[0]!=data[j]][:15])
 assert [x[1] for x in events if x[0]=='prepare_block']==[BLOCK[j] for j in block_indices]
 assert len([x for x in events if x[0]=='drain_pending'])==pending;assert len([x for x in events if x[0]=='stage_update'])==int(do_stage)
 dirty_indices=[]
 if i&32:
  j=doneidx
  while j!=readidx:dirty_indices.append(j);j=(j+1)%capacity
 assert [x[1] for x in events if x[0]=='dirty_block']==[BLOCK[j] for j in dirty_indices]
 counts['dirty_blocks']+=len(dirty_indices)
 counts['successes']+=1;counts['block_calls']+=len(block_indices);counts['pending_drains']+=pending;counts['stage_calls']+=int(do_stage)
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,qualification='Whole ordinary native prepareAndRetain success path512 cases, ring capacity8 all read/write/done indices, changed/unchanged external page generation, pending drains0..3, first/reused mapping preparations, first/reused manager and staged-update success/zero. Full PM/manager/TA descriptor/config/staged/pending bytes compare independently. Mapping preparation, support locks/generation getters, retain, PM prepare-page/get-generation/prepare-block/change services are explicit no-op or return fixtures. Dirty1a8 ring loop included; failure unwinds, external method implementations and live resource registration excluded. No direct loadPBDesc call observed in this method; eventual binding path still to join. No GPU submission.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
