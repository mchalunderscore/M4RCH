#!/usr/bin/env python3
"""Execute only the matched firmware's twelve-channel empty check offline."""
import argparse,hashlib,json,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify
FW=0xfffffc0000000000
p=argparse.ArgumentParser(description=__doc__);p.add_argument('text',type=Path);p.add_argument('arena',type=Path);p.add_argument('receipt',type=Path);a=p.parse_args()
text=a.text.read_bytes();qualify(text);arena=a.arena.read_bytes();receipt=json.loads(a.receipt.read_text());base=int(receipt['base'],16)
main=int(next(o for o in receipt['objects'] if o['name']=='main')['gpu_va'],16)
def run(changed=None):
 m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
 m.mem_map(FW,0x60000);m.mem_write(FW,text)
 m.mem_map(FW+0x60000,0x138000)
 m.mem_write(FW+0x18e4c0,struct.pack('<Q',main))
 m.mem_map(base,len(arena));m.mem_write(base,arena)
 if changed is not None:m.mem_write(int(receipt['empty_channel_fixture'][changed]['cursors'][2],16),struct.pack('<I',1))
 sentinel=FW+0x400;m.reg_write(c.UC_ARM64_REG_LR,sentinel)
 trace=[]
 def code(mu,address,size,opaque):
  if address==sentinel:mu.emu_stop();return
  if not FW+0x66ec<=address<FW+0x6820:raise ValueError('Unexpected firmware code target')
 def read(mu,kind,address,size,value,opaque):
  if base<=address<base+len(arena):trace.append(hex(address))
 m.hook_add(u.UC_HOOK_CODE,code);m.hook_add(u.UC_HOOK_MEM_READ,read)
 m.emu_start(FW+0x66ec,sentinel,count=1000)
 if m.reg_read(c.UC_ARM64_REG_PC)!=sentinel:raise ValueError('Check failed to return')
 return m.reg_read(c.UC_ARM64_REG_W0),trace
result,trace=run()
if result!=0 or len(trace)!=48:raise ValueError('Expected24 pointer and24 cursor reads')
for i in range(12):
 result,_=run(i)
 if result!=1:raise ValueError(f'Channel{i} unequal cursors not detected')
print(json.dumps({'scope':'Offline firmware predicate only; no hardware initialization or queue submission','empty_result':0,'unequal_results':[1]*12,'matched_text_sha256':hashlib.sha256(text).hexdigest(),'empty_check_reads':len(trace)},indent=2))
