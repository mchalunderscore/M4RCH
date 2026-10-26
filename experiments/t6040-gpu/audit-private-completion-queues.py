#!/usr/bin/env python3
"""Run actual native G16 completion queue descriptor population offline."""
from pathlib import Path
from private_completion_queue import populate
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END=0xfffffe00089d76c0,0xfffffe00089d7948
m.mem_map(0xfffffe00089d7000,4096);m.mem_write(START,read(START,END-START));m.mem_map(0x220000,0x40000)
GPU,MV,GET=0x220000,0x240000,0x252000
RESOURCE=[0x241000+j*0x100 for j in range(4)];MAP58=[0x250000+j*0x100 for j in range(4)];MAP50=[0x251000+j*0x100 for j in range(4)]
m.mem_write(MV+0x158,struct.pack('<Q',GET));events=[]
for j in range(4):
 m.mem_write(RESOURCE[j]+0x58,struct.pack('<Q',MAP58[j]));m.mem_write(RESOURCE[j]+0x50,struct.pack('<Q',MAP50[j]))
 for obj in (MAP58[j],MAP50[j]):m.mem_write(obj,struct.pack('<Q',MV))
constants=struct.unpack('<8I',read(0xfffffe000712d8e0,32));assert constants==(64,0,64,1,64,2,64,3)
def completion_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);obj=m.reg_read(regs[0]);assert target==GET
  if obj in MAP58:j=MAP58.index(obj);role=0
  else:j=MAP50.index(obj);role=1
  assert mappings[j] is not None;events.append((j,role));m.reg_write(regs[0],mappings[j][role]);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,completion_hook);rng=random.Random(604046);counts=dict(cases=0,present_descriptors=0,absent_descriptors=0)
for i in range(1024):
 presence=i%16;capacity=rng.getrandbits(32);gpu=bytearray(rng.randbytes(0x1c000));initial=rng.randbytes(0x80);mappings=[(rng.getrandbits(64),rng.getrandbits(64)) if presence&(1<<j) else None for j in range(4)]
 struct.pack_into('<I',gpu,0xee58,capacity)
 for j in range(4):struct.pack_into('<Q',gpu,0x1af70+j*8,RESOURCE[j] if mappings[j] is not None else 0)
 expected=populate(initial,capacity,mappings);m.mem_write(GPU,bytes(gpu));m.mem_write(D,initial);events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,GPU),(c.UC_ARM64_REG_X1,D),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=1000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 assert bytes(m.mem_read(D,len(initial)))==expected and bytes(m.mem_read(GPU,len(gpu)))==gpu
 assert events==[(j,role) for j in range(4) if mappings[j] is not None for role in (0,1)]
 counts['cases']+=1;counts['present_descriptors']+=presence.bit_count();counts['absent_descriptors']+=4-presence.bit_count()
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,constants=list(constants),qualification='Actual G16 populateKSMCompletionQueue1024 full128-byte output and accelerator preservation checks, all16 resource presence masks, randomu32 capacities and mapping158 returns. Four32-byte descriptors:resource58 mapping,resource50 mapping,capacity,64-byte entries,index0..3,zero. Absent descriptors clear only first address and preserve remaining24 bytes. Underlying mapping services remain fixtures; count representability is not valid/live capacity or object identity. Not the72-byte firmware event ring, no completion consumption/retirement/cache or GPU execution.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
