#!/usr/bin/env python3
"""Execute complete native PM initialization, including HWPB factory and reset."""
from pathlib import Path
from private_pm_reset import reset_hw
source_full=Path(__file__).with_name('audit-private-pm-full-init.py')
setup_full=source_full.read_text().replace('m.hook_add(u.UC_HOOK_CODE,full_hook)','full_handle=m.hook_add(u.UC_HOOK_CODE,full_hook)').replace('if address==0xfffffe00089fd2d0:', 'if address==0:').replace("exec(compile(tail,str(source),'exec'))",'')
exec(compile(setup_full,str(source_full),'exec'));m.hook_del(full_handle)
FACTORY,FACTORY_END,HW=0xfffffe00089fd3a8,0xfffffe00089fda5c,0xfffffe00089fb720
m.mem_write(FACTORY,read(FACTORY,FACTORY_END-FACTORY));m.mem_map(0xfffffe00089fb000,4096);m.mem_write(HW,read(HW,0x1d4));m.mem_map(0x2b0000,0x20000)
HMETA=0xfffffe000c6e7be8
HMVT,HVT,KRES,KVT,SUPPORT,SCHED,SVT,FIRST,SECOND,RVT,STATE,COUNTER= [0x2b0000+0x1000*i for i in range(12)]
HRES=[0x2bc000,0x2bd000];HMAP=[0x2be000,0x2bf000];HCPU=[0x2c0000,0x2c1000];HMAPVT,HCPUVT=0x2c2000,0x2c3000
HNEW,RETAIN,RELEASE,ASSOC,CASTMAP,MAPFIRST,MAPSECOND,TRANSLATE,MAPCONFIG,HMAPGET,HCPUGET=[0x2c4000+8*i for i in range(11)]
def qwrite(a,v):m.mem_write(a,struct.pack('<Q',v))
qwrite(HMETA,HMVT);qwrite(HMVT+0xa8,HNEW)
for vt,slot,target in [(HVT,0x20,RETAIN),(HVT,0x28,RELEASE),(KVT,0x20,RETAIN),(KVT,0x170,ASSOC),(SVT,0x240,CASTMAP),(SVT,0x2d8,TRANSLATE),(RVT,0x158,MAPFIRST),(PMVT,0x208,MAPCONFIG),(HMAPVT,0x158,HMAPGET),(HCPUVT,0x138,HCPUGET)]:qwrite(vt+slot,target)
# The second reset mapping uses a different object and service.
OLD=0x2c6000;qwrite(OLD,HVT)
RVT2=0x2c5000;qwrite(RVT2+0x158,MAPSECOND)
for obj,vt in [(KRES,KVT),(SCHED,SVT),(FIRST,RVT),(SECOND,RVT2)]:qwrite(obj,vt)
qwrite(KRES+0x28,SUPPORT);qwrite(KRES+0x20,SECOND)
for j in range(2):
 qwrite(HRES[j]+0x50,HMAP[j]);qwrite(HRES[j]+0x60,HCPU[j]);qwrite(HMAP[j],HMAPVT);qwrite(HCPU[j],HCPUVT)
h_events=[];hnew=0;mapping_values=[]
def finish_service(address,value):m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
def native_hwpb_hook(m,address,size,user):
 global hnew
 word=struct.unpack('<I',m.mem_read(address,4))[0];x0=m.reg_read(c.UC_ARM64_REG_X0)
 if address==0xfffffe00089fd2d0:full_events.append(('create_hwpb',)) # actual BL executes
 if address==0xfffffe00089fd470:
  assert [m.reg_read(regs[j]) for j in range(5)]==[GPU,SHARED,(manager_count*struct.unpack_from('<Q',device,0)[0]*4)&((1<<64)-1),0x5000000003 if i&1 else 0x4000000003,1 if i&1 else 5]
  h_events.append(('kernel_resource',));finish_service(address,KRES);return
 if address==0xfffffe00089fd4f4:
  assert x0==SUPPORT;requested=m.reg_read(c.UC_ARM64_REG_W1);assert requested==struct.unpack_from('<I',qcfg,0x28)[0];m.mem_write(SUPPORT+0x78,struct.pack('<I',requested));h_events.append(('resize_support',));finish_service(address,0);return
 if address==0xfffffe00089fd514:
  assert x0==SUPPORT and m.reg_read(regs[1])==0xfffffe000c6e5ed0;h_events.append(('cast',));finish_service(address,SUPPORT);return
 if address in (0xfffffe00089fd5c8,0xfffffe00089fd7ac):
  j=int(address==0xfffffe00089fd7ac);assert [m.reg_read(regs[k]) for k in range(4)]==[HRES[j],GPU,4 if j else 0xc0,0x63]
  h_events.append(('internal_init',j));finish_service(address,1);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if address==0xfffffe00089fd424:
   assert target==INIT and x0==HWM;h_events.append(('inherited_hwm',));finish_service(address,1);return
  if address in (0xfffffe00089fd590,0xfffffe00089fd77c):
   assert target==NEW and x0==META and hnew<2;value=HRES[hnew];h_events.append(('new_internal',hnew));hnew+=1;finish_service(address,value);return
  if target in (HNEW,RETAIN,RELEASE,ASSOC,CASTMAP,MAPFIRST,MAPSECOND,TRANSLATE,MAPCONFIG,HMAPGET,HCPUGET):
   if target==HNEW:assert x0==HMETA;value=HWM;h_events.append(('new_hwm',))
   elif target in (RETAIN,RELEASE):assert x0 in (HWM,KRES,OLD);value=0;h_events.append(('retain' if target==RETAIN else 'release',x0))
   elif target==ASSOC:assert x0==KRES and m.reg_read(regs[1])==SHARED;value=0;h_events.append(('associate',))
   elif target==CASTMAP:assert [m.reg_read(regs[k]) for k in range(4)]==[SCHED,SUPPORT,9,0];value=FIRST;h_events.append(('scheduler_map',))
   elif target in (HMAPGET,HCPUGET):
    j=(HMAP if target==HMAPGET else HCPU).index(x0);value=mapping_values[j] if target==HMAPGET else [STATE,COUNTER][j];h_events.append(('map50' if target==HMAPGET else 'map60',j))
   elif target==MAPFIRST:assert x0==FIRST;value=mapping_values[2];h_events.append(('reset_first',))
   elif target==MAPSECOND:assert x0==SECOND;value=mapping_values[4];h_events.append(('reset_second',))
   elif target==TRANSLATE:assert [m.reg_read(regs[k]) for k in range(3)]==[SCHED,mapping_values[2],0];value=mapping_values[3];h_events.append(('reset_translate',))
   else:assert x0==S;value=mapping_values[5];h_events.append(('reset_config',))
   finish_service(address,value);return
 full_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,native_hwpb_hook)
# Keep the independent full-PM/vector/scene expectations from the earlier audit.
tail=tail.replace('604028','604029').replace('range(128)','range(256)')
tail=tail.replace("services.clear();resource_events.clear();full_events.clear();new_count=0;", "services.clear();resource_events.clear();full_events.clear();new_count=0;h_events.clear();hnew=0;")
tail=tail.replace('for addr,data in [(S,bytes(original))', "struct.pack_into('<Q',original,0x20,OLD if i&2 else 0);struct.pack_into('<Q',gpu,0x5b0,SCHED);struct.pack_into('<Q',gpu,0x6d0,(i&1)<<47)\n for addr,data in [(S,bytes(original))")
needle='m.emu_start(START,STOP,count=50000);'
prepare="""manager_original=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',manager_original,0,HVT);struct.pack_into('<I',manager_original,0x30,0)
 m.mem_write(HWM,bytes(manager_original));state_original=rng.randbytes(0x100);counter_original=rng.randbytes(0x40);m.mem_write(STATE,state_original);m.mem_write(COUNTER,counter_original)
 support_count=rng.getrandbits(64);qwrite(KRES+0x78,support_count);qwrite(SUPPORT+0x78,0 if i&4 else 0xffffffff);mapping_values=[rng.getrandbits(64) or 1 for _ in range(6)]
 """
tail=tail.replace(needle,prepare+needle)
tail=tail.replace("actual=bytes(m.mem_read(S,len(original)));", "struct.pack_into('<Q',expected,0x228,1)\n actual=bytes(m.mem_read(S,len(original)));")
needle="assert new_count==3;"
check="""assert hnew==2
 expected_manager=bytearray(manager_original)
 for off,v,n in [(0x98,S,8),(0x18,GPU,8),(0x68,(1<<64)-1,8),(0x10,0xffffffff,4),(0x20,KRES,8),(0x70,0,8),(0x28,FIRST,8),(0x80,0,4),(0x88,HRES[0],8),(0x90,HRES[1],8),(0x48,STATE,8),(0x58,mapping_values[0],8),(0x50,COUNTER,8),(0x60,mapping_values[1],8)]:expected_manager[off:off+n]=v.to_bytes(n,'little')
 em,es,ec=reset_hw(expected_manager,expected,state_original,counter_original,*mapping_values[2:],support_count)
 for addr,data in [(HWM,em),(STATE,es),(COUNTER,ec)]:
  actual_data=bytes(m.mem_read(addr,len(data)));assert actual_data==data,(i,hex(addr),[(hex(j),actual_data[j],data[j]) for j in range(len(data)) if actual_data[j]!=data[j]][:20])
 assert [e[0] for e in h_events]==(['release'] if i&2 else [])+['new_hwm','inherited_hwm','kernel_resource','retain','associate']+(['resize_support'] if i&4 else [])+['cast','scheduler_map','new_internal','internal_init','map50','map60','map50','map60','new_internal','internal_init','map50','map60','map50','map60','retain','reset_first','reset_translate','reset_second','reset_config','release'],h_events
 """
tail=tail.replace(needle,check+needle)
tail=tail.replace("report=dict(","report=dict(reset_range_sha256=hashlib.sha256(read(HW,0x1d4)).hexdigest(),hwpb_range=[hex(FACTORY),hex(FACTORY_END)],hwpb_range_sha256=hashlib.sha256(read(FACTORY,FACTORY_END-FACTORY)).hexdigest(),")
tail=tail.replace("args.output.write_text", "report['qualification']='Complete actual native PM initializer including native HWPB allocation factory and nested native HW reset,256 successful cases, full PM/manager/state/counter/vector/scene bytes and external service order/arguments checked. Both GPU bit47 resource-flag branches. Allocators, inherited/resource initialization, preexisting mapping services, registration, scheduler translation and PM configuration are explicit fixtures. Initializer old-manager release and factory support-resize branches each covered128 times; factory old-manager replacement excluded; lazy mappings, failures and live identities excluded. No live GPU command or rendering readiness proved.'\nargs.output.write_text")
exec(compile(tail,str(source_full),'exec'))
