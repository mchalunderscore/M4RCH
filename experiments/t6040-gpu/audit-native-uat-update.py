"""Audit actual native UAT leaf update, including owned metadata and guards."""
import sys,struct,json,hashlib,random
from pathlib import Path
repo=Path(__file__).resolve().parent
sys.path.insert(0,str(repo))
from native_uat_flags import encode
from native_uat_mapping import leaf_update
import unicorn as u
from unicorn import arm64_const as c
source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'uat_setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];BASE=0xfffffe0000000000;START=BASE+0x8a2ebf8;END=BASE+0x8a2ee28;ENC=BASE+0x8a32588;STOP=0x21f000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for va,n in [(BASE+0x8a2e000,8192),(BASE+0x8a32000,4096),(BASE+0x7131000,4096),(0x200000,0x20000),(0x300000,0x20000)]:m.mem_map(va,n)
m.mem_write(START,read(START,END-START));m.mem_write(ENC,read(ENC,0x10c));m.mem_write(BASE+0x71313f4,read(BASE+0x71313f4,64))
GUARDS=[BASE+x for x in (0x8a2ed04,0x8a2ed2c,0x8a2ed54,0x8a2ed7c,0x8a2eda4,0x8a2edcc,0x8a2edf4)]
calls=[]
def hook(m,addr,size,user):
 if addr in (*GUARDS,STOP):m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word==0xd503237f or addr==BASE+0x8a2ec98:m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR))
 elif addr==BASE+0x8a2ecb4:
  assert m.reg_read(c.UC_ARM64_REG_X8)==ENC
  calls.append((m.reg_read(c.UC_ARM64_REG_W1),m.reg_read(c.UC_ARM64_REG_W2)))
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,ENC)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604088);OBJ=0x300000;ROOT=0x301000;L1DIR=0x302000;L1=0x304000;L2DIR=0x303000;L2=0x308000;LEAF=0x30c000;VT=0x310000
valid=[(a,f) for a in (0,1) for f in range(1024) if not(f&~0x30f) and f&12!=12]
counts=dict(updated=0,guards=[0]*7);indexmax=[0,0,0]
for i in range(1536):
 aperture,flags=valid[i%len(valid)];ri=rng.randrange(64);mi=rng.randrange(2048);li=rng.randrange(2048)
 va=(aperture<<42)|(ri<<36)|(mi<<25)|(li<<14)|rng.randrange(16384)
 if aperture:va|=0xfffff80000000000
 pa=rng.randrange(1<<26)<<14;dummy=rng.getrandbits(64);kind=-1 if i<1024 else (i-1024)%7
 image=bytearray(rng.randbytes(0x14000))
 def put(addr,value):struct.pack_into('<Q',image,addr-OBJ,value)
 block=OBJ+aperture*0x90
 put(OBJ,VT);put(VT+0x190,ENC);put(block+0x30,ROOT);put(block+0x40,L1DIR);put(block+0x58,L2DIR);put(OBJ+0xb0,dummy)
 put(ROOT+ri*8,3);put(L1DIR+ri*8,L1);put(L1+mi*8,3);put(L2DIR+ri*8,L2);put(L2+mi*8,LEAF);put(LEAF+li*8,dummy)
 if kind==0:pa|=1 if i&1 else 1<<40
 elif kind==1:put(ROOT+ri*8,0)
 elif kind==2:put(L1DIR+ri*8,0)
 elif kind==3:put(L1+mi*8,0)
 elif kind==4:put(L2DIR+ri*8,0)
 elif kind==5:put(L2+mi*8,0)
 elif kind==6:put(LEAF+li*8,dummy^1)
 m.mem_write(OBJ,bytes(image));calls.clear()
 for reg,value in [(c.UC_ARM64_REG_X0,OBJ),(c.UC_ARM64_REG_X1,va),(c.UC_ARM64_REG_X2,pa),(c.UC_ARM64_REG_W3,flags),(c.UC_ARM64_REG_SP,0x21e000),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,value)
 m.emu_start(START,STOP,count=250)
 if kind<0:
  assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==0x21e000
  plan=leaf_update(va,pa,flags)
  assert (plan['aperture'],plan['root_index'],plan['middle_index'],plan['leaf_index'])==(aperture,ri,mi,li)
  put(LEAF+li*8,plan['pte']);counts['updated']+=1
  indexmax=[max(indexmax[0],ri),max(indexmax[1],mi),max(indexmax[2],li)]
 else:
  assert m.reg_read(c.UC_ARM64_REG_PC)==GUARDS[kind],(i,hex(m.reg_read(c.UC_ARM64_REG_PC)),kind)
  counts['guards'][kind]+=1
 assert bytes(m.mem_read(OBJ,len(image)))==image,i
 assert calls==([(aperture,flags)] if kind in (-1,6) else []),(i,calls)
report=dict(binary_sha256=ns['sha'],range=[hex(START),hex(END)],sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,index_max=indexmax,findings=['Aperture selected from VA bit42; six-bit root index36..41, middle25..35, leaf14..24','Physical address guard permits bits39..14 only; VA low14 bits ignored by this update method','Per aperture metadata stride90: hardware root pointer30, CPU L1 directory40, CPU L2 directory58','Root/middle require valid bit0; CPU directory pointers must exist','Actual generic encoder dispatched at vtable slot190 and executed, not replaced by model','Leaf must equal object+b0 dummy PTE before replacement; update writes physical OR encoded flags'],qualification='1024 whole native leaf updates and512 guards in emulated RAM, whole object/directory/table image comparison. PAC authentication bypassed; numeric dispatch target checked. No allocation, mapping API translation, hardware root publication, cache clean/TLB invalidation or GPU translation proved.')
ns['a'].output.write_text(json.dumps(report,indent=2)+'\n');print(counts,indexmax)
