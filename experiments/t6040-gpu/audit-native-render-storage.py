#!/usr/bin/env python3
"""Offline native G16 render-storage packing; no hardware or exported code bytes."""
import argparse, hashlib, json, random, struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,n in [(B+0x8a0a000,0x2000),(B+0x7ea2000,4096),(0x200000,0x10000)]:
 m.mem_map(addr,n)
 if addr>B:m.mem_write(addr,read(addr,n))
O,R,E,S,STOP,SHIFT=0x200000,0x202000,0x204000,0x20e000,0x20f000,0x206000
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)]
seen=set(); services=[]; service_mode=None; service_return=0
A,SH,VT,DESC=0x20a000,0x20b000,0x20c000,0x208000
def hook(m,addr,size,user):
 seen.add(addr);word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if addr==STOP:m.emu_stop();return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if service_mode and addr==B+0x8a0ad9c:
  args=[m.reg_read(regs[j]) for j in range(5)]
  services.append(('allocate',args));m.reg_write(regs[0],service_return);m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if service_mode and addr==B+0x8a0adfc:
  services.append(('priority',[m.reg_read(regs[0]),m.reg_read(regs[1])]));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if service_mode and word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);args=[m.reg_read(regs[j]) for j in range(2)]
  assert target in (0x207000,0x207100,0x207200)
  services.append((hex(target),args));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(start,end=STOP,**values):
 for reg in regs:m.reg_write(reg,0)
 for name,v in values.items():m.reg_write(getattr(c,'UC_ARM64_REG_'+name.upper()),v)
 m.reg_write(c.UC_ARM64_REG_SP,S);m.reg_write(c.UC_ARM64_REG_LR,STOP);m.emu_start(B+start,end,count=2000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==end
 return m.reg_read(c.UC_ARM64_REG_X0)
def q(b,o):return struct.unpack_from('<Q',b,o)[0]
def put(b,o,v):struct.pack_into('<Q',b,o,v&((1<<64)-1))
def align(v,a):return v if not a else (v+a-1)&(-a)&((1<<64)-1)
rng=random.Random(604022);counts={'gtp_reuse_full_function':0,'ring_offset_publication_slice':0,'ring_entry_sizing_slice':0,'ring_capacity_growth_slice':0};examples=[]
for i in range(1024):
 # Full updateGtpOnlyBuffers, sufficient preallocated capacity; no calls on this branch.
 original=bytearray(rng.randbytes(0x400));expected=bytearray(original)
 sizes=[rng.randrange(0,1<<17) for _ in range(8)];alignments=[0,32,64,128,256,16384]
 aa=[rng.choice(alignments) for _ in range(7)]
 for j,v in enumerate(sizes):put(original,0x140+8*j,v)
 for j,v in enumerate(aa):put(original,0x188+8*j,v)
 offsets=[0]
 for j in range(7):offsets.append(align(offsets[-1]+sizes[j],aa[j]))
 total=offsets[-1]+sizes[-1];put(original,0x1c8,total+(i%3));put(original,0x1c0,R)
 mapped=rng.randrange(1<<40,1<<41);m.mem_write(R+0x18,struct.pack('<Q',mapped))
 expected=bytearray(original);put(expected,0x1d0,total)
 for j,v in enumerate(sizes):put(expected,0x1d8+8*j,v)
 for j,v in enumerate(offsets):put(expected,0x218+8*j,v)
 m.mem_write(O,bytes(original));value=run(0x8a0abec,x0=O)
 assert value==mapped and bytes(m.mem_read(O,0x400))==expected and m.reg_read(c.UC_ARM64_REG_SP)==S
 counts['gtp_reuse_full_function']+=1
 # Final updateRenderTarget offset stores. Entry selection/wait and whole function are excluded.
 original=bytearray(rng.randbytes(0x400));expected=bytearray(original);entry=rng.randbytes(0x58);ee=bytearray(entry)
 capacity=1<<(14+i%9);cursor=rng.randrange(0,1<<42);n0=rng.randrange(0,capacity//4+1);n1=rng.randrange(0,1025);n2=rng.randrange(0,1025)
 for off,v in [(0x10,n0),(0x30,n1),(0x260,n2)]:put(original,off,v)
 expected=bytearray(original)
 for off,v in [(0x2a8,cursor&(capacity-1)),(0x2b0,(cursor+n0)&(capacity-1)),(0x2b8,(cursor+n0+n1)&(capacity-1)),(0x2a0,cursor+n0+n1+n2)]:put(expected,off,v)
 struct.pack_into('<QQQ',ee,0,n0,n1,n2);m.mem_write(O,bytes(original));m.mem_write(E,entry)
 run(0x8a0b294,B+0x8a0b2d8,x19=O,x12=E,x9=capacity,x8=cursor)
 assert bytes(m.mem_read(O,0x400))==expected and bytes(m.mem_read(E,0x58))==ee
 counts['ring_offset_publication_slice']+=1
 # Native entry-size sequence: geometry bytes use a 32-bit load/add before 4KiB alignment.
 original=bytearray(rng.randbytes(0x400));geometry=[1280,4096,4097,0xfffff000,0xfffff001,0xffffffff][i%6]
 put(original,0x10,geometry);put(original,0x30,n1);put(original,0x260,n2);put(original,0x270,0);expected=bytearray(original)
 padded=((geometry+4095)&0xffffffff)&0xfffff000;put(expected,0x10,padded)
 m.mem_write(O,bytes(original));run(0x8a0affc,B+0x8a0b02c,x19=O)
 assert bytes(m.mem_read(O,0x400))==expected
 assert m.reg_read(c.UC_ARM64_REG_X21)==padded+n1+n2 and m.reg_read(c.UC_ARM64_REG_X22)==16*(padded+n1+n2)
 counts['ring_entry_sizing_slice']+=1
 # Fresh capacity grows by powers of two from supplied page shift. Actual OS shift provider excluded.
 original=bytearray(rng.randbytes(0x400));extra=i%2;original[0x2c0]=extra;expected=bytearray(original)
 shift=[12,14][i%2];needed=rng.randrange(1,1<<25);cap=1<<shift
 while cap<needed:cap*=2
 put(expected,0x270,cap);put(expected,0x268,cap+(cap//16 if extra else 0))
 m.mem_write(B+0x7ea2388,struct.pack('<Q',SHIFT));m.mem_write(SHIFT,struct.pack('<I',shift));m.mem_write(O,bytes(original))
 run(0x8a0b09c,B+0x8a0b0e0,x19=O,x22=needed)
 assert bytes(m.mem_read(O,0x400))==expected and m.reg_read(c.UC_ARM64_REG_X2)==q(expected,0x268)
 counts['ring_capacity_growth_slice']+=1
 if i<6:examples.append({'case':i,'gtp_sizes':sizes,'gtp_alignments':aa,'gtp_offsets':offsets,'gtp_total':total,'ring_geometry_bytes':geometry,'ring_padded_bytes':padded,'ring_extra_bytes':[n1,n2],'ring_offsets':[cursor&(capacity-1),(cursor+n0)&(capacity-1),(cursor+n0+n1)&(capacity-1)],'ring_growth_required':needed,'page_shift_fixture':shift,'ring_capacity':cap,'ring_allocation':q(expected,0x268)})
counts['gtp_allocation_success']=0;counts['gtp_allocation_failure']=0
for i in range(512):
 original=bytearray(rng.randbytes(0x400));sizes=[rng.randrange(0,1<<17) for _ in range(8)];aa=[rng.choice([0,32,64,128,256]) for _ in range(7)]
 for j,v in enumerate(sizes):put(original,0x140+8*j,v)
 for j,v in enumerate(aa):put(original,0x188+8*j,v)
 offsets=[0]
 for j in range(7):offsets.append(align(offsets[-1]+sizes[j],aa[j]))
 total=offsets[-1]+sizes[-1];assert total>0
 old=R+0x100 if i%2 else 0;success=i%5!=0;special=i%3==0;priority=i%7
 put(original,0x120,A);put(original,0x128,SH);put(original,0x1c0,old);put(original,0x1c8,0);struct.pack_into('<I',original,0x258,priority)
 m.mem_write(A+0x6d0,struct.pack('<Q',(1<<47) if special else 0))
 for resource in (R,R+0x100):m.mem_write(resource,struct.pack('<Q',VT))
 m.mem_write(VT+0x170,struct.pack('<Q',0x207000));m.mem_write(VT+0x28,struct.pack('<Q',0x207100));m.mem_write(VT+0x20,struct.pack('<Q',0x207200))
 m.mem_write(R+0x28,struct.pack('<Q',DESC));m.mem_write(DESC+0x78,struct.pack('<I',priority-1 if priority else 0));mapped=0x1000000000+i*0x4000;m.mem_write(R+0x18,struct.pack('<Q',mapped))
 services.clear();service_mode=True;service_return=R if success else 0;m.mem_write(O,bytes(original));value=run(0x8a0abec,x0=O);service_mode=None
 expected=bytearray(original);put(expected,0x1c0,R if success else 0);put(expected,0x1c8,total if success else 0)
 if success:
  put(expected,0x1d0,total)
  for j,v in enumerate(sizes):put(expected,0x1d8+8*j,v)
  for j,v in enumerate(offsets):put(expected,0x218+8*j,v)
 assert bytes(m.mem_read(O,0x400))==expected and value==(mapped if success else 0) and m.reg_read(c.UC_ARM64_REG_SP)==S
 want=[]
 if old:want += [('0x207000',[old,SH]),('0x207100',[old,SH])]
 want += [('allocate',[A,SH,total,0x1000000003 if special else 3,1 if special else 5])]
 if success:
  want += [('0x207200',[R,SH])]
  if priority:want += [('priority',[DESC,priority])]
 assert services==want,(i,services,want)
 counts['gtp_allocation_success' if success else 'gtp_allocation_failure']+=1
ranges=[(0x8a0abec,0x8a0ae74),(0x8a0b294,0x8a0b2d8),(0x8a0affc,0x8a0b02c),(0x8a0b09c,0x8a0b0e0)]
report={'private_binary_sha256':sha,'counts':counts,'examples':examples,'native_ranges':[{'start':hex(B+x),'end':hex(B+y),'sha256':hashlib.sha256(read(B+x,y-x)).hexdigest()} for x,y in ranges],'visited_instructions':len(seen),'qualification':'Full GTP-only update on reuse plus success/failure allocation branches with argument-checked supplied services; other tests are explicitly bounded slices. Full object byte comparisons and ring-entry untouched bytes checked. Native allocation call arguments checked but actual resource creation, retain/release, priority and map/cache services supplied; no real resources, event wait, allocation lifetime, full render-target update or GPU job executed. Page shift supplied, not queried from running kernel. PAC return bypassed. Deliberate 32-bit overflow cases characterize arithmetic, not valid job inputs.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
