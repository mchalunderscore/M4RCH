"""Execute G16 Gart geometry initializers and native legacy leaf update."""
import sys,struct,json,hashlib,random
from pathlib import Path
repo=Path(__file__).resolve().parent
sys.path.insert(0,str(repo))
from native_uat_flags import legacy_g16
from native_g16_mapping import leaf_update,context_root
import unicorn as u
from unicorn import arm64_const as c
source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];B=0xfffffe0000000000
for table,slot,target in [(0x7eae388,0x11b0,0x895f11c),(0x7eae388,0x1168,0x895f33c),(0x7ead9a0,0x168,0x89e6dac),(0x7ead9a0,0x198,0x89e675c)]:
 encoded=struct.unpack('<Q',read(B+table+16+slot,8))[0]
 assert B+0x7004000+(encoded&0xffffffff)==B+target
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for va,n in [(B+0x895f000,4096),(B+0x89e6000,4096),(B+0x89dc000,4096),(B+0x89f2000,4096),(B+0x89f3000,4096),(B+0x712d000,4096),(B+0xc6e5000,4096),(B+0x7ea2000,4096),(0x300000,0x100000)]:m.mem_map(va,n)
INIT=[B+0x89dc90c,B+0x89dce3c];UPDATE=B+0x89f2328;ENC=B+0x89dcad8;COPY=B+0x89f3c20;STOP=0x3fff00;STACK=0x3ff000
for va,n in [(B+0x895f11c,0x48),(B+0x895f33c,0x48),(B+0x89e6dac,12),(B+0x89e675c,0x9c),(INIT[0],0xb0),(INIT[1],0xb0),(UPDATE,0x1ec),(B+0x89dcb40,0x218),(ENC,0x24),(COPY,0x48),(B+0x712d938,24),(B+0x712dd90,16)]:m.mem_write(va,read(va,n))
for va,value in [(B+0xc6e5ac0,16384),(B+0xc6e5ab0,14)]:m.mem_write(va,struct.pack('<I',value))
m.mem_write(B+0x7ea2388,struct.pack('<Q',0x3fe000));m.mem_write(0x3fe000,struct.pack('<I',14))
OBJ=0x300000;BACK=0x301000;GPU=0x320000;MIRROR=0x340000;MVT=0x341000;CALLBACK=0x342000;VT=0x34f000;ROOT=0x350000;MIDDLE=0x354000;LEAF=0x358000
rng=random.Random(604089);calls=[]
def hook(m,addr,size,user):
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or addr in (B+0x89f23b0,B+0x89f24bc,B+0x89dcba0,B+0x89dcc28,B+0x89dcc7c,B+0x89dcca8,B+0x895f13c,B+0x895f35c):m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
 elif addr==B+0x89f23c8:
  assert m.reg_read(c.UC_ARM64_REG_X8)==ENC
  calls.append(('encode',m.reg_read(c.UC_ARM64_REG_W1)))
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,ENC)
 elif addr==B+0x89dccb0:
  m.reg_write(c.UC_ARM64_REG_X17,m.reg_read(c.UC_ARM64_REG_X16));m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif addr in (B+0x89dcbb4,B+0x89dcc90):
  assert m.reg_read(c.UC_ARM64_REG_X8)==GET_TTB and m.reg_read(c.UC_ARM64_REG_X0)==GPU
  calls.append(('get_ttbat',));m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,GET_TTB)
 elif addr==B+0x89dcc44:
  assert m.reg_read(c.UC_ARM64_REG_X8)==INVALIDATE and m.reg_read(c.UC_ARM64_REG_X0)==GPU
  calls.append(('invalidate',m.reg_read(c.UC_ARM64_REG_W1),m.reg_read(c.UC_ARM64_REG_W2)));m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,INVALIDATE)
 elif addr in (B+0x895f15c,B+0x895f37c):
  target=B+0x89e6dac if addr==B+0x895f15c else B+0x89e675c
  assert m.reg_read(c.UC_ARM64_REG_X16)==target and m.reg_read(c.UC_ARM64_REG_X0)==SM
  m.reg_write(c.UC_ARM64_REG_PC,target)
 elif addr==B+0x89e679c:
  assert m.reg_read(c.UC_ARM64_REG_X0)==GPU and m.reg_read(c.UC_ARM64_REG_X1)==0xd08030
  assert m.reg_read(c.UC_ARM64_REG_W2)==(old<<8)
  service_events.append(('write',0xd08030,old<<8));m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif addr==B+0x89e67c4:
  assert m.reg_read(c.UC_ARM64_REG_X0)==GPU and m.reg_read(c.UC_ARM64_REG_X1)==0xd08030
  service_events.append(('read',0xd08030));m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
 elif addr==B+0x89dccd8:
  assert m.reg_read(c.UC_ARM64_REG_X9)==B+0x89dcd40 and m.reg_read(c.UC_ARM64_REG_X0)==OBJ and m.reg_read(c.UC_ARM64_REG_W1)==0
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,B+0x89dcd40)
 elif addr==B+0x89dcd48:
  assert m.reg_read(c.UC_ARM64_REG_X0)==DESCRIPTOR
  calls.append(('root_physical',));m.reg_write(c.UC_ARM64_REG_X0,root_pa);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
 elif addr==B+0x89f2510:
  assert m.reg_read(c.UC_ARM64_REG_X16)==CALLBACK
  calls.append(('mirror',m.reg_read(c.UC_ARM64_REG_X0),m.reg_read(c.UC_ARM64_REG_X1),m.reg_read(c.UC_ARM64_REG_X2),m.reg_read(c.UC_ARM64_REG_W3)))
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
m.hook_add(u.UC_HOOK_CODE,hook)
def execute(start,x0,x1=0,x2=0,x3=0,x4=0):
 for reg,val in [(c.UC_ARM64_REG_X0,x0),(c.UC_ARM64_REG_X1,x1),(c.UC_ARM64_REG_X2,x2),(c.UC_ARM64_REG_X3,x3),(c.UC_ARM64_REG_X4,x4),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 try:m.emu_start(start,STOP,count=300)
 except u.UcError:
  print("failed",hex(m.reg_read(c.UC_ARM64_REG_PC)),"iteration",globals().get("i"));raise
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
geometry=bytearray(96)
for j,(shift,count,mask) in enumerate([(36,64,0x3f000000000),(25,2048,0xffe000000),(14,2048,0x1ffc000)]):
 struct.pack_into('<BBBBHHQQQ',geometry,j*32,8,14,14,shift,count,16384,1,0x3ffffffc000,mask)
for i in range(64):
 original=bytearray(rng.randbytes(0xd0));expected=bytearray(original)
 struct.pack_into('<H',expected,0x18,16384);expected[0x1a]=14;expected[0x1b]=3;expected[0x1c:0x7c]=geometry;expected[0x78:0x80]=bytes(8)
 for start in INIT:
  m.mem_write(BACK,bytes(original));execute(start,BACK)
  assert bytes(m.mem_read(BACK,len(original)))==expected
# Execute the actual caller's contiguous copy from backing1c to Gart390.
m.mem_write(OBJ+0x10,struct.pack('<Q',GPU));m.mem_write(GPU+0x18d08,struct.pack('<Q',BACK));m.mem_write(BACK+0x1c,bytes(geometry))
m.reg_write(c.UC_ARM64_REG_X19,OBJ);m.emu_start(COPY,COPY+0x48,count=30)
assert bytes(m.mem_read(OBJ+0x390,96))==geometry
counts=dict(initializers=128,caller_geometry_copy=1,updates=0,unchanged=0,mirror_callbacks=0,high_physical_cases=0)
A=0xfffffc2000000000;D=0xfffffc2180000000;E=0xfffffc2181400000;F=E+0x4000000
bounds=[A-1,A,A+1,D-1,D,D+1,E-1,E,E+1,F-1,F,F+1]
for i in range(1536):
 va=rng.randrange(1<<42) if i<1024 else bounds[(i-1024)%len(bounds)]
 pa=(0x10000000000+rng.randrange(0x600000000)//16384*16384) if i%2 else rng.randrange(1<<28)*16384
 flags=rng.getrandbits(32);check=bool(i&1);same=bool(i&2);entry=(pa&0x3ffffffc000)|legacy_g16(flags)
 indices=[(va>>36)&63,(va>>25)&2047,(va>>14)&2047]
 image=bytearray(rng.randbytes(0x60000))
 def put(addr,value,fmt='<Q'):struct.pack_into(fmt,image,addr-OBJ,value)
 image[0x390:0x3f0]=geometry;put(OBJ,VT);put(OBJ+0x10,GPU);put(OBJ+0x330,ROOT);put(VT+0x270,ENC)
 put(ROOT+indices[0]*8,MIDDLE);put(MIDDLE+indices[1]*8,LEAF)
 previous=entry if same else entry^1;put(LEAF+indices[2]*8,previous)
 counter=rng.getrandbits(32);put(OBJ+0x3f0,counter,'<I');put(GPU+0x5b0,MIRROR);put(MIRROR,MVT);put(MVT+0x2f0,CALLBACK)
 m.mem_write(OBJ,bytes(image));calls.clear();execute(UPDATE,OBJ,va,pa,flags,int(check))
 plan=leaf_update(va,pa,flags,previous,check,counter)
 assert tuple(indices)==plan["indices"] and entry==plan["pte"]
 changed=plan["changed"]
 if changed:put(LEAF+indices[2]*8,entry);put(OBJ+0x3f0,plan["counter"],'<I');counts['updates']+=1
 else:counts['unchanged']+=1
 mirror=plan["mirror"]
 expected=[('encode',flags)]
 if mirror:expected.append(('mirror',MIRROR,va,pa,flags&1));counts['mirror_callbacks']+=1
 assert calls==expected,(i,hex(va),calls,expected)
 assert bytes(m.mem_read(OBJ,len(image)))==image,i
 if pa&(1<<40):counts['high_physical_cases']+=1
# Actual context registration: TTBAT services are checked boundaries, no MMIO.
TTBAT=0x360000;GVT=0x361000;GET_TTB=B+0x895f11c;INVALIDATE=B+0x895f33c;SM=0x365000;SMVT=0x366000;service_events=[];DESCRIPTOR=0x364000
counts.update(context_registered=0,context_removed=0,old_context_invalidated=0,direct_invalidation=0,service_invalidation=0)
for i in range(1024):
 selector=i&1;old=-1 if i%5==0 else rng.randrange(128);new=-1 if i%7==0 else rng.randrange(128)
 root_pa=0x10000000000+rng.randrange(0x600000000);image=bytearray(rng.randbytes(0x90000))
 def put(addr,value,fmt='<Q'):struct.pack_into(fmt,image,addr-OBJ,value)
 put(OBJ,VT);put(OBJ+0x10,GPU);put(OBJ+0x300,DESCRIPTOR);put(OBJ+0x230+selector*4,old&0xffffffff,'<I')
 put(VT+0x1c0,B+0x89dcd40);put(GPU,GVT);put(GVT+0x11b0,GET_TTB);put(GVT+0x1168,INVALIDATE)
 put(GPU+0x1aef0,SM);put(SM,SMVT);put(SM+0x20,TTBAT);put(SM+0x40,GPU)
 put(SMVT+0x168,B+0x89e6dac);put(SMVT+0x198,B+0x89e675c)
 put(GPU+0xc774,i&1,'<I');put(GPU+0xc980,0xd00000);put(GPU+0xf8e8,0x380000)
 service_events.clear()
 expected=[]
 if old>=0:
  first=rng.getrandbits(64);second=rng.getrandbits(64)
  if i%3==0:first&=~1;second&=~1
  put(TTBAT+old*16,first);put(TTBAT+old*16+8,second);expected.append(('get_ttbat',))
 m.mem_write(OBJ,bytes(image));calls.clear();execute(B+0x89dcb40,OBJ,new&0xffffffff,selector)
 if old>=0 and (first|second)&1:
  put(TTBAT+old*16,first&~1);put(TTBAT+old*16+8,second&~1)
  expected.append(('invalidate',old,0));counts['old_context_invalidated']+=1
  if i&1:
   put(0x388030,old<<8,'<I');counts['direct_invalidation']+=1
  else:
   assert service_events==[('write',0xd08030,old<<8),('read',0xd08030)];counts['service_invalidation']+=1
 put(OBJ+0x230+selector*4,new&0xffffffff,'<I')
 if new>=0:
  ttbr0,ttbr1=context_root(root_pa,new);put(TTBAT+new*16,ttbr0);put(TTBAT+new*16+8,ttbr1)
  expected += [('get_ttbat',),('root_physical',)];counts['context_registered']+=1
 else:counts['context_removed']+=1
 assert calls==expected,(i,calls,expected)
 assert bytes(m.mem_read(OBJ,len(image)))==image,i
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],counts=counts,geometry_blocks=[dict(entry_bytes=8,physical_output_shift=14,physical_input_shift=14,va_shift=s,entries=n,allocation_bytes=16384,valid=1,physical_mask='0x3ffffffc000',va_mask=hex(mask)) for s,n,mask in [(36,64,0x3f000000000),(25,2048,0xffe000000),(14,2048,0x1ffc000)]],ranges={name:dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for name,start,end in [('shared_init',INIT[0],INIT[0]+0xb0),('legacy_shared_init',INIT[1],INIT[1]+0xb0),('caller_copy',COPY,COPY+0x48),('legacy_update',UPDATE,UPDATE+0x1ec),('context_registration',B+0x89dcb40,B+0x89dcd58),('accelerator_getter',B+0x895f11c,B+0x895f164),('accelerator_invalidate',B+0x895f33c,B+0x895f384),('g16_invalidate',B+0x89e675c,B+0x89e67f8),('g16_getter',B+0x89e6dac,B+0x89e6db8)]},mirror_ranges=[[hex(A),hex(D)],[hex(E),hex(F)]],qualification='Actual G16 initializer numeric constants, two128-byte initializer outputs checked in128 randomized images with16KiB page globals; actual caller geometry copy and1536 whole native legacy updates. Actual G16 encoder slot270 executed, PAC bypassed. External mirror callback target and arguments checked, body not executed. Native masks preserve physical bit40 and six root bits. Additionally1024 actual context registration/removal executions; old pair valid bits cleared before executed native accelerator/secure-monitor invalidation chain. Actual getter follows accelerator1aef0 -> secureMonitor20. Invalidation follows secureMonitor40 accelerator and writes context<<8 to GFXd08030 with readback; both external register services and RAM-surrogate direct branch checked, replacement TTBR0 encodes aligned root physical plus ASID48 and valid1, TTBR1 zero. Native root physical getter executed but external physical-address service supplied. G16 and secure-monitor virtual slot targets checked against pinned binary tables; flags argument0 only in this composed registration audit. No live context registration, hardware invalidate behavior, cache/TLB behavior, live translation or rendering proved.'),indent=2)+'\n');print(counts)
