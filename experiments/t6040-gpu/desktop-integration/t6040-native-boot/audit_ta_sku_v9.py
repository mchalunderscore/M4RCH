from pathlib import Path
import sys,struct,random,json,hashlib,importlib.util
R=Path(__file__).resolve().parents[4];sys.path.insert(0,str(R/'experiments/t6040-gpu'))
from private_ta_sku_v9 import stream
spec=importlib.util.spec_from_file_location('p',R/'experiments/t6040-gpu/prepare-native-sksm-registers.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
O=R/'out/gpu-gravity-native-ta-sku-v9-source';O.mkdir(exist_ok=True)
ns=p.harness(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'),O/'setup.json','ta');u=__import__('unicorn');c=ns['c'];old=ns['m'];m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for start,end,prot in old.mem_regions():m.mem_map(start,end-start+1);m.mem_write(start,bytes(old.mem_read(start,end-start+1)))
BASE=0xfffffe0000000000;m.mem_write(BASE+0x89e7188,ns['read'](BASE+0x89e7188,0x89e7aec-0x89e7188));m.mem_map(BASE+0x8a16000,4096);m.mem_write(BASE+0x8a16ba4,ns['read'](BASE+0x8a16ba4,0x8a16ed0-0x8a16ba4))
A,C,D=ns['A'],ns['C'],ns['D'];CH,E,B,SP=0x239000,0x23a000,0x23b000,0x24d800
qwrite=lambda a,v:m.mem_write(a,struct.pack('<Q',v))
qwrite(CH,0x232000);qwrite(CH+0x10,A);qwrite(CH+0xa8,E);qwrite(E+8,A);qwrite(E+0x20,0x236000);qwrite(0x236000,0x237000);qwrite(0x237000+0x158,0x235100)
qwrite(ns['R1'],0x232000);qwrite(0x232000+0x1e0,0x235000);qwrite(0x232000+0x258,0x235200);qwrite(ns['P'],0x237000);qwrite(0x237000+0x2d8,0x235300)
values={};calls=[]
def hook(mu,address,size,user):
 word=struct.unpack('<I',mu.mem_read(address,4))[0]
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00 in (0xdac11800,0xdac10800) or word&0xffffffe0==0xdac147e0:mu.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word==0xd65f0fff:mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=mu.reg_read(ns['regs'][(word>>5)&31]);calls.append(hex(target))
  if target==0x235000:answer=values['resource_type']
  elif target==0x231000:answer=values['resource_map']
  elif target==0x235100:answer=values['stream_gpu']
  elif target==0x235200:answer=0
  elif target==0x235300:answer=values['stream_fw']+mu.reg_read(c.UC_ARM64_REG_X1)-values['stream_gpu']
  else:raise ValueError(hex(target))
  mu.reg_write(c.UC_ARM64_REG_X0,answer);mu.reg_write(c.UC_ARM64_REG_PC,address+4 if word&0xfffffc00==0xd73f0800 else mu.reg_read(c.UC_ARM64_REG_LR));return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=address+imm*4
  if target==BASE+0xb744bf0:
   dest,src,n=[mu.reg_read(ns['regs'][i]) for i in range(3)];assert n==0x1c8;mu.mem_write(dest,bytes(mu.mem_read(src,n)));mu.reg_write(c.UC_ARM64_REG_PC,address+4)
  elif target not in (BASE+0x8a16cdc,BASE+0x8a16ba4):raise ValueError(('BL',hex(target)))
m.hook_add(u.UC_HOOK_CODE,hook)
def invalid(mu,access,address,size,value,user):
 print('invalid',hex(address),size,'pc',hex(mu.reg_read(c.UC_ARM64_REG_PC)));return False
m.hook_add(u.UC_HOOK_MEM_INVALID,invalid)
rng=random.Random(604120);cases=[]
for i in range(96):
 command=bytearray(rng.randbytes(0x9c0));desc=bytearray(rng.randbytes(0x1800));initial=rng.randbytes(0x400)
 struct.pack_into('<I',command,0,0);struct.pack_into('<I',desc,0x1388,i%17);desc[0x1138]=i%2
 struct.pack_into('<Q',desc,0x58,ns['R1']);struct.pack_into('<Q',desc,0x190,ns['O']);struct.pack_into('<Q',desc,0x1428,ns['R1'])
 values=dict(command_gpu=0x830000000+i*0x10000,translated_state=0xfffffc2002000000+i*0x1000,fw_state=0xfffffc2003000000+i*0x1000,state=0xfffffc2004000000+i*0x1000,counter=i*11,resource_type=i*13,context_id=i*17,resource_map=0x850000000+i*0x1000,feature=i*3,channel_config=i*5,timestamp_index=i*7,stream_fw=0xfffffc2005000000+i*0x1000,stream_gpu=0x860000000+i*0x1000)
 m.mem_write(C,bytes(command));m.mem_write(D,bytes(desc));m.mem_write(B,initial);m.mem_write(SP,bytes(0x230));qwrite(E+0x28,B);qwrite(E+0x68,B);m.mem_write(E+0x5c,bytes(4));m.mem_write(ns['O']+8,struct.pack('<I',values['context_id']));m.mem_write(A+0x6d5,bytes([values['feature']&255]));m.mem_write(A+0xf570,bytes([values['channel_config']&255]))
 for off,v in [(0x20,C),(0x30,values['timestamp_index']),(0x38,values['counter']),(0x40,C+0x8ae),(0x48,values['translated_state']),(0x28,CH+0xa8)]:qwrite(SP+off,v)
 for reg in ns['regs']:m.reg_write(reg,0)
 for n,v in {19:C,20:CH,21:values['command_gpu'],22:values['fw_state'],23:values['state'],24:D,25:SP+0x1dc,26:values['counter'],28:D+0x1000}.items():m.reg_write(ns['regs'][n],v)
 m.reg_write(c.UC_ARM64_REG_SP,SP);calls.clear();expected,expected_cmd,length=stream(initial,command,desc,values)
 try:m.emu_start(BASE+0x89e72ec,BASE+0x89e775c,count=20000)
 except Exception:
  print('exception pc',hex(m.reg_read(c.UC_ARM64_REG_PC)));raise
 assert m.reg_read(c.UC_ARM64_REG_PC)==BASE+0x89e775c
 actual=bytes(m.mem_read(B,0x400));actualcmd=bytes(m.mem_read(C,0x9c0))
 if actual!=expected:raise ValueError((i,'stream',[hex(j) for j in range(0x400) if actual[j]!=expected[j]][:20]))
 assert bytes(m.mem_read(D,0x1800))==bytes(desc)
 assert actualcmd==expected_cmd,(i,'command',hex(struct.unpack_from('<Q',actualcmd,0x790)[0]),hex(struct.unpack_from('<Q',expected_cmd,0x790)[0]),[hex(j) for j in range(0x9c0) if actualcmd[j]!=expected_cmd[j]])
 cases.append(dict(case=i,count=i%17,length=length,sha256=hashlib.sha256(actual).hexdigest()))

(O/'qualification.json').write_text(json.dumps(dict(cases=cases,count=len(cases),source_binary_sha256=ns['sha'],core_range_sha256=hashlib.sha256(ns['read'](BASE+0x89e72ec,0x89e775c-0x89e72ec)).hexdigest(),helper_range_sha256=hashlib.sha256(ns['read'](BASE+0x8a16ba4,0x8a16ed0-0x8a16ba4)).hexdigest(),qualification='Actual TA primary SKU core instructions 89e72ec..89e775c including native timestamp helper and SIMD zero/copy/reduction. Resource type, map, FW alias conversion and callback explicit owned provider stubs; native finishEncode executes. Whole stream/command matched numeric model. Does not qualify protected context/secondary entry branch or full beginEncoding/wait.'),indent=2)+'\n')
