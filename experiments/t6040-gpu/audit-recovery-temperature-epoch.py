#!/usr/bin/env python3
"""RAM-only native epoch binding and firmware zero-sensor consumer audit.

Usage: audit-recovery-temperature-epoch.py TEXT MACHO OUTPUT
External mapping/allocation/zero services are not emulated. No device access.
"""
import argparse, hashlib, importlib.util, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser();p.add_argument('text',type=Path);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
repo=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('contract',repo/'firmware_text_contract.py');contract=importlib.util.module_from_spec(s);s.loader.exec_module(contract)
t=a.text.read_bytes();identity=contract.qualify(t)
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
pos=32;segments=[]
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==0x19:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(va,n):
 spans=[o+va-v for v,_,o,sz in segments if v<=va and va+n<=v+sz];assert len(spans)==1
 return raw[spans[0]:spans[0]+n]
B=0xfffffe0000000000;HOST=0x200000;VT=0x201000;POWER=0x204000;STACK=0x210000;EPOCH=0x211000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for va,n in [(B+0x89ab000,0x1000),(B+0x712d000,0x1000),(B+0x89d0000,0x1000),(B+0x89c8000,0x2000),(HOST,0x12000),(0,0x60000)]:
 m.mem_map(va,n)
 if va>=B:m.mem_write(va,read(va,n))
m.mem_write(0,t);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
def q(addr,v):m.mem_write(addr,struct.pack('<Q',v))
def hook(mu,pc,size,unused):
 if pc in (B+0x89d0f68,B+0x89d0f70):mu.reg_write(c.UC_ARM64_REG_PC,pc+4)
 elif pc==B+0x89d0f98:
  assert mu.reg_read(c.UC_ARM64_REG_X9)==B+0x89c8ff8 and mu.reg_read(c.UC_ARM64_REG_X0)==HOST and mu.reg_read(c.UC_ARM64_REG_W2)==0
  mu.reg_write(c.UC_ARM64_REG_LR,pc+4);mu.reg_write(c.UC_ARM64_REG_PC,B+0x89c8ff8)
 elif pc==0x2fdf4:mu.reg_write(c.UC_ARM64_REG_PC,pc+4)
m.hook_add(u.UC_HOOK_CODE,hook)
# Actual straight-line allocation descriptor construction, including native size constant.
m.reg_write(c.UC_ARM64_REG_X19,HOST);m.reg_write(c.UC_ARM64_REG_SP,STACK)
m.emu_start(B+0x89abb94,B+0x89abbb0,count=20)
descriptor=struct.unpack('<QQII',m.mem_read(STACK+0x290,24));assert descriptor==(HOST+0x3a0,HOST+0x3a8,8,0)
rng=random.Random(6040301);cases=0
for i in range(128):
 image=bytearray(rng.randbytes(0x8000));epoch=0 if i==0 else rng.getrandbits(32);cached=epoch if i==0 or i%2 else epoch^1
 struct.pack_into('<Q',image,0x3b58,0);struct.pack_into('<I',image,0x3b60,0);struct.pack_into('<I',image,0x3b48,cached)
 m.mem_write(POWER,bytes(image));q(HOST,VT);q(VT+0x2d8,B+0x89c8ff8);q(HOST+0x2d8,POWER);q(HOST+0x3a8,EPOCH)
 m.reg_write(c.UC_ARM64_REG_X19,HOST);m.reg_write(c.UC_ARM64_REG_SP,STACK)
 m.emu_start(B+0x89d0f5c,B+0x89d0fa4,count=40)
 struct.pack_into('<Q',image,0x3b50,EPOCH);assert bytes(m.mem_read(POWER,len(image)))==image
 q(EPOCH,epoch);m.reg_write(c.UC_ARM64_REG_X0,POWER+0x3118);m.reg_write(c.UC_ARM64_REG_SP,STACK)
 m.emu_start(0x2fdf4,0x30224,count=100)
 struct.pack_into('<4I',image,0x3b1c,0,0,0x7fffffff,0x80000000)
 if cached!=epoch:struct.pack_into('<3I',image,0x3b40,0x7fffffff,0x80000000,epoch)
 assert bytes(m.mem_read(POWER,len(image)))==image,(i,'power image')
 assert struct.unpack('<Q',m.mem_read(EPOCH,8))[0]==epoch
 cases+=1
# Replay the observed null fault through the same actual firmware path.
q(POWER+0x3b50,0);m.reg_write(c.UC_ARM64_REG_X0,POWER+0x3118);m.reg_write(c.UC_ARM64_REG_SP,STACK)
# Address zero is code-mapped for relative TEXT, so protect only the null-read address.
null_read=[]
def nullhook(mu,access,address,size,value,unused):
 if address==0:null_read.append((mu.reg_read(c.UC_ARM64_REG_PC),size));mu.emu_stop()
h=m.hook_add(u.UC_HOOK_MEM_READ,nullhook);m.emu_start(0x2fdf4,0x30224,count=100);m.hook_del(h)
assert null_read==[(0x301a8,4)]
ranges=[('allocation_descriptor',0x89abb94,0x89abbb0),('generic_allocation_zero_and_bind',0x89a7df0,0x89a7eb4),('suballocation_alignment',0x89a7c84,0x89a7ca8),('initial_publication',0x89cc520,0x89cc560),('init_publication',0x89d0f5c,0x89d0fa4),('identity_converter',0x89c8ff8,0x89c9004),('temperature_epoch_host_reader',0x89c33f4,0x89c340c),('temperature_epoch_host_increment',0x89c3494,0x89c34a4),('sensor_region_zero',0x89cc3b4,0x89cc3c8)]
report=dict(schema='m4rch-recovery-temperature-epoch-audit-v1',static_contract_verified=True,hardware_verified=False,private_binary_sha256=sha,firmware_text_identity=identity,native_descriptor=dict(cpu_field='0x3a0',mapped_va_field='0x3a8',bytes=8,suballocation_alignment=64),binding=dict(power_pointer_offset='0x3b50',consumer_base_offset='0x3118',consumer_pointer_offset='0xa38',read_width=4),native_ranges=[dict(name=n,start=hex(B+x),end=hex(B+y),sha256=hashlib.sha256(read(B+x,y-x)).hexdigest()) for n,x,y in ranges],firmware_ranges=[dict(start=hex(x),end=hex(y),sha256=hashlib.sha256(t[x:y]).hexdigest()) for x,y in [(0xcbe8,0xcbf4),(0x2fdf4,0x302ec),(0x39234,0x39264)]],counts=dict(native_binding_cases=cases,zero_sensor_consumer_cases=cases,null_fault_reproductions=1),required_initialization={'temperature_epoch':'8 zero bytes','power+3b58':'zero sensor mask fixture','power+3b60':'zero sensor count fixture'},target_candidate=dict(owner='status_b reservation tail, semantically separate temperature_epoch',offset='0xf000',bytes=8,alignment=64,qualified_status_extent='0xe440',reservation='0x10000'),qualification='Native8-byte descriptor and converter/publication slice, actual firmware zero-sensor path, whole power-image comparisons across128 equal/changed epoch cases, exact null4-byte readat301a8 reproduced. Native generic allocator zero-and-bind path and64-byte packing reviewed/hash-pinned; external zero service b744da0 not executed here, allocator/mapping/cache services not executed. PAC instructions bypassed. No nonzero sensor table, hardware reset, MMIO, recovery completion, DMA retirement or rendering established.')
report['observed_failure'] = {
 'source': 'out/recovery-idle/crash.json',
 'source_sha256': 'ec4bb20da0a911cc90fe494f984df1b558112e2fc021f1f4d49441407d3b63a5',
 'boot_id': 'e3501874-8c10-47f2-92e1-a8de666e7caf',
 'pc': '0x301a8', 'far': 0, 'esr': '0x96000004',
 'task6_stack': ['0x301a8', '0xcbf0', '0x39260', '0x38f9c'],
 'consumer_base': '0xfffffc2000133118', 'power_base': '0xfffffc2000130000',
 'phase': 'After host acknowledged recovery phase1 with phase2',
 'qualification': 'Recorded prior live evidence, not re-read or replayed on hardware by this audit.',
}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(f'{cases} native bindings and firmware consumer cases; null read301a8 reproduced; static_contract_verified=true')
