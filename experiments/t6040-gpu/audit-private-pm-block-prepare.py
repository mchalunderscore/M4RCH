#!/usr/bin/env python3
"""Execute concrete PM block preparation into packed page-index array."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
PREPARE,PREPARE_END=0xfffffe00089fea44,0xfffffe00089feafc;m.mem_write(PREPARE,read(PREPARE,PREPARE_END-PREPARE));m.mem_map(0x220000,0x10000)
BLOCK,GART,BVT,GVT,PAGES,PRESERVICE,MAPSERVICE=0x220000,0x221000,0x222000,0x223000,0x224000,0x225000,0x225008
m.mem_write(BVT+0x140,struct.pack('<Q',PRESERVICE));m.mem_write(GART,struct.pack('<Q',GVT));m.mem_write(GVT+0x160,struct.pack('<Q',MAPSERVICE));events=[]
def prepare_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);x0=m.reg_read(regs[0])
  if target==PRESERVICE:assert x0==BLOCK;events.append(('prepare_resource',));value=1
  elif target==MAPSERVICE:assert x0==GART;events.append(('map160',));value=mapped
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,prepare_hook);rng=random.Random(604040);counts=dict(successes=0)
for i in range(1024):
 mapped=rng.getrandbits(64);index=i%32;pm=bytearray(rng.randbytes(0x300));block=bytearray(rng.randbytes(0x100));pages=rng.randbytes(0x1000);struct.pack_into('<Q',pm,0x90,PAGES);struct.pack_into('<Q',block,0,BVT);struct.pack_into('<Q',block,0x18,GART);struct.pack_into('<I',block,0xc,index)
 epages=bytearray(pages);struct.pack_into('<I',epages,index*8,(mapped>>15)&0x1ffffff);eb=bytearray(block);eb[0x10]=1
 for addr,data in [(S,pm),(BLOCK,block),(PAGES,pages)]:m.mem_write(addr,bytes(data))
 events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,S),(c.UC_ARM64_REG_X1,BLOCK),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(PREPARE,STOP,count=400);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 for addr,data in [(S,pm),(BLOCK,eb),(PAGES,epages)]:assert bytes(m.mem_read(addr,len(data)))==bytes(data),(i,hex(addr))
 assert events==[('prepare_resource',),('map160',)];counts['successes']+=1
report=dict(private_binary_sha256=sha,range=[hex(PREPARE),hex(PREPARE_END)],range_sha256=hashlib.sha256(read(PREPARE,PREPARE_END-PREPARE)).hexdigest(),counts=counts,qualification='Whole native concrete prepareParameterBufferBlock1024 full PM/block/page-array comparisons. Block ID0..31, randomized64-bit mapping160 result; page index=(mapping>>15)&1ffffff writes u32 at PM90+ID*8, upper adjacent word preserved; block10 byte1. Block virtual140 preparation and GART virtual160 mapping remain explicit services with arguments/order checked. No live mapping address qualification, invalid index/PAC validation or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
