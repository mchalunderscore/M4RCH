#!/usr/bin/env python3
"""Connected native primary SKU startup/timestamps/callback/end, offline RAM."""
import argparse,hashlib,json,random,struct,sys
from pathlib import Path
from private_sku_startup import build
from private_sku_records import startup,timestamp
from private_sku_end import primary
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
checker=Path(__file__).with_name('audit-private-sku-startup.py');prefix=checker.read_text().split('rng=random.Random(604016);counts={};examples=[]')[0]
ns={'__name__':'stream','__file__':str(checker)}
modified=prefix.replace('m.hook_add(u.UC_HOOK_CODE,hook)','hook_handle=m.hook_add(u.UC_HOOK_CODE,hook)')
av=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)]
try:exec(compile(modified,str(checker),'exec'),ns)
finally:sys.argv=av
m=ns['m'];c=ns['c'];u=ns['u'];regs=ns['regs'];BASE=ns['BASE'];read=ns['read'];E,CH,A,D,CMD,B,STACK=map(ns.get,['E','CH','A','D','CMD','B','STACK'])
m.hook_del(ns['hook_handle'])
m.mem_write(BASE+0x89d5344,read(BASE+0x89d5344,0x89d5a2c-0x89d5344))
m.mem_map(BASE+0x8a16000,4096);m.mem_write(BASE+0x8a16ba4,read(BASE+0x8a16ba4,0x8a16ed0-0x8a16ba4))
m.mem_map(BASE+0x712d000,4096);m.mem_write(BASE+0x712d000,read(BASE+0x712d000,4096))
CVT=0x221500;CALLBACK=0x221900;FRAME=STACK+0x800
m.mem_write(CH,struct.pack('<Q',CVT));m.mem_write(CVT+0x258,struct.pack('<Q',CALLBACK))
resource_type=resource_map=stream_map=translated=cursor=0;calls=[];timestamp_entries=[]
def hook(m,addr,size,user):
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if addr==BASE+0x8a16cdc:timestamp_entries.append(m.reg_read(c.UC_ARM64_REG_W5))
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word&0xfffffc00 in (0xd73f0800,0xd71f0800):
  target=m.reg_read(regs[(word>>5)&31]);x0,x1,x2=[m.reg_read(regs[i]) for i in range(3)]
  if target==0x221100:assert x0==ns['R1'];value=resource_type;calls.append('type')
  elif target==0x221200:assert x0==ns['R2'];value=resource_map;calls.append('parameter_map')
  elif target==0x221300:assert x0==ns['R3'];value=stream_map;calls.append('stream_map')
  elif target==0x221000:assert x0==ns['F'] and x2==0 and x1 in [stream_map+cursor-B+4,stream_map+cursor-B];value=x1+0x100000000;calls.append('translate')
  elif target==CALLBACK:assert x0==CH;value=0;calls.append('channel258')
  else:raise AssertionError(hex(target))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,addr+4 if word&0xfffffc00==0xd73f0800 else m.reg_read(c.UC_ARM64_REG_LR));return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+4*imm
  if target==BASE+0xb744bf0:
   dest,source,n=[m.reg_read(regs[i]) for i in range(3)];assert n==0x1e8;assert source==STACK+0x80;m.mem_write(dest,bytes(m.mem_read(source,n)));m.reg_write(c.UC_ARM64_REG_PC,addr+4);calls.append('copy')
  elif target not in (BASE+0x8a16cdc,BASE+0x8a16ba4):raise AssertionError(hex(target))
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604017);examples=[];record_counts={7:0,3:0,8:0};cases=1024
for i in range(cases):
 desc=bytearray(rng.randbytes(0x1000));command=bytearray(rng.randbytes(0x2300));stack=bytearray(rng.randbytes(0x300));encoder=bytearray(rng.randbytes(0x100));backing=rng.randbytes(0x4000)
 struct.pack_into('<I',command,0,1);count=i%17;struct.pack_into('<I',desc,0xa70,count)
 for off,val in [(0x58,ns['R1']),(0x190,0x221400),(0xb90,ns['N'])]:struct.pack_into('<Q',desc,off,val)
 desc[0xc48]=0;desc[0x893]=i&1;struct.pack_into('<I',stack,0x20,(i>>1)&1)
 context=i;resource_type=i;resource_map=0x810000000;stream_map=0x820000000;translated=stream_map+((i%8)*512)+4+0x100000000
 gpu=0x840000000;pm=0x850000000;state=0x860000000;config=i&0xfe;feature=i&255;channel_config=(i>>2)&255;index=i*7
 cursor=B+(i%8)*512;struct.pack_into('<Q',encoder,8,A);struct.pack_into('<Q',encoder,0x20,ns['R3']);struct.pack_into('<Q',encoder,0x28,B);struct.pack_into('<Q',encoder,0x68,cursor);struct.pack_into('<I',encoder,0x5c,cursor-B)
 m.mem_write(D,bytes(desc));m.mem_write(CMD,bytes(command));m.mem_write(STACK,bytes(stack));m.mem_write(E,bytes(encoder));m.mem_write(B,backing);m.mem_write(0x221408,struct.pack('<I',context));m.mem_write(A+0xed48,bytes([config]));m.mem_write(A+0x6d5,bytes([feature]));m.mem_write(A+0xf570,bytes([channel_config]));m.mem_write(A+0x1aed4,b'\0')
 expected_stack,secondary=build(stack,desc,command,gpu,pm,state,resource_type,resource_map,context,config,feature);assert secondary==0
 expected=bytearray(backing);off=cursor-B;expected[off:off+0x1ec]=startup(expected[off:off+0x1ec],expected_stack[0x80:0x268]);off+=0x1ec;sequence=[7];want_ts=[]
 if not desc[0x893]&1:expected[off:off+0x4c]=timestamp(expected[off:off+0x4c],command,index,gpu,state,True);off+=0x4c;sequence.append(0x80000003);want_ts.append(1)
 if not struct.unpack_from('<I',stack,0x20)[0]&1:expected[off:off+0x4c]=timestamp(expected[off:off+0x4c],command,index,gpu,state,False);off+=0x4c;sequence.append(3);want_ts.append(0)
 expected[off:off+0xbc]=primary(expected[off:off+0xbc],expected_stack,command,desc,gpu,translated,0,channel_config,B,cursor-B,B+off);off+=0xbc;sequence.append(8)
 struct.pack_into('<I',expected,off,0x40000002);off+=4;sequence.append(0x40000002)
 expected_command=bytearray(command);struct.pack_into('<Q',expected_command,0x14,translated-4);struct.pack_into('<I',expected_command,0x1c,(off-(cursor-B)+63)&~63)
 calls.clear();timestamp_entries.clear()
 for reg in regs:m.reg_write(reg,0)
 for j,v in {19:CMD,20:CH,21:STACK+0x80,22:state,23:0,24:gpu,25:pm,26:D,27:index,29:FRAME}.items():m.reg_write(regs[j],v)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.emu_start(BASE+0x89d5344,BASE+0x89d5990,count=20000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==BASE+0x89d5990;assert bytes(m.mem_read(B,len(backing)))==bytes(expected),(i,'stream');assert timestamp_entries==want_ts
 struct.pack_into('<Q',encoder,0x68,B+off);assert bytes(m.mem_read(E,len(encoder)))==bytes(encoder)
 assert bytes(m.mem_read(D,len(desc)))==bytes(desc);assert bytes(m.mem_read(CMD,len(command)))==bytes(expected_command)
 assert calls==['type','parameter_map','stream_map','translate','copy','channel258','stream_map','translate']
 record_counts[7]+=1;record_counts[8]+=1;record_counts[3]+=len(want_ts)
 if i<8:examples.append({'case':i,'startup_entries':count,'record_sequence':[hex(x) for x in sequence],'stream_bytes':off-(cursor-B),'sha256':hashlib.sha256(expected[cursor-B:off]).hexdigest()})
report={'private_binary_sha256':ns['sha'],'cases':cases,'record_counts':record_counts,'examples':examples,'range':['0xfffffe00089d5344','0xfffffe00089d5990'],'range_sha256':hashlib.sha256(read(BASE+0x89d5344,0x89d5990-0x89d5344)).hexdigest(),'qualification':'Connected native startup payload/publication, conditional real timestamp encoders, synthetic channel258 callback and primary opcode8 through native finishEncode and caller pointer/rounded-size publication. Whole backing/encoder/descriptor and resulting command checked against independent composition. PAC bypassed; resource providers/firmware translation/memcpy/channel callback explicit stubs. Entry counts0..16 synthetic, optional secondary phase disabled; leading/trailing wait excluded. Callback effects beyond supplied no-op not established. No GPU job validity, microsequence interpretation, real allocation/cache/firmware execution or completion.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(record_counts)
