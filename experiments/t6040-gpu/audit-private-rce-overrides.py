#!/usr/bin/env python3
"""Whole native override and append functions against independent RAM models."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_rce_entry import encode_entry,decode_entry
from private_rce_overrides import apply_overrides,append_native
from private_spm_recipe import spm_entries,append_spm
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
raw=a.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size

def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError('address not file backed')
APPEND,OVERRIDE,DECODE,ENCODE=0xfffffe00089df538,0xfffffe00089df5a4,0xfffffe00089df6ec,0xfffffe00089df714
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.mem_map(APPEND&~4095,4096);m.mem_write(APPEND,read(APPEND,0x89df73c-0x89df538))
m.mem_map(0x200000,0x30000)
A,P,T,E,B,V=0x200000,0x201000,0x202000,0x204000,0x205000,0x218000
STACK,STOP=0x22e000,0x22f000
m.mem_write(V,struct.pack('<QQ',ENCODE,DECODE));m.mem_write(A+0x5b0,struct.pack('<Q',P));m.mem_write(P+0x380,struct.pack('<Q',T));m.mem_write(E,struct.pack('<QQ',V,B))
for slot,target in [(0,ENCODE),(8,DECODE)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007ead480+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];seen=set();encode_calls=0;decode_calls=0

def hook(m,address,size,user):
 global encode_calls,decode_calls
 seen.add(address)
 if address==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word==0xd503237f or word&0xfffffc00==0xdac11800:
  m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target in (ENCODE,DECODE)
  encode_calls+=target==ENCODE;decode_calls+=target==DECODE
  m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)
rng=random.Random(604009);totals={'override_cases':0,'append_cases':0,'spm_backing_override_cases':0,'matched_patches':0,'native_decodes':0};edge={'empty_table':0,'empty_entries':0,'unmatched_rows':0,'duplicate_rows':0,'count_wrap':0};examples=[]

def run(start,args):
 global encode_calls,decode_calls
 encode_calls=decode_calls=0
 for reg in regs:m.reg_write(reg,0)
 for i,value in enumerate(args):m.reg_write(regs[i],value)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(start,STOP,count=200000)
 assert m.reg_read(c.UC_ARM64_REG_PC)==STOP,'instruction budget exhausted'
 assert m.reg_read(c.UC_ARM64_REG_SP)==STACK

for i in range(1280):
 backing=bytearray(rng.randbytes(0x1000))
 if i<1024:
  count=i%49;struct.pack_into('<HH',backing,0x708,count,rng.randrange(0,65536))
  for j in range(count):
   reg=rng.randrange(0,24)*8+0x15000;backing[j*12:j*12+12]=encode_entry(backing[j*12:j*12+12],reg,rng.randrange(2),rng.getrandbits(64))
  mode='override_cases'
 else:
  phase=i%4;accel=rng.randbytes(0x1000);command=rng.randbytes(0x3000);desc=bytearray(rng.randbytes(0x1000));desc[0x897]&=~1
  struct.pack_into('<HH',backing,0x708,0,0)
  backing=bytearray(append_spm(backing,spm_entries(accel,command,desc,phase,(i//4)%2,rng.getrandbits(64))))
  count=struct.unpack_from('<H',backing,0x708)[0];mode='spm_backing_override_cases'
 table=bytearray(rng.randbytes(0x1000));rowcount=i%17;rows=[]
 for j in range(rowcount):
  if count and j%3!=0:reg=decode_entry(backing[(j%count)*12:(j%count)*12+12])[0]
  else:reg=rng.getrandbits(32) # full u32 table key, not normalized
  mask=[0,(1<<64)-1,rng.getrandbits(64)][j%3];value=rng.getrandbits(64)
  if j>0 and j%4==0:reg=rows[-1][2];edge['duplicate_rows']+=1
  rows.append((mask,value,reg));struct.pack_into('<QQI',table,0x800+j*24,mask,value,reg)
 struct.pack_into('<I',table,0x980,rowcount)
 expected,patches=apply_overrides(backing,rows)
 m.mem_write(B,bytes(backing));m.mem_write(T,bytes(table));run(OVERRIDE,[E,A])
 assert bytes(m.mem_read(B,len(backing)))==expected,(i,'backing')
 assert bytes(m.mem_read(T,len(table)))==bytes(table)
 assert bytes(m.mem_read(E,16))==struct.pack('<QQ',V,B)
 assert encode_calls==len(patches)
 assert decode_calls==count*rowcount
 totals[mode]+=1;totals['matched_patches']+=len(patches);totals['native_decodes']+=decode_calls
 edge['empty_table']+=rowcount==0;edge['empty_entries']+=count==0;edge['unmatched_rows']+=sum(not any(p[1]==reg for p in patches) for _,_,reg in rows)
 if i in (0,1,16,48,1024):examples.append(dict(case=i,mode=mode,entry_count=count,row_count=rowcount,patch_count=len(patches)))
for i in range(512):
 backing=bytearray(rng.randbytes(0x1000));count=65535 if i%4==0 else rng.randrange(65536);cursor=12*rng.randrange(0,64)
 struct.pack_into('<HH',backing,0x708,count,cursor);register=rng.getrandbits(32);flag=rng.randrange(256);value=rng.getrandbits(64)
 expected=append_native(backing,register,flag,value);m.mem_write(B,bytes(backing));run(APPEND,[E,register,flag,value])
 assert bytes(m.mem_read(B,len(backing)))==expected
 assert encode_calls==1 and decode_calls==0
 assert bytes(m.mem_read(E,16))==struct.pack('<QQ',V,B)
 totals['append_cases']+=1;edge['count_wrap']+=count==65535
report=dict(binary_sha256=sha,totals=totals,edges=edge,examples=examples,visited_instruction_count=len(seen),ranges=[dict(start=hex(x),end=hex(y),sha256=hashlib.sha256(read(x,y-x)).hexdigest()) for x,y in [(APPEND,OVERRIDE),(OVERRIDE,DECODE),(DECODE,ENCODE),(ENCODE,0xfffffe00089df73c)]],qualification='Whole append and override functions with actual native encode/getEntry calls in emulated RAM. PAC bypass for unsigned fixture pointers. Counts0..48, override rows0..16, safe nonoverlapping backing cursor for append. SPM-generated backing fixtures use previously checked Python SPM model. Table population/provenance, concurrent modification, large-count/truncated scan behavior and live GPU acceptance excluded.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(totals,'edges',edge)
