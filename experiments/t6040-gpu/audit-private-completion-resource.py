#!/usr/bin/env python3
"""Check complete native completion-resource allocation/mapping wrapper offline."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-completion-queues.py')
setup=base.read_text().split('m.hook_add(u.UC_HOOK_CODE,completion_hook);rng=')[0]
exec(compile(setup,str(base),'exec'))
START,END=0xfffffe000895fe24,0xfffffe0008960064
for address,size in [(0xfffffe000895f000,0x2000),(0xfffffe0007ea2000,4096),(0xfffffe000c6e7000,4096),(0x260000,0x10000)]:m.mem_map(address,size)
m.mem_write(START,read(START,END-START))
OBJ,MD,DM,FM,TYPE,MVT,OVT,MDVT,DVT,FVT,NEW,CREATE,GET,RETAIN,RELEASE=range(0x260000,0x26f000,0x1000)
META=0xfffffe000c6e75c8
q=lambda address,value:m.mem_write(address,struct.pack('<Q',value))
q(META,MVT);q(MVT+0xa8,NEW);q(OVT+0x28,RELEASE);q(MDVT+0x150,CREATE)
for vt in (DVT,FVT):
 for off,target in [(0x20,RETAIN),(0x28,RELEASE),(0x158,GET)]:q(vt+off,target)
q(0xfffffe0007ea25c0,TYPE);q(TYPE,0x1234567890abcdef)
events=[]
def service(address,value):m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4)
def resource_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0];x0,x1,x2,x3=[m.reg_read(regs[j]) for j in range(4)]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==NEW:assert x0==META;events.append(('new',));value=0 if failure==0 else OBJ
  elif target==CREATE:
   assert x0==MD
   if x2==0x600000087:assert x1==device_context;events.append(('create_device',x2));value=0 if failure==2 else DM
   else:assert x2==0x20900000084 and x1==firmware_context;events.append(('create_firmware',x2));value=0 if failure==4 else FM
  elif target in (RETAIN,RELEASE):assert x0 in (OBJ,DM,FM);events.append(('retain' if target==RETAIN else 'release',x0));value=0
  elif target==GET:assert x0 in (DM,FM);events.append(('address',x0));value=addresses[0 if x0==DM else 1]
  else:raise AssertionError((hex(address),hex(target)))
  service(address,value);return
 if address==0xfffffe000895fea0:
  assert (x0,x1,x2,x3)==(OBJ,GPU,requested,flags|0x23);events.append(('init',requested,flags|0x23));service(address,int(failure!=1));return
 if address==0xfffffe000895feac:assert x0==GPU;events.append(('device_context',));service(address,device_context);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,resource_hook);rng=random.Random(604049)
counts=dict(cases=0,success=0,failures=[0]*6,device_creations=0,firmware_creations=0)
for case in range(1024):
 # Negative service returns and both preexisting-map branches. A failure at
 # a skipped create operation is instead a successful preexisting-map case.
 failure=case%7;requested=[256,512,16384,65536][case%4];flags=rng.getrandbits(32)
 device_context=0x270000;firmware_context=0x271000;existing_d=bool(case&8);existing_f=bool(case&16)
 addresses=[0 if failure==3 else rng.randrange(1,1<<40),0 if failure==5 else rng.randrange(1,1<<40)]
 gpu=bytearray(rng.randbytes(0x1c000));struct.pack_into('<I',gpu,0x18e00,flags)
 obj=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',obj,0,OVT);struct.pack_into('<Q',obj,0x18,firmware_context);struct.pack_into('<Q',obj,0x48,MD)
 struct.pack_into('<QQ',obj,0x50,FM if existing_f else 0,DM if existing_d else 0)
 q(MD,MDVT);q(DM,DVT);q(FM,FVT);q(DM+0x20,device_context)
 original=rng.randbytes(8);m.mem_write(D,original);m.mem_write(OBJ,bytes(obj));m.mem_write(GPU,bytes(gpu));events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(regs[0],GPU),(regs[1],D),(regs[2],requested),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=2000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 expected=[('new',)];expected_obj=bytearray(obj);success=False;failed=failure
 if failure!=0:
  struct.pack_into('<Q',expected_obj,0x10,0x1234567890abcdef);expected.append(('init',requested,flags|0x23))
  if failure!=1:
   expected.append(('device_context',))
   if not existing_d:expected.append(('create_device',0x600000087));counts['device_creations']+=1
   if existing_d or failure!=2:
    if not existing_d:expected += [('retain',DM),('release',DM)];struct.pack_into('<Q',expected_obj,0x58,DM)
    expected.append(('address',DM))
    if addresses[0]:
     if not existing_f:expected.append(('create_firmware',0x20900000084));counts['firmware_creations']+=1
     if existing_f or failure!=4:
      if not existing_f:expected += [('retain',FM),('release',FM)];struct.pack_into('<Q',expected_obj,0x50,FM)
      expected.append(('address',FM));success=bool(addresses[1])
  if not success:expected.append(('release',OBJ))
 assert events==expected,(case,events,expected)
 assert bytes(m.mem_read(GPU,len(gpu)))==gpu and bytes(m.mem_read(OBJ,len(obj)))==expected_obj
 assert bytes(m.mem_read(D,8))==(struct.pack('<Q',OBJ) if success else original)
 assert m.reg_read(c.UC_ARM64_REG_W0)==int(success),(case,events)
 counts['cases']+=1
 if success:counts['success']+=1
 else:counts['failures'][failed]+=1
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,qualification='1024 complete allocSingleKSMCompletionQueue wrapper calls: new/init/mapping creation/address failures, preexisting/fresh device/firmware maps, full object/output/GPU comparisons and exact argument/order. Resource initInner, allocator, context, retain/release and mapping services explicit; no allocation destruction semantics. Resource10 type word, init flags low32GPU18e00|23, resource58 map flags600000087 in device context, resource50 flags20900000084 with resource18 context. Same resource48 provider backs both maps, not two independent allocation identities. Success publishes resource only after both158 addresses nonzero; failures preserve output, release object. No live allocation/cache or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
