import sys,struct,random,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
import importlib.util
spec=importlib.util.spec_from_file_location('prepare',ROOT/'experiments/t6040-gpu/prepare-native-sksm-registers.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
out=ROOT/'out/gpu-gravity-native-rce-typed-v9-qualification';out.mkdir(exist_ok=True)
rs='''#[path="/home/alice/Desktop/m4rch/out/private-apple/native-rce-semantic-v9.rs"] mod g16_native_rce_semantic_v9;
#[path="/home/alice/Desktop/m4rch/experiments/t6040-gpu/desktop-integration/t6040-native-boot/g16_t6040_rce_ram_v9.rs"] mod typed;
use std::{env,fs};
fn q(d:&[u8],o:usize)->u64{u64::from_le_bytes(d[o..o+8].try_into().unwrap())}
fn main(){let a:Vec<String>=env::args().collect();let mut d=fs::read(&a[1]).unwrap();let pc=u64::from_str_radix(&a[4],16).unwrap();let mapped=u64::from_str_radix(&a[5],16).unwrap();let kind=if pc==0xfffffe00089dd2c4{typed::Kind::Tiling}else{typed::Kind::Fragment};let command_gpu=q(&d,0x26000+if pc==0xfffffe00089dd2c4{0xfa0}else{0x440});
let providers=typed::Providers{gpu_clusters:q(&d,0x4e4) as u32,address_bit47:q(&d,0x6d0)&(1<<47)!=0,descriptor_policy:d[0x6d9],fragment_policy:d[0x111a8],controller_mode:q(&d,0x29980) as u32,controller_feature:q(&d,0x29810) as u32,command_gpu,parameter_gpu:mapped};
let mut command:[u8;0x3000]=d[0x22000..0x25000].try_into().unwrap();let mut descriptor:[u8;0x1800]=d[0x26000..0x27800].try_into().unwrap();let context:[u8;0x100]=d[0x2c000..0x2c100].try_into().unwrap();let scene:[u8;0x100]=d[0x38000..0x38100].try_into().unwrap();let mut scratch=[0;0x400];
let mut backing=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,context:&context,scene:&scene,providers};backing.produce(kind).unwrap();d[0x22000..0x25000].copy_from_slice(&command);d[0x26000..0x27800].copy_from_slice(&descriptor);fs::write(&a[3],d).unwrap();}
'''.replace('/home/alice/Desktop/m4rch',str(ROOT))
(out/'host.rs').write_text(rs);subprocess.run(['rustc','--edition=2021','-Awarnings',str(out/'host.rs'),'-o',str(out/'host')],check=True)
rng=random.Random(604099);cases=[];reads={}
for kind in ('ta','3d'):
 ns=p.harness(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'),out/'setup.json',kind);m,c=ns['m'],ns['c'];A,C,D=(ns[x] for x in ('A','C','D'))
 def read_hook(mu,access,address,size,value,user):
  if not (C<=address<C+0x3000 or D<=address<D+0x1800 or 0x24d000<=address<0x24f000 or ns['O']<=address<ns['O']+0x100 or 0x238000<=address<0x238100):reads[(address,size)]=bytes(mu.mem_read(address,size)).hex()
 m.hook_add(__import__('unicorn').UC_HOOK_MEM_READ,read_hook)
 (out/'constants.bin').write_bytes(ns['read'](0xfffffe000712d000,4096))
 for i in range(48):
  desc=bytearray(0x1800)
  # Arbitrary integer payloads; pointer-bearing service identities remain owned.
  for off in range(0x200,0x1800,8):struct.pack_into('<Q',desc,off,rng.getrandbits(64) if rng.randrange(3) else 0)
  # Restrict producer control/count fields to meaningful bounded domains.
  for off in (0x1558,0x1280,0x113a,0x113e,0x1140,0x897,0x88e,0x88f):desc[off]=rng.randrange(2)
  desc[0x960]=[0,2,3][i%3]
  for off in (0x4a4,0x4a8):struct.pack_into('<I',desc,off,[16,32][i%2])
  struct.pack_into('<I',desc,0x8c8,[1,2,4][i%3]);struct.pack_into('<I',desc,0xb88,i%8)
  reloc={0x190:ns['O'],0xb90:ns['R1'],0x918:0x238000,0x1230:0x238000,0x1428:ns['R1'],0xfa0:0x830000000+i*0x10000,0x440:0x830000000+i*0x10000}
  for off,v in reloc.items():struct.pack_into('<Q',desc,off,v)
  context=bytearray(rng.randbytes(0x100));scene=bytearray(rng.randbytes(0x100));context[0x54]=i%2;scene[0x54]=(i//2)%2
  m.mem_write(ns['O'],bytes(context));m.mem_write(0x238000,bytes(scene));m.mem_write(C,bytes(0x3000));m.mem_write(D,bytes(desc));m.mem_write(A+0x6d0,struct.pack('<Q',(i%2)<<47));m.mem_write(A+0x4e4,struct.pack('<I',1+i%2));m.mem_write(A+0x6d9,bytes([i%2]));m.mem_write(A+0x111a8,bytes([(i//2)%2]));m.mem_write(ns['T']+0x980,struct.pack('<I',(i//4)%2))
  mapped=0x870000000+i*0x10000;ns['mapped']=mapped;ns['pending']=None;ns['entries'].clear();ns['calls'].clear();ns['map_calls']=0
  (out/'input.bin').write_bytes(bytes(m.mem_read(0x200000,0x50000)))
  for r in ns['regs']:m.reg_write(r,0)
  for r,v in ((c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])):m.reg_write(r,v)
  m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP']
  expected=bytes(m.mem_read(0x200000,0x50000))
  subprocess.run([str(out/'host'),str(out/'input.bin'),str(out/'constants.bin'),str(out/'actual.bin'),f'{ns["START"]:x}',f'{mapped:x}'],check=True)
  actual=(out/'actual.bin').read_bytes()
  # Stack scratch intentionally differs at PAC identities; compare all outputs and read-only owned providers.
  for off,n in ((C-0x200000,0x3000),(D-0x200000,0x1800),(ns['O']-0x200000,0x100),(0x38000,0x100)):
   if actual[off:off+n]!=expected[off:off+n]:
    bad=[hex(j) for j in range(n) if actual[off+j]!=expected[off+j]];raise ValueError((kind,i,hex(off),bad[:20]))
  cases.append(dict(kind=kind,case=i,command_sha256=hashlib.sha256(actual[C-0x200000:C-0x200000+0x3000]).hexdigest(),native_encoder_calls=len(ns['entries'])))
  print(kind,i,flush=True)
(out/'qualification.json').write_text(json.dumps(dict(cases=cases,count=len(cases),qualification='Bounded typed Rust RAM adapter and portable semantic producer compared whole command 0x3000, descriptor 0x1800, read-only context/scene against actual native execution. Random integer payloads with bounded producer branch controls. No render parameter adapter or hardware acceptance.'),indent=2)+'\n')

(out/'read-providers.json').write_text(json.dumps([dict(address=hex(a),size=n,bytes=v) for (a,n),v in sorted(reads.items())],indent=2)+'\n')
