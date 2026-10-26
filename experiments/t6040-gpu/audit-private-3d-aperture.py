#!/usr/bin/env python3
"""Execute ordinary3D mcache caller and actual helper/HAL offline."""
import argparse
import hashlib
import json
import random
import struct
import sys
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_3d_command import aperture_records

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
source=Path(__file__).with_name('audit-private-ta-command.py')
code=source.read_text().split('rng = random.Random(604018)')[0]
ns={'__file__':str(source),'__name__':'ta_postproducer_setup'}
previous=sys.argv
try:
    sys.argv=[str(source),str(a.macho),str(a.output)]
    exec(compile(code,str(source),'exec'),ns)
finally:
    sys.argv=previous
m,read,BASE=ns['m'],ns['read'],ns['BASE']
D,C,CTX,CH,ACC,STACK=(ns[x] for x in ('D','C','CTX','CH','ACC','STACK'))
AVT=0x218000;STOP=0x22f000
START,END=BASE+0x895bbdc,BASE+0x895bc2c
m.mem_map(BASE+0x895b000,4096)
HELPER,HAL=BASE+0x895f738,BASE+0x89e8a9c
for page in (BASE+0x895f000,BASE+0x89e8000):m.mem_map(page,4096)
for start,end in [(START,END),(HELPER,BASE+0x895f878),(HAL,BASE+0x89e8ae0)]:
    m.mem_write(start,read(start,end-start))
for slot,target in [(0xfe8,HELPER),(0xfb8,HAL)]:
    encoded=struct.unpack('<Q',read(BASE+0x7eae388+16+slot,8))[0]
    assert BASE+0x7004000+(encoded&0xffffffff)==target
    m.mem_write(AVT+slot,struct.pack('<Q',target))
m.mem_write(ACC,struct.pack('<Q',AVT))
m.mem_write(CH+0x10,struct.pack('<Q',ACC))
m.mem_write(ACC+0x1aed4,b'\0')
calls=[]
def hook(m,addr,size,user):
    if addr==END:
        m.emu_stop();return
    word=struct.unpack('<I',m.mem_read(addr,4))[0]
    if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
        m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
    if word==0xd65f0fff:
        m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
    if word&0xfffffc00==0xd73f0800:
        target=m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)))
        assert target in (HELPER,HAL),hex(target)
        if target==HELPER:
            assert [m.reg_read(getattr(c,'UC_ARM64_REG_X'+str(j))) for j in range(5)]==[
                ACC,D+0x970,struct.unpack_from('<I',descriptor,0x144)[0],C+0xa0,0]
            calls.append('helper')
        else:
            calls.append('hal')
        m.reg_write(c.UC_ARM64_REG_LR,addr+4)
        m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604020);counts=dict(cases=0,empty=0,records=0)
for i in range(1024):
    descriptor=bytearray(rng.randbytes(0x1800));command=bytearray(rng.randbytes(0x2240))
    context=bytearray(rng.randbytes(0x600));count=i%17;flags=rng.getrandbits(8)
    struct.pack_into('<I',descriptor,0xa70,count);struct.pack_into('<Q',descriptor,0x438,C)
    pointer=[0,(1 << 64)-1,rng.getrandbits(64)][i%3]
    struct.pack_into('<Q',command,0x7a0,pointer)
    if i&1:context[0x390:0x3b0]=bytes(32)
    m.mem_write(D,bytes(descriptor));m.mem_write(C,bytes(command));m.mem_write(CTX,bytes(context))
    m.mem_write(ACC+0xf570,bytes([flags]));calls.clear()
    for reg in ns['regs']:m.reg_write(reg,0)
    for reg,val in [(c.UC_ARM64_REG_X19,CH),(c.UC_ARM64_REG_X20,D),
                    (c.UC_ARM64_REG_X24,C),(c.UC_ARM64_REG_X28,CTX),
                    (c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
    m.emu_start(START,END,count=10000)
    assert m.reg_read(c.UC_ARM64_REG_PC)==END
    expected,desc_expected=aperture_records(command,descriptor)
    assert bytes(m.mem_read(C,len(command)))==expected,(i,'command')
    assert bytes(m.mem_read(D,len(descriptor)))==desc_expected,(i,'descriptor')
    assert bytes(m.mem_read(CTX,len(context)))==bytes(context)
    assert calls==['helper']+['hal']*count
    assert m.reg_read(c.UC_ARM64_REG_SP)==STACK
    counts['cases']+=1;counts['empty']+=int(not count);counts['records']+=count
report=dict(binary_sha256=ns['sha'],counts=counts,
    ranges=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest())
        for start,end in [(START,END),(HELPER,BASE+0x895f878),(HAL,BASE+0x89e8ae0)]],
    qualification='Native postproducer caller through actual mcache aperture helper and G16 HAL encoder, full command/descriptor compared and caller context unchanged. Counts0..16, trace disabled, high address/pointer wrap and random record fields. Authentication skipped. No queue publication, cache visibility, actual GPU mappings, valid draw, completion or live hardware proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
