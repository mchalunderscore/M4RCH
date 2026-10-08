#!/usr/bin/env python3
"""Whole native 3D SKU stream versus composed models; resource providers synthetic."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_sku_startup import build
from private_sku_records import timestamp,startup,wait_record
from private_sku_end import primary,secondary
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('not file backed')
BASE=0xfffffe0000000000;FN=BASE+0x89d517c;BEGIN=BASE+0x8a16958;FINISH=BASE+0x8a16ba4;WFI=BASE+0x89d4b54
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,size in [(BASE+0x89d4000,0x2000),(BASE+0x8a16000,4096),(BASE+0x712d000,4096),(BASE+0x7ea2000,4096),(0x200000,0x90000)]:m.mem_map(addr,size)
for addr,size in [(FN,0x89d5a30-0x89d517c),(WFI,0x20),(BEGIN,0x8a16ed0-0x8a16958),(BASE+0x712d000,4096)]:m.mem_write(addr,read(addr,size))
E,CH,A,D,CMD,N,O,R1,R2,R3,VT1,VT2,VT3,F,FVT,B,STACK,CVT,EVENT,V,COOKIE,CFG=0x200000,0x201000,0x202000,0x222000,0x224000,0x227000,0x228000,0x229000,0x22a000,0x22b000,0x22c000,0x22d000,0x22e000,0x22f000,0x230000,0x232000,0x280000,0x243000,0x244000,0x245000,0x246000,0x247000
STOP=0x288000
m.mem_write(BASE+0x7ea25a0,struct.pack('<Q',COOKIE));m.mem_write(COOKIE,struct.pack('<Q',0x123456789abcdef0))
m.mem_write(CH,struct.pack('<Q',CVT));m.mem_write(CH+0x10,struct.pack('<Q',A));m.mem_write(CVT+0x258,struct.pack('<Q',WFI));m.mem_write(A+0x5b0,struct.pack('<Q',F));m.mem_write(A+0xf598,struct.pack('<Q',CFG));m.mem_write(F,struct.pack('<Q',FVT));m.mem_write(FVT+0x2d8,struct.pack('<Q',0x241000))
for r,vt,slot,target in [(R1,VT1,0x1e0,0x241100),(R2,VT2,0x158,0x241200),(R3,VT3,0x158,0x241300)]:m.mem_write(r,struct.pack('<Q',vt));m.mem_write(vt+slot,struct.pack('<Q',target))
m.mem_write(N+0x30,struct.pack('<Q',O));m.mem_write(O+0x58,struct.pack('<Q',R2));m.mem_write(A+0x1aed4,b'\0')
encoded=struct.unpack('<Q',read(BASE+0x7eaa560+16+0x258,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==WFI
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];seen=set();fw_returns=[];resource_type=resource_map=stream_map=0

def hook(m,addr,size,user):
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  if target in (BEGIN,FINISH,BASE+0x8a16cdc):return
  x0,x1,x2=[m.reg_read(regs[j]) for j in range(3)]
  if target==BASE+0xa7d0308:assert x0==0x248000 and x1==V+64;value=1;calls.append(('available',))
  elif target==BASE+0xa7d0d18:assert x0==0x248000 and x1==EVENT and x2==V+64;value=x0;calls.append(('associate',))
  elif target==BASE+0xb744bf0:
   assert x2 in (0x1e8,0x150);m.mem_write(x0,bytes(m.mem_read(x1,x2)));value=x0;calls.append(('copy',x2))
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(regs[(word>>5)&31]);x0,x1,x2=[m.reg_read(regs[j]) for j in range(3)]
  if target==WFI:
   assert x0==CH
   m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,WFI);calls.append(('wfi',));return
  if target==0x241100:assert x0==R1;value=resource_type;calls.append(('type',))
  elif target==0x241200:assert x0==R2;value=resource_map;calls.append(('parameter_map',))
  elif target==0x241300:assert x0==R3;value=stream_map;calls.append(('stream_map',))
  elif target==0x241000:
   assert x0==F and x2==0;idx=sum(row[0]=='fw' for row in calls);assert idx<6;value=fw_returns[idx];calls.append(('fw',x1,value))
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,addr+4 if word&0xfffffc00==0xd73f0800 else m.reg_read(c.UC_ARM64_REG_LR))
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604018);counts={};examples=[]
for i in range(1024):
 descriptor=bytearray(rng.randbytes(0x1000));command=bytearray(rng.randbytes(0x2300));struct.pack_into('<I',command,0,1)
 struct.pack_into('<Q',descriptor,0x58,R1);struct.pack_into('<Q',descriptor,0x138,E);struct.pack_into('<Q',descriptor,0x190,0x249000);struct.pack_into('<Q',descriptor,0xb90,N);struct.pack_into('<I',descriptor,0xa70,i%17)
 # Additional independent notification and optional timestamp-pointer cases.
 if (i//128)%2:
  descriptor[0xa78:0xa98]=bytes(32)
  struct.pack_into('<I',descriptor,0xa70,0)
 if (i//256)%2:
  command[0x21a8:0x21b8]=bytes(16)
  command[0x21c0:0x21c8]=bytes(8)
 descriptor[0x893]=i%2;descriptor[0x868]=(i//2)%2;descriptor[0xc48]=(i//4)%2
 # Toggle optional second phase via accelerator ed48 & descriptorc48.
 config=(i//8)%2;feature=(i//16)%2;cfgflag=(i//32)%2;cfgmode=(i//64)%2
 m.mem_write(A+0xed48,bytes([config]));m.mem_write(A+0x6d5,bytes([feature]));m.mem_write(CFG+0x54,bytes([cfgflag]));m.mem_write(CFG+0x28,struct.pack('<I',cfgmode));m.mem_write(A+0xf570,bytes([i%256]))
 state=rng.getrandbits(64);m.mem_write(CH+0x80,struct.pack('<Q',state));context=rng.getrandbits(32);m.mem_write(0x249008,struct.pack('<I',context))
 resource_type=rng.getrandbits(64);resource_map=rng.getrandbits(64);stream_map=rng.getrandbits(64);fw_returns=[rng.getrandbits(64) for _ in range(6)];original_gpu=rng.getrandbits(64)
 struct.pack_into('<Q',F_data:=bytearray(8),0,rng.getrandbits(64));m.mem_write(F+0x310,bytes(F_data))
 backing=rng.randbytes(0x10000);m.mem_write(B,backing);enc=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',enc,8,A);struct.pack_into('<Q',enc,0x20,R3);struct.pack_into('<Q',enc,0x28,B);struct.pack_into('<2Q',enc,0x38,0x248000,V);struct.pack_into('<I',enc,0x48,2);struct.pack_into('<Q',enc,0x50,4096);struct.pack_into('<I',enc,0x58,2);struct.pack_into('<I',enc,0x60,0)
 m.mem_write(E,bytes(enc));m.mem_write(D,bytes(descriptor));m.mem_write(CMD,bytes(command));m.mem_write(STACK-0x400,rng.randbytes(0x400));calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for j,value in enumerate([CH,CMD,D,original_gpu,EVENT]):m.reg_write(regs[j],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);m.emu_start(FN,STOP,count=10000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 # Compose independently checked records in caller order.
 gpu=fw_returns[3];pm=fw_returns[1];index=struct.unpack_from('<Q',command,0x2168)[0]&0xffffffff
 waitflag=(int(cfgmode!=1)|descriptor[0x868]) if not descriptor[0x893]&1 and cfgflag&1 else 0
 seed=bytearray(0x300);struct.pack_into('<Q',seed,0x60,fw_returns[2]);struct.pack_into('<Q',seed,0x70,index);struct.pack_into('<Q',seed,0x78,fw_returns[0])
 payload_stack,second=build(seed,descriptor,command,gpu,pm,state,resource_type,resource_map,context,config,feature)
 payload_stack=bytearray(payload_stack);struct.pack_into('<I',payload_stack,0x2c,waitflag)
 out=bytearray(backing);position=4096;order=[]
 def emit(size,fn,label):
  global position
  out[position:position+size]=fn(bytes(out[position:position+size]));position+=size;order.append(label)
 if waitflag&1:emit(0x14,lambda r:wait_record(r,struct.unpack_from('<I',descriptor,0x86c)[0],index,gpu,True),'wait_begin')
 emit(0x1ec,lambda r:startup(r,payload_stack[0x80:0x268]),'start')
 if not descriptor[0x893]&1:emit(0x4c,lambda r:timestamp(r,command,index,gpu,state,True),'timestamp_begin')
 emit(4,lambda r:struct.pack('<I',1),'wfi')
 if not descriptor[0x893]&1:emit(0x4c,lambda r:timestamp(r,command,index,gpu,state,False),'timestamp_end')
 if waitflag&1:emit(0x14,lambda r:wait_record(r,struct.unpack_from('<I',descriptor,0x86c)[0],index,gpu,False),'wait_end')
 first_cursor=B+position
 emit(0xbc,lambda r:primary(r,payload_stack,command,descriptor,gpu,fw_returns[4],second,i%256,B,4096,first_cursor),'end')
 if second:
  altered=bytearray(payload_stack[0x80:0x268]);struct.pack_into('<Q',altered,0x90,0x100000000)
  emit(0x1ec,lambda r:startup(r,altered),'second_start');emit(4,lambda r:struct.pack('<I',1),'second_wfi')
  saved=bytearray(payload_stack);struct.pack_into('<I',saved,4,struct.unpack_from('<I',command,0xc)[0]);struct.pack_into('<Q',saved,8,(gpu+0x21e8)&((1<<64)-1));struct.pack_into('<I',saved,0x14,struct.unpack_from('<I',descriptor,0xc40)[0]);struct.pack_into('<I',saved,0x18,descriptor[0x895]&1);struct.pack_into('<I',saved,0x1c,descriptor[0xc44]);struct.pack_into('<Q',saved,0x20,(fw_returns[4]+0x1ac)&((1<<64)-1));struct.pack_into('<I',saved,0x2c,struct.unpack_from('<I',command,0x2154)[0])
  vector=descriptor[0xa78:0xa98] if struct.unpack_from('<I',descriptor,0xa70)[0] or any(struct.unpack_from('<4Q',descriptor,0xa78)) else bytes(32)
  flags=int(any(vector) or struct.unpack_from('<I',descriptor,0xa70)[0]!=0)|((i%256&3)<<2)
  values={21:(gpu+0x2130)&((1<<64)-1),23:state,24:gpu,25:struct.unpack_from('<Q',command,0x2148)[0],26:pm,27:flags,28:struct.unpack_from('<I',command,0x2150)[0]}
  second_cursor=B+position;emit(0xbc,lambda r:secondary(r,saved,values,vector,B,4096,second_cursor),'second_end')
 emit(4,lambda r:struct.pack('<I',0x40000002),'terminate')
 assert bytes(m.mem_read(B,len(backing)))==bytes(out),(i,'stream',order)
 expected_command=bytearray(command);struct.pack_into('<Q',expected_command,0x14,fw_returns[5]);struct.pack_into('<I',expected_command,0x1c,(position-4096+63)&0xffffffc0)
 assert bytes(m.mem_read(CMD,len(command)))==bytes(expected_command);assert bytes(m.mem_read(D,len(descriptor)))==bytes(descriptor)
 expected_enc=bytearray(enc);struct.pack_into('<I',expected_enc,0x78,index);struct.pack_into('<I',expected_enc,0x60,1);struct.pack_into('<I',expected_enc,0x5c,4096);struct.pack_into('<Q',expected_enc,0x68,B+position)
 assert bytes(m.mem_read(E,len(enc)))==bytes(expected_enc)
 fw_calls=[row for row in calls if row[0]=='fw'];assert len(fw_calls)==6
 assert [row[1] for row in fw_calls[:4]]==[struct.unpack('<Q',F_data)[0],struct.unpack_from('<Q',descriptor,0x910)[0],struct.unpack_from('<Q',descriptor,0x908)[0],original_gpu]
 prefix=0x14 if waitflag&1 else 0;assert fw_calls[4][1]==(stream_map+4096+prefix+4)&((1<<64)-1);assert fw_calls[5][1]==(stream_map+4096)&((1<<64)-1)
 notification=bool(struct.unpack_from('<I',descriptor,0xa70)[0] or any(struct.unpack_from('<4Q',descriptor,0xa78)))
 key_notification='notification_present' if notification else 'notification_absent';counts[key_notification]=counts.get(key_notification,0)+1
 key='second_phase' if second else 'single_phase';counts[key]=counts.get(key,0)+1
 if waitflag&1:counts['wait_pair']=counts.get('wait_pair',0)+1
 if not descriptor[0x893]&1:counts['timestamp_pair']=counts.get('timestamp_pair',0)+1
 if i<32:examples.append(dict(case=i,order=order,bytes=position-4096,reported=(position-4096+63)&0xffffffc0))
report=dict(binary_sha256=sha,counts=counts,examples=examples,visited_instruction_count=len(seen),function=dict(start=hex(FN),end=hex(BASE+0x89d5a30),sha256=hashlib.sha256(read(FN,0x89d5a30-0x89d517c)).hexdigest()),wfi_vtable=dict(base=hex(BASE+0x7eaa560),slot='0x258',target=hex(WFI)),qualification='Whole native G16 3D SKU builder, native begin/timestamp/WFI/finish run in RAM versus composed independently checked models; complete stream/encoder/command outputs compared. PAC bypassed; external availability/event association/resource/firmware maps and memcpy stubbed. Both optional second phase and wait/timestamp branches covered. Native G16 SKU path is not proof SKSM uses this path; no valid shader/job, mapping/cache or live firmware execution established.')
sksm_table=BASE+0x7eaa8e0
sksm_entry=struct.unpack('<Q',read(sksm_table+16+0x228,8))[0]
sksm_target=BASE+0x7004000+(sksm_entry&0xffffffff)
assert sksm_target==BASE+0x89d5ce4
wrapper=read(sksm_target,12)
assert struct.unpack('<2I',wrapper[:8])==(0xd503245f,0xf9400800)
branch=struct.unpack('<I',wrapper[8:])[0];assert branch>>26==0b000101
imm=branch&0x3ffffff
if imm&(1<<25):imm-=1<<26
parent=sksm_target+8+imm*4;assert parent==BASE+0x89df73c
report['sksm_register_generator']=dict(vtable=hex(sksm_table),slot='0x228',wrapper=hex(sksm_target),parent=hex(parent),wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),qualification='Static native vtable/wrapper route to previously audited common register generator; not proof of whole SKSM submission or GPU execution.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
