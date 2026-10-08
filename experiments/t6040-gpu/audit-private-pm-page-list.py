#!/usr/bin/env python3
"""Execute actual PM page-list builder and model expanded page indices."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-reset.py');setup=base.read_text().split('rng=random.Random(604024);')[0].replace('m.hook_add(u.UC_HOOK_CODE,reset_hook)','reset_handle=m.hook_add(u.UC_HOOK_CODE,reset_hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(reset_handle)
BUILD,BUILD_END=0xfffffe00089fb414,0xfffffe00089fb658;m.mem_write(BUILD,read(BUILD,BUILD_END-BUILD));m.mem_map(0x240000,0x10000);m.mem_map(0xfffffe0007ea2000,4096)
PAGES,VECTOR,BLOCKS,BUFFER,STAGED,TYPEINFO,MAPOBJ,DESC,MAPVT,GETBUF=0x240000,0x241000,0x242000,0x244000,0x245000,0x246000,0x247000,0x248000,0x249000,0x24a000
m.mem_write(0xfffffe0007ea25c0,struct.pack('<Q',TYPEINFO));m.mem_write(TYPEINFO,struct.pack('<Q',0xabcdef));m.mem_write(MAPOBJ,struct.pack('<Q',MAPVT));m.mem_write(MAPVT+0x138,struct.pack('<Q',GETBUF))
events=[]
def finish(address,value):m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
def page_hook(m,address,size,user):
 x0=m.reg_read(regs[0])
 if address==0xfffffe00089fb44c:assert x0==DESC;events.append(('cast',));finish(address,DESC);return
 if address==0xfffffe00089fb454:assert x0==DESC;events.append(('allocation_context',));finish(address,TYPEINFO);return
 if address==0xfffffe00089fb490:
  assert [m.reg_read(regs[j]) for j in range(6)]==[TYPEINFO,0xabcdef,0,1,0,0];events.append(('create_cpu_mapping',));finish(address,MAPOBJ);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target==GETBUF and x0==MAPOBJ;events.append(('cpu_map',));finish(address,BUFFER);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,page_hook);rng=random.Random(604039);counts=dict(successes=0,page_entries=0,new_cpu_maps=0,empty_lists=0)
for i in range(1024):
 capacity=1+i%16;completed=i%capacity;write=(i//16)%capacity;unit=[0,0x1000,0x8000,0x10000,0x20000,0x40000][i%6];newmap=bool(i&1)
 pm=bytearray(rng.randbytes(0x300));manager=bytearray(rng.randbytes(0x100));state=rng.randbytes(0x100);resource=bytearray(rng.randbytes(0x100));config=bytearray(rng.randbytes(0x100));staged=bytearray(rng.randbytes(0x40));pages=rng.randbytes(0x1000);buffer=rng.randbytes(0x1000);factor=i%4
 for off,v in [(0x20,M),(0x90,PAGES),(0x98,CONFIG),(0x1a0,VECTOR),(0x70,unit),(0x138,(1+i%32)*0x20000)]:struct.pack_into('<Q',pm,off,v)
 struct.pack_into('<I',pm,0x148,capacity);struct.pack_into('<I',pm,0x1d8,factor);struct.pack_into('<Q',manager,0x20,SUPPORT);struct.pack_into('<Q',manager,0x48,STATE)
 struct.pack_into('<Q',resource,0x28,DESC);struct.pack_into('<Q',resource,0x50,GPU);struct.pack_into('<Q',resource,0xa0,0 if newmap else MAPOBJ);struct.pack_into('<I',config,8,completed);struct.pack_into('<I',staged,0,write)
 ids=[(j*7)%capacity for j in range(capacity)] # need not bijective: distinct vector position vs block ID
 for j,b in enumerate(ids):m.mem_write(VECTOR+8*j,struct.pack('<Q',BLOCKS+j*0x100));m.mem_write(BLOCKS+j*0x100+0xc,struct.pack('<I',b))
 es=bytearray(state);em=bytearray(manager);er=bytearray(resource);eb=bytearray(buffer);page_count=((struct.unpack_from('<Q',pm,0x138)[0]>>17)*factor)&0xffffffff
 struct.pack_into('<I',es,0x34,page_count);struct.pack_into('<I',es,0x54,(page_count-1)&0xffffffff);struct.pack_into('<II',es,0x3c,write,completed);em[0x34:0x44]=bytes(16);struct.pack_into('<Q',er,0xa0,MAPOBJ)
 values=[];j=completed
 if unit<=0x20000 and unit>>15:
  while j!=write:
   for k in range(0x20000//unit):
    value=struct.unpack_from('<I',pages,ids[j]*8+k*4)[0]
    values.extend((value+n)&0xffffffff for n in range(unit>>15))
   j=(j+1)%capacity
 for j,value in enumerate(values):struct.pack_into('<I',eb,j*4,value)
 for addr,data in [(S,pm),(M,manager),(STATE,state),(SUPPORT,resource),(CONFIG,config),(STAGED,staged),(PAGES,pages),(BUFFER,buffer)]:m.mem_write(addr,bytes(data))
 m.mem_write(GPU+0x18e00,struct.pack('<I',0));events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,STAGED),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(BUILD,STOP,count=4000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==1
 for addr,data in [(S,pm),(M,em),(STATE,es),(SUPPORT,er),(CONFIG,config),(STAGED,staged),(PAGES,pages),(BUFFER,eb)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 assert [e[0] for e in events]==['cast','allocation_context']+(['create_cpu_mapping'] if newmap else [])+['cpu_map'];counts['successes']+=1;counts['page_entries']+=len(values);counts['new_cpu_maps']+=int(newmap);counts['empty_lists']+=int(not values)
report=dict(private_binary_sha256=sha,range=[hex(BUILD),hex(BUILD_END)],range_sha256=hashlib.sha256(read(BUILD,BUILD_END-BUILD)).hexdigest(),counts=counts,qualification='Complete native buildPageList success path1024 cases, full PM/manager/state/resource/config/staged/source/destination buffers compare. Ring capacity1..16, wrapped cursors, per-block source IDs independent from vector positions, units0/1000/8000/10000/20000/40000, page-count factor0..3 and existing/new CPU mappings. Cast/context/map creation/map pointer services explicit. Invalid index assertions and service-failure returns excluded; zero/oversized unit early-no-copy behavior characterized, not recommended live values. No live mapping/publication/cache or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
