#!/usr/bin/env python3
"""Full ordinary G16 geometry and segment-control functions in offline RAM.

Private-derived numeric ABI evidence; provider values remain explicit fixtures.
No Apple executable bytes exported and no hardware access.
"""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_render_inputs import load_render_target
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
BASE=0xfffffe0000000000
GEO=BASE+0x89e5e04;SEG=BASE+0x89e6400;MIN=BASE+0x89e6478;PMMIN=BASE+0x89e8204
LOADER=BASE+0x895d7b4

def read(addr,n):
 for vm,_,off,length in segs:
  if vm<=addr and addr+n<=vm+length:return raw[off+addr-vm:off+addr-vm+n]
 raise ValueError(hex(addr))
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(BASE+0x89e5000,0x2000),(BASE+0x89e8000,4096),(BASE+0x712d000,4096),(BASE+0x7130000,4096),(BASE+0x895d000,4096),(0x200000,0x40000)]:
 m.mem_map(addr,n)
 if addr>BASE:m.mem_write(addr,read(addr,n))
O,A,VT,D,N,R,RVT,STACK,STOP=0x200000,0x201000,0x214000,0x216000,0x218000,0x219000,0x21a000,0x23e000,0x23f000
PROVIDER,MAP=0x21b000,0x21b100
m.mem_write(A,struct.pack('<Q',VT));m.mem_write(VT+0x1050,struct.pack('<Q',PROVIDER))
m.mem_write(N+0x20,struct.pack('<Q',R));m.mem_write(R,struct.pack('<Q',RVT));m.mem_write(RVT+0x158,struct.pack('<Q',MAP))
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];provider=0;maps=[];calls=[];seen=set()
def hook(m,addr,size,user):
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);arg=m.reg_read(regs[0])
  if target==PROVIDER:assert arg==A;v=provider;calls.append('provider1050')
  elif target==MAP:assert arg==R;v=maps[len([x for x in calls if x=='map158'])];calls.append('map158')
  else:raise AssertionError(('unqualified provider',hex(target)))
  m.reg_write(regs[0],v);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(start,**values):
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for name,v in values.items():m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),v)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP);m.emu_start(start,STOP,count=4000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 return m.reg_read(c.UC_ARM64_REG_X0)
MASK=(1<<64)-1
def geometry(original,accelerator,argument,provider_value):
 b=bytearray(original);q=lambda off:struct.unpack_from('<I',original,off)[0];aq=lambda off:struct.unpack_from('<I',accelerator,off)[0]
 def put(off,v,size=4):struct.pack_into('<I' if size==4 else '<Q',b,off,v&((1<<(size*8))-1))
 tx=(q(0x40)+31)>>5;ty=(q(0x44)+31)>>5;mx=((tx+3)//4+3)&~3;my=((ty+3)//4+3)&~3
 ux=2 if q(0x90)==16 else 1;uy=2 if q(0x94)==16 else 1
 cells=16*mx*my*ux*uy;size=5*cells
 put(0x18,size>>6);put(0x10,q(0x98)*size,8);put(0x20,0,8);put(0x28,cells>>3)
 put(0x140,aq(0x4e4)*q(0x98)*cells*8,8);put(0x180,64,8);put(0x30,256 if q(0x98)>1 else 0,8)
 if q(0x3c)>=2:
  put(0x148,q(0x98)*size*provider_value,8);put(0x150,(256 if q(0x98)>1 else 0)*provider_value,8)
  put(0x188,64,8);put(0x190,256,8);put(0x160,q(0x3c)*0x2c0+0x680,8);put(0x168,q(0x3c)*0x500,8)
  put(0x1a0,32,8);put(0x1a8,32,8)
  memory=struct.unpack_from('<Q',accelerator,0x11188)[0]
  assert memory!=0 # This fixture excludes fallback provider1028.
  page_count=(memory+0x7fff)//0x8000+0x17ff
  high=(page_count*0x000aaaaaaaaaaaab)>>64
  put(0x170,(high*8+8)*provider_value,8);put(0x178,128,8);put(0x1b0,128,8);put(0x1b8,64,8)
 put(0x260,(~(aq(0x6d0)>>11))&0x200,8)
 width=q(0x9c) if q(0xa4)&1 else q(0x40);height=q(0xa0) if q(0xa4)&1 else q(0x44)
 put(0x100,(width-1)|((height-1)<<16));put(0x104,(tx-1)|((ty-1)<<12));put(0x114,(tx-1)|((ty-1)<<12));put(0x118,tx*ty)
 put(0x108,3*mx|(mx<<10)|(mx<<18));put(0x10c,3*my|(my<<18)|(my<<10));put(0x110,mx*my)
 utile=(0x2000 if q(0x90)==32 else 0x1000)|(0x8000 if q(0x94)==32 else 0x4000)
 samples=q(0x48);assert samples in (1,2,4)
 pattern=sum(q(0x4c+4*i)<<(4*i) for i in range(2*samples))
 put(0xf0,utile,8);put(0xf8,pattern,8);put(0xe8,argument,8);put(0xf0,utile|{1:0,2:1,4:2}[samples],8)
 put(0xb8,samples);put(0xbc,((max(1,mx*ux)&0x3fd)<<16)|(max(1,my*uy)&0x3fd));put(0xb0,pattern,8)
 constant=struct.unpack('<f',struct.pack('<I',0x3fddb3d9))[0]
 for off,extent in [(0xc8,width),(0xcc,height)]:
  if extent:struct.pack_into('<f',b,off,constant/extent)
  else:put(off,0x38ddb3d7)
 return bytes(b)
rng=random.Random(604018);counts={'ordinary_geometry':0,'geometry_to_loader':0,'segment_control':0,'dynamic_min_passthrough':0,'default_pm_min':0};examples=[]
for i in range(1024):
 original=bytearray(rng.randbytes(0x400));accel=bytearray(rng.randbytes(0x12000))
 w=[1,16,31,32,33,64,255,256,16384][i%9];h=[1,33,64,129,16384][i%5];samples=[1,2,4][i%3];layers=1+i%4;groups=1+i%3
 for off,v in [(0x3c,groups),(0x40,w),(0x44,h),(0x48,samples),(0x90,[16,32][i%2]),(0x94,[16,32][i%2]),(0x98,layers),(0x9c,w//2),(0xa0,h//2),(0xa4,i%2)]:struct.pack_into('<I',original,off,v)
 for j in range(16):struct.pack_into('<I',original,0x4c+4*j,j&15)
 struct.pack_into('<Q',original,0x120,A);struct.pack_into('<I',accel,0x4e4,groups);struct.pack_into('<Q',accel,0x11188,16<<30)
 argument=rng.getrandbits(32);provider=1+i%4
 expected=geometry(original,accel,argument,provider)
 m.mem_write(O,bytes(original));m.mem_write(A,bytes(accel));m.mem_write(A,struct.pack('<Q',VT))
 run(GEO,x0=O,x1=0,x2=argument)
 actual=bytes(m.mem_read(O,len(original)))
 if actual!=expected:
  raise AssertionError((i,[(hex(j),hex(actual[j]),hex(expected[j])) for j in range(len(actual)) if actual[j]!=expected[j]][:30]))
 assert calls==(['provider1050'] if groups>=2 else []);counts['ordinary_geometry']+=1
 descriptor=rng.randbytes(0x1000);source=bytearray(actual);struct.pack_into('<Q',source,0x130,N);maps=[0x1000000000,0x1000100000,0x1000200000]
 m.mem_write(O,bytes(source));m.mem_write(D,descriptor);run(LOADER,x0=D,x1=O)
 assert bytes(m.mem_read(D,0x1000))==load_render_target(descriptor,source,maps);assert calls==['map158']*3;counts['geometry_to_loader']+=1
 # Segment helper: unsigned arithmetic, exact native masks, provider memory fixtures.
 original=bytearray(rng.randbytes(0x400));struct.pack_into('<I',original,0x3c,groups);struct.pack_into('<Q',original,0x120,A);expected=bytearray(original)
 flag=i&1
 if groups<2:struct.pack_into('<Q',expected,0xd8,struct.unpack_from('<Q',original,0xd8)[0]|1)
 else:
  q=lambda off:struct.unpack_from('<I',accel,off)[0]
  value=flag^1;value|=(q(0xed04)<<4)&0x000fff87f0f0
  value|=(((q(0xed14)-q(0xed18))&0xffffffff)<<8)&0xffffff87ff00
  value|=((q(0xed1c)-q(0xed18))&0xffffffff)<<19
  struct.pack_into('<QQ',expected,0xd8,value,q(0xed08))
 m.mem_write(O,bytes(original));run(SEG,x0=O,x1=flag);assert bytes(m.mem_read(O,0x400))==expected,(i,bytes(m.mem_read(O+0xd8,16)).hex(),expected[0xd8:0xe8].hex());counts['segment_control']+=1
 value=rng.getrandbits(64);m.mem_write(D,bytes(16));run(MIN,x0=O,x2=value,x5=D,x6=D+8);assert bytes(m.mem_read(D,16))==struct.pack('<QQ',value,value);counts['dynamic_min_passthrough']+=1
 vals=[rng.randrange(1,100) for _ in range(4)];aa,bb,cc,div=vals
 for off,v in [(0x4b8,aa),(0x4b4,bb),(0x4bc,cc),(0x4e4,div)]:struct.pack_into('<I',accel,off,v)
 m.mem_write(A,bytes(accel));value=run(PMMIN,x0=A)
 want=(((2*(bb//div)+4*(cc+aa//div)+5)&0xffffffff)<<15)&0x7ffffffe0000
 assert value==want;counts['default_pm_min']+=1
 if i<6:examples.append({'case':i,'width':w,'height':h,'samples':samples,'q3c_provider_branch':groups,'q98_storage_multiplier':layers,'size18':hex(struct.unpack_from('<I',actual,0x18)[0]),'bytes10':hex(struct.unpack_from('<Q',actual,0x10)[0]),'bytes140':hex(struct.unpack_from('<Q',actual,0x140)[0]),'packed104':hex(struct.unpack_from('<I',actual,0x104)[0]),'packed108':hex(struct.unpack_from('<Q',actual,0x108)[0])})
report={'private_binary_sha256':sha,'counts':counts,'examples':examples,'native_ranges':[{'start':hex(x),'end':hex(y),'sha256':hashlib.sha256(read(x,y-x)).hexdigest()} for x,y in [(GEO,BASE+0x89e63b8),(SEG,MIN),(MIN,MIN+16),(PMMIN,PMMIN+0x38),(LOADER,BASE+0x895d914)]],'visited_instructions':len(seen),'qualification':'Complete ordinary geometry and segment-control functions execute in Unicorn; all object bytes compare against numeric independent model. Complete native geometry-to-loader composition checked. PAC bypassed. Synthetic accelerator1050 provider; nonzero11188 excludes fallback1028. Samples1/2/4, positive extents and q3c/q98 1..4 fixtures, not exhaustive object initialization or subtype semantics. PM minimum still depends on unqualified topology values. No real allocation, GPU job or hardware acceptance.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
