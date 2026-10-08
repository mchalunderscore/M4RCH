#!/usr/bin/env python3
"""Offline native client-common copy feeding ordinary 3D command state."""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('Not file backed')


from private_3d_passthrough import copy_common,COPIES,FLAGS
from private_3d_command import body
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
start,end=0xfffffe00089ebbe4,0xfffffe00089ebe34
m.mem_map(start&~4095,4096);m.mem_write(start,read(start,end-start))
bstart,bend=0xfffffe000895b604,0xfffffe000895b8f8
m.mem_map(bstart&~4095,4096);m.mem_write(bstart,read(bstart,bend-bstart))
m.mem_map(0x200000,0x20000)
D,S,C,O,CH,STACK,STOP=0x200000,0x202000,0x204000,0x208000,0x20a000,0x20c000,0x21f000
rng=random.Random(60403)
for case in range(1024):
 descriptor=rng.randbytes(0x1000);common=rng.randbytes(0x400);command=rng.randbytes(0x2240);other=rng.randbytes(0x400);channel=bytearray(rng.randbytes(0x300))
 m.mem_write(D,descriptor);m.mem_write(S,common);m.reg_write(c.UC_ARM64_REG_X0,D);m.reg_write(c.UC_ARM64_REG_X1,S);m.reg_write(c.UC_ARM64_REG_X30,STOP)
 m.emu_start(start,STOP,count=500);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP
 expected=copy_common(descriptor,common);assert bytes(m.mem_read(D,0x1000))==expected
 assert bytes(m.mem_read(S,0x400))==common
 m.mem_write(C,command);m.mem_write(O,other);m.mem_write(CH,bytes(channel));m.mem_write(STACK+0x60,struct.pack('<Q',O))
 for reg,value in [(19,CH),(20,D),(24,C),(28,C+0x1f38)]:m.reg_write(getattr(c,'UC_ARM64_REG_X'+str(reg)),value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.emu_start(bstart,bend,count=500)
 assert m.reg_read(c.UC_ARM64_REG_PC)==bend
 assert bytes(m.mem_read(C,len(command)))==body(command,expected,other)
 counter=struct.unpack_from('<I',channel,0x204)[0];struct.pack_into('<I',channel,0x204,(counter+1)&0xffffffff)
 assert bytes(m.mem_read(CH,len(channel)))==channel
 assert bytes(m.mem_read(D,0x1000))==expected and bytes(m.mem_read(S,0x400))==common
report=dict(binary_sha256=sha,cases=1024,range=[hex(start),hex(end)],slice_sha256=hashlib.sha256(read(start,end-start)).hexdigest(),copies=COPIES,low_bit_flags=FLAGS,connected_native_body=[hex(bstart),hex(bend)],qualification='Complete native copy3DCommonPassthroughData followed by native ordinary command state-copy slice. Independent copy table and body model compared; entire buffers and channel counter checked. Separate native calls, not full processRenderSetup or submit. Synthetic client bytes have no shader/register validity; no mapping, allocation, native firmware consumption or rendering proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 native client-common -> descriptor -> command copy cases passed')
