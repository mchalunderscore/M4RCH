#!/usr/bin/env python3
"""Join native firmware-data caller to actual completion descriptor builder offline."""
from pathlib import Path
from private_completion_queue import populate
base=Path(__file__).with_name('audit-private-completion-queues.py')
setup=base.read_text().split('rng=random.Random(604046);')[0].replace('m.hook_add(u.UC_HOOK_CODE,completion_hook)','completion_handle=m.hook_add(u.UC_HOOK_CODE,completion_hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(completion_handle)
CALLER,AFTER=0xfffffe00089cd41c,0xfffffe00089cd44c
FW,HW,GVT=0x260000,0x264000,0x268000
m.mem_map(FW,0xc000);m.mem_map(CALLER&~4095,4096)
m.mem_write(CALLER,read(CALLER,AFTER-CALLER));m.mem_write(GVT+0xd68,struct.pack('<Q',START))
encoded=struct.unpack('<Q',read(0xfffffe0007eae388+16+0xd68,8))[0]
assert 0xfffffe0007004000+(encoded&0xffffffff)==START
calls=[]
def attached_hook(m,address,size,user):
 if address==AFTER:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800 and m.reg_read(regs[(word>>5)&31])==START:
  assert m.reg_read(regs[0])==GPU and m.reg_read(regs[1])==HW+0x2620
  calls.append((GPU,HW+0x2620));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,START);return
 completion_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,attached_hook);rng=random.Random(604047)
counts=dict(cases=0,present_descriptors=0,absent_descriptors=0)
for i in range(512):
 presence=i%16;capacity=rng.getrandbits(32)
 gpu=bytearray(rng.randbytes(0x1c000));fw=bytearray(rng.randbytes(0x2000));hw=rng.randbytes(0x4000)
 struct.pack_into('<Q',gpu,0,GVT);struct.pack_into('<I',gpu,0xee58,capacity)
 struct.pack_into('<Q',fw,0x298,GPU);struct.pack_into('<Q',fw,0x2b8,HW)
 mappings=[(rng.getrandbits(64),rng.getrandbits(64)) if presence&(1<<j) else None for j in range(4)]
 for j in range(4):struct.pack_into('<Q',gpu,0x1af70+j*8,RESOURCE[j] if mappings[j] else 0)
 expected=bytearray(hw);expected[0x2620:0x26a0]=populate(hw[0x2620:0x26a0],capacity,mappings)
 m.mem_write(GPU,bytes(gpu));m.mem_write(FW,bytes(fw));m.mem_write(HW,hw);events.clear();calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,value in [(c.UC_ARM64_REG_X0,GPU),(c.UC_ARM64_REG_X19,FW),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,value)
 m.emu_start(CALLER,AFTER,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==AFTER and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 assert bytes(m.mem_read(HW,len(hw)))==expected and bytes(m.mem_read(FW,len(fw)))==fw and bytes(m.mem_read(GPU,len(gpu)))==gpu
 assert calls==[(GPU,HW+0x2620)] and events==[(j,role) for j in range(4) if mappings[j] for role in (0,1)]
 counts['cases']+=1;counts['present_descriptors']+=presence.bit_count();counts['absent_descriptors']+=4-presence.bit_count()
report=dict(private_binary_sha256=sha,caller_range=[hex(CALLER),hex(AFTER)],caller_sha256=hashlib.sha256(read(CALLER,AFTER-CALLER)).hexdigest(),builder_range=[hex(START),hex(END)],vtable_slot='0xd68',hardware_offset='0x2620',counts=counts,qualification='Actual firmware-data caller slice joined to actual G16 completion descriptor builder;512 full hardware/FW/accelerator comparisons, all16 presence masks. FW298 accelerator and FW2b8 hardware are explicit host fixtures; caller requires accelerator already inX0. Placement established at hardware2620..269f, not allocation ownership, live root binding or consumer/retirement. Mapping158 services fixture; no GPU commands.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
