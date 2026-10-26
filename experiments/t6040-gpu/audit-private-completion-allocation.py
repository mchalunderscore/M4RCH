#!/usr/bin/env python3
"""Qualify G16 completion allocation caller, size and short-circuit behavior."""
from pathlib import Path
from private_completion_queue import allocation_bytes
base=Path(__file__).with_name('audit-private-completion-queues.py')
setup=base.read_text().split('m.hook_add(u.UC_HOOK_CODE,completion_hook);rng=')[0]
exec(compile(setup,str(base),'exec'))
START,END=0xfffffe00089d712c,0xfffffe00089d71ec;m.mem_write(START,read(START,END-START));ALLOC=0x253000;m.mem_write(MV+0xf50,struct.pack('<Q',ALLOC));events=[]
def allocation_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(regs[(word>>5)&31]);assert target==ALLOC
  index=len(events);assert index<2;slot=GPU+0x1af70+index*16
  assert [m.reg_read(regs[j]) for j in range(3)]==[GPU,slot,allocation_bytes(capacity)]
  value=int(success[index]);events.append((index,value))
  if value:m.mem_write(slot,struct.pack('<Q',RESOURCE[index*2]))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4 if word&0xfffffc00==0xd73f0800 else m.reg_read(c.UC_ARM64_REG_LR));return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,allocation_hook);rng=random.Random(604047);counts=dict(cases=0,first_failure=0,second_failure=0,success=0)
for i in range(1024):
 capacity=[0,1,2,3,4,5,255,256,0xffffffff][i%9] if i<256 else rng.getrandbits(32);success=[bool(i&1),bool(i&2)];gpu=bytearray(rng.randbytes(0x1c000));struct.pack_into('<Q',gpu,0,MV);struct.pack_into('<I',gpu,0xee58,capacity);expected=bytearray(gpu)
 if success[0]:struct.pack_into('<Q',expected,0x1af70,RESOURCE[0])
 if all(success):struct.pack_into('<Q',expected,0x1af80,RESOURCE[2])
 m.mem_write(GPU,bytes(gpu));events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,GPU),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=300);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==int(all(success))
 assert bytes(m.mem_read(GPU,len(gpu)))==expected
 assert events==[(0,int(success[0]))]+([(1,int(success[1]))] if success[0] else [])
 counts['cases']+=1;counts['success' if all(success) else 'second_failure' if success[0] else 'first_failure']+=1
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,qualification='Actual G16 allocKSMCompletionQueues1024 full accelerator comparisons and service argument/order checks. Capacityu32 fromee58; size=(capacity*64+255)&0x7fffffff00. Allocates resource slots1af70 then1af80 only, first failure short-circuits, second failure leaves successful first output; second allocation tail call covered. Zero and maxu32 are arithmetic cases, not valid/recommended live allocations. Underlying allocSingleKSMCompletionQueue remains explicit success/failure fixture; actual unwind/allocation/mapping not qualified. No GPU completion consumer/retirement or commands.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
