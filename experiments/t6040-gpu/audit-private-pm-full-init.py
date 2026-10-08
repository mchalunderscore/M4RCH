#!/usr/bin/env python3
"""Execute entire native PM initializer with explicit HWPB/provider services."""
from pathlib import Path
import sys
source=Path(__file__).with_name('audit-private-pm-creation.py')
setup=source.read_text().split('rng=random.Random(604027);')[0].replace('m.hook_add(u.UC_HOOK_CODE,creation_hook)','creation_handle=m.hook_add(u.UC_HOOK_CODE,creation_hook)')
exec(compile(setup,str(source),'exec'));m.hook_del(creation_handle)
END=0xfffffe00089fd3a8;m.mem_write(START,read(START,END-START));m.mem_map(0x2a0000,0x10000)
PMVT,PMREADY,STATS,HWM=0x2a0000,0x2a1000,0x2a1008,0x2a2000
m.mem_write(PMVT+0x150,struct.pack('<Q',PMREADY));m.mem_write(GVT+0x2a0,struct.pack('<Q',STATS))
full_events=[]
def full_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if address==0xfffffe00089fd0e4:
  ptr=m.reg_read(c.UC_ARM64_REG_X0);assert results['manager_array']<=ptr<results['manager_array']+manager_count*64;full_events.append(('manager_state_init',ptr));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address==0xfffffe00089fd2d0:
  assert m.reg_read(c.UC_ARM64_REG_X0)==S;full_events.append(('create_hwpb',));m.mem_write(S+0x20,struct.pack('<Q',HWM));m.reg_write(c.UC_ARM64_REG_X0,1);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target in (PMREADY,STATS):
   x0=m.reg_read(c.UC_ARM64_REG_X0)
   if target==PMREADY:assert x0==S;full_events.append(('pm_ready',));value=1
   else:
    assert x0==GPU and m.reg_read(c.UC_ARM64_REG_X3)==32
    size=m.reg_read(c.UC_ARM64_REG_X2);assert size in [x<<17 for x in (1,2,3)];full_events.append(('statistic',size));value=0
   m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 creation_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,full_hook)
# Reuse the entire independently modeled creation loop; add full-tail expectations.
tail=source.read_text().split('rng=random.Random(604027);',1)[1]
tail='rng=random.Random(604028);'+tail
tail=tail.replace('for i in range(256):','for i in range(128):').replace('joined_pm_creation','complete_pm_initializer')
tail=tail.replace("struct.pack_into('<Q',original,0xa8,0);", "struct.pack_into('<Q',original,0xa8,0);struct.pack_into('<Q',original,0,PMVT);struct.pack_into('<Q',original,0x20,0);qcfg=bytearray(qcfg);struct.pack_into('<3I',qcfg,0x14,1,2,3);")
tail=tail.replace('m.mem_write(addr,data)','m.mem_write(addr,bytes(data))')
tail=tail.replace("for addr,data in [(S,bytes(original))", "gpu[0x11170]=i&1;gpu[0x11171]=(i>>1)&1;struct.pack_into('<Q',gpu,0x11178,0 if i&4 else 0x3000);struct.pack_into('<Q',gpu,0x11160,0x4000)\n for addr,data in [(S,bytes(original))")
tail=tail.replace("services.clear();resource_events.clear();new_count=0;", "services.clear();resource_events.clear();full_events.clear();new_count=0;")
tail=tail.replace("(c.UC_ARM64_REG_SP,STACK)]", "(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]")
tail=tail.replace("m.emu_start(START,END,count=30000);assert m.reg_read(c.UC_ARM64_REG_PC)==END", "m.emu_start(START,STOP,count=50000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==1")
tail=tail.replace("actual=bytes(m.mem_read(S,len(original)));", "for off,v,size in [(0xc0,CPU50[2],8),(0x90,CPU60[2],8),(0x160,i&3,4),(0x164,0,4),(0x168,0,8),(0x14c,1,4),(0x154,1,4),(0x150,0,4),(0x15c,2,4),(0x158,3,4),(0x20,HWM,8)]:expected[off:off+size]=v.to_bytes(size,'little')\n assert [x[0] for x in full_events]==['manager_state_init']*manager_count+['statistic']*3+['pm_ready','create_hwpb']\n actual=bytes(m.mem_read(S,len(original)));")
tail=tail.replace("qualification='Joined actual PM initializer allocation/configuration -> three resource creation/association paths -> registration outputs -> scene-array publication.256 successful positive-count fixtures, both allocation override branches. Full PM object, vectors, scene/scratch buffers compare independently. Resource map50/map60 already exist; lazy creation, allocation/registration failures, remaining PM initializer/HWPB creation excluded. Inherited services, resource alloc/init/mapping and registration are explicit stubs; sizes/argument/object ordering checked. CPU-dereferenced returned pointers differ from FW scene addresses, no universal virtual-slot mapping semantics claimed. No live root/resource/queue registration or GPU command.'", "qualification='Entire native PM initializer returns success with restored stack in128 positive-capacity fixtures. Full PM object/vector/scene/scratch comparisons include final mapped pointers, memory flags, thresholds and HWPB binding. Underlying inherited init, allocators, resource initialization/mapping, registration, statistic/state-init, PM readiness and createNewHWPBManager are explicit services; actual HWPB constructor excluded and stub supplies a manager pointer. Preexisting map50/map60 path only; old manager null, failures and lazy mapping excluded. No live allocation/root/queue identity, GPU submission or valid live parameter manager proved.'")
exec(compile(tail,str(source),'exec'))
