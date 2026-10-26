"""Execute actual firmware mapping descriptor construction and ring insertion."""
import sys,struct,json,hashlib,random
from pathlib import Path
repo=Path(__file__).resolve().parent
sys.path.insert(0,str(repo))
from native_mapping_notify import descriptor,ring_transition
from native_uat_flags import legacy_g16
from native_g16_mapping import GEOMETRY
import unicorn as u
from unicorn import arm64_const as c
source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];B=0xfffffe0000000000;m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
NOTIFY=B+0x89c8e28;INSERT=B+0x89c8cc8;CONVERT=B+0x89c8ff8;SHIFT=B+0x89d1688;STOP=0x3fff00;STACK=0x3ff000
for va,n in [(B+0x89c8000,8192),(B+0x89d1000,4096),(B+0x89dc000,4096),(B+0x89f2000,4096),(B+0xc6e5000,4096),(0x300000,0x100000)]:m.mem_map(va,n)
for va,n in [(INSERT,CONVERT+12-INSERT),(SHIFT,12),(B+0x89dcad8,36),(B+0x89f2328,0x1ec)]:m.mem_write(va,read(va,n))
m.mem_write(B+0xc6e5ab0,struct.pack('<I',14))
FW=0x300000;VT=0x302000;STATE=0x304000;RING=0x308000;BATCH=0x310000;LOCK=0x320000;PROVIDER=0x321000;PVT=0x322000;FLUSH=0x323000
GUARDS=(B+0x89c8fc4,B+0x89c8dd8,B+0x89c8e00)
events=[];waits=0;wait_limit=0
regs=[getattr(c,f'UC_ARM64_REG_X{i}') for i in range(31)]
def hook(m,addr,size,user):
 global waits
 if addr in (*GUARDS,STOP):m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or addr in (B+0x89c8e68,B+0x89c8ea4,B+0x89c8d2c,B+0x89f23b0,B+0x89f24bc):m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if addr==B+0x89f23c8:
  assert m.reg_read(regs[8])==B+0x89dcad8
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,B+0x89dcad8);return
 if addr==B+0x89f2510:
  assert m.reg_read(regs[16])==NOTIFY and tuple(m.reg_read(regs[x]) for x in (0,1,2,3))==(FW,va,pa,writable)
  m.reg_write(c.UC_ARM64_REG_PC,NOTIFY);return
 if addr==B+0x89c8eac:m.reg_write(regs[17],m.reg_read(regs[16]));m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if addr in (B+0x89c8e88,B+0x89c8ed0):
  target=m.reg_read(regs[8] if addr==B+0x89c8e88 else regs[9]);assert target==(CONVERT if addr==B+0x89c8e88 else SHIFT)
  if target==CONVERT:assert m.reg_read(regs[0])==FW and m.reg_read(regs[1])==va and m.reg_read(regs[2])==0
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
 if addr==B+0x89c8d48:
  assert m.reg_read(regs[8])==FLUSH and tuple(m.reg_read(regs[x]) for x in (0,1,2))==(PROVIDER,0x85000000000000,0)
  events.append('flush');m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfc000000==0x94000000 or addr in (B+0x89c8dd4,B+0x89c8fc0):
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;target=addr+imm*4;x0=m.reg_read(regs[0])
  if target in (B+0xbf2635c,B+0xbf2645c):
   assert x0==LOCK;events.append('lock' if target==B+0xbf2635c else 'unlock')
  elif target==INSERT:
   assert x0==FW;assert bytes(m.mem_read(m.reg_read(regs[1]),24))==record
   m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
  elif target==B+0xbf25a08:
   assert x0==10;events.append('wait');waits+=1
   if waits==wait_limit:m.mem_write(STATE,struct.pack('<I',(head+1)&255))
  else:raise AssertionError(hex(target))
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR) if addr in (B+0x89c8dd4,B+0x89c8fc0) else addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604090);counts=dict(batch=0,batch_guard=0,ring=0,disabled=0,ring_guard=0,flush=0,wait=0)
for i in range(2176):
 combined=i>=1664
 mode=(i%3) if combined else (0 if i<512 else 1 if i<1024 else 2 if i<1536 else 3)
 va=rng.choice([0xfffffc2000100000,0xfffffc20c0000000,0xfffffc2180000000,rng.getrandbits(64)])
 if combined:va=rng.choice([0xfffffc2000100000,0xfffffc20c0000000,0xfffffc2181400000])+rng.randrange(32)*16384
 pa=0x10000000000+(rng.randrange(0x600000000)//16384)*16384;writable=i&1;gate=(i>>1)&1
 flags=(3 if 0xfffffc20c0000000<=va<0xfffffc2180000000 and not gate else 1)|(4 if writable else 0)
 record=descriptor(va,pa,writable,gate)
 assert struct.unpack('<QIIHHI',record)==(va,(pa>>12)&0xffffffff,0,1,flags,0)
 image=bytearray(rng.randbytes(0x50000))
 def put(addr,val,fmt='<Q'):struct.pack_into(fmt,image,addr-FW,val)
 put(FW,VT);put(VT+0x2d8,CONVERT);put(VT+0x358,SHIFT);put(FW+0x16e0,LOCK);put(FW+0x16c0,STATE);put(FW+0x16c8,RING);put(FW+0x1668,PROVIDER);put(PROVIDER,PVT);put(PVT+0x8a8,FLUSH)
 put(FW+0x16e8,BATCH if mode==0 else 0);put(FW+0x1714,int(mode!=2),'<B');put(FW+0x2a9,gate,'<B')
 size=rng.randrange(1,128);cursor=size if i%8==0 else rng.randrange(size)
 put(FW+0x16f0,cursor,'<H');put(FW+0x16f2,size,'<H')
 head=rng.randrange(256);tail=rng.randrange(256)
 if mode==1 and i%4==0:head=(tail+1)&255
 if mode==3:
  if i&1:tail=256
  else:head=256
 put(STATE,head,'<I');put(STATE+0x10,tail,'<I')
 if combined:
  GART=0x340000;GVT=0x341000;GPU=0x342000;ROOT=0x330000;MID=0x334000;LEAF=0x338000
  geometry=bytearray(96)
  for j,(shift,n,mask) in enumerate(GEOMETRY):struct.pack_into('<BBBBHHQQQ',geometry,j*32,8,14,14,shift,n,16384,1,0x3ffffffc000,mask)
  image[GART-FW+0x390:GART-FW+0x3f0]=geometry
  put(GART,GVT);put(GART+0x10,GPU);put(GPU+0x5b0,FW);put(GVT+0x270,B+0x89dcad8);put(VT+0x2f0,NOTIFY)
  put(GART+0x330,ROOT);put(ROOT+((va>>36)&63)*8,MID);put(MID+((va>>25)&2047)*8,LEAF)
  entry=(pa&0x3ffffffc000)|legacy_g16(writable);put(LEAF+((va>>14)&2047)*8,entry^1);put(GART+0x3f0,0xffffffff,'<I')
 m.mem_write(FW,bytes(image));events.clear();waits=0;wait_limit=1+i%3
 for reg,val in [(regs[0],FW),(regs[1],va),(regs[2],pa),(regs[3],writable),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 if combined:
  m.reg_write(regs[0],GART);m.reg_write(regs[4],1)
  m.emu_start(B+0x89f2328,STOP,count=800)
  put(LEAF+((va>>14)&2047)*8,entry);put(GART+0x3f0,0,'<I')
 else:m.emu_start(NOTIFY,STOP,count=600)
 expected=['lock'];guard=None
 if mode==0:
  if cursor==size:guard=GUARDS[0];counts['batch_guard']+=1
  else:
   image[BATCH-FW+cursor*24:BATCH-FW+(cursor+1)*24]=record;put(FW+0x16f0,cursor+1,'<H');counts['batch']+=1
 elif mode in (1,3):
  expected+=['lock']
  if tail>=256:guard=GUARDS[1]
  elif head>=256:guard=GUARDS[2]
  else:
   plan=ring_transition(head,tail)
   if plan['flush']:expected+=['flush'];counts['flush']+=1
   if plan['wait']:
    expected+=['wait']*wait_limit;put(STATE,(head+1)&255,'<I');counts['wait']+=wait_limit
   image[RING-FW+tail*24:RING-FW+(tail+1)*24]=record;put(STATE+0x10,(tail+1)&255,'<I');expected+=['unlock'];counts['ring']+=1
  if guard:counts['ring_guard']+=1
 else:counts['disabled']+=1
 if guard:assert m.reg_read(c.UC_ARM64_REG_PC)==guard
 else:
  expected+=['unlock'];assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 assert events==expected,(i,events,expected)
 assert bytes(m.mem_read(FW,len(image)))==image,i
bindings=[]
for slot,target in [(0x2d8,CONVERT),(0x2f0,NOTIFY),(0x358,SHIFT)]:
 word=struct.unpack('<Q',read(B+0x7ea8668+16+slot,8))[0];assert B+0x7004000+(word&0xffffffff)==target
 bindings.append(dict(slot=hex(slot),target=hex(target)))
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],counts=counts,combined_legacy_notifications=512,bindings=bindings,range=[hex(INSERT),hex(CONVERT+12)],sha256=hashlib.sha256(read(INSERT,CONVERT+12-INSERT)).hexdigest(),descriptor=dict(size=24,format='<QIIHHI',fields=['VA unchanged','physical>>12 truncated u32','zero u32','1 (16KiB unit count)','classification1/3 plus writable4','zero u32']),qualification='1664 actual firmware notify executions plus512 continuous legacy G16 leaf-update -> native notify -> batching/ring cases with the actual callback target and ASID-independent high physical address encoding. Full leaf/counter and notification storage images compared; counter wrap covered. Standalone cases, includes native convert(identity), FW page shift14 and native ring insertion. Whole firmware/state/ring/batch images and lock/flush/wait service arguments/order checked. External locks, provider send and firmware head advance supplied; no actual firmware ring publication or consumption. High physical addresses preserved as page numbers. No PTE installed or pixels proved.'),indent=2)+'\n');print(counts)
