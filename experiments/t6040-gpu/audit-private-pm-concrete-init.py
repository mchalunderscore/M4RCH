#!/usr/bin/env python3
"""Execute full PM initializer with concrete scene setup and native HWPB reset."""
from pathlib import Path
from private_pm_scene_setup import scene_setup
source_native=Path(__file__).with_name('audit-private-pm-native-hwpb.py')
setup_native=source_native.read_text().replace('m.hook_add(u.UC_HOOK_CODE,native_hwpb_hook)','native_handle=m.hook_add(u.UC_HOOK_CODE,native_hwpb_hook)').replace("exec(compile(tail,str(source_full),'exec'))",'')
exec(compile(setup_native,str(source_native),'exec'));m.hook_del(native_handle)
SCENE,SCENE_END,DISCARD_GET=0xfffffe00089fefb0,0xfffffe00089ff3a4,0xfffffe00089fe3ec
m.mem_map(0xfffffe00089ff000,4096);m.mem_write(SCENE,read(SCENE,SCENE_END-SCENE));m.mem_write(DISCARD_GET,read(DISCARD_GET,0x54));m.mem_map(0x2d0000,0x10000)
BLOCKALLOC,SCALLOC,SRESOURCE,DISCARD,SINNER,DINNER,SSUPPORT,DSUPPORT,SRVT,BLOCK,CREATE,MAPSC,MAPDIS=[0x2d0000+0x100*i for i in range(13)]
qwrite(PMVT+0x150,SCENE);qwrite(PMVT+0x1a8,CREATE);qwrite(PMVT+0x208,DISCARD_GET)
for obj,inner,support in [(SRESOURCE,SINNER,SSUPPORT),(DISCARD,DINNER,DSUPPORT)]:qwrite(obj,SRVT);qwrite(obj+0x20,inner);qwrite(inner,SRVT);qwrite(inner+0x18,support);m.mem_write(support+0x78,struct.pack('<I',0xffffffff))
# Distinct inner mapping objects prevent equating scene and discard addresses.
qwrite(SRVT+0x20,RETAIN);qwrite(SRVT+0x170,ASSOC);qwrite(SRVT+0x160,MAPSC);DVT=0x2d2000;qwrite(DINNER,DVT);qwrite(DVT+0x160,MAPDIS)
m.mem_write(BLOCK+0xc,struct.pack('<I',0));scene_events=[]
def concrete_hook(m,address,size,user):
 if address in (0xfffffe00089fefe0,0xfffffe00089ff27c):
  n=m.reg_read(regs[1]);assert n==(manager_count*8 if address==0xfffffe00089fefe0 else state_count);scene_events.append(('allocate',n));finish_service(address,BLOCKALLOC if address==0xfffffe00089fefe0 else SCALLOC);return
 if address in (0xfffffe00089ff1b4,0xfffffe00089ff304):
  pm_now=bytes(m.mem_read(S,0x300));_,_,_,_,size_request=scene_setup(pm_now,gpu,bytes(0x100),bytes(0x1000),dict(block_alloc=BLOCKALLOC,scene_alloc=SCALLOC,resource=SRESOURCE,discard_resource=DISCARD),[0],scene_map,0)
  assert [m.reg_read(regs[j]) for j in range(5)]==[GPU,SHARED,size_request if address==0xfffffe00089ff1b4 else 0x8000,0x5000000003 if i&1 else 0x4000000003,1 if i&1 else 5]
  scene_events.append(('resource',));finish_service(address,SRESOURCE if address==0xfffffe00089ff1b4 else DISCARD);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0=m.reg_read(regs[0])
  if target in (SCENE,DISCARD_GET):
   assert x0==S
   if target==SCENE:full_events.append(('pm_ready',))
   else:h_events.append(('reset_config',))
   m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
  if target==CREATE:assert x0==S;scene_events.append(('create_block',));finish_service(address,BLOCK);return
  if target in (RETAIN,ASSOC) and x0 in (SRESOURCE,DISCARD):
   if target==ASSOC:assert m.reg_read(regs[1])==SHARED
   scene_events.append(('retain' if target==RETAIN else 'associate',x0));finish_service(address,0);return
  if target in (MAPSC,MAPDIS):assert x0==(SINNER if target==MAPSC else DINNER);finish_service(address,scene_map if target==MAPSC else mapping_values[5]);return
 if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return # autibsp bypass like other PAC fixtures
 native_hwpb_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,concrete_hook)
tail=tail.replace('604029','604036').replace('state_count=i%8','state_count=1+i%8')
tail=tail.replace("struct.pack_into('<Q',gpu,0x5b0,SCHED);", "struct.pack_into('<Q',gpu,0x11188,0x40000000);gpu[0xed48]=int(bool(i&4));struct.pack_into('<Q',gpu,0x5b0,SCHED);")
tail=tail.replace("struct.pack_into('<Q',device,8,alignment)", "struct.pack_into('<Q',device,8,alignment);struct.pack_into('<4Q',device,16,64,128,8,64)")
tail=tail.replace('h_events.clear();hnew=0;', 'h_events.clear();hnew=0;scene_events.clear();scene_map=rng.getrandbits(64);')
# Derive scene setup from the independent pre-setup PM and scene/config models.
needle="struct.pack_into('<Q',expected,0x228,1)"
model="""baseline_scene=bytearray(cpu_backing[CPU60[0]])
 for j in range(slot_count):struct.pack_into('<QQ',baseline_scene,j*0x80,fw_maps[0]+j*stride,fw_maps[1]+j*stride)
 # The HWPB factory increments228 after scene setup; that increment has no setup effect.
 expected_scene_pm,expected_cfg,expected_scene,stride_scene,size_scene=scene_setup(expected,gpu,cpu_backing[CPU60[1]],baseline_scene,dict(block_alloc=BLOCKALLOC,scene_alloc=SCALLOC,resource=SRESOURCE,discard_resource=DISCARD),[0],scene_map,0)
 expected=bytearray(expected_scene_pm)
 """
tail=tail.replace(needle,model+needle)
tail=tail.replace("expected_data=bytes(expected_scenes) if addr==CPU60[0] else", "expected_data=expected_scene if addr==CPU60[0] else expected_cfg if addr==CPU60[1] else")
tail=tail.replace("assert hnew==2", "expected_manager_vector=struct.pack('<Q',BLOCK)+backing['manager_vector'][8:];assert bytes(m.mem_read(results['manager_vector'],0x1000))==expected_manager_vector\n assert [x[0] for x in scene_events]==['allocate','create_block','resource','retain','associate','allocate','resource','retain','associate']\n assert hnew==2")
tail=tail.replace("args.output.write_text", "report['qualification']='256 complete native PM initializers replace virtual150 readiness with actual concrete setupSceneState, then execute native HWPB factory/reset including actual concrete discard-page getter208. Full PM/manager/state/counter/scenes/config/vector byte comparisons. Positive state counts1..8, capacity1..32, one initial block per initializer, both bit47 and optional extra shared-scene branches. Block creation, inherited alloc/resource/mapping/registration/translation services still explicit. Concrete page mapping/block implementation, failure paths, live identities/cache visibility and GPU submission excluded.'\nreport['concrete_scene_range']=[hex(SCENE),hex(SCENE_END)]\nargs.output.write_text")
exec(compile(tail,str(source_native),'exec'))
