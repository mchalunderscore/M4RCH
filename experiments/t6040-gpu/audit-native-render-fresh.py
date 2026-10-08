#!/usr/bin/env python3
"""Complete native fresh G16 target update with supplied resource/event services."""
import argparse,ast,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_render_inputs import load_render_target
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);p.add_argument('--candidate-directory',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,n=struct.unpack_from('<II',raw,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=n
B=0xfffffe0000000000

def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return raw[off+addr-vm:off+addr-vm+n]
 raise ValueError(hex(addr))
# Reuse the independently checked arithmetic model without executing its audit main.
model_path=Path(__import__('private_render_inputs').__file__).with_name('audit-private-render-geometry.py');tree=ast.parse(model_path.read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='geometry');ns={'struct':struct,'MASK':(1<<64)-1};exec(compile(ast.Module(body=[node],type_ignores=[]),str(model_path),'exec'),ns);geometry=ns['geometry']
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(B+0x8a0a000,0x2000),(B+0x89e5000,0x2000),(B+0x895d000,4096),(B+0x712d000,4096),(B+0x7130000,4096),(B+0x7ea2000,4096),(0x200000,0x100000)]:
 m.mem_map(addr,n)
 if addr>B:m.mem_write(addr,read(addr,n))
O,A,INFO,VT,AVT,SH,R,RVT,N,INNER,META,ARRAY,DESC,STACK,STOP,SHIFT=0x200000,0x210000,0x230000,0x240000,0x241000,0x242000,0x243000,0x244000,0x245000,0x246000,0x247000,0x250000,0x260000,0x2fe000,0x2ff000,0x248000
m.mem_write(O,struct.pack('<Q',VT));m.mem_write(A,struct.pack('<Q',AVT));m.mem_write(R,struct.pack('<Q',RVT));m.mem_write(N,struct.pack('<Q',RVT));m.mem_write(R+0x18,struct.pack('<Q',META));m.mem_write(N+0x20,struct.pack('<Q',R));m.mem_write(R+0x20,struct.pack('<Q',INNER));m.mem_write(INNER+0x18,struct.pack('<Q',META));m.mem_write(RVT+0x20,struct.pack('<Q',0x249000));m.mem_write(RVT+0x170,struct.pack('<Q',0x249100));m.mem_write(RVT+0x158,struct.pack('<Q',0x249200));m.mem_write(AVT+0x1050,struct.pack('<Q',0x249300));m.mem_write(B+0x7ea2388,struct.pack('<Q',SHIFT));m.mem_write(SHIFT,struct.pack('<I',14))
expected_slots={0x170:0x89e63b8,0x160:0x89e6400,0x178:0x89e5e04}
for slot,offset in expected_slots.items():
 encoded=struct.unpack('<Q',read(B+0x7ead700+16+slot,8))[0];decoded=B+0x7004000+(encoded&0xffffffff);assert decoded==B+offset,(slot,hex(decoded));m.mem_write(VT+slot,struct.pack('<Q',decoded))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];provider=2;mapped=0x1000040000;map_count=0;seen=set()
def hook(m,addr,size,user):
 global map_count
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==B+0x8a0b078:
  calls.append(('event_initialize',[m.reg_read(regs[0])]));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr==B+0x8a0b108:
  args=[m.reg_read(regs[j]) for j in range(5)];calls.append(('allocate',args));m.reg_write(regs[0],N);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);arg=m.reg_read(regs[0])
  if target in [B+x for x in expected_slots.values()]:
   m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
  if target==0x249300:assert arg==A;calls.append(('provider1050',[arg]));m.reg_write(regs[0],provider)
  elif target==0x249000:assert arg==N;calls.append(('retain',[arg]))
  elif target==0x249100:assert arg==N and m.reg_read(regs[1])==SH;calls.append(('map',[arg,SH]))
  elif target==0x249200:assert arg==R;calls.append(('mapped_base',[arg]));map_count+=1;m.reg_write(regs[0],mapped)
  else:raise AssertionError(('service',hex(addr),hex(target),hex(arg)))
  m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(addr,**values):
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for name,value in values.items():m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);
 try:m.emu_start(B+addr,STOP,count=20000)
 except u.UcError:
  print('fault',hex(m.reg_read(c.UC_ARM64_REG_PC)),calls);raise
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(regs[0])
def put(b,off,value,size=8):struct.pack_into('<Q' if size==8 else '<I',b,off,value)
rng=random.Random(604024);counts={'fresh_updates':0,'fresh_update_to_3d_loader':0};examples=[]
for i in range(512):
 original=bytearray(bytes(0x400) if i==0 else rng.randbytes(0x400));accel=bytearray(bytes(0x12000) if i==0 else rng.randbytes(0x12000));info=bytearray(0x70);w=[32,33,64,127,256][i%5];h=[32,64,65,128][i%4];samples=[1,2,4][i%3];layers=1+i%3;groups=1+i%2;provider=1+i%4;special=i%2;extra=i%3==0;argument=(i+1)<<15
 if i==0:w=h=64;samples=layers=1;groups=provider=2;special=extra=0
 for off,value in [(0,w),(4,h),(8,samples),(0x50,32),(0x54,32),(0x58,layers)]:put(info,off,value,4)
 for j in range(16):put(info,0xc+4*j,j&15,4)
 for off,value in [(0,VT),(0x120,A),(0x128,SH),(0x130,0),(0x270,0),(0x290,ARRAY),(0x298,0),(0x2a0,0)]:put(original,off,value)
 for off,value in [(0x280,16),(0x284,0),(0x288,0),(0x138,0)]:put(original,off,value,4)
 original[0x2c0]=int(extra)
 put(accel,0,AVT);put(accel,0x4e4,groups,4);put(accel,0xecf0,0,4);put(accel,0x6d0,(1<<47) if special else 0);put(accel,0x11188,16<<30)
 m.mem_write(O,bytes(original));m.mem_write(A,bytes(accel));m.mem_write(INFO,bytes(info));m.mem_write(ARRAY,bytes(16*0x58));m.mem_write(META+0x78,struct.pack('<I',0))
 expected=bytearray(original);expected[0x40:0xb0]=info
 put(expected,0x3c,groups,4);expected[0x140:0x1c0]=bytes(0x80)
 # Segment-control field on grouping1 sets bit0; grouping2 uses supplied accelerator inputs.
 if groups<2:put(expected,0xd8,struct.unpack_from('<Q',expected,0xd8)[0]|1)
 else:
  aq=lambda off:struct.unpack_from('<I',accel,off)[0]
  ctrl=0|((aq(0xed04)<<4)&0x000fff87f0f0)|((((aq(0xed14)-aq(0xed18))&0xffffffff)<<8)&0xffffff87ff00)|(((aq(0xed1c)-aq(0xed18))&0xffffffff)<<19)
  put(expected,0xd8,ctrl&((1<<64)-1));put(expected,0xe0,aq(0xed08))
 expected=bytearray(geometry(expected,accel,argument>>15,provider));padded=((struct.unpack_from('<I',expected,0x10)[0]+4095)&0xffffffff)&0xfffff000;put(expected,0x10,padded)
 n1=struct.unpack_from('<Q',expected,0x30)[0];n2=struct.unpack_from('<Q',expected,0x260)[0];entry=padded+n1+n2;cap=1<<14
 while cap<16*entry:cap*=2
 allocation=cap+(cap//16 if extra else 0)
 for off,value in [(0x130,N),(0x270,cap),(0x268,allocation),(0x298,0),(0x2a0,entry),(0x2a8,0),(0x2b0,padded),(0x2b8,padded+n1)]:put(expected,off,value)
 put(expected,0x284,0,4);put(expected,0x288,1,4)
 value=run(0x8a0ae74,x0=O,x1=INFO,x2=0,x3=7,x4=0x274000,x5=0,x6=argument,x7=0)
 actual=bytes(m.mem_read(O,0x400))
 assert actual==expected,(i,[(hex(j),hex(actual[j]),hex(expected[j])) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 record=bytearray(16*0x58);struct.pack_into('<QQQ',record,0,padded,n1,n2)
 assert bytes(m.mem_read(ARRAY,len(record)))==record and value==ARRAY+0x18
 want=([('provider1050',[A])] if groups>=2 else [])+[('event_initialize',[ARRAY+0x18+j*0x58]) for j in range(16)]+[('allocate',[A,SH,allocation,0x3000000003 if special else 0x2000000003,1 if special else 5]),('retain',[N]),('map',[N,SH])]
 assert calls==want,(i,calls,want);counts['fresh_updates']+=1
 descriptor=bytes(0x1000) if i==0 else rng.randbytes(0x1000);m.mem_write(DESC,descriptor);map_count=0
 run(0x895d7b4,x0=DESC,x1=O)
 assert bytes(m.mem_read(DESC,0x1000))==load_render_target(descriptor,actual,[mapped]*3) and map_count==3;counts['fresh_update_to_3d_loader']+=1
 if i==0 and a.candidate_directory:
  a.candidate_directory.mkdir(parents=True,exist_ok=True)
  (a.candidate_directory/'render-target-source-fixture.bin').write_bytes(actual)
  (a.candidate_directory/'descriptor-render-fields-fixture.bin').write_bytes(bytes(m.mem_read(DESC,0x1000)))
  (a.candidate_directory/'ring-records-fixture.bin').write_bytes(bytes(record))
  sizes=[struct.unpack_from('<Q',actual,0x140+8*j)[0] for j in range(8)];alignments=[struct.unpack_from('<Q',actual,0x188+8*j)[0] for j in range(7)];offsets=[0]
  for j,alignment in enumerate(alignments):
   end=offsets[-1]+sizes[j];offsets.append(end if alignment==0 else (end+alignment-1)&-alignment)
  profile={'submission_ready':False,'width':64,'height':64,'samples':1,'layers':1,'topology_fixture':{'accelerator4e4':groups,'provider1050':provider,'memory11188':16<<30,'flags6d0':0,'record_count':16,'page_shift':14},'ring':{'entry_main_bytes':padded,'entry_adjacent_bytes':n1,'entry_extra_bytes':n2,'capacity_bytes':cap,'allocation_bytes':allocation,'offsets':[0,padded,padded+n1],'candidate_device_base':hex(mapped),'records':16,'record_size':0x58,'event_offset':0x18},'gtp':{'sizes':sizes,'alignments':alignments,'offsets':offsets,'allocation_bytes':offsets[-1]+sizes[-1]},'qualification':'Native fresh-update and 3D-loader result for zero base fixture and explicit synthetic accelerator inputs. Resource/object pointers remain CPU fixtures. Descriptor contains only render fields, not a complete command. Event services opaque; real backing contents and event implementation unproved. Candidate base is supplied, not a live GPU mapping.'}
  profile['files']={x.name:{'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in a.candidate_directory.glob('*.bin')}
  (a.candidate_directory/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
 if i<5:examples.append({'width':w,'height':h,'samples':samples,'layers':layers,'grouping_fixture':groups,'provider_fixture':provider,'ring_main':padded,'ring_extra':[n1,n2],'capacity':cap,'allocation':allocation,'descriptor_addresses':[hex(mapped),hex(mapped+padded),hex(mapped+padded+n1)],'event_return':hex(value)})
ranges=[(0x8a0ae74,0x8a0b300),(0x895d7b4,0x895d914)]
report={'private_binary_sha256':sha,'geometry_model_source_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'counts':counts,'examples':examples,'native_ranges':[{'start':hex(B+x),'end':hex(B+y),'sha256':hashlib.sha256(read(B+x,y-x)).hexdigest()} for x,y in ranges],'visited_instructions':len(seen),'qualification':'Complete fresh native target update executes actual G16 validation, segment control and geometry methods, then complete 3D loader. Whole target/record/descriptor bytes checked. Fresh ring records are supplied zero fixtures, not evidence of real event initialization. Actual page shift14 supplied. Resource allocate/retain/map/base, event initialization and accelerator1050 supplied and arguments checked; no actual cache/allocation/GPU event services. Genuine topology/configuration absent. No ring reuse/wait branches, allocation failure or hardware job tested. PAC bypassed.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
