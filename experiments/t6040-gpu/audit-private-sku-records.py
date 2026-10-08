#!/usr/bin/env python3
"""Check native timestamp, startup-copy and conditional wait record encoders."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_sku_records import timestamp,startup,wait_record,TIMESTAMP_LAYOUTS
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
 raise ValueError('not file backed')
BASE=0xfffffe0000000000;TS=BASE+0x8a16cdc;INVALID=BASE+0x8a16e98
RANGES=[(TS,BASE+0x8a16ed0),(BASE+0x89d5610,BASE+0x89d5630),(BASE+0x89d59d4,BASE+0x89d59fc),(BASE+0x89d5a00,BASE+0x89d5a28)]
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
for addr,size in [(BASE+0x8a16000,4096),(BASE+0x89d5000,4096),(BASE+0x712d000,4096),(0x200000,0x20000)]:m.mem_map(addr,size)
for start,end in RANGES:m.mem_write(start,read(start,end-start))
m.mem_write(BASE+0x712d000,read(BASE+0x712d000,4096))
E,CMD,B,CH,D,STACK,STOP=0x200000,0x202000,0x206000,0x208000,0x209000,0x21e000,0x21f000
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];seen=set();trap=None;copies=[]
def hook(m,addr,size,user):
 global trap
 seen.add(addr)
 if addr==STOP:m.emu_stop();return
 if addr==INVALID:trap=addr;m.emu_stop();return
 if addr==BASE+0x89d562c:
  word=struct.unpack('<I',m.mem_read(addr,4))[0];imm=word&0x3ffffff
  if imm&(1<<25):imm-=1<<26
  assert addr+4*imm==BASE+0xb744bf0
  dest,src,n=[m.reg_read(regs[i]) for i in range(3)];assert n==0x1e8 and dest==B+4 and src==STACK+0x80
  copies.append((dest,src,n));m.mem_write(dest,bytes(m.mem_read(src,n)));m.reg_write(regs[0],dest);m.reg_write(c.UC_ARM64_REG_PC,addr+4)
m.hook_add(u.UC_HOOK_CODE,hook)
def run(start,end,initial):
 global trap
 trap=None;copies.clear()
 for reg in regs:m.reg_write(reg,0)
 for i,v in initial.items():m.reg_write(regs[i],v)
 m.reg_write(c.UC_ARM64_REG_SP,STACK);m.reg_write(c.UC_ARM64_REG_LR,STOP)
 m.emu_start(start,end,count=300)
 assert trap is not None or m.reg_read(c.UC_ARM64_REG_PC)==end
rng=random.Random(604014);counts={};examples=[]
for i in range(1024):
 opcode=i%4;command=bytearray(rng.randbytes(0x2300));struct.pack_into('<I',command,0,opcode)
 pair=TIMESTAMP_LAYOUTS[opcode][2];value=TIMESTAMP_LAYOUTS[opcode][4]
 pattern=(i//4)%4;pair_values=[0,0]
 if pattern&1:pair_values[0]=rng.getrandbits(64) or 1
 if pattern&2:pair_values[1]=rng.getrandbits(64) or 1
 struct.pack_into('<2Q',command,pair,*pair_values);struct.pack_into('<Q',command,value,0 if i%3==0 else rng.getrandbits(64) or 1)
 record=rng.randbytes(0x300);enc=rng.randbytes(0x100);enc=bytearray(enc);struct.pack_into('<Q',enc,0x68,B)
 index=rng.getrandbits(32);gpu=rng.getrandbits(64);state=rng.getrandbits(64);begin=[0,1,2,0xffffffff][(i//16)%4]
 m.mem_write(E,bytes(enc));m.mem_write(CMD,bytes(command));m.mem_write(B,record)
 run(TS,STOP,{0:E,1:index,2:CMD,3:gpu,4:state,5:begin})
 assert bytes(m.mem_read(B,len(record)))==timestamp(record,command,index,gpu,state,begin)
 struct.pack_into('<Q',enc,0x68,B+0x4c);assert bytes(m.mem_read(E,len(enc)))==bytes(enc);assert bytes(m.mem_read(CMD,len(command)))==bytes(command)
 counts['timestamp']=i+1
 if i<16:examples.append(dict(opcode=opcode,pair_presence=pattern,begin=begin))
 payload=rng.randbytes(0x1e8);m.mem_write(STACK+0x80,payload);m.mem_write(CH+0xa8,struct.pack('<Q',E));struct.pack_into('<Q',enc,0x68,B);m.mem_write(E,bytes(enc));m.mem_write(B,record)
 run(RANGES[1][0],RANGES[1][1],{20:CH,8:E})
 assert bytes(m.mem_read(B,len(record)))==startup(record,payload);struct.pack_into('<Q',enc,0x68,B+0x1ec);assert bytes(m.mem_read(E,len(enc)))==bytes(enc);assert len(copies)==1;assert bytes(m.mem_read(STACK+0x80,len(payload)))==payload
 counts['startup_copy']=i+1
 value32=rng.getrandbits(32);address=rng.getrandbits(64);m.mem_write(D+0x86c,struct.pack('<I',value32))
 for j,flag in [(2,True),(3,False)]:
  struct.pack_into('<Q',enc,0x68,B);m.mem_write(E,bytes(enc));m.mem_write(B,record)
  run(*RANGES[j],{20:CH,26:D,27:index,24:address})
  assert bytes(m.mem_read(B,len(record)))==wait_record(record,value32,index,address,flag);struct.pack_into('<Q',enc,0x68,B+0x14);assert bytes(m.mem_read(E,len(enc)))==bytes(enc)
  counts['wait_begin' if flag else 'wait_end']=i+1
for opcode in [4,5,7,15,0xffffffff,0x80000000]:
 command=bytearray(0x2300);struct.pack_into('<I',command,0,opcode);m.mem_write(CMD,bytes(command));record=rng.randbytes(0x100);m.mem_write(B,record);enc=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',enc,0x68,B);m.mem_write(E,bytes(enc))
 run(TS,STOP,{0:E,1:1,2:CMD,3:0,4:0,5:1});assert trap==INVALID
 expected=bytearray(record);struct.pack_into('<I',expected,0,0x80000003);assert bytes(m.mem_read(B,len(record)))==bytes(expected);struct.pack_into('<Q',enc,0x68,B+0x4c);assert bytes(m.mem_read(E,len(enc)))==bytes(enc)
counts['unsupported_timestamp_opcodes']=6
vectors={hex(off):[hex(v) for v in struct.unpack('<2Q',read(BASE+0x712d000+off,16))] for off in (0xf40,0xf50,0xf60,0xf70)}
report=dict(binary_sha256=sha,counts=counts,examples=examples,native_constant_vectors=vectors,timestamp_layouts=TIMESTAMP_LAYOUTS,ranges=[dict(start=hex(start),end=hex(end),sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in RANGES],visited_instruction_count=len(seen),qualification='Actual native timestamp and record-building slices in RAM; independent numeric outputs full-byte compared. Startup external memcpy explicitly implements only byte-copy contract. Unsupported timestamp command assertion intercepted, cursor/header already changed. Synthetic command/stack/GPU-address fields are not valid jobs. Record names follow symbol/caller behavior, not full opcode semantics. No live GPU or cache/mapping context tested.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
