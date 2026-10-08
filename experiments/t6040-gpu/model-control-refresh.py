#!/usr/bin/env python3
"""Offline matched-TEXT control drain with explicit zero private-state fixtures.

No hardware access. Four globals are seeded from the reviewed root-parser
assignments. Cache configuration is explicitly disabled in this model, and
pointer authentication omitted. Neither assumption qualifies native behavior.
"""
import argparse, hashlib, json, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify
FW=0xfffffc0000000000
p=argparse.ArgumentParser(description=__doc__)
for name in ['text','arena','receipt','output']:p.add_argument(name,type=Path)
a=p.parse_args();text=a.text.read_bytes();contract=qualify(text)
arena=a.arena.read_bytes();receipt=json.loads(a.receipt.read_text());base=int(receipt['base'],16)
if receipt.get('control_refresh',{}).get('opcode')!=0x16:raise ValueError('Missing refresh fixture')
count=receipt['control_refresh'].get('count',1)
if type(count) is not int or not 1<=count<=32:raise ValueError('Unqualified refresh count')
entry=struct.unpack_from('<i',text,0x5284+(0x16-4)*4)[0]+0x3a3c
if entry!=0x4b1c or text[0x58850+0x16]!=0:raise ValueError('Unexpected command dispatch/power class')
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
m.mem_map(FW,0x60000,u.UC_PROT_READ|u.UC_PROT_EXEC);m.mem_write(FW,text)
m.mem_map(FW+0x60000,0x138000);m.mem_map(base,len(arena));m.mem_write(base,arena)
objects={o['name']:o for o in receipt['objects']}
# Root parser 2f2c8..2f300: main, status_a, status_b and region_c globals.
for offset,name in [(0x18e4c0,'main'),(0x18e3f0,'status_a'),(0x18ee70,'status_b'),(0x195748,'region_c')]:
 m.mem_write(FW+offset,struct.pack('<Q',int(objects[name]['gpu_va'],16)))
m.mem_map(0x4000000,0x10000);m.reg_write(c.UC_ARM64_REG_SP,0x400f000)
m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
sentinel=FW+0x400;m.reg_write(c.UC_ARM64_REG_LR,sentinel);m.reg_write(c.UC_ARM64_REG_X0,count)
steps=[];accesses=[];omissions=[]
def code(mu,address,size,opaque):
 if address==sentinel:mu.emu_stop();return
 off=address-FW;steps.append(off)
 if not any(lo<=off<hi for lo,hi in [(0x385c,0x3a48),(0x4b1c,0x4b4c),(0x511c,0x5194),(0x30a8,0x3390),(0x3ca80,0x3ca8c),(0x58134,0x58168)]):
  raise ValueError(f'Unreviewed code target {off:x}')
 word=struct.unpack('<I',mu.mem_read(address,4))[0]
 if word in [0xd503237f,0xd65f0fff]:
  omissions.append(hex(off));mu.reg_write(c.UC_ARM64_REG_PC,address+4 if word==0xd503237f else mu.reg_read(c.UC_ARM64_REG_LR))
def memory(mu,kind,address,size,value,opaque):
 if base<=address<base+len(arena):
  obj=next(o for o in objects.values() if base+o['arena_offset']<=address<base+o['arena_offset']+o['reserved_bytes'])
  offset=address-base-obj['arena_offset']
  if offset+size>obj['input_bytes']:raise ValueError('Object access beyond explicit input')
  accesses.append(dict(object=obj['name'],offset=hex(offset),bytes=size,write=kind==u.UC_MEM_WRITE))
m.hook_add(u.UC_HOOK_CODE,code);m.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,memory)
m.emu_start(FW+0x385c,sentinel,count=20000,timeout=5_000_000)
channel=receipt['empty_channel_fixture'][12]
cursors=[struct.unpack('<I',m.mem_read(int(x,16),4))[0] for x in channel['cursors']]
if m.reg_read(c.UC_ARM64_REG_PC)!=sentinel or cursors!=[count]*3 or steps.count(0x4b1c)!=count or 0x3388 not in steps:
 raise ValueError('Refresh did not return with consumed control and cleared flag')
result=dict(text_contract=contract,arena_sha256=hashlib.sha256(arena).hexdigest(),
 instructions=len(steps),dispatch=hex(entry),handler_entries=steps.count(0x4b1c),control_cursors_after=cursors,
 object_accesses=accesses,omitted_authentication=omissions,
 qualification='Offline control-handler model only. Explicit zero private state and disabled cache-helper configuration; four parser globals seeded. No device mappings, native queue processing, timing or rendering established.')
a.output.write_text(json.dumps(result,indent=2)+'\n');print('Control refresh returned; cursors',cursors,'instructions',len(steps))
