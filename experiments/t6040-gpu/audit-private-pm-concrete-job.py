#!/usr/bin/env python3
"""Join concrete PM initialization, block/page preparation and native PB ring load."""
from pathlib import Path
from private_pb_ring import load_entry
source_block=Path(__file__).with_name('audit-private-pm-concrete-block-init.py')
setup_block=source_block.read_text().split('try:exec(compile(tail,')[0].replace('m.hook_add(u.UC_HOOK_CODE,block_init_hook)','block_handle=m.hook_add(u.UC_HOOK_CODE,block_init_hook)')
exec(compile(setup_block,str(source_block),'exec'));m.hook_del(block_handle)
PREPARE,BUILD,PB,HAL=0xfffffe00089fea44,0xfffffe00089fb414,0xfffffe00089fe1b4,0xfffffe00089d6f54
m.mem_write(PREPARE,read(PREPARE,0xb8));m.mem_write(BUILD,read(BUILD,0x244));m.mem_write(PB,read(PB,0x17c));m.mem_map(0xfffffe00089d6000,0x2000);m.mem_write(HAL,read(HAL,0x100))
PAGE_MAP,PAGE_VT,PAGE_BUFFER,STAGED,PRESERVICE,GFWMAP,GETPAGES=0x2d8000,0x2d8100,0x2d9000,0x2da000,0x2d8200,0x2d8208,0x2d8210
RINGRES,RINGOBJ,RINGVT,RINGGET,RING=0x2db000,0x2db100,0x2db200,0x2db300,0x2dc000
qwrite(BVT+0x140,PRESERVICE);qwrite(GARTVT+0x160,GFWMAP);qwrite(PAGE_MAP,PAGE_VT);qwrite(PAGE_VT+0x138,GETPAGES);qwrite(RINGRES+0x60,RINGOBJ);qwrite(RINGOBJ,RINGVT);qwrite(RINGVT+0x138,RINGGET);qwrite(GVT+0x10f8,HAL)
qwrite(PMVT+0x1c0,PREPARE);qwrite(PMVT+0x1c8,BUILD)
job_events=[]
def concrete_job_hook(m,address,size,user):
 x0=m.reg_read(regs[0])
 if address==0xfffffe00089fb44c:assert x0==SUPPORT;job_events.append(('cast_page',));finish_service(address,SUPPORT);return
 if address==0xfffffe00089fb454:assert x0==SUPPORT;job_events.append(('page_context',));finish_service(address,SUPPORT);return
 if address==0xfffffe00089fb490:
  assert [m.reg_read(regs[j]) for j in range(6)]==[SUPPORT,0x1234567890abcdef,0,1,0,0];job_events.append(('create_page_cpu_map',));finish_service(address,PAGE_MAP);return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==PRESERVICE:assert x0==BLOCK;job_events.append(('prepare_block_resource',));finish_service(address,1);return
  if target==GFWMAP:assert x0==GART;job_events.append(('block_address',));finish_service(address,block_address);return
  if target==GETPAGES:assert x0==PAGE_MAP;job_events.append(('page_cpu_map',));finish_service(address,PAGE_BUFFER);return
  if target==HAL:assert [m.reg_read(regs[j]) for j in range(4)]==[GPU,STATE,HWM+0x34,request];job_events.append(('native_hal',));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,HAL);return
  if target==RINGGET:assert x0==RINGOBJ;job_events.append(('ring_cpu_map',));finish_service(address,RING);return
 block_init_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,concrete_job_hook)
tail=tail.replace('604038','604041').replace("struct.pack_into('<Q',gpu,0x140,BCTX);", "struct.pack_into('<Q',gpu,0xf928,RINGRES);struct.pack_into('<Q',gpu,0x140,BCTX);")
tail=tail.replace("struct.pack_into('<4Q',device,16,64,128,8,64)", "struct.pack_into('<4Q',device,16,64,128,8,64);struct.pack_into('<Q',device,0,4)")
needle='assert new_count==3;'
chain="""job_pm=bytes(m.mem_read(S,0x300));job_block=bytes(m.mem_read(BLOCK,0x100));job_pages=bytes(m.mem_read(CPU60[2],0x1000));job_state=bytes(m.mem_read(STATE,0x100));job_manager=bytes(m.mem_read(HWM,0x100));block_address=rng.getrandbits(64);job_events.clear()
 def call_native(fn,x0,x1):
  for reg in regs:m.reg_write(reg,0)
  for reg,val in [(c.UC_ARM64_REG_X0,x0),(c.UC_ARM64_REG_X1,x1),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
  m.emu_start(fn,STOP,count=2000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 call_native(PREPARE,S,BLOCK)
 eb_job=bytearray(job_block);eb_job[0x10]=1;pages_job=bytearray(job_pages);frame=(block_address>>15)&0x1ffffff;struct.pack_into('<I',pages_job,0,frame)
 assert bytes(m.mem_read(BLOCK,0x100))==eb_job and bytes(m.mem_read(CPU60[2],0x1000))==pages_job and bytes(m.mem_read(S,0x300))==job_pm
 page_buffer_before=rng.randbytes(0x1000);m.mem_write(PAGE_BUFFER,page_buffer_before);m.mem_write(STAGED,struct.pack('<I',1));qwrite(KRES+0xa0,0);qwrite(KRES+0x50,GPU)
 call_native(BUILD,S,STAGED);assert m.reg_read(c.UC_ARM64_REG_W0)==1
 expected_page_buffer=struct.pack('<4I',frame,frame+1,frame+2,frame+3)+page_buffer_before[16:]
 es_job=bytearray(job_state);struct.pack_into('<I',es_job,0x34,4);struct.pack_into('<I',es_job,0x54,3);struct.pack_into('<II',es_job,0x3c,1,0);em_job=bytearray(job_manager);em_job[0x34:0x44]=bytes(16)
 for addr,data in [(PAGE_BUFFER,expected_page_buffer),(STATE,es_job),(HWM,em_job),(S,job_pm),(CPU60[2],pages_job)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 ring_before=rng.randbytes(0x1000);m.mem_write(RING,ring_before);request=i%32;scene_before=bytes(m.mem_read(CPU60[0],0x1000))
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,HWM),(c.UC_ARM64_REG_X2,request),(c.UC_ARM64_REG_X3,3),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(PB,STOP,count=1000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 ep_job=bytearray(job_pm)
 if not ep_job[0x230]&1:ep_job[0x230]=1;struct.pack_into('<Q',ep_job,0x238,1)
 struct.pack_into('<I',em_job,0x30,2);struct.pack_into('<I',es_job,0xc,request);ring_job=bytearray(ring_before);ring_job[request*16:request*16+16]=load_entry(ring_before[request*16:request*16+16],es_job,em_job[0x34:0x44]);scene_job=bytearray(scene_before);struct.pack_into('<I',scene_job,0x48,0)
 for addr,data in [(S,ep_job),(HWM,em_job),(STATE,es_job),(RING,ring_job),(CPU60[0],scene_job),(PAGE_BUFFER,expected_page_buffer)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 assert job_events==[('prepare_block_resource',),('block_address',),('cast_page',),('page_context',),('create_page_cpu_map',),('page_cpu_map',),('native_hal',),('ring_cpu_map',)]
 """
tail=tail.replace(needle,chain+needle)
tail=tail.replace("args.output.write_text", "report['qualification']='256 dataflow chains: actual full PM initialization/concrete scene setup/actual block creation/HWPB reset -> actual block preparation -> actual page-list builder -> actual PM job bind and actual G16 packed ring load. Independent whole-byte comparisons at each boundary; actual created block/HW objects reused. One initial block, capacity2..33, staged cursor1/completed0,32KiB page units, four generated page entries, request0..31. Manual orchestration between methods does not prove native caller ordering or full prepareAndRetain; external resource/memory/registration/map/preparation services still fixtures. No live identity/cache visibility or submission/completion readiness.'\nreport['job_methods']=[hex(PREPARE),hex(BUILD),hex(PB),hex(HAL)]\nargs.output.write_text")
exec(compile(tail,str(source_block),'exec'))
