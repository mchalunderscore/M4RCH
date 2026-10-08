"""Execute native firmware mapping buffer publication slice, and root status-buffer linkage, independently of hardware."""
from pathlib import Path
import sys,struct,hashlib,json,random
import unicorn as u
from unicorn import arm64_const as c
repo=Path(__file__).resolve().parent;source=repo/'audit-private-3d-pool.py';ns={'__file__':str(source),'__name__':'setup'}
exec(compile(source.read_text().split('m=u.Uc')[0],str(source),'exec'),ns)
read=ns['read'];B=0xfffffe0000000000;START=B+0x89d0eb4;END=B+0x89d0f5c;CONVERT=B+0x89c8ff8
LINK=B+0x89cdb84; LINKEND=B+0x89cdbc8
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
for va,n in [(B+0x89d0000,4096),(B+0x89c8000,8192),(B+0x89cd000,4096),(0x300000,0x20000)]:m.mem_map(va,n)
m.mem_write(LINK,read(LINK,LINKEND-LINK));m.mem_write(START,read(START,END-START));m.mem_write(CONVERT,read(CONVERT,12))
FW=0x300000;VT=0x303000;DEST=0x308000;STATE=0x310000;STACK=0x31f000;calls=[];ROOT=0x314000
def hook(m,addr,size,user):
 if addr in (END,LINKEND):m.emu_stop();return
 if addr in (B+0x89d0ec4,B+0x89d0efc,B+0x89cdb8c):m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif addr in (B+0x89d0f04,B+0x89cdb94):m.reg_write(c.UC_ARM64_REG_X17,m.reg_read(c.UC_ARM64_REG_X16));m.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif addr in (B+0x89d0ee0,B+0x89d0f2c,B+0x89cdbbc):
  target=m.reg_read(c.UC_ARM64_REG_X8 if addr==B+0x89d0ee0 else c.UC_ARM64_REG_X9)
  assert target==CONVERT and m.reg_read(c.UC_ARM64_REG_X0)==FW and m.reg_read(c.UC_ARM64_REG_W2)==0
  calls.append(m.reg_read(c.UC_ARM64_REG_X1));m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target)
rng=random.Random(604091);m.hook_add(u.UC_HOOK_CODE,hook)
for i in range(512):
 image=bytearray(rng.randbytes(0x18000));state_va=0xfffffc200088c000+i*0x4000;entries_va=0xfffffc2001000000+i*0x4000
 def put(addr,val,fmt='<Q'):struct.pack_into(fmt,image,addr-FW,val)
 put(FW,VT);put(VT+0x2d8,CONVERT);put(FW+0x960,DEST);put(FW+0x970,0xfffffc2000144000+i*0x10000);put(FW+0x16c0,STATE);put(FW+0x16d0,state_va);put(FW+0x16d8,entries_va)
 m.mem_write(FW,bytes(image));calls.clear();m.reg_write(c.UC_ARM64_REG_X19,FW);m.reg_write(c.UC_ARM64_REG_SP,STACK)
 m.emu_start(START,END,count=100)
 assert m.reg_read(c.UC_ARM64_REG_PC)==END and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 put(DEST+0x48e0,state_va);put(DEST+0x48e8,entries_va);put(STATE,0,'<I');put(STATE+0x10,0,'<I')
 put(DEST+0x48f0,0);put(DEST+0x4900,0,'<I');put(DEST+0x4910,0,'<I')
 assert bytes(m.mem_read(FW,len(image)))==image and calls==[state_va,entries_va]
 m.reg_write(c.UC_ARM64_REG_X20,ROOT);m.reg_write(c.UC_ARM64_REG_X22,FW)
 m.emu_start(LINK,LINKEND,count=100)
 assert m.reg_read(c.UC_ARM64_REG_PC)==LINKEND
 put(ROOT+0xb0,0xfffffc2000144000+i*0x10000)
 assert bytes(m.mem_read(FW,len(image)))==image and calls==[state_va,entries_va,0xfffffc2000144000+i*0x10000]
ns['a'].output.write_text(json.dumps(dict(binary_sha256=ns['sha'],cases=512,range=[hex(START),hex(END)],root_link_range=[hex(LINK),hex(LINKEND)],sha256=hashlib.sha256(read(START,END-START)).hexdigest(),root_link_sha256=hashlib.sha256(read(LINK,LINKEND-LINK)).hexdigest(),findings=['StateGPUVA hostFW16d0 -> object(hostFW960)+48e0','EntriesGPUVA hostFW16d8 -> object(hostFW960)+48e8','StateCPU hostFW16c0: head0 and producer10 cleared','Publication target48f0(u64),4900(u32),4910(u32) cleared','Actual converter slot2d8 executed and preserves both VAs'],root_offset='0xb0',allocation_bytes=58432,qualification='Native root link proves hostFW970 mapping is root+b0 (status_b); hostFW960 CPU backing correspondence follows separately qualified allocation descriptor. Actual allocator/mapping service is not executed. Contiguous native initialization publication slice with512 whole firmware/state/target image comparisons. CPU/GPU alias correspondence is supplied, not exercised on hardware. These offsets must not be applied blindly to the community main-buffer layout. No hardware publication or consumption.'),indent=2)+'\n');print('512 native notification bindings and root status_b links matched')
