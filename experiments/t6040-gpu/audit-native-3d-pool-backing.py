"""Execute complete ordinary3D pool backing/mapping wrapper with explicit services."""
import sys,struct,random,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parent
import unicorn as u
from unicorn import arm64_const as c
source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'backing_setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];BASE=0xfffffe0000000000;START,END=BASE+0x89abdf0,BASE+0x89ac178;STOP=0x2ff000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
for addr,size in ((BASE+0x89ab000,8192),(BASE+0x7ea2000,4096),(BASE+0xc6e7000,4096),(0x200000,0x100000)):m.mem_map(addr,size)
m.mem_write(START,read(START,END-START))
POOL,RES,MD,DM,FM,CM,TYPE,MVT,SHIFT,DCTX,FCTX,BITMAP=0x200000,0x201000,0x202000,0x203000,0x204000,0x205000,0x206000,0x207000,0x208000,0x209000,0x20a000,0x20b000
GPU,RVT,MDVT,DMVT,FMVT,CMVT,NEW,CREATE,GET,RETAIN,RELEASE,CPUMAP,CPUADDR=0x220000,0x240000,0x241000,0x242000,0x243000,0x244000,0x250000,0x250004,0x250008,0x25000c,0x250010,0x250014,0x250018
regs=[getattr(c,'UC_ARM64_REG_X'+str(j)) for j in range(31)]
def q(addr,val):m.mem_write(addr,struct.pack('<Q',val))
q(BASE+0x7ea2388,SHIFT);q(BASE+0x7ea25c0,TYPE);q(TYPE,0x123456789abcdef0);q(BASE+0xc6e75c8,MVT);q(MVT+0xa8,NEW)
q(MD,MDVT);q(MDVT+0x150,CREATE);q(MDVT+0x228,CPUMAP)
for vt in (RVT,DMVT,FMVT,CMVT):
 for off,target in ((0x20,RETAIN),(0x28,RELEASE),(0x158,GET),(0x138,CPUADDR)):q(vt+off,target)
for obj,vt in ((DM,DMVT),(FM,FMVT),(CM,CMVT)):q(obj,vt)
q(DM+0x20,DCTX)
events=[];cpu_calls=0

def answer(value):m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
def hook(m,addr,size,user):
 global cpu_calls
 if addr==STOP or addr==BASE+0x89ac150:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0];x0,x1,x2,x3=[m.reg_read(regs[j]) for j in range(4)]
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==NEW:assert x0==BASE+0xc6e75c8;events.append('new');value=0 if failure==0 else RES
  elif target==CREATE:
   assert x0==MD
   if x2==0x600000085:assert x1==DCTX;events.append('create_device');value=0 if failure==2 else DM
   else:assert x1==FCTX and x2==0x20900000084;events.append('create_firmware');value=0 if failure==4 else FM
  elif target==GET:
   assert x0 in (DM,FM);events.append('device_address' if x0==DM else 'firmware_address');value=(0 if failure==3 else device_base) if x0==DM else (0 if failure==5 else firmware_base)
  elif target in (RETAIN,RELEASE):
   assert x0 in (RES,DM,FM);events.append(('retain:' if target==RETAIN else 'release:')+{RES:'resource',DM:'device',FM:'firmware'}[x0]);value=0
  elif target==CPUMAP:assert x0==MD and x1==0;events.append('cpu_map');value=0 if failure==6 else CM
  elif target==CPUADDR:
   assert x0==CM;cpu_calls+=1;events.append('cpu_address');value=0 if failure==(7 if cpu_calls==1 else 8) else cpu_base
  else:raise AssertionError((hex(addr),hex(target)))
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);answer(value);return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  if addr==BASE+0x89abea4:
   assert (x0,x1,x2,x3)==(RES,GPU,rounded,flags|0x23);events.append('init');value=int(failure!=1)
  elif target==BASE+0xa7f9f18:assert x0==GPU;events.append('device_context');value=DCTX
  elif target==BASE+0xa805a30:assert x0==MD;events.append('cpu_cast');value=MD
  elif target==BASE+0xbf25514:assert x0==rounded//stride;events.append('occupancy_allocate');value=0 if failure==9 else BITMAP
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);answer(value)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604024);counts=dict(cases=0,success=0,failure=0,context_guard=0,existing_device=0,existing_firmware=0,existing_cpu=0)
for i in range(2048):
 failure=i%12;requested=[1,2,3,16,128][i%5];stride=0x2240;shift=[12,14,16][i%3];flags=rng.getrandbits(32)
 rounded=(requested*stride+(1<<shift)-1)&-(1<<shift)
 device_base,firmware_base,cpu_base=[rng.randrange(1,1<<48) for _ in range(3)]
 existing_d=bool(i&16);existing_f=bool(i&32);existing_c=bool(i&64)
 pool=bytearray(rng.randbytes(0x80));struct.pack_into('<Q',pool,0x20,stride)
 resource=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',resource,0,RVT);struct.pack_into('<Q',resource,0x18,FCTX);struct.pack_into('<Q',resource,0x48,MD)
 struct.pack_into('<3Q',resource,0x50,FM if existing_f else 0,DM if existing_d else 0,CM if existing_c else 0)
 m.mem_write(POOL,bytes(pool));m.mem_write(RES,bytes(resource));m.mem_write(GPU+0x18e00,struct.pack('<I',flags));m.mem_write(SHIFT,struct.pack('<I',shift));q(DM+0x20,DCTX+8 if failure==10 else DCTX)
 expected_pool=bytearray(pool);struct.pack_into('<Q',expected_pool,0,GPU);expected_resource=bytearray(resource);expected_events=['new'];success=False;guard=False
 if failure!=0:
  struct.pack_into('<Q',expected_resource,0x10,0x123456789abcdef0);expected_events.append('init')
  stage_ok=failure!=1
  if stage_ok:
   expected_events.append('device_context')
   if not existing_d:
    expected_events.append('create_device');stage_ok=failure!=2
    if stage_ok:expected_events+=['retain:device','release:device'];struct.pack_into('<Q',expected_resource,0x58,DM)
   if stage_ok and failure==10:guard=True
   if stage_ok and not guard:
    expected_events.append('device_address');stage_ok=failure!=3
  if stage_ok and not guard:
   if not existing_f:
    expected_events.append('create_firmware');stage_ok=failure!=4
    if stage_ok:expected_events+=['retain:firmware','release:firmware'];struct.pack_into('<Q',expected_resource,0x50,FM)
   if stage_ok:expected_events.append('firmware_address');stage_ok=failure!=5
  if stage_ok and not guard:
   if not existing_c:
    expected_events+=['cpu_cast','cpu_map'];struct.pack_into('<Q',expected_resource,0x60,0 if failure==6 else CM);stage_ok=failure!=6
   if stage_ok:expected_events.append('cpu_address');stage_ok=failure!=7
  if stage_ok and not guard:
   struct.pack_into('<Q',expected_pool,8,RES);expected_events.append('cpu_address')
   if failure==8:
    struct.pack_into('<Q',expected_pool,0x10,0);expected_events.append('release:resource');struct.pack_into('<Q',expected_pool,8,0)
   else:
    struct.pack_into('<Q',expected_pool,0x10,cpu_base);struct.pack_into('<I',expected_pool,0x28,rounded//stride);expected_events.append('occupancy_allocate')
    struct.pack_into('<Q',expected_pool,0x18,0 if failure==9 else BITMAP)
    if failure==9:
     struct.pack_into('<Q',expected_pool,0x10,0);struct.pack_into('<Q',expected_pool,8,0);expected_events.append('release:resource')
    else:success=True
  elif not guard:expected_events.append('release:resource')
 events.clear();cpu_calls=0
 for reg in regs:m.reg_write(reg,0)
 for j,val in ((0,POOL),(1,requested),(2,GPU),(3,rng.getrandbits(64)),(4,i&1)):m.reg_write(regs[j],val)
 m.reg_write(c.UC_ARM64_REG_SP,0x2fe000);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(START,STOP,count=2500)
 assert events==expected_events,(i,events,expected_events)
 assert bytes(m.mem_read(POOL,len(pool)))==bytes(expected_pool),(i,'pool')
 assert bytes(m.mem_read(RES,len(resource)))==bytes(expected_resource),(i,'resource')
 if guard:
  assert m.reg_read(c.UC_ARM64_REG_PC)==BASE+0x89ac150;counts['context_guard']+=1
 else:
  assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==0x2fe000
  assert m.reg_read(c.UC_ARM64_REG_W0)==int(success)
  counts['success' if success else 'failure']+=1
 counts['cases']+=1;counts['existing_device']+=int(existing_d);counts['existing_firmware']+=int(existing_f);counts['existing_cpu']+=int(existing_c)
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],counts=counts,function=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),device_map_flags='0x600000085',firmware_map_flags='0x20900000084',qualification='Complete native pool createBacking wrapper with whole pool/resource comparisons, fresh/preexisting map branches and service failures. Context-mismatch path stops before native panic. InitInner, allocator, device-context, mapping creation/address, CPU cast/map/address, retain/release and occupancy allocator explicit checked callbacks. Mapping flags are native service arguments, not decoded Linux PTE/cache attributes. No actual allocation/DMA/cache/concurrency/retirement/rendering.'),indent=2)+'\n');print(counts)
