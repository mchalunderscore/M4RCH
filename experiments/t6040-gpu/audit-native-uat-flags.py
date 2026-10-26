"""Execute native UAT flags encoder and characterize all supported inputs."""
import sys,struct,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parent;sys.path.insert(0,str(repo))
import unicorn as u
from unicorn import arm64_const as c
from native_uat_flags import encode,DPRR,legacy_g16
source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'uat_setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];BASE=0xfffffe0000000000;START,END=BASE+0x8a32588,BASE+0x8a32694;STOP=0x20f000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
m.mem_map(BASE+0x8a32000,4096);m.mem_map(BASE+0x7131000,4096);m.mem_map(0x200000,0x10000)
m.mem_write(START,read(START,END-START));table=read(BASE+0x71313f4,64);m.mem_write(BASE+0x71313f4,table);assert struct.unpack('<16I',table)==DPRR
GUARDS=(BASE+0x8a3261c,BASE+0x8a32644,BASE+0x8a3266c)
def hook(m,addr,size,user):
 if addr in (*GUARDS,STOP):m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f:m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
m.hook_add(u.UC_HOOK_CODE,hook)
counts=dict(encoded=0,guard=0);examples=[]
# All input flag words0..1023, both valid apertures and one invalid aperture.
for aperture in (0,1,2):
 for flags in range(1024):
  m.reg_write(c.UC_ARM64_REG_X0,0x200000);m.reg_write(c.UC_ARM64_REG_W1,aperture);m.reg_write(c.UC_ARM64_REG_W2,flags)
  m.reg_write(c.UC_ARM64_REG_SP,0x20e000);m.reg_write(c.UC_ARM64_REG_LR,STOP)
  m.emu_start(START,STOP,count=80)
  try:expected=encode(aperture,flags)
  except ValueError:
   guard=GUARDS[0] if aperture>=2 else GUARDS[1] if flags&~0x30f else GUARDS[2]
   assert m.reg_read(c.UC_ARM64_REG_PC)==guard;counts['guard']+=1
  else:
   assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_X0)==expected
   assert m.reg_read(c.UC_ARM64_REG_SP)==0x20e000;counts['encoded']+=1
   examples.append(dict(aperture=aperture,flags=hex(flags),pte_flags=hex(expected)))
LEGACY=BASE+0x89dcad8
m.mem_map(BASE+0x89dc000,4096);m.mem_write(LEGACY,read(LEGACY,36))
for flags in list(range(1024))+[0xffffffff,0x80000000,0x80000001]:
 m.reg_write(c.UC_ARM64_REG_W1,flags);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(LEGACY,STOP,count=30)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_X0)==legacy_g16(flags)
counts['legacy_encoded']=1027
bindings=[]
for vtable,target,length in ((BASE+0x7eba590,START,0x1e0),(BASE+0x7eace28,LEGACY,0x290)):
 found=[]
 for slot in range(0,length,8):
  word=struct.unpack('<Q',read(vtable+16+slot,8))[0]
  if BASE+0x7004000+(word&0xffffffff)==target:found.append(slot)
 assert len(found)==1
 bindings.append(dict(vtable=hex(vtable),slot=hex(found[0]),target=hex(target)))
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],counts=counts,function=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),bindings=bindings,lookup=list(DPRR),lookup_sha256=hashlib.sha256(table).hexdigest(),examples=examples,qualification='Complete native generic AGXUnifiedAddressTranslator PTE encoder in emulated RAM, all0..1023 flag words and apertures0/1/2. Separately1027 actualLegacyG16 encoder calls and numeric vtable dispatch targets verified; the two encoders take different arguments. Native panic guards stopped before diagnostic. Lookup constant copied as numeric data, arithmetic independently modeled. This does not qualify translation from64-bit resource mapping API options to encoder inputs or actual mapping dispatch/cache behavior.'),indent=2)+'\n');print(counts)
