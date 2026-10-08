#!/usr/bin/env python3
"""Join native PM allocation, resource association, registration and scene creation."""
from pathlib import Path
import sys
from private_pm_allocation import allocation_prelude
base=Path(__file__).with_name('audit-private-pm-allocation.py');prefix=base.read_text().split('rng=random.Random(604026);')[0].replace('m.hook_add(u.UC_HOOK_CODE,allocation_hook)','allocation_handle=m.hook_add(u.UC_HOOK_CODE,allocation_hook)')
exec(compile(prefix,str(base),'exec'));m.hook_del(allocation_handle)
END=0xfffffe00089fd040;m.mem_write(START,read(START,END-START))
META=0xfffffe000c6e75c8;m.mem_map(META&~4095,4096);MVT,TINFO=0x23c000,0x23e000;NEW=0x239010
m.mem_write(META,struct.pack('<Q',MVT));m.mem_write(MVT+0xa8,struct.pack('<Q',NEW));m.mem_write(0xfffffe0007ea25c0,struct.pack('<Q',TINFO));m.mem_write(TINFO,struct.pack('<Q',0x1234567890abcdef))
RES=[0x280000,0x281000,0x282000];MAPOBJ=[0x283000,0x284000,0x285000];CPUOBJ=[0x286000,0x287000,0x288000];MAPVT,CPUVT=0x289000,0x28a000
MAPGET,CPUGET=0x239018,0x239020;REGP,REGVT,REGOBJ,REGOVT,REGREQ,REGCOMMIT=0x292000,0x293000,0x294000,0x295000,0x239028,0x239030
CPU50=[0x28b000,0x28c000,0x28d000];CPU60=[0x28e000,0x28f000,0x290000];SCRATCH=0x296000
METRICS_RESOURCE=0x297000
m.mem_write(MAPVT+0x158,struct.pack('<Q',MAPGET));m.mem_write(CPUVT+0x138,struct.pack('<Q',CPUGET))
for i,r in enumerate(RES):
 m.mem_write(r+0x50,struct.pack('<Q',MAPOBJ[i]));m.mem_write(r+0x60,struct.pack('<Q',CPUOBJ[i]));m.mem_write(MAPOBJ[i],struct.pack('<Q',MAPVT));m.mem_write(CPUOBJ[i],struct.pack('<Q',CPUVT))
m.mem_write(REGP,struct.pack('<Q',REGVT));m.mem_write(REGVT+0x218,struct.pack('<Q',REGREQ));m.mem_write(REGOBJ,struct.pack('<Q',REGOVT));m.mem_write(REGOVT+0x228,struct.pack('<Q',REGCOMMIT))
constant=read(0xfffffe000712dee0,16);constant70,constant78=struct.unpack('<QQ',constant)
new_count=0;resource_events=[];fw_maps=[];registration_id=0

def creation_hook(m,address,size,user):
 global new_count
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if address in (0xfffffe00089fc9a8,0xfffffe00089fcb98,0xfffffe00089fcd88):
  values=tuple(m.reg_read(x) for x in regs[:4]);index=[0xfffffe00089fc9a8,0xfffffe00089fcb98,0xfffffe00089fcd88].index(address)
  expected_sizes=[0x40|(slot_count<<7),0x80,constant78*manager_count]
  assert values[:3]==(RES[index],GPU,expected_sizes[index]);assert values[3]==0x63
  resource_events.append(('init_resource',index,expected_sizes[index]));m.reg_write(c.UC_ARM64_REG_X0,1);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address==0xfffffe00089fceb4:
  assert m.reg_read(c.UC_ARM64_REG_X0)==SHARED;resource_events.append(('registration_provider',));m.reg_write(c.UC_ARM64_REG_X0,REGP);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0=m.reg_read(c.UC_ARM64_REG_X0)
  if target in (NEW,MAPGET,CPUGET,REGREQ,REGCOMMIT):
   if target==NEW:assert x0==META and new_count<3;value=RES[new_count];resource_events.append(('new_resource',new_count));new_count+=1
   elif target==MAPGET:
    index=MAPOBJ.index(x0);value=CPU50[index];resource_events.append(('map50_get158',index))
   elif target==CPUGET:
    index=CPUOBJ.index(x0);value=CPU60[index];resource_events.append(('map60_get138',index))
   elif target==REGREQ:assert x0==REGP;assert m.reg_read(c.UC_ARM64_REG_X1)==struct.unpack_from('<Q',qcfg,0x28)[0];value=REGOBJ;resource_events.append(('registration_request',))
   else:
    assert x0==REGOBJ;assert m.reg_read(c.UC_ARM64_REG_X1)==S;assert m.reg_read(c.UC_ARM64_REG_X2)==S+0x48;assert m.reg_read(regs[6])==S+0x50
    for reg,v in [(3,SCRATCH),(4,fw_maps[1]),(5,fw_maps[0])]:m.mem_write(m.reg_read(regs[reg]),struct.pack('<Q',v))
    struct.pack_into('<I',expected_registration,0,registration_id);m.mem_write(S+0x48,bytes(expected_registration));m.mem_write(S+0x50,struct.pack('<Q',METRICS_RESOURCE));resource_events.append(('registration_commit',));value=1
   m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address==0xfffffe00089fcf44:
  x0=m.reg_read(c.UC_ARM64_REG_X0);n=m.reg_read(c.UC_ARM64_REG_W1);assert x0==SCRATCH and n==slot_count*stride;m.mem_write(SCRATCH,bytes(n));resource_events.append(('clear_registration_scratch',n));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 allocation_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,creation_hook)
rng=random.Random(604027);counts=dict(joined_pm_creation=0,created_resources=0,scene_records=0);examples=[]
for i in range(256):
 slot_count=1+i%32;state_count=i%8;manager_count=1+i%32;alignment=[4,8,16,32][i%4];stride=(alignment+3)&-alignment;memory=(manager_count<<17)+(i%131072);registration_id=i%32;fw_maps=[0xffffffa000000000,0xffffffb000000000]
 gpu=bytearray(0x19000);device=bytearray(rng.randbytes(0x40));qcfg=rng.randbytes(0x80);original=bytearray(rng.randbytes(0x300));struct.pack_into('<Q',original,0xa8,0);struct.pack_into('<Q',device,8,alignment)
 for fallback,override,value in [(0x718,0xf528,slot_count),(0x71c,0xf52c,state_count)]:struct.pack_into('<I',gpu,fallback,value);struct.pack_into('<I',gpu,override,0 if i&1 else value)
 struct.pack_into('<Q',gpu,0,GVT);struct.pack_into('<Q',gpu,0x11168,0x2000);struct.pack_into('<Q',gpu,0x11180,0 if i&2 else 0x1000)
 for addr,data in [(S,bytes(original)),(GPU,bytes(gpu)),(DEVICE,bytes(device)),(QCFG,qcfg)]:m.mem_write(addr,data)
 backing={role:rng.randbytes(0x1000) for role in ['vector_a','vector_b','state_array','manager_array','manager_vector']}
 for role,data in backing.items():m.mem_write(results[role],data)
 cpu_backing={addr:rng.randbytes(0x1000) for addr in CPU50+CPU60+[SCRATCH]}
 for addr,data in cpu_backing.items():m.mem_write(addr,data)
 services.clear();resource_events.clear();new_count=0;expected_registration=bytearray(4)
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,GPU),(c.UC_ARM64_REG_X2,SHARED),(c.UC_ARM64_REG_X3,DEVICE),(c.UC_ARM64_REG_X4,QCFG),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(START,END,count=30000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 expected,_,_,_=allocation_prelude(original,gpu,device,qcfg,GPU,SHARED,results,memory);expected=bytearray(expected)
 for off,v in [(0x38,RES[0]),(0x40,RES[1]),(0x30,RES[2]),(0x50,METRICS_RESOURCE),(0xb8,CPU50[0]+slot_count*0x80),(0xc8,CPU50[1]),(0x98,CPU60[1]),(0xa0,CPU50[1]+0x40),(0x80,CPU60[1]+0x40)]:struct.pack_into('<Q',expected,off,v)
 struct.pack_into('<I',expected,0x48,registration_id);expected[0x70:0x80]=constant
 actual=bytes(m.mem_read(S,len(original)));assert actual==expected,(i,[(hex(j),actual[j],expected[j]) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 for role,baseptr in [('vector_a',CPU50[0]),('vector_b',CPU60[0])]:
  expected_vector=b''.join(struct.pack('<Q',baseptr+j*0x80) for j in range(slot_count))+backing[role][slot_count*8:];assert bytes(m.mem_read(results[role],0x1000))==expected_vector
 expected_scenes=bytearray(cpu_backing[CPU60[0]])
 for j in range(slot_count):struct.pack_into('<QQ',expected_scenes,j*0x80,fw_maps[0]+j*stride,fw_maps[1]+j*stride)
 for addr,data in cpu_backing.items():
  expected_data=bytes(expected_scenes) if addr==CPU60[0] else bytes(slot_count*stride)+data[slot_count*stride:] if addr==SCRATCH else data
  assert bytes(m.mem_read(addr,0x1000))==expected_data,(i,hex(addr))
 assert new_count==3;counts['joined_pm_creation']+=1;counts['created_resources']+=3;counts['scene_records']+=slot_count
 if i<4:examples.append(dict(slot_count=slot_count,manager_count=manager_count,alignment=alignment,resource_sizes=[0x40|(slot_count<<7),0x80,constant78*manager_count],resource_events=resource_events.copy(),descriptor_sha256=hashlib.sha256(actual).hexdigest()))
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,constant70=hex(constant70),constant78=hex(constant78),examples=examples,qualification='Joined actual PM initializer allocation/configuration -> three resource creation/association paths -> registration outputs -> scene-array publication.256 successful positive-count fixtures, both allocation override branches. Full PM object, vectors, scene/scratch buffers compare independently. Resource map50/map60 already exist; lazy creation, allocation/registration failures, remaining PM initializer/HWPB creation excluded. Inherited services, resource alloc/init/mapping and registration are explicit stubs; sizes/argument/object ordering checked. CPU-dereferenced returned pointers differ from FW scene addresses, no universal virtual-slot mapping semantics claimed. No live root/resource/queue registration or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts,'PM70/78',hex(constant70),hex(constant78))
