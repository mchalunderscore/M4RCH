#!/usr/bin/env python3
"""Compare typed resource-address conversion to both actual native getters."""
import hashlib,json,struct,subprocess,tempfile
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_SP,UC_ARM64_REG_PC
ROOT=Path(__file__).resolve().parents[4]
APPLE=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
SOURCE=Path(__file__).with_name('g16_t6040_resource_address_v9.rs')
BASE=0xfffffe0000000000
raw=APPLE.read_bytes(); segs=[];o=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,o)
 if cmd==0x19:segs.append(struct.unpack_from('<QQQQ',raw,o+24))
 o+=size

def read(vm,size):
 for start,extent,off,length in segs:
  if start<=vm and vm+size<=start+length:return raw[off+vm-start:off+vm-start+size]
 raise ValueError(hex(vm))

def native(kind,device,flag,index,base):
 start,end=(0x8a0ef74,0x8a0f030) if kind=='secure' else (0x89f11e4,0x89f1248)
 uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
 for page,size in [(start&~0xfff,0x2000),(0x200000,0x1000),(0x300000,0x2000),(0x7130000,0x2000)]:uc.mem_map(page,size)
 uc.mem_write(start,read(BASE+start,end-start))
 obj=bytearray(0x100);obj[0x58]=flag;obj[0x59]=index;struct.pack_into('<H',obj,0x12,index)
 struct.pack_into('<Q',obj,0x20,0x200100);struct.pack_into('<Q',obj,0,0x200200)
 uc.mem_write(0x200000,bytes(obj));uc.mem_write(0x200100,struct.pack('<Q',0x200200))
 uc.mem_write(0x7130810+index*0x20,struct.pack('<Q',base))
 uc.reg_write(UC_ARM64_REG_X0,0x200000);uc.reg_write(UC_ARM64_REG_SP,0x301000)
 calls=[]
 def hook(u,pc,size,data):
  ins=struct.unpack('<I',u.mem_read(pc,4))[0]
  if pc in [0x8a0efac,0x89f1218]:
   calls.append('device');u.reg_write(UC_ARM64_REG_X0,device);u.reg_write(UC_ARM64_REG_PC,pc+4)
  elif pc==0x8a0f000:
   calls.append('allocator');u.mem_write(u.reg_read(UC_ARM64_REG_X1),struct.pack('<Q',base));u.mem_write(u.reg_read(UC_ARM64_REG_X2),bytes(8));u.reg_write(UC_ARM64_REG_PC,pc+4)
  elif ins in [0xd503237f,0xdac11a30]:u.reg_write(UC_ARM64_REG_PC,pc+4)
  elif ins==0xd65f0fff:u.emu_stop()
 uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(start,end,count=200)
 assert calls==(['device','allocator'] if kind=='secure' and flag&1 and index==1 else ['device'])
 return uc.reg_read(UC_ARM64_REG_X0)

cases=[]
for kind in ['secure','legacy']:
 for flag in [0,1,2,3]:
  for index in [0,1,2,7]:
   for device,base in [(0x100001234,0x100000000),(0x7130810,0),(0x20,0x100),(0xfffffffedabcdef0,0x123456789)]:
    got=native(kind,device,flag,index,base);expected=(device-(base if flag&1 else 0))&((1<<64)-1)
    assert got==expected,(kind,flag,index,hex(got),hex(expected))
    cases.append(dict(kind=kind,flag=flag,index=index,device=device,base=base,user=got))
with tempfile.TemporaryDirectory(prefix='native-address-') as td:
 t=Path(td);rust='#[path='+json.dumps(str(SOURCE))+'] mod address;\nfn main(){\n'
 for c in cases:
  variant='Absolute' if not c['flag']&1 else ('Allocator { base: '+str(c['base'])+' }' if c['kind']=='secure' and c['index']==1 else 'Region { index: '+str(c['index'])+', base: '+str(c['base'])+' }')
  rust+='let a=address::Address::from_mapping('+str(c['device'])+',address::Aperture::'+variant+'); assert_eq!(a.user,'+str(c['user'])+'); assert_eq!(a.device,'+str(c['device'])+');\n'
 rust+='}\n';(t/'main.rs').write_text(rust)
 subprocess.run(['rustc','--edition=2021','-Dwarnings',str(t/'main.rs'),'-o',str(t/'run')],check=True)
 subprocess.run([str(t/'run')],check=True)
out=ROOT/'out/gpu-gravity-native-resource-address-v9';out.mkdir(parents=True,exist_ok=True)
def pin(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
report=dict(schema='m4rch.native-resource-address-v9.v1',cases=len(cases),actual_native_getters=['0x8a0ef74','0x89f11e4'],pins=[pin(SOURCE),pin(Path(__file__).resolve()),pin(APPLE)],hardware_actions=[],runtime_enabled=False,conclusion='Slot160 is user/aperture-relative device mapping address, not firmware-root alias. Native flag bit0 selects wrapping base subtraction. Caller must bind actual owning aperture and retain mapping; Linux context_base equivalence still requires selected resource aperture binding.')
(out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
