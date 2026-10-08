#!/usr/bin/env python3
"""Check continuous native ordinary3D construction through real counter callbacks."""
import argparse,hashlib,json,random,struct,sys
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_3d_command import header,body,tail,bindings
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
source=Path(__file__).with_name('audit-private-3d-command.py')
ns={'__file__':str(source),'__name__':'continuous_3d_setup'};previous=sys.argv
try:
 sys.argv=[str(source),str(a.macho),str(a.output)]
 exec(compile(source.read_text().split('rng=random.Random(604012);counts={}')[0],str(source),'exec'),ns)
finally:sys.argv=previous
m,read,BASE,regs=[ns[name] for name in ('m','read','BASE','regs')]
D,C,S,CH,O,STACK,FRAME=[ns[name] for name in ('D','C','S','CH','O','STACK','FRAME')]
START,END=BASE+0x895b388,BASE+0x895b9d8
KICK_METHOD,PM_METHOD,PAYLOAD=BASE+0x8987000,BASE+0x895d5c0,BASE+0x89d5cf0
for page in (BASE+0x8987000,BASE+0x895d000,BASE+0x89d5000):m.mem_map(page,4096)
for start,end in [(START,END),(KICK_METHOD,KICK_METHOD+0x18),(PM_METHOD,PM_METHOD+0x18),(PAYLOAD,PAYLOAD+12)]:m.mem_write(start,read(start,end-start))
ACC,FW,DVT,FVT,CVT=0x20c000,0x20d000,0x20e000,0x20f000,0x210000
KICK,PM,N,NVT,RES,PROV,MAP,MVT=0x211000,0x212000,0x213000,0x214000,0x215000,0x216000,0x217000,0x218000
NOTIFY_CB,MAP_CB,TRANSLATE_CB=0x219000,0x219004,0x219008
for table,slot,target in [(BASE+0x7eb7898,0x1a8,KICK_METHOD),(BASE+0x7eb7898,0x1f0,PM_METHOD),(BASE+0x7eaa8e0,0x220,PAYLOAD)]:
 enc=struct.unpack('<Q',read(table+16+slot,8))[0];assert BASE+0x7004000+(enc&0xffffffff)==target
for address,value in [(DVT+0x1a8,KICK_METHOD),(DVT+0x1f0,PM_METHOD),(CVT+0x220,PAYLOAD),
 (FVT+0x2d8,TRANSLATE_CB),(NVT+0x150,NOTIFY_CB),(MVT+0x158,MAP_CB),
 (FW,FVT),(N,NVT),(MAP,MVT),(RES+0x30,PROV),(PROV+0x50,MAP)]:m.mem_write(address,struct.pack('<Q',value))
calls=[];translation_index=0;descriptor=b'';translations=[];mapping=notification=0

def hook(m,addr,size,user):
 global translation_index
 if addr==END:m.emu_stop();return
 if addr in (KICK_METHOD,PM_METHOD,PAYLOAD):calls.append({KICK_METHOD:'kick',PM_METHOD:'pm',PAYLOAD:'payload'}[addr])
 if addr==NOTIFY_CB:
  assert [m.reg_read(regs[j]) for j in range(3)]==[N,D+0xb50,struct.unpack_from('<I',descriptor,0x144)[0]]
  m.mem_write(D+0xb50,struct.pack('<Q',notification));calls.append('notification')
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if addr==MAP_CB:
  assert m.reg_read(regs[0])==MAP;calls.append('mapping');m.reg_write(regs[0],mapping)
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if addr==TRANSLATE_CB:
  source=(0x908,0x910,0x938)[translation_index]
  assert [m.reg_read(regs[j]) for j in range(3)]==[FW,struct.unpack_from('<Q',descriptor,source)[0],0]
  calls.append('translation');m.reg_write(regs[0],translations[translation_index]);translation_index+=1
  m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 word=struct.unpack('<I',m.mem_read(addr,4))[0]
 if word&0xfffffc00==0xdac11800 or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,addr+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target in (KICK_METHOD,PM_METHOD,PAYLOAD,NOTIFY_CB,MAP_CB,TRANSLATE_CB),hex(target)
  m.reg_write(c.UC_ARM64_REG_LR,addr+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook);rng=random.Random(604021);counts=dict(cases=0,notification_present=0,notification_absent=0)
for i in range(1024):
 command=rng.randbytes(0x2300);desc=bytearray(rng.randbytes(0x1800));source=rng.randbytes(0x400);stack=bytearray(rng.randbytes(0x100));frame=rng.randbytes(24)
 channel=bytearray(rng.randbytes(0x300));owner=bytearray(rng.randbytes(0x700));kick=bytearray(rng.randbytes(0x100));pm=bytearray(rng.randbytes(0x100))
 serial=[0,1,(1<<64)-1,rng.getrandbits(64)][i%4];counter=[0,255,0xffffffff,rng.getrandbits(32)][i%4]
 kick_count=[0,0xffffffff,rng.getrandbits(32)][i%3];pm_count=[0xffffffff,0,rng.getrandbits(32)][i%3]
 for offset,value in [(0,DVT),(0x438,C),(0x198,KICK),(0x940,PM),(0xb58,N),(0xb90,RES),(0xb70,rng.getrandbits(64) if i&1 else 0)]:struct.pack_into('<Q',desc,offset,value)
 struct.pack_into('<Q',stack,0x60,S);struct.pack_into('<Q',channel,0,CVT);struct.pack_into('<Q',channel,0x10,ACC);struct.pack_into('<I',channel,0x204,counter)
 struct.pack_into('<Q',owner,0x5e8,serial);struct.pack_into('<I',kick,0,kick_count);struct.pack_into('<I',pm,0,pm_count)
 m.mem_write(ACC+0x5b0,struct.pack('<Q',FW));descriptor=bytes(desc)
 for address,data in [(D,descriptor),(C,command),(S,source),(CH,channel),(O,owner),(KICK,kick),(PM,pm),(STACK,stack),(FRAME-0xb8,frame)]:m.mem_write(address,bytes(data))
 translations=[rng.getrandbits(64) for _ in range(3)];mapping=[0,(1<<64)-1,rng.getrandbits(64)][i%3];notification=rng.getrandbits(64)
 w21,w22=rng.getrandbits(32),rng.getrandbits(32);calls.clear();ns['calls'].clear();translation_index=0
 for reg in regs:m.reg_write(reg,0)
 for index,value in {19:CH,20:D,21:w21,22:w22,29:FRAME}.items():m.reg_write(regs[index],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.emu_start(START,END,count=10000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 expected=header(command,descriptor,serial,frame)
 expected=bindings(expected,descriptor,translations,mapping)
 expected=body(expected,descriptor,source)
 expected=tail(expected,descriptor,stack,w21,w22,(counter+1)&255)
 assert bytes(m.mem_read(C,len(command)))==expected,(i,'command')
 if i&1:struct.pack_into('<Q',desc,0xb50,notification)
 struct.pack_into('<Q',owner,0x5e8,(serial+1)&((1<<64)-1));struct.pack_into('<I',channel,0x204,(counter+1)&0xffffffff)
 struct.pack_into('<I',kick,0,(kick_count+1)&0xffffffff);struct.pack_into('<I',pm,0,(pm_count+1)&0xffffffff)
 for address,data in [(D,desc),(S,source),(CH,channel),(O,owner),(KICK,kick),(PM,pm),(STACK,stack)]:assert bytes(m.mem_read(address,len(data)))==bytes(data),(i,hex(address))
 assert calls==['kick']+(['notification','mapping'] if i&1 else [])+['translation']*3+['pm','payload']
 assert len(ns['calls'])==1 and translation_index==3
 counts['cases']+=1;counts['notification_present' if i&1 else 'notification_absent']+=1
report=dict(binary_sha256=ns['sha'],counts=counts,ranges=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in [(START,END),(KICK_METHOD,KICK_METHOD+0x18),(PM_METHOD,PM_METHOD+0x18),(PAYLOAD,PAYLOAD+12)]],qualification='Continuous ordinary3D preproducer construction executes actual submitted-kick, PM-operation and scratch-payload callbacks. Full2300 command/source/channel/owner/counters compared with independent models. Three translations and conditional notification/mapping services are explicit fixtures; authentication skipped. Caller preamble, register producer/postproducer, real mappings/cache/queue/completion and valid drawing remain unqualified. No live GPU command.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
