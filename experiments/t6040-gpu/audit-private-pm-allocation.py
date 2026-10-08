#!/usr/bin/env python3
"""Execute native PM initial configuration through backing/vector allocations."""
from pathlib import Path
import sys
from private_pm_allocation import allocation_prelude
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END=0xfffffe00089fc624,0xfffffe00089fc948
m.mem_map(0xfffffe00089fc000,0x2000);m.mem_write(START,read(START,END-START));m.mem_map(0xfffffe0007ea2000,4096);m.mem_map(0x220000,0x80000)
GPU,GVT,SHARED,DEVICE,QCFG,INVT=0x260000,0x23a000,0x232000,0x234000,0x236000,0x238000
INIT,MEMORY=0x239000,0x239008;m.mem_write(0xfffffe0007ea24e0,struct.pack('<Q',INVT));m.mem_write(INVT+0xb8,struct.pack('<Q',INIT));m.mem_write(GVT+0x1028,struct.pack('<Q',MEMORY))
results=dict(vector_a=0x240000,vector_b=0x241000,state_array=0x242000,manager_array=0x243000,manager_vector=0x244000,lock_a=0x250000,lock_b=0x251000,main_lock=0x252000)
ALLOC={0xfffffe00089fc6f8:'lock_a',0xfffffe00089fc700:'lock_b',0xfffffe00089fc744:'vector_a',0xfffffe00089fc750:'main_lock',0xfffffe00089fc7c4:'vector_b',0xfffffe00089fc8d0:'state_array',0xfffffe00089fc920:'manager_array',0xfffffe00089fc93c:'manager_vector'}
services=[];memory=0;slot_count=state_count=manager_count=0;original_hook=hook

def allocation_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if address in ALLOC:
  role=ALLOC[address];x0=m.reg_read(c.UC_ARM64_REG_X0);x1=m.reg_read(c.UC_ARM64_REG_X1)
  if role=='vector_a':assert x0==slot_count*8
  elif role=='vector_b':assert x1==slot_count*8
  elif role=='state_array':assert x0==state_count*64
  elif role=='manager_array':assert x0==manager_count*64
  elif role=='manager_vector':assert x1==manager_count*8
  services.append((role,x0,x1));m.reg_write(c.UC_ARM64_REG_X0,results[role]);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address in (0xfffffe00089fc8f8,0xfffffe00089fc914):
  x0=m.reg_read(c.UC_ARM64_REG_X0);assert x0==S+0xd8 or results['state_array']<=x0<results['state_array']+state_count*64
  services.append(('state_init',x0,0));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target in (INIT,MEMORY):
   x0=m.reg_read(c.UC_ARM64_REG_X0);x1=m.reg_read(c.UC_ARM64_REG_X1)
   if target==INIT:assert x0==S;value=1;role='inherited'
   else:assert x0==GPU and x1 in (0x1000,0x2000);value=memory;role='memory_provider'
   services.append((role,x0,x1));m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,allocation_hook)
rng=random.Random(604026);counts=dict(complete_allocation_prelude=0,vector_bytes_cleared=0,state_initializer_calls=0);examples=[]
for i in range(1024):
 slot_count=i%33;state_count=i%8;manager_count=i%33;memory=(manager_count<<17)+(i%131072);gpu=bytearray(0x19000);device=rng.randbytes(0x40);qcfg=rng.randbytes(0x80);original=bytearray(rng.randbytes(0x300));struct.pack_into('<Q',original,0xa8,0)
 for fallback,override,value in [(0x718,0xf528,slot_count),(0x71c,0xf52c,state_count)]:
  struct.pack_into('<I',gpu,fallback,value);struct.pack_into('<I',gpu,override,0 if i&1 else value)
 struct.pack_into('<Q',gpu,0,GVT);struct.pack_into('<Q',gpu,0x11168,0x2000);struct.pack_into('<Q',gpu,0x11180,0 if i&2 else 0x1000)
 m.mem_write(S,bytes(original));m.mem_write(GPU,bytes(gpu));m.mem_write(DEVICE,device);m.mem_write(QCFG,qcfg)
 backing={role:rng.randbytes(0x1000) for role in ['vector_a','vector_b','state_array','manager_array','manager_vector']}
 for role,data in backing.items():m.mem_write(results[role],data)
 services.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,GPU),(c.UC_ARM64_REG_X2,SHARED),(c.UC_ARM64_REG_X3,DEVICE),(c.UC_ARM64_REG_X4,QCFG),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(START,END,count=10000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 expected,n,sc,mc=allocation_prelude(original,gpu,device,qcfg,GPU,SHARED,results,memory);assert (n,sc,mc)==(slot_count,state_count,manager_count)
 actual=bytes(m.mem_read(S,len(original)));assert actual==expected,(i,[(hex(j),actual[j],expected[j]) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 for role,data in backing.items():
  expected_data=bytes(slot_count*8)+data[slot_count*8:] if role in ('vector_a','vector_b') else data
  assert bytes(m.mem_read(results[role],len(data)))==expected_data,(i,role)
 assert bytes(m.mem_read(DEVICE,len(device)))==device and bytes(m.mem_read(QCFG,len(qcfg)))==qcfg and bytes(m.mem_read(GPU,len(gpu)))==gpu
 wanted=['inherited','lock_a','lock_b','vector_a','main_lock','memory_provider','vector_b','state_array']+['state_init']*(state_count+1)+['manager_array','manager_vector'];assert [x[0] for x in services]==wanted
 counts['complete_allocation_prelude']+=1;counts['vector_bytes_cleared']+=slot_count*16;counts['state_initializer_calls']+=state_count+1
 if i<4:examples.append(dict(slot_count=slot_count,state_count=state_count,manager_count=manager_count,service_order=[x[0] for x in services],allocation_sizes=dict(vector_bytes=slot_count*8,state_bytes=state_count*64,manager_bytes=manager_count*64,manager_vector_bytes=manager_count*8)))
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,examples=examples,qualification='Complete native PM initializer allocation/configuration prelude, full object comparison and vector backing clear checks.1024 cases, slot/manager counts0..32 and state count0..7, both override/fallback and memory-provider argument branches. Old vector_a null excludes freeing/replacement path; negative capacity and allocation failures excluded. Inherited init, locks, allocators, memory-size provider and state-init services explicit stubs; actual sizes/arguments/order checked. State-init no-op backing preservation is fixture behavior, not actual initialized state. Remaining resource creation/registration, full PM init/HWPB binding and live mappings excluded. No GPU command or live allocation.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
