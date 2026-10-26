#!/usr/bin/env python3
"""Check native parameter-buffer job binding and reuse bookkeeping."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-reset.py')
setup=base.read_text().split('rng=random.Random(604024);')[0].replace('m.hook_add(u.UC_HOOK_CODE,reset_hook)','reset_handle=m.hook_add(u.UC_HOOK_CODE,reset_hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(reset_handle)
LOAD,LOAD_END=0xfffffe00089fe1b4,0xfffffe00089fe330;m.mem_write(LOAD,read(LOAD,LOAD_END-LOAD))
GVT,PROVIDER,VECTOR,SCENES=0x235000,0x237000,0x238000,0x239000
m.mem_write(GPU,struct.pack('<Q',GVT));m.mem_write(GVT+0x10f8,struct.pack('<Q',PROVIDER))
events=[]
def pb_hook(m,address,size,user):
 if address in (0xfffffe00089fe200,0xfffffe00089fe300):events.append(('generation_assert',));m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target==PROVIDER
  args_seen=[m.reg_read(regs[j]) for j in range(4)];assert args_seen==[GPU,STATE,M+0x34,request];events.append(('prepare_state',))
  m.reg_write(c.UC_ARM64_REG_X0,0);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,pb_hook)
rng=random.Random(604030);counts=dict(successful_load=0,provider_calls=0,asserted_generation_mismatch=0);examples=[]
for i in range(1024):
 mode=i%4;first=not bool(i&4);generation_check=bool(i&8);active=bool(i&16);mismatch=bool(i&32);index=i%16;request=rng.getrandbits(32)
 pm=bytearray(rng.randbytes(0x300));manager=bytearray(rng.randbytes(0x100));state=rng.randbytes(0x100);scenes=rng.randbytes(0x1000);gpu=bytearray(rng.randbytes(0x2000));struct.pack_into('<Q',gpu,0,GVT);gpu[0x478]=int(generation_check)
 for off,val in [(0x10,GPU),(0x20,M),(0x88,VECTOR),(0x228,123),(0x238,122 if mismatch else 123)]:struct.pack_into('<Q',pm,off,val)
 struct.pack_into('<I',pm,0x2c,index);pm[0x230]=int(active)
 struct.pack_into('<Q',manager,0x48,STATE);usage=0 if first else 3+i;struct.pack_into('<I',manager,0x30,usage)
 for j in range(16):m.mem_write(VECTOR+8*j,struct.pack('<Q',SCENES+j*0x80))
 for addr,data in [(S,bytes(pm)),(M,bytes(manager)),(STATE,state),(SCENES,scenes),(GPU,bytes(gpu))]:m.mem_write(addr,data)
 ep=bytearray(pm);em=bytearray(manager);es=bytearray(state);esc=bytearray(scenes)
 asserted=mode==2 and generation_check and mismatch or mode==3 and active and generation_check and mismatch
 if not asserted:
  if mode==2:ep[0x230]=0
  if mode==3 and not active:ep[0x230]=1;struct.pack_into('<Q',ep,0x238,123)
  if first:struct.pack_into('<I',es,0xc,request)
  struct.pack_into('<I',em,0x30,usage+2);struct.pack_into('<I',esc,index*0x80+0x48,0)
 events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,M),(c.UC_ARM64_REG_X2,request),(c.UC_ARM64_REG_X3,mode|0xa500),(c.UC_ARM64_REG_X4,D),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(LOAD,STOP,count=1000)
 if asserted:assert events==[('generation_assert',)];counts['asserted_generation_mismatch']+=1
 else:
  assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
  assert events==([('prepare_state',)] if first else []);counts['successful_load']+=1;counts['provider_calls']+=int(first)
 for addr,expected in [(S,ep),(M,em),(STATE,es),(SCENES,esc),(GPU,gpu)]:assert bytes(m.mem_read(addr,len(expected)))==bytes(expected),(i,hex(addr))
 if i<8:examples.append(dict(mode=mode,first=first,events=events.copy()))
report=dict(private_binary_sha256=sha,range=[hex(LOAD),hex(LOAD_END)],range_sha256=hashlib.sha256(read(LOAD,LOAD_END-LOAD)).hexdigest(),counts=counts,examples=examples,qualification='Complete native loadPBDesc successful path plus generation assertion entries.1024 combinations cover low-byte mode0..3, initial/reused manager, optional generation check, activation and mismatch; full PM/manager/state/scene/GPU preservation comparisons. First-use GPU virtual10f8 is an explicit no-op fixture, arguments checked. Index0..15 only. No provider implementation, prepareAndRetain composition, firmware acceptance or job submission.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
