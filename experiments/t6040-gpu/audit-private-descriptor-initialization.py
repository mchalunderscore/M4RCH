#!/usr/bin/env python3
"""Execute full native 3D and TA constructors with declared external services."""
from pathlib import Path
import sys
from private_descriptor_initialization import init_3d,init_ta
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
INIT3D,INITTA=0xfffffe000895da40,0xfffffe0008a213c0
m.mem_write(INIT3D,read(INIT3D,0x250));m.mem_write(PM-12,read(PM-12,12))
m.mem_map(0xfffffe0008a21000,4096);m.mem_write(INITTA,read(INITTA,0x1d4));m.mem_write(0xfffffe0008a21000,read(0xfffffe0008a21000,4096))
GLOBAL=0xfffffe0007ea2000;m.mem_map(GLOBAL,4096)
GVT,QUEUE,TASK,CAST,OWNER,ROOT,DEBUG,DBVT,DVT=0x212000,0x213000,0x214000,0x215000,0x216000,0x217000,0x218000,0x219000,0x21b000
INHERITED,RETAIN=0x21a000,0x21a008
m.mem_write(GLOBAL+0x560,struct.pack('<Q',GVT));m.mem_write(GLOBAL+0x590,struct.pack('<Q',0x1234567890abcdef));m.mem_write(GVT+0x150,struct.pack('<Q',INHERITED));m.mem_write(DEBUG,struct.pack('<Q',DBVT));m.mem_write(DBVT+0x20,struct.pack('<Q',RETAIN))
m.mem_write(CAST+0x538,struct.pack('<Q',OWNER));m.mem_write(OWNER+0x5b0,struct.pack('<Q',ROOT))
# Resolve both native descriptor vtables; do not substitute a size-getter return.
vtables=[0xfffffe0007eb7898,0xfffffe0007eb7560];leaves=[]
for vt in vtables:
 encoded=struct.unpack('<Q',read(vt+16+0x1e0,8))[0];target=0xfffffe0007004000+(encoded&0xffffffff);leaves.append(target)
assert leaves==[0xfffffe000895d5e4,0xfffffe0008a20cb0]
m.mem_map(0xfffffe0008a20000,4096);m.mem_write(leaves[1],read(leaves[1],12))
external_calls=[];allocation=0;parent_result=0;debug=0
DIRECT={0xfffffe000895dabc:'task_cast',0xfffffe000895dafc:'lifecycle',0xfffffe000895db04:'state_init',0xfffffe000895db5c:'zero',0xfffffe0008a214dc:'lifecycle',0xfffffe0008a214e4:'state_init',0xfffffe0008a214ec:'lifecycle',0xfffffe0008a214f4:'state_init',0xfffffe0008a21508:'allocation'}
original_hook=hook

def constructor_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 kind=DIRECT.get(address)
 target=m.reg_read(regs[(word>>5)&31]) if word&0xfffffc00==0xd73f0800 else None
 if target in (INHERITED,RETAIN):kind='inherited' if target==INHERITED else 'retain'
 if kind:
  values=tuple(m.reg_read(reg) for reg in regs[:7]);external_calls.append((kind,values))
  if kind=='task_cast':assert values[0]==TASK;m.reg_write(c.UC_ARM64_REG_X0,CAST)
  elif kind=='zero':assert values[:2]==(D+0x4b0,0x350);m.mem_write(values[0],bytes(values[1]))
  elif kind=='allocation':assert values[:2]==(1,0x1234567890abcdef);m.reg_write(c.UC_ARM64_REG_X0,allocation)
  elif kind=='inherited':assert values[0]==D and values[2]==QUEUE;m.reg_write(c.UC_ARM64_REG_X0,parent_result)
  elif kind=='retain':assert values[0]==debug
  elif kind=='lifecycle':assert values[0]==D
  elif kind=='state_init':assert values[0] in (D+0x1c8,D+0xdc8,D+0xd28)
  m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if target in leaves:
  assert m.reg_read(c.UC_ARM64_REG_X0)==D;m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,constructor_hook)
rng=random.Random(604022);counts=dict(full_3d_constructor=0,full_ta_and_parent_constructor=0,native_self_pointer_getter=0);examples=[]
for i in range(1024):
 is_ta=bool(i&1);debug=DEBUG if i&2 else 0;allocation=rng.getrandbits(64) if i%8 else 0;parent_result=i%2
 original=bytearray(rng.randbytes(0x1800));struct.pack_into('<Q',original,0,DVT);struct.pack_into('<Q',original,0x60,TASK)
 m.mem_write(D,bytes(original));m.mem_write(DVT+0x1e0,struct.pack('<Q',leaves[is_ta]));queue_value=rng.getrandbits(64);m.mem_write(QUEUE+0x550,struct.pack('<Q',queue_value));external_calls.clear()
 payload=0x123456781000;length=rng.getrandbits(32)
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,D),(c.UC_ARM64_REG_X1,0xfeed0000),(c.UC_ARM64_REG_X2,QUEUE),(c.UC_ARM64_REG_X3,TASK),(c.UC_ARM64_REG_X4,payload),(c.UC_ARM64_REG_X5,length),(c.UC_ARM64_REG_X6,debug),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(INITTA if is_ta else INIT3D,STOP,count=4000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==1
 expected=init_3d(original,D,payload,length,debug,queue_value,ROOT)
 if is_ta:expected=init_ta(expected,D,allocation)
 actual=bytes(m.mem_read(D,0x1800));assert actual==expected,(i,[(hex(j),actual[j],expected[j]) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 kinds=[k for k,_ in external_calls];assert kinds==['inherited']+(['retain'] if debug else [])+['task_cast','lifecycle','state_init','zero']+(['lifecycle','state_init','lifecycle','state_init','allocation'] if is_ta else [])
 assert external_calls[0][1]==(D,0xfeed0000,QUEUE,TASK,payload,length,debug)
 counts['full_ta_and_parent_constructor' if is_ta else 'full_3d_constructor']+=1;counts['native_self_pointer_getter']+=1
 if i<4:examples.append(dict(ta=is_ta,debug=bool(debug),external_parent_return=parent_result,constructor_return=1,service_order=kinds,self_pointer=hex(struct.unpack_from('<Q',actual,0x408)[0]),command_limit=struct.unpack_from('<I',actual,0x410)[0],descriptor_sha256=hashlib.sha256(actual).hexdigest()))
report=dict(private_binary_sha256=sha,counts=counts,examples=examples,native_getters=[hex(x) for x in leaves],ranges=[dict(start=hex(x),end=hex(y),sha256=hashlib.sha256(read(x,y-x)).hexdigest()) for x,y in [(INIT3D,0xfffffe000895dc90),(INITTA,0xfffffe0008a21594)]],qualification='Complete native 3D constructor and complete TA constructor including actual 3D parent. Actual vtable1e0 getter executes and returns descriptor+210, not an external fixed-size stub. Full0x1800 byte comparisons with independent model, random prior contents and source scalars. Inherited IOGPU initialization, cast, retain, lifecycle/state helpers, allocation and explicit zero helper are declared service fixtures; zero implements byte clearing, others no-op/explicit returns. Inherited return0/1 is deliberately varied and ignored by these visible constructors; no proof actual failure is usable. Initial vtable and task binding pre-supplied as inherited fixtures. PAC bypassed. No live resource/root/work queue identity, job or GPU submission proved.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
