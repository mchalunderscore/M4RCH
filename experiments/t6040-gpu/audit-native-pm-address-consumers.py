#!/usr/bin/env python3
"""Qualify native host-pointer translation and scene write windows, not full serializers."""
from pathlib import Path
import argparse,hashlib,json,struct,random
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser();p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args();raw=a.macho.read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(raw)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,n=struct.unpack_from('<II',raw,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=n
B=0xfffffe0000000000
def read(addr,n):
 for vm,_,off,size in segs:
  if vm<=addr and addr+n<=vm+size:return raw[off+addr-vm:off+addr-vm+n]
 raise ValueError(hex(addr))
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
for addr in (B+0x895b000,B+0x8a1f000,B+0x8a22000):m.mem_map(addr,4096);m.mem_write(addr,read(addr,4096))
m.mem_map(0x200000,0x40000)
D,G,SCHED,VT,PM,OUT,SCENE,SERVICE=0x200000,0x210000,0x220000,0x221000,0x222000,0x223000,0x224000,0x225000
regs=[getattr(c,'UC_ARM64_REG_X'+str(j)) for j in range(31)];calls=[];result=0
qwrite=lambda addr,v:m.mem_write(addr,struct.pack('<Q',v))
qwrite(G+0x5b0,SCHED);qwrite(SCHED,VT);qwrite(VT+0x2d8,SERVICE)
def hook(m,addr,size,user):
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target==SERVICE
  args=[m.reg_read(regs[j]) for j in range(3)];assert args[0]==SCHED and args[2]==0;calls.append(args)
  m.reg_write(regs[0],result);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
windows=[('3d_vector_a',0x895b530,0x895b57c,0x910,0x30),('3d_aux_end',0x895b57c,0x895b5cc,0x938,0x38),('ta_vector_a',0x8a1f43c,0x8a1f488,0x1228,0x28),('ta_aux_end',0x8a1f488,0x8a1f4d8,0x1250,0x30)]
rng=random.Random(604042);counts={w[0]:0 for w in windows};examples=[]
for i in range(512):
 for name,start,end,src,dst in windows:
  desc=bytearray(rng.randbytes(0x1800));out=rng.randbytes(0x100);host=rng.getrandbits(64);result=rng.getrandbits(64)
  struct.pack_into('<Q',desc,0x10,G);struct.pack_into('<Q',desc,src,host);expected=bytearray(out);struct.pack_into('<Q',expected,dst,result)
  m.mem_write(D,bytes(desc));m.mem_write(OUT,out);calls.clear()
  for reg in regs:m.reg_write(reg,0)
  for index,value in [(19,D),(20,D),(24,OUT)]:m.reg_write(regs[index],value)
  m.emu_start(B+start,B+end,count=200)
  assert m.reg_read(c.UC_ARM64_REG_PC)==B+end and calls==[[SCHED,host,0]]
  assert bytes(m.mem_read(OUT,0x100))==expected and bytes(m.mem_read(D,0x1800))==desc
  counts[name]+=1
  if i==0:examples.append({'window':name,'source_offset':hex(src),'output_offset':hex(dst),'host_input':hex(host),'supplied_translation':hex(result)})
counts['scene_host_write']=0;branches={str(j):0 for j in range(4)}
for i in range(512):
 mode=i%4;desc=bytearray(rng.randbytes(0x1800));scene=rng.randbytes(128);expected=bytearray(scene);generation=rng.getrandbits(64)
 struct.pack_into('<Q',desc,0xd68,PM);struct.pack_into('<Q',desc,0x1230,SCENE)
 m.mem_write(D,bytes(desc));m.mem_write(SCENE,scene);m.mem_write(G+0x5c0,bytes([mode]));qwrite(PM+0x228,generation)
 for reg in regs:m.reg_write(reg,0)
 m.reg_write(regs[19],D);m.reg_write(regs[23],G);m.emu_start(B+0x8a22c4c,B+0x8a22c6c,count=100)
 if mode in (1,2):struct.pack_into('<Q',expected,0x4c,generation)
 assert bytes(m.mem_read(SCENE,128))==expected and bytes(m.mem_read(D,0x1800))==desc
 counts['scene_host_write']+=1;branches[str(mode)]+=1
report={'private_binary_sha256':sha(raw),'counts':counts,'scene_write_modes':branches,'windows':[{'name':name,'start':hex(B+s),'end':hex(B+e),'sha256':sha(read(B+s,e-s)),'source_offset':hex(src),'output_offset':hex(dst)} for name,s,e,src,dst in windows],'scene_window':{'start':hex(B+0x8a22c4c),'end':hex(B+0x8a22c6c),'sha256':sha(read(B+0x8a22c4c,0x20))},'examples':examples,'qualification':'Actual native bounded consumer windows prove 3D910/938 and TA1228/1250 are passed to scheduler2d8(host_pointer,0), with translated results stored in output structures. TA1230 is CPU-dereferenced for an unaligned64-bit scene write at+4c when mode1or2. PAC bypassed; scheduler translation supplied and exact arguments checked. Output object class/final firmware serialization and actual translation implementation not qualified. Not complete prepare/submit; no hardware execution.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
