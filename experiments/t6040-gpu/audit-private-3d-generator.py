#!/usr/bin/env python3
"""Trace assembled native 3D generator and qualify its helper/metadata integration."""
import struct,hashlib,json,argparse,random
from private_spm_recipe import spm_entries,append_spm
from private_rce_entry import rce_metadata
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
p=argparse.ArgumentParser();p.add_argument('macho',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
raw=args.macho.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size

def read(addr,size):
 for vm,_,off,length in segments:
  if vm<=addr and addr+size<=vm+length:return raw[off+addr-vm:off+addr-vm+size]
 raise ValueError(hex(addr))
START=0xfffffe00089df73c;END=0xfffffe00089e2948;ENC=0xfffffe00089df714;DEC=0xfffffe00089df6ec
m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM);m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX);m.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
m.mem_map(0xfffffe00089df000,0x4000);m.mem_write(0xfffffe00089df538,read(0xfffffe00089df538,END-0xfffffe00089df538))
m.mem_map(0xfffffe00089e7000,4096);m.mem_write(0xfffffe00089e7fd8,read(0xfffffe00089e7fd8,24))
m.mem_map(0xfffffe0007ead000,4096);m.mem_write(0xfffffe0007ead480,struct.pack('<QQ',ENC,DEC))
m.mem_map(0xfffffe000712d000,4096);m.mem_write(0xfffffe000712d000,read(0xfffffe000712d000,4096))
m.mem_map(0x200000,0x50000);A,C,D,P,T,AV,O=0x200000,0x222000,0x226000,0x228000,0x229000,0x22a000,0x22c000
STACK,STOP=0x24e000,0x24f000
m.mem_write(A,struct.pack('<Q',AV));m.mem_write(A+0x5b0,struct.pack('<Q',P));m.mem_write(P+0x380,struct.pack('<Q',T));m.mem_write(AV+0x10e8,struct.pack('<Q',0xfffffe00089e7fe4));m.mem_write(AV+0x10f0,struct.pack('<Q',0xfffffe00089e7fd8))
R1,R2,R3,RV=0x22d000,0x22e000,0x22f000,0x230000
m.mem_write(D+0xb90,struct.pack('<Q',R1));m.mem_write(R1+0x30,struct.pack('<Q',R2));m.mem_write(R2+0x58,struct.pack('<Q',R3));m.mem_write(R3,struct.pack('<Q',RV));m.mem_write(RV+0x158,struct.pack('<Q',0x231000))
m.mem_write(A+0xf598,struct.pack('<Q',O))
mapped=0;pending=None;helper_checks=0;map_calls=0;seen=set()
regs=[getattr(c,'UC_ARM64_REG_X'+str(i)) for i in range(31)];calls=[];entries=[]

def hook(m,address,size,user):
 global pending,helper_checks,map_calls
 seen.add(address)
 if address==0xfffffe00089e1df4:
  phase=m.reg_read(c.UC_ARM64_REG_W4);enabled=m.reg_read(c.UC_ARM64_REG_W5)
  backing=C+phase*0x720+0xa0
  predicted=spm_entries(bytes(m.mem_read(A,0x1000)),bytes(m.mem_read(C,0x3000)),bytes(m.mem_read(D,0x1000)),phase,enabled,mapped)
  pending=(backing,append_spm(bytes(m.mem_read(backing,0x70c)),predicted))
 if address==0xfffffe00089df7e4 and pending is not None:
  backing,predicted=pending;assert bytes(m.mem_read(backing,len(predicted)))==predicted
  helper_checks+=1;pending=None
 if address==STOP:m.emu_stop();return
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word==0xd65f0fff:m.reg_write(c.UC_ARM64_REG_PC,m.reg_read(c.UC_ARM64_REG_LR));return
 if word==0xd503237f or word&0xfffffc00 in (0xdac11800,0xdac10800) or word&0xffffffe0==0xdac147e0:
  m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);calls.append((hex(address),hex(target)))
  if target==0x231000:
   assert m.reg_read(c.UC_ARM64_REG_X0)==R3
   map_calls+=1
   m.reg_write(c.UC_ARM64_REG_X0,mapped);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
  assert target in (ENC,DEC,0xfffffe00089e7fe4,0xfffffe00089e7fd8),(hex(address),hex(target))
  if target==ENC:entries.append((m.reg_read(c.UC_ARM64_REG_X1)-C, m.reg_read(c.UC_ARM64_REG_W2),m.reg_read(c.UC_ARM64_REG_W3),m.reg_read(c.UC_ARM64_REG_X4)))
  m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,target)
m.hook_add(u.UC_HOOK_CODE,hook)
for slot,target in [(0,ENC),(8,DEC)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007ead480+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target
for slot,target in [(0x10e8,0xfffffe00089e7fe4),(0x10f0,0xfffffe00089e7fd8)]:
 encoded=struct.unpack('<Q',read(0xfffffe0007eae388+16+slot,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==target

rng=random.Random(604010);fixtures=[]
for i in range(128):
 descriptor=bytearray(0x1000);command=rng.randbytes(0x3000)
 for off in range(0x600,0x800,8):struct.pack_into('<Q',descriptor,off,rng.getrandbits(64) if rng.randrange(2) else 0)
 for off in (0x4a4,0x4a8):struct.pack_into('<I',descriptor,off,32 if rng.randrange(2) else 16)
 struct.pack_into('<I',descriptor,0x8c8,[1,2,4][i%3])
 struct.pack_into('<Q',descriptor,0x440,0x800000000+i*0x10000)
 struct.pack_into('<Q',descriptor,0xb80,0 if i%2==0 else 0x810000000+i*0x1000)
 struct.pack_into('<I',descriptor,0xb88,i%8);struct.pack_into('<I',descriptor,0xb98,i*64)
 descriptor[0x897]=(i//2)%2;descriptor[0x88e]=(i//4)%2;descriptor[0x88f]=(i//8)%2
 for off,ptr in [(0x190,O),(0x918,O),(0xb90,R1)]:struct.pack_into('<Q',descriptor,off,ptr)
 m.mem_write(D,bytes(descriptor));m.mem_write(C,command);m.mem_write(A+0x6d0,struct.pack('<Q',rng.getrandbits(64)))
 m.mem_write(O,bytes(0x100));m.mem_write(O+0x54,bytes([(i//16)%2]));m.mem_write(O+8,struct.pack('<I',i%64));m.mem_write(O+0x28,struct.pack('<Q',rng.getrandbits(64)))
 mapped=0x820000000+i*0x10000;entries.clear();calls.clear();pending=None;map_calls=0
 for reg in regs:m.reg_write(reg,0)
 for reg,value in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,value)
 m.emu_start(START,STOP,count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP
 assert m.reg_read(c.UC_ARM64_REG_SP)==STACK;assert pending is None
 final_command=bytes(m.mem_read(C,0x3000));final_descriptor=bytes(m.mem_read(D,0x1000))
 assert final_descriptor==rce_metadata(descriptor,final_command,0x400000000)
 phasecounts=[struct.unpack_from('<H',final_command,0x7a8+j*0x720)[0] for j in range(4)]
 desccounts=[struct.unpack_from('<H',final_descriptor,0x830+j*16)[0] for j in range(4)]
 assert phasecounts[1:]==desccounts[1:]
 for j in range(4):
  assert struct.unpack_from('<H',final_command,0x7aa+j*0x720)[0]==12*phasecounts[j]
  assert struct.unpack_from('<Q',final_descriptor,0x828+j*16)[0]==0x800000000+i*0x10000+j*0x720+0xa0
 fixtures.append(dict(case=i,phase_counts=phasecounts,descriptor_counts=desccounts,map_calls=map_calls,native_encode_calls=len(entries),command_sha256=hashlib.sha256(final_command).hexdigest(),phase0_tail_count=phasecounts[0]-desccounts[0]))
assert helper_checks==384
report=dict(binary_sha256=sha,assembled_cases=128,independent_spm_helper_checks=helper_checks,visited_instruction_count=len(seen),fixtures=fixtures,native_range=[hex(START),hex(END)],native_range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),duplication_getters=[dict(slot='0x10e8',target='0xfffffe00089e7fe4',constant=1),dict(slot='0x10f0',target='0xfffffe00089e7fd8',constant=2)],qualification='Assembled native parent generator, SPM, empty override, append, encode and G16X min/max getters execute in RAM. PAC bypassed; one resource map service stub returns synthetic mapped address. Helper and descriptor metadata independently compared, phase0 complete register recipe only observed, not independently modeled. Synthetic descriptor fields are not validated rendering inputs. No live firmware/GPU acceptance, allocation/cache policy or shader/target preparation proved.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print('128 assembled generators returned; 384 helper outputs and 128 descriptor metadata patches matched')
