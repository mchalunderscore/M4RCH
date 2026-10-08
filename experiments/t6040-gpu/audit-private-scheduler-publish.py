#!/usr/bin/env python3
"""Native scheduler accounting and direct MMIO kick arithmetic, RAM emulation only."""
import argparse,hashlib,json,random,struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_scheduler_publish import publish_nop,direct_kick
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
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.mem_map(0x100000,4096);m.mem_map(0x200000,0x200000)
rng=random.Random(604002)
start,end=0xfffffe00089dc1d4,0xfffffe00089dc1f4
code=read(start,end-start);m.mem_write(0x100000,read(start,0xfffffe00089dc228-start))
# Stop at diagnostic branch before stack writes or external diagnostic call.
stops=[]
def stop_full(uc,address,size,user):
 if address==0x100000+0x50:stops.append(address);uc.emu_stop()
m.hook_add(u.UC_HOOK_CODE,stop_full)
normal=full=0
for i in range(1024):
 queue=bytearray(rng.randbytes(0x100));capacity=[1,2,3,16,256][i%5]
 old=[0,max(capacity-1,0),capacity,capacity+1,0xffffffff][(i//5)%5];timestamp=rng.getrandbits(64)
 struct.pack_into('<I',queue,0x10,capacity);struct.pack_into('<I',queue,0x44,old)
 m.mem_write(0x201000,bytes(queue));m.reg_write(c.UC_ARM64_REG_X19,0x201000);m.reg_write(c.UC_ARM64_REG_X0,timestamp)
 stops.clear();m.emu_start(0x100000,0x100000+len(code),count=50)
 expected,overflow=publish_nop(queue,timestamp)
 assert bytes(m.mem_read(0x201000,0x100))==expected;assert bool(stops)==overflow
 assert m.reg_read(c.UC_ARM64_REG_X0)==timestamp
 full+=overflow;normal+=not overflow
start2,end2=0xfffffe00089dc2b8,0xfffffe00089dc300
code2=read(start2,end2-start2);m.mem_write(0x100000,code2);m.ctl_remove_cache(0x100000,0x101000)
writes=[]
def record_write(uc,access,address,size,value,user):
 if 0x310000<=address<0x320000:writes.append((address-0x310000,size,value & ((1 << (size*8))-1)))
m.hook_add(u.UC_HOOK_MEM_WRITE,record_write)
for i in range(1024):
 qid=rng.getrandbits(32);count=rng.getrandbits(32);offset0=0x100;offset1=0x108;stride=rng.randrange(512)
 m.mem_write(0x20100c,struct.pack('<I',qid));m.mem_write(0x220358,struct.pack('<Q',0x310000));m.mem_write(0x2206d3,b'\0')
 m.mem_write(0x22ee28,struct.pack('<3I',offset0,offset1,stride))
 m.reg_write(c.UC_ARM64_REG_X20,0x201000);m.reg_write(c.UC_ARM64_REG_X21,0x220000);m.reg_write(c.UC_ARM64_REG_W19,count)
 writes.clear();m.emu_start(0x100000,0x100000+len(code2),count=100)
 assert writes==[(off,8,value) for off,value in direct_kick(qid,count,offset0,offset1,stride)], (writes,direct_kick(qid,count,offset0,offset1,stride))
report=dict(binary_sha256=sha,publication_cases=1024,normal_path_cases=normal,capacity_equal_diagnostic_cases=full,direct_kick_cases=1024,
 instruction_ranges=[[hex(start),hex(end)],[hex(start2),hex(end2)]],slice_hashes=[hashlib.sha256(code).hexdigest(),hashlib.sha256(code2).hexdigest()],
 findings=['LDADDAL increments queue +0x44 and compares OLD count to capacity; equality takes diagnostic branch after increment',
 'Normal path sets queue +0x98 byte to1 and caches ORIGINAL timestamp at +0xa0',
 'Direct kick stores two u64 words through accelerator +0x358; offsets are eE28+9*eE30 and eE2c+9*eE30',
 'Control word is 0x0020040000021018 OR queueID shifted43; second u64 store zero-extends kick count'],
 qualification='Actual LSE instruction executed with Unicorn MAX CPU, single-thread emulated RAM. Does not prove concurrent ordering or live MMIO semantics. Capacity+1 and all-ones count inputs characterize equality/overflow, not valid queue states. Stops before external diagnostic call and excludes bit3-set service-assisted path. No hardware touched.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 accounting cases and 1024 direct kick write traces matched')
