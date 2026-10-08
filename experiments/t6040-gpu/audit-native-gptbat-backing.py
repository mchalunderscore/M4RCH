"""Qualify native GPTBAT allocation arguments, zeroing and object binding slices."""
import struct,random,json,hashlib
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
repo=Path(__file__).resolve().parent;p=repo/'audit-private-3d-pool.py';ns={'__file__':str(p),'__name__':'setup'}
exec(compile(p.read_text().split('m=u.Uc')[0],str(p),'exec'),ns)
read=ns['read'];B=0xfffffe0000000000;ALLOC=B+0x8a12cf4;ZERO=B+0x8a12db4
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.mem_map(B+0x8a12000,4096);m.mem_write(ALLOC,read(ALLOC,0x20));m.mem_write(ZERO,read(ZERO,0xbc));m.mem_map(0x300000,0x100000)
SM=0x300000;DESC=0x301000;MAP=0x302000;SHIFT=0x303000;DATA=0x320000;STACK=0x3ff000
rng=random.Random(604096);calls=[];counts=dict(allocation_cases=512,allocation_failure=0,new_zeroed=0,inherited_preserved=0)
def hook(mu,addr,size,unused):
 if addr in (B+0x8a12d14,B+0x8a12c14,B+0x8a12e40,B+0x8a12e70):mu.emu_stop();return
 if addr==B+0x8a12d08:
  args=tuple(mu.reg_read(r) for r in (c.UC_ARM64_REG_X0,c.UC_ARM64_REG_X1,c.UC_ARM64_REG_X2))
  assert args==(3,1<<shift,1<<shift);calls.append(args);mu.reg_write(c.UC_ARM64_REG_X0,0 if failure else DESC);mu.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
for i in range(512):
 shift=12 if i&1 else 14;failure=i%5==0;size=1<<shift
 m.mem_write(SHIFT,struct.pack('<I',shift));calls.clear()
 for reg,val in [(c.UC_ARM64_REG_X21,size),(c.UC_ARM64_REG_X22,SHIFT),(c.UC_ARM64_REG_X24,1),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(ALLOC,B+0x8a12d14,count=100)
 assert m.reg_read(c.UC_ARM64_REG_PC)==(B+0x8a12c14 if failure else B+0x8a12d14) and calls==[(3,size,size)]
 counts['allocation_failure']+=failure
 image=bytearray(rng.randbytes(0x30000));inherited=bool(i&2)
 m.mem_write(SM,bytes(image))
 for reg,val in [(c.UC_ARM64_REG_X0,DATA),(c.UC_ARM64_REG_X19,SM),(c.UC_ARM64_REG_X20,DESC),(c.UC_ARM64_REG_X21,size),(c.UC_ARM64_REG_X22,MAP),(c.UC_ARM64_REG_X23,int(inherited)),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(ZERO,B+0x8a12e70,count=5000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==(B+0x8a12e70 if inherited else B+0x8a12e40)
 struct.pack_into('<QQQ',image,0x10,DESC,MAP,DATA)
 if not inherited:image[DATA-SM:DATA-SM+size]=bytes(size)
 assert bytes(m.mem_read(SM,len(image)))==image,i
 counts['inherited_preserved' if inherited else 'new_zeroed']+=1
result=dict(binary_sha256=ns['sha'],counts=counts,ranges={name:dict(start=hex(a),end=hex(b),sha256=hashlib.sha256(read(a,b-a)).hexdigest()) for name,a,b in [('generic_allocation',ALLOC,ALLOC+0x20),('zero_and_bind',ZERO,ZERO+0xbc)]},findings=['Generic allocation service arguments (3,page_bytes,page_bytes); service identity/semantics not executed','New path zeros page_bytes before binding; inherited path preserves every byte','secureMonitor10 descriptor,18 mapping object,20 CPU pointer bound in both paths','12/14 page shifts exercised; current G16 profile14; size16KiB holds1024 16-byte pairs by arithmetic, audited context ID domain remains0..127'],qualification='Actual native bounded slices and whole randomized memory images. Allocation service supplied at checked callsite, descriptor/mapping/CPU address correspondence supplied, protected existing-resource allocation and mapping services not executed. Zeroing audit is independent of allocation outcome; it does not continue a failed allocation. No live GPU allocation, context, firmware or register publication.')
ns['a'].output.write_text(json.dumps(result,indent=2)+'\n');print(counts)
