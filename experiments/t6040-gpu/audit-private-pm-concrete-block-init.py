#!/usr/bin/env python3
"""Run native PM initializer with actual scene setup and actual block creation."""
from pathlib import Path
source_concrete=Path(__file__).with_name('audit-private-pm-concrete-init.py')
setup_concrete=source_concrete.read_text().replace('m.hook_add(u.UC_HOOK_CODE,concrete_hook)','concrete_handle=m.hook_add(u.UC_HOOK_CODE,concrete_hook)').replace("exec(compile(tail,str(source_native),'exec'))",'')
exec(compile(setup_concrete,str(source_concrete),'exec'));m.hook_del(concrete_handle)
BCREATE,WRAPPER=0xfffffe00089febec,0xfffffe00089fef60;m.mem_write(BCREATE,read(BCREATE,WRAPPER+8-BCREATE));qwrite(PMVT+0x1a8,WRAPPER)
MD,IO,BSUPPORT,GART,BREG,BVT,IOVT,MDVT,GARTVT,MVT,BCTX,BNEW,BINIT,MAPGART,ELIGIBLE=[0x2d4000+0x100*i for i in range(15)]
BLOCKALLOC=0x2d6000;BLOCK=0x2d5000
BMETA=0xfffffe000c6e7cb0;qwrite(BMETA,MVT);qwrite(MVT+0xa8,BNEW)
for obj,vt in [(BLOCK,BVT),(MD,MDVT),(IO,IOVT),(GART,GARTVT)]:qwrite(obj,vt)
for vt,slot,target in [(BVT,0xa8,BINIT),(BVT,0x20,RETAIN),(BVT,0x28,RELEASE),(MDVT,0x28,RELEASE),(IOVT,0x28,RELEASE),(IOVT,0x150,MAPGART),(GARTVT,0x170,ELIGIBLE)]:qwrite(vt+slot,target)
qwrite(GART+0x18,BSUPPORT);m.mem_write(GART+0x10,struct.pack('<H',1));m.mem_write(BSUPPORT+0x78,struct.pack('<I',0xffffffff));block_events=[]
def block_init_hook(m,address,size,user):
 x0=m.reg_read(regs[0])
 if address==0xfffffe00089fec64:assert x0==BCTX and m.reg_read(regs[1])==results['manager_array'];block_events.append(('state_slot',));finish_service(address,1);return
 if address==0xfffffe00089fece4:assert [m.reg_read(regs[j]) for j in range(4)]==[0,0x100063,0x20000,0x8000];block_events.append(('memory_descriptor',));finish_service(address,MD);return
 if address==0xfffffe00089fecfc:assert [m.reg_read(regs[j]) for j in range(3)]==[GPU,0,MD];block_events.append(('mapping_object',));finish_service(address,IO);return
 if address==0xfffffe00089fed08:assert x0==IO;block_events.append(('mapping_prepare',));finish_service(address,0);return
 if address==0xfffffe00089fed28:assert x0==SHARED;block_events.append(('registration_provider',));finish_service(address,BREG);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==WRAPPER:assert x0==S;scene_events.append(('create_block',));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,WRAPPER);return
  if target==BNEW:assert x0==BMETA;block_events.append(('new_block',));finish_service(address,BLOCK);return
  if target==BINIT:assert x0==BLOCK;block_events.append(('inherited_init',));finish_service(address,1);return
  if target in (RETAIN,RELEASE) and x0 in (BLOCK,MD,IO):block_events.append(('retain' if target==RETAIN else 'release',x0));finish_service(address,0);return
  if target==ELIGIBLE:assert x0==GART;block_events.append(('eligible',));finish_service(address,1);return
  if target==MAPGART:assert x0==IO and m.reg_read(regs[1])==BREG and m.reg_read(regs[2])==(0x1100000007 if i&1 else 0x500000007);block_events.append(('map_gart',));finish_service(address,GART);return
 concrete_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,block_init_hook)
tail=tail.replace('604036','604038').replace('manager_count=1+i%32','manager_count=2+i%32')
tail=tail.replace("struct.pack_into('<Q',gpu,0x11188,0x40000000);", "struct.pack_into('<Q',gpu,0x140,BCTX);struct.pack_into('<Q',gpu,0x11188,0x40000000);")
tail=tail.replace('scene_events.clear();scene_map=', 'scene_events.clear();block_events.clear();block_original=bytearray(rng.randbytes(0x100));struct.pack_into(\'<Q\',block_original,0,BVT);m.mem_write(BLOCK,bytes(block_original));alloc_original=rng.randbytes(0x1000);m.mem_write(BLOCKALLOC,alloc_original);scene_map=')
tail=tail.replace('expected=bytearray(expected_scene_pm)', "expected=bytearray(expected_scene_pm);struct.pack_into('<I',expected,0x250,1);expected_cfg=bytearray(expected_cfg);struct.pack_into('<I',expected_cfg,0,1)")
tail=tail.replace('assert hnew==2', "expected_block=bytearray(block_original);struct.pack_into('<I',expected_block,0xc,0);struct.pack_into('<Q',expected_block,0x18,GART);assert bytes(m.mem_read(BLOCK,0x100))==bytes(expected_block);assert bytes(m.mem_read(BLOCKALLOC,0x1000))==struct.pack('<Q',GART)+alloc_original[8:]\n assert [x[0] for x in block_events]==['state_slot','new_block','inherited_init','memory_descriptor','mapping_object','mapping_prepare','registration_provider','map_gart','release','release','retain','release']\n assert hnew==2")
tail=tail.replace("args.output.write_text", "report['qualification']='256 complete native PM initializers including actual concrete scene setup, no-argument wrapper plus actual parameter-block creation, native HWPB factory/reset and concrete discard-page getter. Independent full PM/config/manager/block/allocation-vector/scenes/HW-state/counter checks. Capacity2..33 reserves empty slot; positive state count1..8. Both bit47 resource/GART mapping flags and optional extra scene branch. External inherited/resource/memory-descriptor/registration/mapping/state alloc services remain fixtures. No allocator/root/cache visibility, staged job/TA association, KSM submission or completion readiness proved.'\nreport['block_range']=[hex(BCREATE),hex(WRAPPER+8)]\nargs.output.write_text")
try:exec(compile(tail,str(source_concrete),'exec'))
except (u.UcError,AssertionError):
 print('Native failure',hex(m.reg_read(c.UC_ARM64_REG_PC)),hex(m.reg_read(regs[0])),hex(m.reg_read(regs[1])),block_events,scene_events);raise
