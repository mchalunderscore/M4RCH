#!/usr/bin/env python3
"""Offline allocation-descriptor construction from the pinned private Mach-O.

Execute only the reviewed straight-line descriptor-building segment in Unicorn;
no Apple code executes natively and no allocation/service calls are permitted.
Output numeric ABI observations, not a disassembly or clean-room claim.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();digest=hashlib.sha256(raw).hexdigest()
if digest!='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e':raise ValueError('Wrong AGX353.14/25G83 binary')
pos=32;segments=[]
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==0x19:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(address,size):
 spans=[off+address-vm for vm,_,off,length in segments if vm<=address and address+size<=vm+length]
 if len(spans)!=1:raise ValueError('Address not wholly file backed')
 return raw[spans[0]:spans[0]+size]
start=0xfffffe00089ab98c;end=0xfffffe00089abbb8
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for address in (start&~0xfff,0xfffffe000712d000):
 m.mem_map(address,0x1000,u.UC_PROT_READ|u.UC_PROT_EXEC);m.mem_write(address,read(address,0x1000))
host=0x2000000;private=0x3000000;stack=0x4000000
for address in (host,private,stack):m.mem_map(address,0x10000)
m.reg_write(c.UC_ARM64_REG_X19,host);m.reg_write(c.UC_ARM64_REG_X23,private);m.reg_write(c.UC_ARM64_REG_SP,stack)
m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20);steps=[]
def code(mu,address,size,unused):
 if not start<=address<end:raise ValueError('Unreviewed code target')
 steps.append(address)
m.hook_add(u.UC_HOOK_CODE,code);m.emu_start(start,end,count=256,timeout=5_000_000)
if m.reg_read(c.UC_ARM64_REG_PC)!=end:raise ValueError('Descriptor construction did not complete')
records=[]
for i in range(27):
 resource,mapped,size,padding=struct.unpack('<QQII',m.mem_read(stack+0x20+i*24,24))
 if not host<=resource<host+0x2000 or not host<=mapped<host+0x2000 or padding or not size:
  raise ValueError('Invalid numeric allocation descriptor')
 records.append(dict(resource_cpu_field=hex(resource-host),mapped_cpu_field=hex(mapped-host),bytes=size))
by_field={r['mapped_cpu_field']:r['bytes'] for r in records}
fields=['0x910','0x930','0x918','0x938'];extents=[by_field[x] for x in fields]
if extents!=[0x30,0x9000,0x30,0x4800]:raise ValueError('Unexpected receive14 extents')
# Exact producers link mapped CPU fields to the four main+1e0 positions.
checks={0xfffffe00089ab948:0x91070108,0xfffffe00089a9e40:0xf9448a61,
 0xfffffe00089a9e84:0xf9001100,0xfffffe00089a9e88:0xf9449a61,
 0xfffffe00089a9ecc:0xf9001500,0xfffffe00089a9ed0:0xf9448e61,
 0xfffffe00089a9f14:0xf9001900,0xfffffe00089a9f18:0xf9449e61,
 0xfffffe00089a9f58:0xf9001d00}
for address,word in checks.items():
 if struct.unpack('<I',read(address,4))[0]!=word:raise ValueError('Changed receive mapping producer')
result=dict(macho_sha256=digest,agx_version='353.14',apple_build='25G83',
 descriptor_model_range=[hex(start),hex(end)],instructions=len(steps),allocation_records=records,
 receive14_main_offset='0x1e0',receive14_cpu_fields=fields,receive14_extents=extents,
 receive13_cpu_fields=['0x900','0x920','0x908','0x928'],receive13_extents=[by_field[x] for x in ['0x900','0x920','0x908','0x928']],
 main200_resource_cpu_field='0x880',main200_extent=by_field['0x880'],pinned_mapping_site_checks=len(checks),
 qualification='Offline straight-line private CPU allocation-descriptor construction and exact mapping sites. Zero fake host object and stack, actual file-backed constants/code, no service/allocation/mapping calls. Numeric extents/pointer positions corroborated; cache policy, initial contents, event type/production, role and live acceptance unqualified. Not clean-room.')
a.output.write_text(json.dumps(result,indent=2)+'\n');print('27 allocation descriptors; receive14 extents',list(map(hex,extents)))
