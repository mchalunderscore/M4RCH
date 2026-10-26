#!/usr/bin/env python3
"""Qualify render descriptor loaders, fast geometry and numeric validation."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_render_inputs import load_render_target,load_fast_target,load_parameter_management,fast_geometry,validate_fast_info,validate_render_info
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
raw=args.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size

def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('address not file backed')
PM,RTM,FAST,GEO,VFAST,VRT=0xfffffe000895d5f0,0xfffffe000895d7b4,0xfffffe000895d914,0xfffffe00089e5b2c,0xfffffe00089e5cf8,0xfffffe00089e63b8
GETTERS=[0xfffffe00089fefa4,0xfffffe00089fef98,0xfffffe00089fef8c]
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,size in [(0xfffffe000895d000,4096),(0xfffffe00089e5000,0x2000),(0xfffffe00089fe000,4096),(0xfffffe000712d000,4096),(0x200000,0x20000)]:m.mem_map(addr,size)
for addr,size in [(PM,FAST+0x54-PM),(GEO,0x89e5d30-0x89e5b2c),(VRT,0x40),(min(GETTERS),0x30),(0xfffffe000712d000,4096)]:m.mem_write(addr,read(addr,size))
D,S,VA,VB,N,R,VT,PV=0x200000,0x202000,0x204000,0x205000,0x206000,0x208000,0x209000,0x20a000
STOP,STACK=0x21f000,0x21e000
m.mem_write(N+0x20,struct.pack('<Q',R));m.mem_write(R,struct.pack('<Q',VT));m.mem_write(VT+0x158,struct.pack('<Q',0x20b000))
for i,target in enumerate(GETTERS):
 slot=0x158+i*8;encoded=struct.unpack('<Q',read(0xfffffe0007eb3050+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
 m.mem_write(PV+slot,struct.pack('<Q',target))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];map_returns=[];map_calls=[];getter_calls=[];trap=None;seen=set()
TRAPS={0xfffffe000895d648,0xfffffe000895d798,0xfffffe000895d7a4,0xfffffe000895d7b0}

def hook(m,address,size,user):
 global trap
 seen.add(address)
 if address==STOP:m.emu_stop();return
 if address in TRAPS:trap=address;m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==0x20b000:
   assert m.reg_read(c.UC_ARM64_REG_X0)==R
   value=map_returns[len(map_calls)];map_calls.append(value);m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
  assert target in GETTERS;assert m.reg_read(c.UC_ARM64_REG_X0)==S
  getter_calls.append(target);m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)

def run(start,x0=D,x1=S):
 global trap
 trap=None;map_calls.clear();getter_calls.clear()
 for reg in regs:m.reg_write(reg,0)
 m.reg_write(c.UC_ARM64_REG_X0,x0);m.reg_write(c.UC_ARM64_REG_X1,x1);m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(start,STOP,count=2000)
 if trap is None:
  assert m.reg_read(c.UC_ARM64_REG_PC)==STOP
  assert m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(c.UC_ARM64_REG_W0)
rng=random.Random(604011);counts=dict(render_target_loader=0,fast_target_loader=0,parameter_loader=0,parameter_trap=0,fast_geometry=0,fast_validator=0,render_validator=0,fast_geometry_to_descriptor=0);traps={};boundary=[]
for i in range(1024):
 descriptor=rng.randbytes(0x1000);source=bytearray(rng.randbytes(0x400));map_returns=[rng.getrandbits(64) for _ in range(3)]
 struct.pack_into('<Q',source,0x130,N)
 m.mem_write(D,descriptor);m.mem_write(S,bytes(source));run(RTM)
 assert bytes(m.mem_read(D,len(descriptor)))==load_render_target(descriptor,source,map_returns)
 assert bytes(m.mem_read(S,len(source)))==bytes(source);assert map_calls==map_returns
 counts['render_target_loader']+=1
 m.mem_write(D,descriptor);m.mem_write(S,bytes(source));run(FAST)
 assert bytes(m.mem_read(D,len(descriptor)))==load_fast_target(descriptor,source)
 assert bytes(m.mem_read(S,len(source)))==bytes(source)
 counts['fast_target_loader']+=1
 # Valid indexed PM; subtype-native getters all return0.
 va=[rng.getrandbits(64) for _ in range(32)];vb=[rng.getrandbits(64) for _ in range(32)]
 capacity=1+i%32;index=i%capacity
 if i%8==0:capacity=0
 elif i%8==1:index=capacity
 elif i%8==2:capacity=1<<29
 elif i%8==3:index=1<<28
 struct.pack_into('<Q',source,0,PV);struct.pack_into('<Q',source,0x88,VB);struct.pack_into('<Q',source,0xa8,0 if i%8==4 else VA);struct.pack_into('<I',source,0xb0,capacity);struct.pack_into('<I',source,0x2c,index)
 try:expected=load_parameter_management(descriptor,source,va,vb,[0,0,0]);invalid=False
 except ValueError:invalid=True
 m.mem_write(D,descriptor);m.mem_write(S,bytes(source));m.mem_write(VA,struct.pack('<32Q',*va));m.mem_write(VB,struct.pack('<32Q',*vb));run(PM)
 if invalid:
  assert trap is not None;assert bytes(m.mem_read(D,len(descriptor)))==descriptor;assert not getter_calls
  counts['parameter_trap']+=1;traps[hex(trap)]=traps.get(hex(trap),0)+1
 else:
  assert trap is None;assert bytes(m.mem_read(D,len(descriptor)))==expected;assert getter_calls==GETTERS;counts['parameter_loader']+=1
 assert bytes(m.mem_read(S,len(source)))==bytes(source)
 target=bytearray(rng.randbytes(0x100));dims=[0,1,15,16,31,32,33,255,16384,0xffffffff]
 for off in (0x10,0x14,0x18,0x1c):struct.pack_into('<I',target,off,rng.choice(dims) if i%2 else rng.getrandbits(32))
 for off in (0x68,0x6c):struct.pack_into('<I',target,off,rng.choice([16,32,0]))
 struct.pack_into('<I',target,0x20,[0,1,2,3,4,7,8,9,0xffffffff][i%9])
 m.mem_write(D,bytes(target));run(GEO,x0=D,x1=0)
 assert bytes(m.mem_read(D,len(target)))==fast_geometry(target),(i,'geometry')
 counts['fast_geometry']+=1
 if i%2==0:
  geometry_output=bytes(m.mem_read(D,len(target)))
  m.mem_write(S,geometry_output);m.mem_write(D,descriptor);run(FAST)
  assert bytes(m.mem_read(D,len(descriptor)))==load_fast_target(descriptor,fast_geometry(target))
  counts['fast_geometry_to_descriptor']+=1
 values=[rng.choice(dims) for _ in range(4)] if i%2 else [rng.getrandbits(32) for _ in range(4)]
 info=struct.pack('<4I',*values);m.mem_write(S,info);result=run(VFAST)
 assert result==validate_fast_info(info);assert bytes(m.mem_read(S,len(info)))==info;counts['fast_validator']+=1
 info=struct.pack('<3I',rng.choice(dims),rng.choice(dims),[0,1,2,3,4,7,8,9,0xffffffff][i%9]);m.mem_write(S,info);result=run(VRT)
 assert result==validate_render_info(info);assert bytes(m.mem_read(S,len(info)))==info;counts['render_validator']+=1
 if i<9:boundary.append(dict(render_input=list(struct.unpack('<3I',info)),render_accept=result))
report=dict(binary_sha256=sha,counts=counts,parameter_trap_sites=traps,boundary_examples=boundary,visited_instruction_count=len(seen),functions=[dict(start=hex(a),end=hex(b),sha256=hashlib.sha256(read(a,b-a)).hexdigest()) for a,b in [(PM,RTM),(RTM,FAST),(FAST,FAST+0x54),(GEO,VFAST),(VFAST,VFAST+0x38),(VRT,VRT+0x40)]],parameter_getters=[hex(x) for x in GETTERS],sample_shifts=[32,36,40,44,48,52,56,60],qualification='Actual loaders, fast geometry and validators in RAM. PAC bypassed. RTM map slot158 returns three independent synthetic addresses; mapping semantics not qualified. PM virtual subtype getters execute actual native zero-return functions; ordinary subtype methods are external/unavailable. PM low unsigned fixture pointers only, panic calls intercepted before execution; overflowed high-pointer arithmetic excluded. Numeric validation is not overall object/job validity. No live GPU or shader preparation proved.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts,'trap sites',traps)
