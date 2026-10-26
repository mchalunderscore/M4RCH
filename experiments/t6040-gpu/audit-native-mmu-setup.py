"""Execute pinned G16 MMU setup against RAM and checked register services."""
import sys,struct,json,hashlib,random
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
repo=Path(__file__).resolve().parent
p=repo/'audit-private-3d-pool.py';ns={'__file__':str(p),'__name__':'setup'}
exec(compile(p.read_text().split('m=u.Uc')[0],str(p),'exec'),ns)
read=ns['read'];B=0xfffffe0000000000;FN=B+0x89e67f8;END=B+0x89e6d28;GET=B+0x89e6dc4
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
m.mem_map(B+0x89e6000,4096);m.mem_write(FN,read(FN,END-FN));m.mem_write(GET,read(GET,12))
m.mem_map(0x300000,0x100000)
for page in (B+0xbfa6000,B+0x8a06000,B+0x8a07000):m.mem_map(page,4096)
SM=0x300000;GPU=0x304000;VT=0x324000;DESC=0x325000;REG=0x380000;STOP=0x3fff00;STACK=0x3ff000
encoded=struct.unpack('<Q',read(B+0x7ead9a0+16+0x158,8))[0]
assert B+0x7004000+(encoded&0xffffffff)==GET
rng=random.Random(604095);events=[];counts=dict(cases=512,direct=0,service=0,already_enabled=0,programmed=0)
def hook(mu,addr,size,unused):
 if addr==STOP:mu.emu_stop();return
 word=struct.unpack('<I',mu.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or addr==B+0x89e6880:mu.reg_write(c.UC_ARM64_REG_PC,addr+4)
 elif word==0xd65f0fff:mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR))
 elif addr==B+0x89e6898:
  assert mu.reg_read(c.UC_ARM64_REG_X8)==GET and mu.reg_read(c.UC_ARM64_REG_X0)==SM
  events.append(('descriptor',));mu.reg_write(c.UC_ARM64_REG_LR,addr+4);mu.reg_write(c.UC_ARM64_REG_PC,GET)
 elif addr==B+0xbfa67a0:
  assert mu.reg_read(c.UC_ARM64_REG_X0)==DESC
  events.append(('physical',));mu.reg_write(c.UC_ARM64_REG_X0,physical);mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR))
 elif addr in (B+0x8a0625c,B+0x8a07578):
  assert mu.reg_read(c.UC_ARM64_REG_X0)==GPU
  offset=mu.reg_read(c.UC_ARM64_REG_X1);assert 0xd08000<=offset<=0xd0802c
  va=REG+offset-0xd08000
  if addr==B+0x8a07578:
   val=mu.reg_read(c.UC_ARM64_REG_W2);events.append(('write',offset,val));mu.mem_write(va,struct.pack('<I',val))
  else:
   events.append(('read',offset));mu.reg_write(c.UC_ARM64_REG_W0,struct.unpack('<I',mu.mem_read(va,4))[0])
  mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR))
def memory(mu,access,addr,size,value,unused):
 if REG<=addr<REG+0x40:
  assert size==4
  events.append(('write',0xd08000+addr-REG,value) if access==u.UC_MEM_WRITE else ('read',0xd08000+addr-REG))
m.hook_add(u.UC_HOOK_CODE,hook);m.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,memory)
for i in range(512):
 image=bytearray(rng.randbytes(0x90000));direct=i&1;enabled=0 if i%3 else rng.randrange(1,1<<32);physical=rng.randrange(1<<42)
 def put(addr,val,fmt='<Q'):struct.pack_into(fmt,image,addr-SM,val)
 put(SM,VT);put(SM+0x40,GPU);put(SM+0x10,DESC);put(VT+0x158,GET)
 put(GPU+0xc774,direct,'<I');put(GPU+0xc980,0xd08000);put(GPU+0xf8e8,REG);put(REG,enabled,'<I')
 m.mem_write(SM,bytes(image));events.clear()
 for reg,val in [(c.UC_ARM64_REG_X0,SM),(c.UC_ARM64_REG_LR,STOP),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(FN,STOP,count=1200);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 expected=[('read',0xd08000)]
 if enabled:counts['already_enabled']+=1
 else:
  counts['programmed']+=1;expected += [('descriptor',),('physical',)]
  writes=[(0x2c,(physical>>14)&0xfffffff),(0x14,0x80d8),(0x18,0x80d8),(0xc,0),(0x10,0),(0x1c,0),(0x20,0),(0x24,0),(0x28,0),(8,1),(4,0x3ff),(0,1)]
  for offset,value in writes:
   expected += [('write',0xd08000+offset,value),('read',0xd08000+offset)];put(REG+offset,value,'<I')
 assert events==expected,(i,events,expected)
 assert bytes(m.mem_read(SM,len(image)))==image,i
 counts['direct' if direct else 'service']+=1
result=dict(binary_sha256=ns['sha'],counts=counts,range=[hex(FN),hex(END)],range_sha256=hashlib.sha256(read(FN,END-FN)).hexdigest(),getter_range=[hex(GET),hex(GET+12)],getter_sha256=hashlib.sha256(read(GET,12)).hexdigest(),base_register='0xd0802c',physical_encoding='(physical >> 14) & 0x0fffffff',writes_after_disabled=[dict(offset=hex(0xd08000+o),value='physical_page_number' if o==0x2c else hex(v)) for o,v in writes],qualification='512 full randomized RAM images and ordered service/direct RAM-register event streams. Actual G16 setup and descriptor getter executed; PAC bypassed. Physical-address service and register services supplied, direct branch uses RAM surrogate. Nonzero control skips all setup without checking current table base. Physical inputs include unaligned values below2^42, native extraction drops low14 bits. No hardware MMU write, translation, coherency, valid live allocation or rendering proved.')
ns['a'].output.write_text(json.dumps(result,indent=2)+'\n');print(counts)
