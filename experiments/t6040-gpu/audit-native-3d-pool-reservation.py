"""Complete native3D pool reservation plus actual descriptor caller in RAM."""
import sys,struct,random,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parent
sys.path.insert(0,str(repo))
import unicorn as u
from unicorn import arm64_const as c
from native_3d_pool import reserve
source=repo/'audit-private-3d-pool.py'
ns={'__file__':str(source),'__name__':'pool_setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];BASE=0xfffffe0000000000
START,END=BASE+0x89a6624,BASE+0x89a679c
CALLER,CALLEND=BASE+0x895e788,BASE+0x895e7cc
STOP=0x24f000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(BASE+0x89a6000,4096);m.mem_map(BASE+0x895e000,4096);m.mem_map(0x200000,0x50000)
m.mem_write(START,read(START,END-START));m.mem_write(CALLER,read(CALLER,CALLEND-CALLER))
FW,SLOTS,RESOURCE,DM,FM,MVT,GET,LOCK,ACC,D,DVT=0x200000,0x203000,0x204000,0x205000,0x206000,0x207000,0x208000,0x209000,0x20a000,0x20b000,0x20d000
regs=[getattr(c,'UC_ARM64_REG_X'+str(j)) for j in range(31)];calls=[]
for address,value in ((RESOURCE+0x50,FM),(RESOURCE+0x58,DM),(FM,MVT),(DM,MVT),(MVT+0x158,GET),(ACC+0x5b0,FW),(DVT+0x2a0,START)):
 m.mem_write(address,struct.pack('<Q',value))
for table in (BASE+0x7ea7860,BASE+0x7ea8668):
 enc=struct.unpack('<Q',read(table+16+0x2a0,8))[0];assert BASE+0x7004000+(enc&0xffffffff)==START
active_stop=STOP

def hook(m,addr,size,user):
 if addr==active_stop or addr==BASE+0x895eaf0:m.emu_stop();return
 if addr==GET:
  obj=m.reg_read(regs[0]);assert obj in (DM,FM);calls.append('device_map' if obj==DM else 'firmware_map')
  m.reg_write(regs[0],device_base if obj==DM else firmware_base);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target in (GET,START)
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  assert target in (BASE+0xb7b13c4,BASE+0xb7b27c0)
  assert m.reg_read(regs[0])==LOCK;calls.append('lock' if target==BASE+0xb7b13c4 else 'unlock')
  m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604023);counts=dict(cases=0,found=0,full=0,absent=0,caller_cases=0,zero_cpu=0)
for i in range(2048):
 capacity=[0,1,2,3,16,256][i%6];cursor=[0,0xffffffff,rng.getrandbits(32)][i%3]
 slots=bytes(rng.choice([0,1,255]) for _ in range(capacity))
 if i%4==0:slots=bytes([1])*capacity
 absent=i%13==0
 cpu_base,device_base,firmware_base=[rng.getrandbits(64) for _ in range(3)]
 if i%37==1:slots=bytes(capacity);cursor=0;cpu_base=0
 stride=[0x2240,0xffffffff,rng.getrandbits(32)][i%3]
 fw=bytearray(rng.randbytes(0x1400));struct.pack_into('<QQQQI',fw,0x1320,RESOURCE,cpu_base,0 if absent else SLOTS,stride,capacity)
 struct.pack_into('<I',fw,0x1344,cursor);struct.pack_into('<Q',fw,0x1350,LOCK);struct.pack_into('<Q',fw,0,DVT)
 desc=bytearray(rng.randbytes(0x1800));struct.pack_into('<Q',desc,0x10,ACC);struct.pack_into('<Q',desc,0x438,0)
 original=bytes(desc);m.mem_write(D,original);m.mem_write(FW,bytes(fw));m.mem_write(SLOTS,slots or b'\0');calls.clear()
 # The actual descriptor caller invokes the entire request function.
 active_stop=CALLEND
 for reg in regs:m.reg_write(reg,0)
 m.reg_write(regs[19],D);m.reg_write(c.UC_ARM64_REG_SP,0x24e000);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(CALLER,CALLEND,count=10000)
 result=None if absent else reserve(slots,cursor,cpu_base,device_base,firmware_base,stride)
 expected=bytearray(desc);expected_fw=bytearray(fw)
 if result:
  struct.pack_into('<3Q',expected,0x438,result['cpu'],result['device'],result['firmware'])
  struct.pack_into('<I',expected_fw,0x1344,result['cursor']);struct.pack_into('<I',expected_fw,0x1348,int(result['cpu']==0))
  assert bytes(m.mem_read(SLOTS,capacity))==result['occupancy']
  assert calls==['lock','firmware_map','device_map','unlock'];counts['found']+=1;counts['zero_cpu']+=int(not result['cpu'])
 else:
  if not absent:struct.pack_into('<I',expected_fw,0x1348,1)
  assert calls==([] if absent else ['lock','unlock'])
  assert bytes(m.mem_read(SLOTS,capacity))==slots
  counts['absent' if absent else 'full']+=1
 assert bytes(m.mem_read(D,len(desc)))==bytes(expected),(i,'descriptor')
 assert bytes(m.mem_read(FW,len(fw)))==bytes(expected_fw),(i,'firmware')
 assert m.reg_read(c.UC_ARM64_REG_PC)==(CALLEND if result and result['cpu'] else BASE+0x895eaf0)
 assert m.reg_read(c.UC_ARM64_REG_SP)==0x24e000
 counts['cases']+=1;counts['caller_cases']+=1
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],counts=counts,ranges=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in ((START,END),(CALLER,CALLEND))],qualification='Actual ordinary3D descriptor reservation caller and complete native firmware request. Whole descriptor/firmware and occupancy compared; missing bitmap, zero capacity, full slots, cursor/u32 product/u64 address wrap tested. Lock/unlock and mapping158 services explicit checked callbacks. Both mapping objects reached through the same resource1320. Allocation/cache/context permissions, actual mappings, concurrency, GPU acceptance/completion unqualified.'),indent=2)+'\n');print(counts)
