#!/usr/bin/env python3
"""Execute native scheduler sequence through post-kick records and pointer publications."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_work_body import patch_work_body
from private_work_prefix import patch_work_prefix
from private_nop_body import convert_timestamp, patch_cached_body
from private_scheduler_config import patch_config
from private_scheduler_publish import publish_nop
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
s=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:s.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def read(address,size):
 for vm,_,off,length in s:
  if vm<=address and address+size<=vm+length:return raw[off+address-vm:off+address-vm+size]
 raise ValueError('Not file backed')
BASE=0xfffffe0000000000;WRAPPER=BASE+0x89db63c;START=BASE+0x895bd00;END=BASE+0x895c374;DIAG=BASE+0x895c438;NOP=BASE+0x89dc07c;BUFFER=0x300000;STOP=0x24f000
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
# Map original file-backed executable segment at its linked virtual address.
for vm,length,off,filesize in s:
 if vm==BASE+0x895a960:
  page=vm&~4095;m.mem_map(page,((vm-page+length+4095)//4096)*4096);m.mem_write(vm,raw[off:off+filesize])
m.mem_map(BASE+0x7130000,4096);m.mem_write(BASE+0x7130000,read(BASE+0x7130000,4096));m.mem_map(0x200000,0x50000);m.mem_map(BUFFER,0x20000);m.mem_map(0x400000,0x30000)
D,DVT,O,CTX,TASK,DEV,ACCEL,STACK=0x222000,0x223000,0x224000,0x225000,0x226000,0x227000,0x228000,0x24e000
GETCMD,GETBAR=BASE+0x895d5e4,BASE+0x895d5d8
for slot,target in [(0x1e0,GETCMD),(0x1e8,GETBAR)]:
 encoded=struct.unpack('<Q',read(BASE+0x7eb7898+16+slot,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==target
 m.mem_write(DVT+slot,struct.pack('<Q',target))
encoded=struct.unpack('<Q',read(BASE+0x7eac548+16+0x168,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==WRAPPER
QVT,CH,FW,CFG=0x221000,0x220000,0x24a000,0x24b000
for slot,target in [(0x148,NOP),(0x168,WRAPPER)]:
 encoded=struct.unpack('<Q',read(BASE+0x7eac548+16+slot,8))[0];assert BASE+0x7004000+(encoded&0xffffffff)==target
 m.mem_write(QVT+slot,struct.pack('<Q',target))
R12,R14,R16,RING,RSTATE,FVT,MVT,CVT,REGISTER,MAP=0x400000,0x401000,0x402000,0x416000,0x417000,0x418000,0x419000,0x41a000,0x41b000,0x41b100
PUB=BASE+0x8981048
m.mem_write(CVT+0x188,struct.pack('<Q',PUB));m.mem_write(FVT+0x2d8,struct.pack('<Q',MAP));m.mem_write(MVT+0x168,struct.pack('<Q',REGISTER))
assert BASE+0x7004000+(struct.unpack('<Q',read(BASE+0x7eaa8e0+16+0x188,8))[0]&0xffffffff)==PUB
RCONFIG,RESOURCE,RVT,SOBJ,SVT,RESOURCE_CB,CHANNEL_CB1,CHANNEL_CB2=0x403000,0x41c000,0x41d000,0x41e000,0x41f000,0x420000,0x420004,0x420008
GETDM=BASE+0x895dc98
m.mem_map(BASE+0x712d000,4096);m.mem_write(BASE+0x712d000,read(BASE+0x712d000,4096))
m.mem_write(DVT+0x188,struct.pack('<Q',GETDM));m.mem_write(RVT+0x1e0,struct.pack('<Q',RESOURCE_CB));m.mem_write(SVT+0x1f0,struct.pack('<Q',CHANNEL_CB1));m.mem_write(SVT+0x1f8,struct.pack('<Q',CHANNEL_CB2))
header=struct.unpack('<Q',read(BASE+0x712d720,8))[0];vector=read(BASE+0x712d9b0,16)
calls=[];published=[]
def hook(m,addr,size,user):
 if addr in (STOP,END,DIAG):m.emu_stop();return
 if addr==NOP:calls.append('native_nop')
 if addr==WRAPPER:calls.append('native_3d')
 if addr==GETDM:calls.append('native_data_master')
 if addr in (RESOURCE_CB,CHANNEL_CB1,CHANNEL_CB2):
  assert m.reg_read(c.UC_ARM64_REG_X0)==(RESOURCE if addr==RESOURCE_CB else SOBJ)
  calls.append('synthetic_config_callback');value=config_callbacks[(addr-RESOURCE_CB)//4]
  m.reg_write(c.UC_ARM64_REG_W0,value);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 if addr==REGISTER:
  assert [m.reg_read(getattr(c,'UC_ARM64_REG_X'+str(j))) for j in range(3)]==[CTX,qid,struct.unpack_from('<I',queue,0x20)[0]]
  calls.append('synthetic_owner_registration');m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 if addr==MAP:
  assert [m.reg_read(getattr(c,'UC_ARM64_REG_X'+str(j))) for j in range(3)]==[FW,struct.unpack_from('<Q',descriptor,0x910)[0],0]
  calls.append('synthetic_firmware_mapping');m.reg_write(c.UC_ARM64_REG_X0,mapped);m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 if addr==PUB:
  values=[m.reg_read(getattr(c,'UC_ARM64_REG_X'+str(j))) for j in range(4)];assert values[0]==CH and values[3]==0
  published.append(values[1:3]);calls.append('native_pointer_publish')
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word in (0xd503237f,0xd50323ff) or word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_X30));return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(getattr(c,'UC_ARM64_REG_X'+str((word>>5)&31)));assert target in (GETCMD,GETBAR,NOP,WRAPPER,REGISTER,MAP,PUB,GETDM,RESOURCE_CB,CHANNEL_CB1,CHANNEL_CB2)

  if target in (GETCMD,GETBAR):calls.append('native_getter')
  m.reg_write(c.UC_ARM64_REG_X30,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target);return
 if word>>26==0b100101:
  imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  target=addr+imm*4
  if target==BASE+0xbeaf410:
   assert m.reg_read(c.UC_ARM64_REG_X0)==struct.unpack_from('<Q',descriptor,0x60)[0] and m.reg_read(c.UC_ARM64_REG_X1)==BASE+0xc6e6298
   calls.append('synthetic_owner_lookup');m.reg_write(c.UC_ARM64_REG_X0,O);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
  elif target==BASE+0xb744da0:
   assert BUFFER<=m.reg_read(c.UC_ARM64_REG_X0)<BUFFER+capacity*0x200 and m.reg_read(c.UC_ARM64_REG_X1)==0x200
   calls.append('synthetic_zero');m.mem_write(m.reg_read(c.UC_ARM64_REG_X0),bytes(0x200));m.reg_write(c.UC_ARM64_REG_PC,addr+4)
  else:assert target in (BASE+0x89db230,BASE+0x89ee94c),hex(target)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604026);counts=dict(release_roundtrips=0,config_records=0,pointer_publications=0,opcode12=0,opcode14=0,opcode16=0,nop_records=0,guard_cases=0,cases=0,fallback_aux=0,descriptor_aux=0,cached=0,uncached=0,qos_local=0,qos_fallback=0,qos_ratio=0)
for i in range(1024):
 capacity=[2,3,16,256][i%4];timestamp=(rng.getrandbits(64)&~255)|(i%capacity);extra=(i//4)%capacity;initial=rng.getrandbits(64);qid=rng.getrandbits(32);cached=bool(i&1);previous=rng.getrandbits(64)
 queue=bytearray(rng.randbytes(0x100));descriptor=bytearray(rng.randbytes(0x1000));owner=bytearray(rng.randbytes(0x1000));context=bytearray(rng.randbytes(0x1000));task=bytearray(rng.randbytes(0x1000));dev=bytearray(rng.randbytes(0x1000));accel=bytearray(rng.randbytes(0x20000))
 struct.pack_into('<Q',descriptor,0,DVT);struct.pack_into('<Q',descriptor,0x10,ACCEL);struct.pack_into('<Q',descriptor,0x60,rng.getrandbits(64));struct.pack_into('<Q',owner,0x898,CTX);struct.pack_into('<Q',context,0x58,TASK);struct.pack_into('<Q',task,0x530,DEV)
 ratio=bool(i&4);selector=i%9 if ratio else 1;denominator=1+rng.randrange(65536);struct.pack_into('<I',dev,0xc68,denominator if ratio else 0);struct.pack_into('<Q',dev,0xc60,selector*denominator)
 local=bool(i&8);struct.pack_into('<I',dev,0xc88,int(local));struct.pack_into('<Q',dev,0x10,ACCEL)
 qos=[struct.unpack_from('<I',context,0x10)[0]&255,rng.getrandbits(16),read(BASE+0x71307f0+selector*3+1,1)[0]]
 struct.pack_into('<H',dev,0xc8e,qos[1]);struct.pack_into('<H',accel,0x770,qos[1]);accel[0x1aed4]&=~8
 ap_addr=rng.getrandbits(64);ap_index=rng.getrandbits(32);ap_count=[0,1,64,65][i%4];struct.pack_into('<Q2I',descriptor,0xa98,ap_addr,ap_index,ap_count)
 payload=[rng.getrandbits(64),rng.getrandbits(64)];m.mem_write(0x208100,struct.pack('<Q',0x208200));m.mem_write(0x208200,struct.pack('<2Q',*payload))
 reglists=[(rng.getrandbits(64),rng.getrandbits(16)) for _ in range(4)];kind=rng.getrandbits(32);struct.pack_into('<I',descriptor,0x820,kind)
 for j,(address,count) in enumerate(reglists):struct.pack_into('<QH',descriptor,0x828+j*16,address,count)
 epochs={}
 for idx in range(24):
  epochs[idx]=(rng.getrandbits(64),rng.getrandbits(64));m.mem_write(0x20a000+0x1458+idx*24,struct.pack('<2Q',*epochs[idx]))
 event=rng.getrandbits(32);idx=rng.randrange(24);struct.pack_into('<2I',descriptor,0x210,event,idx)
 if not cached:previous=(convert_timestamp(epochs[idx][event>>31],event,capacity,initial)-1)&((1<<64)-1)
 n=i%9;struct.pack_into('<I',descriptor,0x218,n);entries=[]
 for j in range(n):
  ev=rng.getrandbits(32);ix=rng.randrange(24);entries.append((ev,ix,epochs[ix][ev>>31]));struct.pack_into('<3I',descriptor,0x21c+j*12,ev,ix,rng.getrandbits(32))
 aux=rng.getrandbits(64);fallback=bool(i&2);struct.pack_into('<Q',descriptor,0x168,0 if fallback else aux);struct.pack_into('<I',descriptor,0x964,i%128);struct.pack_into('<Q',accel,0xfd48+(i%128)*8,aux)
 first=descriptor[0xc44]==3 or bool(descriptor[0x4c]&1);second=bool(descriptor[0xb48]&1)
 masks=[rng.getrandbits(64) for _ in range(4)];m.mem_write(0x205000,struct.pack('<4Q',*masks))
 for off,val,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x14,0x200,'I'),(0x1c,rng.getrandbits(32),'I'),(0x44,0,'I'),(0x48,timestamp,'Q'),(0x68,0x209000,'Q'),(0x78,BUFFER,'Q'),(0x90,initial,'Q'),(0xa0,previous,'Q')]:struct.pack_into('<'+fmt,queue,off,val)
 priority=struct.unpack_from('<I',queue,0x1c)[0];queue[0x98]=(queue[0x98]&254)|cached
 # Wrapper accesses accelerator for trace and fallback; common conversion uses this owner's event machine.
 struct.pack_into('<Q',queue,0,QVT);struct.pack_into('<I',descriptor,0x2dc,0);struct.pack_into('<Q',queue,0x68,ACCEL);struct.pack_into('<Q',accel,0x140,0x20a000)
 baseline=(event-((extra+1)*256+(i%256)))&0xffffffff
 m.mem_write(0x20a000+0x2050+idx*4,struct.pack('<I',baseline));struct.pack_into('<Q',accel,0xf938+idx*8,0x201000);struct.pack_into('<Q',accel,0xf938+(i%128)*8,0x201000)
 channel=bytearray(rng.randbytes(0x1000));struct.pack_into('<Q',channel,0x10,ACCEL);struct.pack_into('<Q',channel,0x80,payload[1]);struct.pack_into('<Q',accel,0x5b0,FW)
 flag63=bool(i&16);flag62=bool(i&32);flag61=bool(i&64);accel[0x6d7]=1 if flag61 else 0;struct.pack_into('<Q',descriptor,0x470,rng.getrandbits(64) if flag62 else 0)
 m.mem_write(FW,struct.pack('<Q',FVT));m.mem_write(FW+0x380,struct.pack('<Q',CFG));m.mem_write(CFG+0xe1c,bytes([int(flag63)]))
 masks=[0,0,0,(int(flag63)<<63)|(int(flag62)<<62)|(int(flag61)<<61)]
 config_original=rng.randbytes(0xc0);config_gpu=rng.getrandbits(64);conditional=bool(i&256);conditional_ptr=rng.getrandbits(64);conditional_value=rng.getrandbits(64);config_callbacks=[rng.getrandbits(32) for _ in range(3)]
 struct.pack_into('<Q',descriptor,0x58,RESOURCE);struct.pack_into('<Q',descriptor,0x170,SOBJ);struct.pack_into('<Q',descriptor,0x460,RCONFIG);struct.pack_into('<Q',descriptor,0x468,config_gpu);struct.pack_into('<Q',descriptor,0xb58,0x421000)
 m.mem_write(RESOURCE,struct.pack('<Q',RVT));m.mem_write(SOBJ,struct.pack('<Q',SVT));m.mem_write(0x4210b0,struct.pack('<Q',conditional_value));m.mem_write(RCONFIG,config_original)
 present12=bool(i&128);present16=flag62;mapped=rng.getrandbits(64);gpu=[rng.getrandbits(64) for _ in range(3)];control_original=[rng.randbytes(0x40) for _ in range(3)]
 for offset,value in [(0x480,R12 if present12 else 0),(0x488,gpu[0]),(0x450,R14),(0x458,gpu[1]),(0x470,R16 if present16 else 0),(0x478,gpu[2])]:struct.pack_into('<Q',descriptor,offset,value)
 for addr,data in zip((R12,R14,R16),control_original):m.mem_write(addr,data)
 struct.pack_into('<Q',context,0,MVT);struct.pack_into('<Q',channel,0,CVT);struct.pack_into('<Q',channel,0x60,RSTATE);struct.pack_into('<Q',channel,0x68,RING);struct.pack_into('<I',channel,0x54,16);accel[0xee5f]&=~1
 pointerstate=bytearray(rng.randbytes(0x100));pointerring=bytearray(rng.randbytes(0x80));pointerpos=i%16
 struct.pack_into('<I',pointerstate,0,pointerpos);struct.pack_into('<I',pointerstate,0x40,pointerpos);struct.pack_into('<I',pointerstate,0x60,16);m.mem_write(RSTATE,bytes(pointerstate));m.mem_write(RING,bytes(pointerring));m.mem_write(STACK+0x78,struct.pack('<Q',CH))
 objects=[(CH,channel),(0x201000,queue),(D,descriptor),(O,owner),(CTX,context),(TASK,task),(DEV,dev),(ACCEL,accel)]
 for addr,obj in objects:m.mem_write(addr,bytes(obj))
 backing=bytearray(rng.randbytes(capacity*0x200));m.mem_write(BUFFER,bytes(backing));calls.clear();published.clear()
 for reg,val in [(c.UC_ARM64_REG_X8,ACCEL),(c.UC_ARM64_REG_X19,CH),(c.UC_ARM64_REG_X20,D),(c.UC_ARM64_REG_X21,event),(c.UC_ARM64_REG_X22,idx),(c.UC_ARM64_REG_X23,0x201000),(c.UC_ARM64_REG_X25,payload[0]),(c.UC_ARM64_REG_X28,qid),(c.UC_ARM64_REG_X24,RCONFIG),(c.UC_ARM64_REG_W27,int(conditional)),(c.UC_ARM64_REG_X26,conditional_ptr),(c.UC_ARM64_REG_X29,STACK+0x1b0),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.mem_write(STACK+0x3c,struct.pack('<I',rng.getrandbits(32)))
 m.emu_start(START,END,count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 assert calls.count('native_nop')==extra and calls.count('native_3d')==1 and calls.count('synthetic_zero')==extra+1
 assert calls.count('native_getter')==2 and calls.count('synthetic_owner_lookup')==6
 # Independent sequence: zero each selected slot, encode NOPs, then ordinary3D.
 for j in range(extra):
  oldts=struct.unpack_from('<Q',queue,0x48)[0];pos=(oldts&255)*0x200
  prior=struct.unpack_from('<Q',queue,0xa0)[0] if queue[0x98]&1 else (convert_timestamp(epochs[idx][event>>31],event,capacity,initial)-1)&((1<<64)-1)
  record,newts=patch_cached_body(bytes(0x200),oldts,qid,priority,prior,[0,0,0,0],[0,0],capacity)
  backing[pos:pos+0x200]=record;struct.pack_into('<Q',queue,0x48,newts);updated,overflow=publish_nop(queue,oldts);assert not overflow;queue[:]=updated
 oldts=struct.unpack_from('<Q',queue,0x48)[0];pos=(oldts&255)*0x200
 prior=struct.unpack_from('<Q',queue,0xa0)[0] if queue[0x98]&1 else (convert_timestamp(epochs[idx][event>>31],event,capacity,initial)-1)&((1<<64)-1)
 prefixed=patch_work_prefix(bytes(0x200),oldts,qid,priority,ap_addr,ap_index,ap_count,first,second,payload)
 expected,counter=patch_work_body(prefixed,oldts,capacity,initial,qid,entries,prior,qos,kind,reglists,masks,aux)
 backing[pos:pos+0x200]=expected;assert bytes(m.mem_read(BUFFER,len(backing)))==bytes(backing),(i,'records')
 struct.pack_into('<Q',queue,0x48,counter);updated,overflow=publish_nop(queue,oldts);assert not overflow;queue[:]=updated
 struct.pack_into('<I',descriptor,0x2dc,extra+1);descriptor[0x2f5]=1
 pair=struct.unpack_from('<QQ',queue,0x80);descid=struct.unpack_from('<I',descriptor,0x144)[0]
 config=bytearray(patch_config(config_original,header,vector,pair,qid,priority,descid,[descriptor[0x180],descriptor[0x181]],[255,config_callbacks[0]]))
 struct.pack_into('<I',config,0x22,1);struct.pack_into('<I',config,0x26,descriptor[0x2e2]&1);struct.pack_into('<Q',config,0x2a,struct.unpack_from('<Q',descriptor,0x2e8)[0]);struct.pack_into('<Q',config,0x36,conditional_ptr if conditional else 0);struct.pack_into('<Q',config,0x3e,conditional_value if conditional else (1<<64)-1);struct.pack_into('<I',config,0x46,struct.unpack_from('<I',descriptor,0xb60)[0] if conditional else 0xffffffff)
 struct.pack_into('<Q',config,0x4a,struct.unpack_from('<Q',owner,0x8b8)[0]);struct.pack_into('<I',config,0x52,descriptor[0x2f6]&1);struct.pack_into('<I',config,0x56,struct.unpack_from('<I',context,0x10)[0]);struct.pack_into('<I',config,0x5e,config_callbacks[1]);struct.pack_into('<I',config,0x5a,config_callbacks[2])
 assert bytes(m.mem_read(RCONFIG,len(config)))==bytes(config) and calls.count('synthetic_config_callback')==3 and calls.count('native_data_master')==1
 counts['config_records']+=1
 expected_controls=[bytearray(x) for x in control_original];expected_publications=[[config_gpu,RCONFIG]]
 if present12:
  record=expected_controls[0];struct.pack_into('<I',record,0,12);struct.pack_into('<H',record,4,qid&0xffff);struct.pack_into('<Q',record,6,oldts);struct.pack_into('<Q',record,14,mapped);expected_publications.append([gpu[0],R12]);counts['opcode12']+=1
 record=expected_controls[1];struct.pack_into('<I',record,0,14);struct.pack_into('<H',record,4,qid&0xffff);struct.pack_into('<H',record,6,(extra+1)&0xffff);record[8]=priority&255;struct.pack_into('<Q',record,9,oldts);struct.pack_into('<I',record,17,1);expected_publications.append([gpu[1],R14]);counts['opcode14']+=1
 if present16:
  record=expected_controls[2];struct.pack_into('<I',record,0,16);struct.pack_into('<H',record,4,qid&0xffff);struct.pack_into('<Q',record,6,oldts);struct.pack_into('<I',record,14,254);expected_publications.append([gpu[2],R16]);counts['opcode16']+=1
 assert published==expected_publications and calls.count('synthetic_owner_registration')==1 and calls.count('synthetic_firmware_mapping')==int(present12)
 for addr,data in zip((R12,R14,R16),expected_controls):assert bytes(m.mem_read(addr,len(data)))==bytes(data)
 for gpu_addr,_ in expected_publications:
  struct.pack_into('<Q',pointerring,pointerpos*8,gpu_addr);pointerpos=(pointerpos+1)%16
 struct.pack_into('<I',pointerstate,0x40,pointerpos)
 assert bytes(m.mem_read(RSTATE,len(pointerstate)))==bytes(pointerstate) and bytes(m.mem_read(RING,len(pointerring)))==bytes(pointerring)
 counts['pointer_publications']+=len(published)
 for addr,obj in objects:assert bytes(m.mem_read(addr,len(obj)))==bytes(obj),(i,hex(addr))
 assert m.reg_read(c.UC_ARM64_REG_X22)==oldts
 counts['nop_records']+=extra
 # Explicitly simulated completion-counter release; no firmware completion claim.
 m.reg_write(c.UC_ARM64_REG_X19,D);m.emu_start(BASE+0x895e1ac,BASE+0x895e1f8,count=64)
 assert m.reg_read(c.UC_ARM64_REG_PC)==BASE+0x895e1f8
 struct.pack_into('<I',queue,0x44,0);struct.pack_into('<I',descriptor,0x144,0xffffffff)
 for addr,obj in objects:assert bytes(m.mem_read(addr,len(obj)))==bytes(obj)
 counts['release_roundtrips']+=1
 counts['qos_local' if local else 'qos_fallback']+=1;counts['qos_ratio']+=int(ratio)
 counts['cases']+=1;counts['fallback_aux' if fallback else 'descriptor_aux']+=1;counts['cached' if cached else 'uncached']+=1
# Invalid padding counts stop before any scheduler emission.
for j in range(64):
 invalid=[capacity,capacity+1,0xffffffff][j%3]
 delta=((invalid+1)<<8)&0xffffffff
 m.mem_write(0x20a000+0x2050+idx*4,struct.pack('<I',(event-delta)&0xffffffff))
 preserved=[(addr,bytes(m.mem_read(addr,len(obj)))) for addr,obj in objects]+[(BUFFER,bytes(m.mem_read(BUFFER,len(backing))))]
 calls.clear();published.clear()
 for reg,val in [(c.UC_ARM64_REG_X8,ACCEL),(c.UC_ARM64_REG_X19,CH),(c.UC_ARM64_REG_X20,D),(c.UC_ARM64_REG_X21,event),(c.UC_ARM64_REG_X22,idx),(c.UC_ARM64_REG_X23,0x201000),(c.UC_ARM64_REG_X25,payload[0]),(c.UC_ARM64_REG_X28,qid),(c.UC_ARM64_REG_X24,RCONFIG),(c.UC_ARM64_REG_W27,int(conditional)),(c.UC_ARM64_REG_X26,conditional_ptr),(c.UC_ARM64_REG_X29,STACK+0x1b0),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(BASE+0x895bfc8,END,count=256)
 assert m.reg_read(c.UC_ARM64_REG_PC)==DIAG and m.reg_read(c.UC_ARM64_REG_W26)==invalid and not calls
 for addr,data in preserved:assert bytes(m.mem_read(addr,len(data)))==data
 counts['guard_cases']+=1
a.output.write_text(json.dumps(dict(binary_sha256=sha,counts=counts,caller=dict(start=hex(START),end=hex(END),sha256=hashlib.sha256(read(START,END-START)).hexdigest()),qualification='Native config construction/publication followed continuously by NOP/3D scheduling and actual post-kick encoding and native pointer publications with actual return/count. Independent full ring/record/count models and explicitly simulated native pending release; owner lookup/registration, firmware mapping and zero service synthetic, optional trace disabled. No full submit, hardware acceptance or completion.'),indent=2)+'\n');print(counts)
