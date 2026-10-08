#!/usr/bin/env python3
"""Execute both complete native TA loaders against independent numeric models."""
from pathlib import Path
import sys
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','base_hook_handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'))
m.hook_del(base_hook_handle)
from private_ta_inputs import load_ta_parameter_management,load_ta_render_target
TPM,TRTM,END=0xfffffe0008a20cbc,0xfffffe0008a20ea0,0xfffffe0008a213ac
m.mem_map(0xfffffe0008a20000,0x2000);m.mem_write(TPM,read(TPM,END-TPM))
Q,R2,VT2,QVT=0x20c000,0x20d000,0x20e000,0x20f000
m.mem_write(Q,struct.pack('<Q',QVT));m.mem_write(Q+0x20,struct.pack('<Q',R2));m.mem_write(R2,struct.pack('<Q',VT2))
TARGETS={0x20b000:('primary',0x158,R),0x210000:('primary',0x160,R),0x210008:('support',0x158,R2),0x210010:('support',0x160,R2),0x210018:('retain',0x20,Q)}
for table,slot,target in [(VT,0x160,0x210000),(VT2,0x158,0x210008),(VT2,0x160,0x210010),(QVT,0x20,0x210018)]:m.mem_write(table+slot,struct.pack('<Q',target))
TRAPS.update([0xfffffe0008a20d10,0xfffffe0008a20e84,0xfffffe0008a20e90,0xfffffe0008a20e9c])
services=[];returns=[]
original_hook=hook

def ta_hook(m,address,size,user):
    word=struct.unpack('<I',m.mem_read(address,4))[0]
    if word==0xd50323ff:m.reg_write(c.UC_ARM64_REG_PC,address+4);return
    if word&0xfffffc00==0xd73f0800:
        target=m.reg_read(regs[(word>>5)&31])
        if target in TARGETS:
            resource,slot,expected=TARGETS[target];assert m.reg_read(c.UC_ARM64_REG_X0)==expected
            value=returns[len(services)];services.append((resource,slot,value))
            m.reg_write(c.UC_ARM64_REG_X0,value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
    original_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,ta_hook)
rng=random.Random(604012);counts=dict(ta_render_target=0,ta_parameter=0,ta_parameter_trap=0);examples=[];trap_sites={}
for i in range(1024):
    descriptor=rng.randbytes(0x1800);source=bytearray(rng.randbytes(0x400))
    struct.pack_into('<Q',source,0x130,N);struct.pack_into('<Q',source,0x1c0,Q);struct.pack_into('<I',source,0x3c,i%4)
    for n,off in enumerate(range(0x1d8,0x218,8)):struct.pack_into('<Q',source,off,0 if not(i&(1<<n)) else rng.getrandbits(64)|1)
    returns=[rng.getrandbits(64) for _ in range(16)];services.clear();expected_calls=[]
    def service(resource,slot):
        value=returns[len(expected_calls)];expected_calls.append((resource,slot,value));return value
    expected=load_ta_render_target(descriptor,source,service)
    m.mem_write(D,descriptor);m.mem_write(S,bytes(source));run(TRTM)
    assert bytes(m.mem_read(D,len(descriptor)))==expected,(i,'RTM')
    assert services==expected_calls,(i,services,expected_calls)
    assert bytes(m.mem_read(S,len(source)))==bytes(source);counts['ta_render_target']+=1
    if i in [0,1,2,255]:examples.append(dict(case=i,groups=i%4,service_order=[dict(resource=a,slot=hex(b)) for a,b,_ in services]))
    va=[rng.getrandbits(64) for _ in range(32)];vb=[rng.getrandbits(64) for _ in range(32)];capacity=1+i%32;index=i%capacity
    if i%8==0:capacity=0
    elif i%8==1:index=capacity
    elif i%8==2:capacity=1<<29
    elif i%8==3:index=1<<28
    struct.pack_into('<Q',source,0,PV);struct.pack_into('<Q',source,0x88,VB);struct.pack_into('<Q',source,0xa8,0 if i%8==4 else VA);struct.pack_into('<I',source,0xb0,capacity);struct.pack_into('<I',source,0x2c,index)
    try:expected=load_ta_parameter_management(descriptor,source,va,vb,[0,0,0]);invalid=False
    except ValueError:invalid=True
    m.mem_write(D,descriptor);m.mem_write(S,bytes(source));m.mem_write(VA,struct.pack('<32Q',*va));m.mem_write(VB,struct.pack('<32Q',*vb));run(TPM)
    if invalid:
        assert trap is not None;assert bytes(m.mem_read(D,len(descriptor)))==descriptor;assert not getter_calls
        counts['ta_parameter_trap']+=1;trap_sites[hex(trap)]=trap_sites.get(hex(trap),0)+1
    else:
        assert trap is None;assert bytes(m.mem_read(D,len(descriptor)))==expected,(i,'PM');assert getter_calls==GETTERS*2
        counts['ta_parameter']+=1
    assert bytes(m.mem_read(S,len(source)))==bytes(source)
report=dict(binary_sha256=sha,base_harness_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),counts=counts,trap_sites=trap_sites,service_examples=examples,functions=[dict(start=hex(a),end=hex(b),sha256=hashlib.sha256(read(a,b-a)).hexdigest()) for a,b in [(TPM,TRTM),(TRTM,END)]],qualification='Complete native TA loaders, including actual 3D PM tail and six native zero getters. Full 0x1800 destination byte comparisons, unchanged source checks. PAC bypassed. Primary/support resource maps and retain services use independent ordered synthetic returns; actual mapping permissions, object lifetime and live render-job validity are not proved. 1024 RT cases cover group counts 0..3 and every support presence bitmask. PM overflow/null/out-of-range traps intercepted. No GPU commands submitted.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts,trap_sites)
