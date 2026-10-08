#!/usr/bin/env python3
"""Join ordinary retention with actual internal-resource preparation and page mapping."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-retain.py');source=base.read_text()
def replace(old,new):
 global source
 assert source.count(old)==1,old;source=source.replace(old,new)
replace('m.hook_add(u.UC_HOOK_CODE,retain_hook);rng=', '''
m.mem_map(0xfffffe00089ed000,4096)
RESOURCE_PREP,RESOURCE_END=0xfffffe00089ed740,0xfffffe00089ed7c0
m.mem_write(RESOURCE_PREP,read(RESOURCE_PREP,RESOURCE_END-RESOURCE_PREP))
PAGE_PREP,PAGE_END=0xfffffe00089fe494,0xfffffe00089fea3c
m.mem_write(PAGE_PREP,read(PAGE_PREP,PAGE_END-PAGE_PREP))
m.mem_map(0x260000,0x10000);PAGEOBJ=0x260000;PAGEVT=0x261000;PAGERET=0x262000
m.mem_write(PAGEOBJ,struct.pack('<Q',PAGEVT));m.mem_write(PAGEVT+0x20,struct.pack('<Q',PAGERET))
inner_events=[];joined_counts={'resource_preparations':0,'page_preparations':0}
def joined_hook(m,address,size,user):
 if address in lock_calls or address in gen_calls:retain_hook(m,address,size,user);return
 x0=m.reg_read(regs[0]);word=struct.unpack('<I',m.mem_read(address,4))[0]
 if address in prep_calls:
  assert x0==prep_calls[address];events.append(('prepare_mapping',x0));joined_counts['resource_preparations']+=1
  m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,RESOURCE_PREP);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==READY:
   assert x0==S and m.reg_read(regs[1])==D;events.append(('prepare_pages',));joined_counts['page_preparations']+=1
   m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,PAGE_PREP);return
  if target==PAGERET:assert x0==PAGEOBJ;inner_events.append(('retain_pages',));done(address,0);return
 if word&0xfc000000==0x94000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=address+imm*4
  if target in (0xfffffe000a8032a8,0xfffffe000b7b13c4,0xfffffe000b7b27c0,0xfffffe000a7c40b0):
   if target==0xfffffe000a7c40b0:assert x0==PAGEOBJ;inner_events.append(('prepare_pages',))
   elif target==0xfffffe000a8032a8:assert x0 in SUP[:2];inner_events.append(('prepare_nested',x0))
   else:assert x0 in SUP[2:4];inner_events.append(('lock' if target==0xfffffe000b7b13c4 else 'unlock',x0))
   done(address,0);return
 retain_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,joined_hook);rng=''' )
replace('pending=i%4;', 'pending=0;')
replace('ep=bytearray(pm);', '''pm[0x28]=0
 struct.pack_into('<Q',pm,0x258,PAGEOBJ);struct.pack_into('<Q',pm,0x240,0)
 resource_expected={};inner_events.clear()
 for j,obj in enumerate(RES[:6]):
  buf=bytearray(m.mem_read(obj,0x100));struct.pack_into('<QQ',buf,0x38,0,SUP[2+j%2]);struct.pack_into('<QQ',buf,0x50,SUP[0] if j&1 else 0,SUP[1] if j&2 else 0)
  m.mem_write(obj,bytes(buf));resource_expected[obj]=buf
 for j in (0,1,2,3,4,5):
  active=(j!=0 or bool(i&2)) and (j!=2 or bool(i&4))
  if active:struct.pack_into('<Q',resource_expected[RES[j]],0x38,1)
 ep=bytearray(pm);''')
replace("# Ring loops: first completed->read only if generation changed; then read->write.", "struct.pack_into('<Q',ed,0xd78,PAGEOBJ)\n # Ring loops: first completed->read only if generation changed; then read->write.")
replace("counts['successes']+=1;", "for obj,expected in resource_expected.items():assert bytes(m.mem_read(obj,len(expected)))==expected,(i,hex(obj),[(hex(k),m.mem_read(obj+k,1)[0],v) for k,v in enumerate(expected) if m.mem_read(obj+k,1)[0]!=v],inner_events)\n assert inner_events[-2:]==[('prepare_pages',),('retain_pages',)]\n counts['successes']+=1;")
replace("args.output.write_text(json.dumps(report,indent=2)+'\\n');print(counts)", "report['joined_counts']=joined_counts\nreport['qualification']='512 ordinary native retention paths join actual internal-resource prepareMappings and actual concrete reused page-mapping method. Full PM/manager/TA/config/staged/pending and six internal-resource bytes checked; native preparation counters increment only for active resources. Page object already exists, PM28=0 and no pending blocks/discard. Page/resource underlying preparation, locks, retain, generation and block/page-builder services remain external fixtures. This is a retention fixture, not the initialized-job chain: PM50 explicitly populated; actual concrete initialization leaves it zero and its lifecycle/caller still needs qualification. No live ownership/cache/GPU command.'\nargs.output.write_text(json.dumps(report,indent=2)+'\\n');print(counts,joined_counts)")
exec(compile(source,str(base),'exec'))
