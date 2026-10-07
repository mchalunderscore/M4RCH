#!/usr/bin/env python3
"""Offline continuation of the native8050 fault to the next table-loop boundary.

Explicit zero private DATA and device-register RAM fixtures. Not hardware
emulation. Diagnostic logger substituted and authentication omitted. Captured
registers seed the continuation; two globals receive explicit fixture values.
Unknown code or memory stops execution. No live device or firmware access.
"""
import argparse,json,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify
FW=0xfffffc0000000000;MMIO=0xfffffc2000200000
p=argparse.ArgumentParser(description=__doc__)
for name in ['text','crash','arena','receipt','output']:p.add_argument(name,type=Path)
a=p.parse_args();text=a.text.read_bytes();contract=qualify(text)
crash=json.loads(a.crash.read_text());regs=next(s for s in crash['sections'] if s['fourcc']=='Crg8')
if int(regs['pc'],16)!=FW+0x8050 or int(regs['far'],16)!=MMIO+0x1ca20:raise ValueError('Unexpected native fault')
r=json.loads(a.receipt.read_text());arena=a.arena.read_bytes();base=int(r['base'],16)
objects={o['name']:int(o['gpu_va'],16) for o in r['objects']}
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
m.mem_map(FW,0x60000,u.UC_PROT_READ|u.UC_PROT_EXEC);m.mem_write(FW,text)
m.mem_map(FW+0x60000,0x138000);m.mem_map(base,len(arena));m.mem_write(base,arena)
m.mem_map(MMIO,0x24000);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for name,value in regs['registers'].items():m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),int(value,16))
m.reg_write(c.UC_ARM64_REG_SP,int(regs['sp'],16))
# Cache primary pointer from native x21 and LDRX [18f6d0]; root-parser main.
for off,val in [(0x18f6d0,MMIO),(0x18e4c0,objects['main'])]:m.mem_write(FW+off,struct.pack('<Q',val))
accesses=[];steps=[];omissions=[]
def code(mu,address,size,opaque):
 off=address-FW
 if off==0x8fb0:mu.emu_stop();return
 steps.append(off)
 if off==0x33de8:
  omissions.append(dict(kind='substituted-diagnostic-logger',caller=hex(mu.reg_read(c.UC_ARM64_REG_LR)-FW)))
  mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR));return
 if not any(lo<=off<hi for lo,hi in [(0x8050,0x8fb0),(0x29610,0x297ec),(0x29804,0x29954)]):raise ValueError(f'Unreviewed target {off:x}')
 word=struct.unpack('<I',mu.mem_read(address,4))[0]
 if word in [0xd503237f,0xd65f0fff]:
  omissions.append(dict(kind='omitted-authentication',pc=hex(off)))
  mu.reg_write(c.UC_ARM64_REG_PC,address+4 if word==0xd503237f else mu.reg_read(c.UC_ARM64_REG_LR))
def memory(mu,kind,address,size,value,opaque):
 if MMIO<=address<MMIO+0x24000:
  accesses.append(dict(pc=hex(mu.reg_read(c.UC_ARM64_REG_PC)-FW),offset=hex(address-MMIO),bytes=size,write=kind==u.UC_MEM_WRITE,value=hex(value) if kind==u.UC_MEM_WRITE else None))
m.hook_add(u.UC_HOOK_CODE,code);m.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,memory)
m.emu_start(FW+0x8050,0,count=20000,timeout=5_000_000)
if m.reg_read(c.UC_ARM64_REG_PC)!=FW+0x8fb0:raise ValueError('Boundary not reached')
pages=sorted(set(int(x['offset'],16)&~0x3fff for x in accesses if x['write']))
if pages!=[0x4000,0x8000,0xc000,0x10000,0x14000,0x18000,0x1c000]:
 raise ValueError('Startup write-page set changed; qualification must be reviewed')
result=dict(text_contract=contract,instructions=len(steps),boundary='0x8fb0 before table loop',
 primary_write_pages=[hex(x) for x in pages],accesses=accesses,omissions=omissions,
 qualification='Bounded offline instruction continuation with zero register RAM and private DATA. Captured fault registers and two explicit globals seeded. Diagnostic logger substituted; authentication omitted. No device behavior, timing, complete wake sequence or native completion established.')
a.output.write_text(json.dumps(result,indent=2)+'\n');print('Reached table-loop boundary;',len(steps),'instructions; write pages',result['primary_write_pages'])
