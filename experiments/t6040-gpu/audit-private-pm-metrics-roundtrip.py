#!/usr/bin/env python3
"""Pair actual metrics request/release with actual allocation release decision."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-metrics.py');source=base.read_text()
def replace(old,new):
 global source
 assert source.count(old)==1,old;source=source.replace(old,new)
replace('m.hook_add(u.UC_HOOK_CODE,metrics_hook);rng=', '''
m.mem_map(0xfffffe00089f6000,4096)
RELEASE,RBLOCK,REND=0xfffffe00089f6ca0,0xfffffe00089f6ea4,0xfffffe00089f70d4
m.mem_write(RELEASE,read(RELEASE,REND-RELEASE))
roundtrip_counts={'roundtrips':0,'actual_release_decisions':0}
def roundtrip_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if address==0xfffffe00089f6d8c:
  assert [m.reg_read(regs[j]) for j in range(3)]==[POOL,index//slots,0];roundtrip_counts['actual_release_decisions']+=1
 if word&0xfc000000==0x14000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+imm*4
  if target==0xfffffe000b7b27c0:
   assert m.reg_read(regs[0])==LOCKOBJ;events.append(('unlock',));m.reg_write(regs[0],0);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 metrics_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,roundtrip_hook);rng=''' )
replace("counter=rng.randrange(0,1000);", "counter=1+rng.randrange(999);")
replace("struct.pack_into('<I',pool,0x2c,0);", "struct.pack_into('<I',pool,0x2c,0);struct.pack_into('<I',pool,0x50,16);")
replace("assert events==expected_events,(i,events,expected_events)", """assert events==expected_events,(i,events,expected_events)
 if not empty:
  events.clear()
  for reg in regs:m.reg_write(reg,0)
  for reg,val in [(c.UC_ARM64_REG_X0,GART),(c.UC_ARM64_REG_X1,S),(c.UC_ARM64_REG_X2,index),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
  m.emu_start(RELEASE,STOP,count=2000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
  for addr,data in [(POOL,pool),(BITS,bitmap),(RECORD,record),(OUT,eo)]:assert bytes(m.mem_read(addr,len(data)))==data,(i,hex(addr))
  assert events==[('lock',),('unlock',)];roundtrip_counts['roundtrips']+=1""")
replace("args.output.write_text", "report['release_range']=[hex(RELEASE),hex(REND)]\nreport['release_range_sha256']=hashlib.sha256(read(RELEASE,REND-RELEASE)).hexdigest()\nreport['roundtrip_counts']=roundtrip_counts\nreport['qualification']='512 successful actual native metrics requests paired with actual releasePMPageMetricsBuffer and actual releaseAllocationBlockIfPossible;512 empty pool requests. Complete pool/bitmap/record/output compares. Request resource output/map variants inherited; release restores consumed bit and outer availability and decrements allocation count to initial positive count. Underlying block remains in use so actual decision skips free/storage resize; terminal zero-count block freeing separately required. External retain/map/mutex/support services remain fixtures, no lifetime/DMA/GPU event retirement proof.'\nargs.output.write_text")
exec(compile(source,str(base),'exec'))
