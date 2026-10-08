#!/usr/bin/env python3
"""Execute native internal-resource mapping prepare/complete, including unwind."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
PREP,COMP,END=0xfffffe00089ed740,0xfffffe00089ed7c0,0xfffffe00089ed82c
m.mem_map(0xfffffe00089ed000,4096);m.mem_write(PREP,read(PREP,END-PREP));m.mem_map(0x220000,4096)
OBJ,LCK,P0,P1=0x220000,0x220100,0x220200,0x220300
PREPSERVICE,COMPSERVICE,LOCK,UNLOCK=0xfffffe000a8032a8,0xfffffe000a8032b4,0xfffffe000b7b13c4,0xfffffe000b7b27c0
events=[]
def mapping_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfc000000 in (0x94000000,0x14000000):
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+imm*4
  if target in (PREPSERVICE,COMPSERVICE,LOCK,UNLOCK):
   x0=m.reg_read(regs[0]);value=0
   if target==PREPSERVICE:
    assert x0 in (P0,P1);events.append(('prepare',x0));value=failures[x0]
   elif target==COMPSERVICE:assert x0 in (P0,P1);events.append(('complete',x0))
   else:assert x0==LCK;events.append(('lock' if target==LOCK else 'unlock',))
   m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4 if word&0xfc000000==0x94000000 else m.reg_read(c.UC_ARM64_REG_LR));return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,mapping_hook)
def execute(start):
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,OBJ),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(start,STOP,count=500)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(c.UC_ARM64_REG_W0)
rng=random.Random(604043);counts=dict(success=0,first_failure=0,second_failure=0,unwind=0,complete=0,empty_complete=0)
for i in range(1024):
 present=[bool(i&1),bool(i&2)];failures={P0:0xdead if i&4 else 0,P1:0xbeef if i&8 else 0}
 initial=i%5;obj=bytearray(rng.randbytes(0x100));struct.pack_into('<QQ',obj,0x38,initial,LCK)
 struct.pack_into('<QQ',obj,0x50,P0 if present[0] else 0,P1 if present[1] else 0)
 expected=bytearray(obj);expected_events=[];error=False
 if present[0]:expected_events.append(('prepare',P0));error=bool(failures[P0])
 if error:counts['first_failure']+=1
 else:
  if present[1]:expected_events.append(('prepare',P1));error=bool(failures[P1])
  if error:
   counts['second_failure']+=1
   if present[0]:expected_events.append(('complete',P0));counts['unwind']+=1
  else:
   expected_events += [('lock',),('unlock',)];struct.pack_into('<Q',expected,0x38,initial+1);counts['success']+=1
 m.mem_write(OBJ,bytes(obj));events.clear();assert execute(PREP)==(0xe00002be if error else 0)
 assert bytes(m.mem_read(OBJ,len(obj)))==expected and events==expected_events,(i,events,expected_events)
 # Complete only successful prepares; separately test initial zero count.
 if error:m.mem_write(OBJ,bytes(obj));expected=bytearray(obj)
 before=struct.unpack_from('<Q',expected,0x38)[0];expected_events=[('lock',)]
 if before:
  for j,pointer in enumerate((P0,P1)):
   if present[j]:expected_events.append(('complete',pointer))
  struct.pack_into('<Q',expected,0x38,before-1);counts['complete']+=1
 else:counts['empty_complete']+=1
 expected_events.append(('unlock',));events.clear();execute(COMP)
 assert bytes(m.mem_read(OBJ,len(obj)))==expected and events==expected_events,(i,events,expected_events)
report=dict(private_binary_sha256=sha,range=[hex(PREP),hex(END)],range_sha256=hashlib.sha256(read(PREP,END-PREP)).hexdigest(),counts=counts,qualification='Actual native prepareMappings/completeMappings1024 whole resource comparisons, nullable nested50/58, external success/failure combinations, lock/order/counter checks and first-mapping unwind on second failure. External mapping prepare/complete and mutex services remain fixtures; counter is number of successful preparations, not GPU event retirement. Null resource itself is not supported. Completion tested at nonnegative0..5 counts; concurrent execution, real mapping service failure semantics and PAC not tested. No GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
