#!/usr/bin/env python3
"""Offline qualification of slot22 write addresses, never hardware execution.

Native continuation and a bounded earlier-selector replay use captured DATA,
owned objects and registers. Device reads use explicitly zero register RAM.
The earlier replay assumes preserved registers and the native state-query
result remain applicable. It stops before the timer helper, not at function exit.
"""
import argparse, hashlib, json, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify

FW = 0xfffffc0000000000
PRIMARY = 0xfffffc2000200000
BANK = 0xfffffc2001200000
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('boot_directory', type=Path)
p.add_argument('crash', type=Path)
p.add_argument('receipt', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
b = a.boot_directory
text = (b/'text.bin').read_bytes()
data = (b/'data-after.bin').read_bytes()
arena = (b/'objects-after.bin').read_bytes()
contract = qualify(text)
r = json.loads(a.receipt.read_text())
crash = json.loads(a.crash.read_text())
regs = next(s for s in crash['sections'] if s['fourcc'] == 'Crg8')
assert int(regs['pc'],16) == FW+0x24210
assert int(regs['far'],16) == BANK+0x4004
assert int(regs['registers']['x10'],16) == BANK
assert int(regs['registers']['x0'],16) == 3
assert struct.unpack_from('<Q',data,0x18f798-0x60000)[0] == BANK
assert struct.unpack_from('<Q',data,0x18f6d0-0x60000)[0] == PRIMARY
descriptor = next(x for x in r['mmio_descriptors'] if x['slot']==22)
assert (int(descriptor['physical'],16),int(descriptor['gpu_va'],16),int(descriptor['size'],16)) == (0x289000000,BANK,0x8000)

def run(start):
    m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
    m.mem_map(FW,0x60000,u.UC_PROT_READ|u.UC_PROT_EXEC)
    m.mem_write(FW,text)
    m.mem_map(FW+0x60000,0x138000)
    m.mem_write(FW+0x60000,data)
    base=int(r['base'],16)
    m.mem_map(base,len(arena));m.mem_write(base,arena)
    m.mem_map(PRIMARY,0x24000);m.mem_map(BANK,0x8000)
    for name,value in regs['registers'].items():
        m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),int(value,16))
    m.reg_write(c.UC_ARM64_REG_SP,int(regs['sp'],16))
    steps=[];accesses=[]
    def code(mu,address,size,opaque):
        off=address-FW
        if off==0x2427c:mu.emu_stop();return
        if not start<=off<0x2427c:raise ValueError(f'Unreviewed code {off:x}')
        steps.append(off)
    def memory(mu,kind,address,size,value,opaque):
        for tag,base,span in [('primary',PRIMARY,0x24000),('slot22',BANK,0x8000)]:
            if base<=address<base+span:
                if address+size>base+span:raise ValueError('Cross-bank access')
                accesses.append(dict(bank=tag,pc=hex(mu.reg_read(c.UC_ARM64_REG_PC)-FW),
                    offset=hex(address-base),bytes=size,write=kind==u.UC_MEM_WRITE,
                    value=hex(value) if kind==u.UC_MEM_WRITE else None))
    m.hook_add(u.UC_HOOK_CODE,code)
    m.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,memory)
    m.emu_start(FW+start,0,count=2000,timeout=5_000_000)
    assert m.reg_read(c.UC_ARM64_REG_PC)==FW+0x2427c
    writes=[x for x in accesses if x['write']]
    bank=[int(x['offset'],16) for x in writes if x['bank']=='slot22']
    assert bank==[0x4004,0x4010]
    pages=sorted({((0x288000000 if x['bank']=='primary' else 0x289000000)+int(x['offset'],16))&~0x3fff for x in writes})
    assert pages==([0x289004000] if start==0x24210 else [0x288004000,0x289004000])
    return dict(start=hex(start),boundary='0x2427c before timer helper',instructions=len(steps),
                writes=len(writes),write_pages=[hex(x) for x in pages],accesses=accesses)

result=dict(text_contract=contract,boot_id=crash['boot_id'],
    input_sha256={name:hashlib.sha256(blob).hexdigest() for name,blob in [('text',text),('captured_data',data),('owned_objects',arena)]},
    native_continuation=run(0x24210),earlier_selector_replay=run(0x24048),
    qualification='Captured native DATA/objects/registers; device reads explicitly zero RAM. Earlier replay assumes preserved registers and native state-query result3. Stops before timer helper; no peripheral semantics, later callback, whole function, startup or rendering success established. Implementation-derived evidence.')
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k: {f:v for f,v in result[k].items() if f!='accesses'} for k in ['native_continuation','earlier_selector_replay']},indent=2))
