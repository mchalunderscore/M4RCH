#!/usr/bin/env python3
"""Execute complete native PM reset and nested HW parameter-buffer reset."""
from pathlib import Path
import sys
from private_pm_reset import reset_hw,reset_pm
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
RESET,HW,END=0xfffffe00089fb670,0xfffffe00089fb720,0xfffffe00089fb8f4
m.mem_map(0xfffffe00089fb000,4096);m.mem_write(RESET,read(RESET,END-RESET));m.mem_map(0x220000,0x20000)
M,STATE,COUNTER,CONFIG,GPU,SCHED,R1,R2,SUPPORT,LOCK,PVT,SVT,RVT1,RVT2=0x220000,0x222000,0x223000,0x224000,0x226000,0x228000,0x22a000,0x22b000,0x22c000,0x22e000,0x22f000,0x230000,0x231000,0x232000
MAP1,TRANSLATE,MAP2,MAPCONFIG,CHANGE=[0x234000+8*i for i in range(5)]
for obj,vt,slot,target in [(R1,RVT1,0x158,MAP1),(R2,RVT2,0x158,MAP2),(SCHED,SVT,0x2d8,TRANSLATE),(S,PVT,0x208,MAPCONFIG),(S,PVT,0x1c8,CHANGE)]:m.mem_write(obj,struct.pack('<Q',vt));m.mem_write(vt+slot,struct.pack('<Q',target))
m.mem_write(GPU+0x5b0,struct.pack('<Q',SCHED));m.mem_write(SUPPORT+0x20,struct.pack('<Q',R2))
services=[];values=[];original_hook=hook

def reset_hook(m,address,size,user):
 if address in (0xfffffe00089fb68c,0xfffffe00089fb70c):
  assert m.reg_read(c.UC_ARM64_REG_X0)==LOCK;services.append(('lock' if address==0xfffffe00089fb68c else 'unlock',));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);arg=m.reg_read(c.UC_ARM64_REG_X0)
  if target in (MAP1,TRANSLATE,MAP2,MAPCONFIG,CHANGE):
   if target==MAP1:assert arg==R1;value=values[0];services.append(('map1',))
   elif target==TRANSLATE:assert arg==SCHED and m.reg_read(c.UC_ARM64_REG_X1)==values[0] and m.reg_read(c.UC_ARM64_REG_X2)==0;value=values[1];services.append(('translate',))
   elif target==MAP2:assert arg==R2;value=values[2];services.append(('map2',))
   elif target==MAPCONFIG:assert arg==S;value=values[3];services.append(('map_config',))
   else:
    assert arg==S;ptr=m.reg_read(c.UC_ARM64_REG_X1);request=struct.unpack('<I',m.mem_read(ptr,4))[0];assert request==struct.unpack('<I',m.mem_read(CONFIG+4,4))[0];value=0;services.append(('change',request))
   m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,reset_hook)
rng=random.Random(604024);counts=dict(hw_only=0,complete_pm_and_hw=0,optional_change=0);examples=[]
for i in range(1024):
 whole=bool(i&1);enabled=bool(i&2);values=[rng.getrandbits(64) for _ in range(4)]
 pm=bytearray(rng.randbytes(0x300));manager=bytearray(rng.randbytes(0x100));state=rng.randbytes(0x100);counter=rng.randbytes(0x40);config=rng.randbytes(0x100);support_count=rng.getrandbits(64)
 for off,val in [(0,PVT),(0x20,M),(0x80,CONFIG+0x40),(0x98,CONFIG),(0x130,LOCK)]:struct.pack_into('<Q',pm,off,val)
 for off,val in [(0x98,S),(0x48,STATE),(0x50,COUNTER),(0x18,GPU),(0x28,R1),(0x20,SUPPORT)]:struct.pack_into('<Q',manager,off,val)
 struct.pack_into('<I',manager,0x30,int(enabled));m.mem_write(SUPPORT+0x78,struct.pack('<Q',support_count))
 for addr,data in [(S,bytes(pm)),(M,bytes(manager)),(STATE,state),(COUNTER,counter),(CONFIG,config)]:m.mem_write(addr,data)
 services.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S if whole else M),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(RESET if whole else HW,STOP,count=4000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 ep,ec=reset_pm(pm,config) if whole else (bytes(pm),config)
 em,es,ect=reset_hw(manager,ep,state,counter,*values,support_count)
 for addr,expected in [(S,ep),(CONFIG,ec),(M,em),(STATE,es),(COUNTER,ect)]:
  actual=bytes(m.mem_read(addr,len(expected)));assert actual==expected,(i,hex(addr),[(hex(j),actual[j],expected[j]) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 expected_services=([('lock',)] if whole else [])+[('map1',),('translate',),('map2',),('map_config',)]+([('change',struct.unpack_from('<I',config,4)[0])] if whole and enabled else [])+([('unlock',)] if whole else [])
 assert services==expected_services,(i,services,expected_services)
 counts['complete_pm_and_hw' if whole else 'hw_only']+=1;counts['optional_change']+=int(whole and enabled)
 if i<4:examples.append(dict(whole_pm=whole,change_enabled=enabled,service_order=[k[0] for k in services],state_sha256=hashlib.sha256(es).hexdigest()))
report=dict(private_binary_sha256=sha,range=[hex(RESET),hex(END)],range_sha256=hashlib.sha256(read(RESET,END-RESET)).hexdigest(),counts=counts,examples=examples,qualification='Complete native PM reset executes its actual nested HW parameter-buffer reset. Independent full PM, configuration/state, manager, HW state and counter byte comparisons. 512 nested PM+HW and512 HW-only randomized fixtures; optional request both branches. Lock/unlock, resource map158, scheduler translation2d8, PM map208 and optional change1c8 remain explicit provider fixtures; exact order and arguments checked. PAC bypassed. Pre-existing resource allocation/capacity/context semantics not proved. No hardware or GPU command submitted.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
