#!/usr/bin/env python3
"""Join native PM/HWPB initialization to job binding and packed PB ring publication."""
from pathlib import Path
from private_pb_ring import load_entry
source_native=Path(__file__).with_name('audit-private-pm-native-hwpb.py')
setup_native=source_native.read_text().replace('m.hook_add(u.UC_HOOK_CODE,native_hwpb_hook)','native_handle=m.hook_add(u.UC_HOOK_CODE,native_hwpb_hook)').replace("exec(compile(tail,str(source_full),'exec'))",'')
exec(compile(setup_native,str(source_native),'exec'));m.hook_del(native_handle)
PB,HAL=0xfffffe00089fe1b4,0xfffffe00089d6f54
m.mem_write(PB,read(PB,0x17c));m.mem_map(0xfffffe00089d6000,0x2000);m.mem_write(HAL,read(HAL,0x100))
encoded=struct.unpack('<Q',read(0xfffffe0007eae388+16+0x10f8,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==HAL
RINGRES,RINGOBJ,RINGVT,RINGGET,RING=0x2c7000,0x2c8000,0x2c9000,0x2ca000,0x2cb000
qwrite(GVT+0x10f8,HAL);qwrite(RINGRES+0x60,RINGOBJ);qwrite(RINGOBJ,RINGVT);qwrite(RINGVT+0x138,RINGGET)
job_events=[]
def job_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==HAL:
   assert [m.reg_read(regs[j]) for j in range(4)]==[GPU,STATE,HWM+0x34,request];job_events.append(('native_hal_load',));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,HAL);return
  if target==RINGGET:
   assert m.reg_read(c.UC_ARM64_REG_X0)==RINGOBJ;job_events.append(('ring_cpu_map',));finish_service(address,RING);return
 native_hwpb_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,job_hook)
tail=tail.replace('604029','604033')
tail=tail.replace("struct.pack_into('<Q',gpu,0x5b0,SCHED);", "struct.pack_into('<Q',gpu,0xf928,RINGRES);struct.pack_into('<Q',gpu,0x5b0,SCHED);")
# Execute the actual job load after all independent initializer assertions.
needle='assert new_count==3;'
job_check="""pm_before=bytes(m.mem_read(S,0x300));scene_before=bytes(m.mem_read(CPU60[0],0x1000));ring_before=rng.randbytes(0x1000);m.mem_write(RING,ring_before);request=i%32;job_events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,HWM),(c.UC_ARM64_REG_X2,request),(c.UC_ARM64_REG_X3,3),(c.UC_ARM64_REG_X4,D),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(PB,STOP,count=1000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 ep_job=bytearray(pm_before)
 if not pm_before[0x230]&1:ep_job[0x230]=1;struct.pack_into('<Q',ep_job,0x238,1)
 em_job=bytearray(em);struct.pack_into('<I',em_job,0x30,2);es_job=bytearray(es);struct.pack_into('<I',es_job,0xc,request)
 scene_job=bytearray(scene_before);struct.pack_into('<I',scene_job,0x48,0);ring_job=bytearray(ring_before);ring_job[request*16:request*16+16]=load_entry(ring_before[request*16:request*16+16],es_job,em[0x34:0x44])
 for addr,data in [(S,ep_job),(HWM,em_job),(STATE,es_job),(COUNTER,ec),(CPU60[0],scene_job),(RING,ring_job)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 assert job_events==[('native_hal_load',),('ring_cpu_map',)]
 """
tail=tail.replace(needle,job_check+needle)
tail=tail.replace("args.output.write_text", "report['qualification']='256 joined native complete PM initializer -> native HWPB factory -> native HW reset -> native PM loadPBDesc -> native G16 descriptor-ring load. Whole objects/state/counter/scenes/ring compare independently at both initializer and job boundaries. First-use jobs mode3, request0..31, scene index0; optional initializer old-manager/support-resize and bit47 allocation flags covered. External alloc/init/registration/mapping/translation remain fixtures. No staged prepareAndRetain/descriptor association, live identities/cache visibility, KSM submission or completion proved.'\nreport['job_ranges']=[[hex(PB),hex(PB+0x17c)],[hex(HAL),hex(HAL+0x100)]]\nargs.output.write_text")
exec(compile(tail,str(source_native),'exec'))
