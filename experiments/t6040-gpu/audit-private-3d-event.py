"""Native ordinary3D event/control window, actual virtual method bodies."""
import sys,struct,random,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parent
sys.path.insert(0,str(repo))
import unicorn as u
from unicorn import arm64_const as c
from private_3d_command import event_control
source=repo/'audit-private-3d-command.py'
ns={'__file__':str(source),'__name__':'event_setup'}
exec(compile(source.read_text().split('rng=random.Random(604012);counts={}')[0],str(source),'exec'),ns)
m,read,BASE,regs=[ns[n] for n in ('m','read','BASE','regs')]
D,C,CH=ns['D'],ns['C'],ns['CH']
START,END=BASE+0x895b9d8,BASE+0x895bbb0
GET,PAYLOAD=BASE+0x895d5e4,BASE+0x89d5cf0
for page in (BASE+0x895d000,BASE+0x89d5000):m.mem_map(page,4096)
for start,end in ((START,END),(GET,GET+12),(PAYLOAD,PAYLOAD+12)):m.mem_write(start,read(start,end-start))
for table,slot,target in ((BASE+0x7eb7898,0x1e0,GET),(BASE+0x7eaa8e0,0x220,PAYLOAD)):
 enc=struct.unpack('<Q',read(table+16+slot,8))[0];assert BASE+0x7004000+(enc&0xffffffff)==target
ACC,QUEUE,OWNER,EVENT,CTX,DVT,CVT=0x300000,0x320000,0x321000,0x322000,0x325000,0x326000,0x327000
m.mem_map(ACC,0x30000)
for address,value in ((DVT+0x1e0,GET),(CVT+0x220,PAYLOAD),(QUEUE+0x68,OWNER),(OWNER+0x140,EVENT)):
 m.mem_write(address,struct.pack('<Q',value))
calls=[]
def hook(m,addr,size,user):
 if addr==END:m.emu_stop();return
 if addr in (GET,PAYLOAD):calls.append(addr)
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target in (GET,PAYLOAD)
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604022);boundaries=[0,1,255,256,0x7ffffffe,0x7fffffff,0x80000000,0xfffffffe,0xffffffff]
counts={'cases':0,'epoch0':0,'epoch1':0,'inactive_aperture':0,'context_only':0}
for i in range(2048):
 command=rng.randbytes(0x2300);desc=bytearray(rng.randbytes(0x1800));context=bytearray(rng.randbytes(0x600));channel=bytearray(rng.randbytes(0x300))
 event=boundaries[i%len(boundaries)] if i<1024 else rng.getrandbits(32)
 capacity=[1,2,3,64,255,256][i%6];initial=rng.getrandbits(64);epochs=[rng.getrandbits(64),rng.getrandbits(64)];payload=rng.randrange(256);qid=i%24;flags=rng.randrange(256)
 count=[0,0,1,16][i%4]
 if i%4==0:context[0x490:0x4b0]=bytes(32);counts['inactive_aperture']+=1
 if i%4==1:counts['context_only']+=1
 struct.pack_into('<Q',desc,0,DVT);struct.pack_into('<Q',desc,0x10,ACC);struct.pack_into('<I',desc,0x210,event);struct.pack_into('<I',desc,0xa70,count)
 struct.pack_into('<Q',channel,0,CVT);struct.pack_into('<Q',channel,0x10,ACC);struct.pack_into('<i',channel,0x18,qid);struct.pack_into('<I',channel,0x204,payload)
 m.mem_write(D,bytes(desc));m.mem_write(C,command);m.mem_write(CH,bytes(channel));m.mem_write(CTX,bytes(context))
 m.mem_write(ACC+0xf938+qid*8,struct.pack('<Q',QUEUE));m.mem_write(ACC+0xf570,bytes([flags]))
 m.mem_write(EVENT+0x1458+qid*24,struct.pack('<2Q',*epochs));m.mem_write(QUEUE+0x10,struct.pack('<I',capacity));m.mem_write(QUEUE+0x90,struct.pack('<Q',initial))
 for reg in regs:m.reg_write(reg,0)
 for j,value in ((19,CH),(20,D),(24,C),(26,CTX),(28,C+0x1f38)):m.reg_write(regs[j],value)
 calls.clear();m.emu_start(START,END,count=300);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 expected,expected_desc=event_control(command,desc,context,epochs,capacity,initial,payload,flags)
 assert bytes(m.mem_read(C,len(command)))==expected,(i,hex(event),'command')
 assert bytes(m.mem_read(D,len(desc)))==expected_desc,(i,hex(event),'descriptor')
 assert bytes(m.mem_read(CTX,len(context)))==bytes(context)
 assert bytes(m.mem_read(CH,len(channel)))==bytes(channel)
 assert calls==[GET,PAYLOAD];counts['cases']+=1;counts['epoch'+str(event>>31)]+=1
report={'binary_sha256':ns['sha'],'counts':counts,'event_boundaries':[hex(x) for x in boundaries],'window':{'start':hex(START),'end':hex(END),'sha256':hashlib.sha256(read(START,END-START)).hexdigest()},'qualification':'Actual continuous ordinary3D event/control code and actual virtual getters in emulated RAM. Entire command/descriptor compared, context/channel unchanged. Queue/event-machine pointers and epochs explicit fixtures; no live allocation, concurrent epoch updates, cache/publication or rendering proof.'}
ns['a'].output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
