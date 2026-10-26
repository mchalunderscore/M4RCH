#!/usr/bin/env python3
"""Join actual metrics registration to concrete initialization and native job ring."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-concrete-job.py')
setup=base.read_text().split("exec(compile(tail,str(source_block),'exec'))")[0].replace('m.hook_add(u.UC_HOOK_CODE,concrete_job_hook)','job_handle=m.hook_add(u.UC_HOOK_CODE,concrete_job_hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(job_handle)
METRICS,ME=0xfffffe00089f740c,0xfffffe00089f7890
m.mem_map(0xfffffe00089f7000,4096);m.mem_write(METRICS,read(METRICS,ME-METRICS));m.mem_map(0x2e0000,0x10000)
MP,MB,MR,MASK,MV,MS,M0,M1,MC,ML,MRET,MGET0,MGET1,MGETCPU,MTARGET=[0x2e0000+0x1000*j for j in range(15)]
qwrite(REGOBJ+0x1e0,MP);qwrite(REGOVT+0x220,MTARGET);qwrite(METRICS_RESOURCE,MV);qwrite(METRICS_RESOURCE+0x48,MS)
qwrite(METRICS_RESOURCE+0x50,M0);qwrite(METRICS_RESOURCE+0x58,M1);qwrite(METRICS_RESOURCE+0x60,MC);qwrite(MV+0x20,MRET)
for obj,target,slot in [(M0,MGET0,0x158),(M1,MGET1,0x158),(MC,MGETCPU,0x138)]:qwrite(obj,obj+0x100);qwrite(obj+0x100+slot,target)
m.mem_write(MS+0x78,struct.pack('<I',0xffffffff));metric_events=[]
def metrics_job_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0];x0=m.reg_read(regs[0])
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==REGCOMMIT:
   assert x0==REGOBJ and m.reg_read(regs[1])==S and m.reg_read(regs[2])==S+0x48 and m.reg_read(regs[6])==S+0x50
   resource_events.append(('registration_commit',));metric_events.append(('native_metrics',));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,METRICS);return
  if target in (MRET,MGET0,MGET1,MGETCPU,MTARGET):
   if target==MRET:assert x0==METRICS_RESOURCE;metric_events.append(('retain',));value=0
   elif target==MTARGET:assert x0==REGOBJ;metric_events.append(('target',));value=0
   else:
    j=[MGET0,MGET1,MGETCPU].index(target);assert x0==[M0,M1,MC][j];metric_events.append(('map',j));value=metric_bases[j]
   finish_service(address,value);return
 if word&0xfc000000==0x94000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+imm*4
  if target in (0xfffffe000b7b13c4,0xfffffe000b7b27c0):
   assert x0==ML;metric_events.append(('lock' if target==0xfffffe000b7b13c4 else 'unlock',));finish_service(address,0);return
 concrete_job_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,metrics_job_hook)
needle='services.clear();'
assert needle in tail
tail=tail.replace(needle,"""metric_offset=registration_id*stride;metric_bases=[fw_maps[1]-metric_offset,fw_maps[0]-metric_offset,SCRATCH-metric_offset]
 qwrite(MP+0x10,METRICS_RESOURCE);m.mem_write(MP+0x2c,bytes(4));qwrite(MP+0x38,ML);qwrite(MP+0x40,MB);qwrite(MP+0x48,8);m.mem_write(MP+0x60,struct.pack('<I',64));qwrite(MP+0x88,1);qwrite(MP+0x90,MASK);qwrite(MP+0xa0,stride);qwrite(MASK,1<<registration_id);qwrite(MB,MR);m.mem_write(MR,bytes(4));qwrite(MR+8,METRICS_RESOURCE);metric_events.clear()
 """+needle)
tail=tail.replace('assert new_count==3;',"""assert metric_events==[('native_metrics',),('lock',),('retain',),('map',0),('map',1),('map',2),('unlock',),('target',)]
 assert struct.unpack('<Q',m.mem_read(S+0x50,8))[0]==METRICS_RESOURCE
 assert struct.unpack('<I',m.mem_read(MR,4))[0]==1 and bytes(m.mem_read(MASK,8))==bytes(8) and bytes(m.mem_read(MP+0x88,8))==bytes(8)
 assert new_count==3;""")
tail=tail.replace("args.output.write_text", "report['metrics_method']=hex(METRICS)\nreport['qualification']='256 chains execute actual full PM initialization, actual requestPMPageMetricsBuffer registration with sixth output PM50, concrete scene/block creation, HWPB factory/reset, block/page preparation, PB binding and native packed hardware ring load. Complete parent object/buffer expectations plus native registration bitmap and block count checked. Registration cursor0..31, slots64 existing pool, singleton available bit and caller alignment stride; three map outputs derive per-slot addresses, PM50 retains metrics backing. External underlying allocator/map/retain/lock/registration-provider services remain explicit. Manual orchestration after initializer, no actual caller, live allocation/cache/ownership or GPU submission.'\nargs.output.write_text")
exec(compile(tail,str(base),'exec'))
