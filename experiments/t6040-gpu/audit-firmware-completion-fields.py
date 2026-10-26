#!/usr/bin/env python3
"""Check completion payload extraction against actual firmware handler prefix."""
from pathlib import Path
from firmware_completion import decode_entry
base=Path(__file__).with_name('audit-firmware-completion-ring.py')
setup=base.read_text().split('m.hook_add(u.UC_HOOK_CODE,hook);rng=')[0]
exec(compile(setup,str(base),'exec'))
START,END=0x12788,0x12850
m.mem_map(0x500000,4096);POINTER,EXTRA=0x500000,0x500100
def fields_hook(m,address,size,user):
 if address==END:m.emu_stop();return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,fields_hook);rng=random.Random(604050);counts=dict(cases=0,phase=[0,0,0],flag=[0,0])
for case in range(1024):
 entry=bytearray(rng.randbytes(64));phase=1+case%3;word=struct.unpack_from('<Q',entry)[0];word=(word&~0x30)|(phase<<4)
 struct.pack_into('<Q',entry,0,word);struct.pack_into('<QQ',entry,0x30,POINTER+(case&1),EXTRA)
 stamp=rng.getrandbits(32);m.mem_write(POINTER,struct.pack('<I',stamp));m.mem_write(RINGS,bytes(entry));mode=case%3
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(regs[0],RINGS),(regs[1],mode),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 calls.clear();current=-1;m.emu_start(START,END,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==END and m.reg_read(c.UC_ARM64_REG_SP)==STACK-0x1d0
 assert calls==[('cache',-1,POINTER,4),('cache',-1,EXTRA,0xa8)]
 decoded=decode_entry(entry);frame=STACK-0x10
 q=lambda address:struct.unpack('<Q',m.mem_read(address,8))[0]
 assert m.reg_read(regs[25])==decoded['queue_id']
 for offset,value in [(-0xb0,EXTRA),(-0xc8,stamp),(-0xc0,phase-1),(-0xb8,decoded['epoch']),(-0xa8,decoded['masked_word28'])]:assert q(frame+offset)==value,(case,hex(offset),hex(q(frame+offset)),hex(value))
 assert m.reg_read(regs[28])==decoded['masked_word20'] and m.reg_read(regs[27])==struct.unpack_from('<Q',entry,0x10)[0]
 assert q(STACK-0x1d0+0x80)==POINTER+(case&1) and q(STACK-0x1d0+0xc0)==struct.unpack_from('<Q',entry,0x18)[0]
 assert bytes(m.mem_read(RINGS,64))==entry and bytes(m.mem_read(POINTER,4))==struct.pack('<I',stamp)
 counts['cases']+=1;counts['phase'][phase-1]+=1;counts['flag'][case&1]+=1
report=dict(firmware=identity,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(text[START:END]).hexdigest(),counts=counts,qualification='Actual12788 completion handler prefix extracts queueID/phase/epoch/masked metadata/pointer30 flag and pointer38;1024 random entries phases1/2/3, both pointer flags. Cache service receives pointer30&~1 length4 and pointer38 lengtha8; pointer30 u32 is read and saved. Field extraction compared with reusable decoder. Diagnostic phase0 and remaining payload processing/notification/stamp writes excluded. No completed-job/retirement claim or hardware execution.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
