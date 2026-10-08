#!/usr/bin/env python3
"""Qualify TA-specific initialization tail, with external lifecycle services explicit."""
from pathlib import Path
import sys
base=Path(__file__).with_name('audit-private-ta-inputs.py')
exec(compile(base.read_text().split('rng=random.Random(604012);')[0],str(base),'exec'))
START,END=0xfffffe0008a213dc,0xfffffe0008a21594
m.mem_write(START,read(START,END-START));GLOBAL=0xfffffe0007ea2000
m.mem_map(GLOBAL,4096);m.mem_write(GLOBAL+0x590,struct.pack('<Q',0x1234567890abcdef))
external_calls=[];allocated=0
# The base hook handle is removed there; ta_hook handles existing native operations.
# Intercept only explicit external BL service call sites before target execution.
SERVICES={0xfffffe0008a214dc:'lifecycle',0xfffffe0008a214e4:'state_init',0xfffffe0008a214ec:'lifecycle',0xfffffe0008a214f4:'state_init',0xfffffe0008a21508:'allocation'}
def external_hook(m,address,size,user):
    if address not in SERVICES:return
    kind=SERVICES[address];x0=m.reg_read(c.UC_ARM64_REG_X0);x1=m.reg_read(c.UC_ARM64_REG_X1);external_calls.append((kind,x0,x1))
    if kind=='allocation':assert x0==1 and x1==0x1234567890abcdef;m.reg_write(c.UC_ARM64_REG_X0,allocated)
    elif kind=='state_init':assert x0 in (D+0xdc8,D+0xd28)
    else:assert x0==D
    m.reg_write(c.UC_ARM64_REG_PC,address+4)
m.hook_add(u.UC_HOOK_CODE,external_hook)
ZERO_RANGES=[(0xc4c,0xd0d),(0x1148,0x1218),(0x121c,0x1270),(0xff0,0x1142),(0x1288,0x13c0),(0x13c8,0x13e8),(0xd98,0xda0),(0xe68,0xff0)]
def model(original,allocation):
    b=bytearray(original)
    for start,end in ZERO_RANGES:b[start:end]=bytes(end-start)
    for off,val,size in [(0x1218,0xffffffff,4),(0x1274,0xffffffff,4),(0x144,0xffffffff,4),(0xe28,0xffffffff,4),(0xe10,allocation,8),(0xf68,D+0xc4c,8),(0xf70,2,4)]:b[off:off+size]=val.to_bytes(size,'little')
    struct.pack_into('<Q',b,0x14d0,struct.unpack_from('<Q',original,0x14d0)[0]&0xfffff000003fffff)
    return bytes(b)
rng=random.Random(604021);counts=dict(ta_initialization_tail=0,external_lifecycle_calls=0);examples=[]
for i in range(1024):
    original=rng.randbytes(0x1800);allocated=0 if i%8==0 else rng.getrandbits(64);external_calls.clear();m.mem_write(D,original)
    for reg in regs:m.reg_write(reg,0)
    m.reg_write(c.UC_ARM64_REG_X19,D);m.reg_write(c.UC_ARM64_REG_SP,STACK-0x30)
    # Enter after the unqualified parent constructor; provide its saved frame.
    m.mem_write(STACK-0x10,struct.pack('<QQ',0,STOP));m.emu_start(START,STOP,count=2000)
    assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
    actual=bytes(m.mem_read(D,0x1800));expected=model(original,allocated)
    assert actual==expected,(i,[(hex(j),actual[j],expected[j]) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
    assert m.reg_read(c.UC_ARM64_REG_W0)==1;assert len(external_calls)==5;counts['ta_initialization_tail']+=1;counts['external_lifecycle_calls']+=len(external_calls)
    if i<2:examples.append(dict(allocation=hex(allocated),return_value=1,services=[dict(kind=k,x0=hex(x),x1=hex(y)) for k,x,y in external_calls]))
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,zero_ranges=[[hex(a),hex(b)] for a,b in ZERO_RANGES],examples=examples,qualification='Actual complete TA-specific constructor tail after its parent call. Full destination byte comparisons with random original bytes. Parent AGX3D constructor, lifecycle/state_init helpers and allocation semantics excluded; service calls intercepted with explicit no-op/result fixtures. The caller frame is supplied, PAC bypassed. Return1 even with allocation0 is observed in this tail, not a proof null allocation is valid for a render job. No live initialization or GPU submission.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
