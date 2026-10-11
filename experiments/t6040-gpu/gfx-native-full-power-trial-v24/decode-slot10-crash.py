#!/usr/bin/env python3
"""Bounded saved crash decoder and exact firmware callback ordinary-RAM replay."""
import argparse,hashlib,json,struct,subprocess,re
from pathlib import Path
from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ_UNMAPPED
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X8
BASE=0xfffffc0000000000

def sha(b):return hashlib.sha256(b).hexdigest()
def pin(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();w=a.capture.resolve();src=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 before=(w/'data-before.bin').read_bytes();d=(w/'data-retained.bin').read_bytes();t=(w/'text.bin').read_bytes();b=d[0xa0000:0xa8000];magic,ver,size,flags=struct.unpack_from('<4I',b);assert magic==0x434c4845 and 32<=size<=len(b)
 sections=[];off=32;regs=None;stack=[]
 while off<size:
  tag=b[off:off+4]
  if tag==b'EHLC':assert off+32==size and b[off:off+32]==b[:32];sections.append(dict(fourcc='CLHE',offset=hex(off),bytes=32));off+=32;break
  n=struct.unpack_from('<I',b,off+12)[0];assert n>=16 and off+n<=size;payload=b[off+16:off+n];item=dict(fourcc=tag[::-1].decode('ascii'),offset=hex(off),bytes=n,payload_sha256=sha(payload))
  if tag==b'8grC':
   assert len(payload)>=0x350;regs={f'x{i}':hex(struct.unpack_from('<Q',payload,8+i*8)[0]) for i in range(31)}
   for name,pos in [('sp',0x100),('pc',0x108),('psr',0x110),('far',0x330),('esr',0x340)]:regs[name]=hex(struct.unpack_from('<Q',payload,pos)[0])
   item['registers']=regs
  if tag==b'tscC':stack=[hex(struct.unpack_from('<Q',payload,i)[0]) for i in range(8,len(payload)-7,8) if struct.unpack_from('<Q',payload,i)[0]];item['stack']=stack
  if tag==b'revC':item['text']=payload[24:].split(b'\0')[0].decode('utf8') if ver==0x303 else payload[16:].split(b'\0')[0].decode('utf8')
  sections.append(item);off+=n
 assert off==size and regs and regs['pc']=='0xfffffc0000025698' and regs['far']=='0x2b40' and regs['x8']=='0x0'
 cached=struct.unpack_from('<Q',d,0x18f5b8-0x60000)[0];assert cached==0
 assert struct.unpack_from('<Q',d,0x146da8-0x60000)[0]&0xffffffff==0x25690
 code=t[0x25690:0x256c8];replays=[]
 for mapped in [False,True]:
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(BASE+0x25000,0x1000);u.mem_write(BASE+0x25690,code);u.mem_map(BASE+0x18f000,0x1000);u.mem_map(0x100000,0x1000);va=0xfffffc2001b00000 if mapped else 0;u.mem_write(BASE+0x18f5b8,struct.pack('<Q',va));expected=bytes(range(16))
  if mapped:u.mem_map(va,0x4000);u.mem_write(va+0x2b40,expected)
  u.reg_write(UC_ARM64_REG_X0,0);u.reg_write(UC_ARM64_REG_X1,0x2b40);u.reg_write(UC_ARM64_REG_X2,0x100000);fault=[]
  def invalid(uc,access,address,size,value,user):fault.append(dict(address=hex(address),bytes=size));return False
  u.hook_add(UC_HOOK_MEM_READ_UNMAPPED,invalid)
  error=None
  try:u.emu_start(BASE+0x25690,BASE+0x256c4,count=32)
  except UcError as e:error=str(e)
  actual=bytes(u.mem_read(0x100000,16));assert (mapped and actual==expected and not error) or (not mapped and fault==[dict(address='0x2b40',bytes=4)])
  replays.append(dict(mapped=mapped,unmapped_reads=fault,error=error,result_matches_four_u32=mapped and actual==expected))
 r=json.loads((src/'graph-receipt.json').read_text());hw=next(x for x in r['objects'] if x['name']=='hardware')['arena_offset'];graph=(src/'graph-before.bin').read_bytes();descriptor=graph[hw+0x7d0:hw+0x7d0+0x24];assert struct.unpack('<QQIIQI',descriptor)==(0x5003c0000,0xfffffc2001b00000,0x4000,0x4000,0,0)
 # Link exact v9 C/Rust ABI object against patched hardware bytes; no GPU.
 obj=src.parent/'prepared-owner-v9/native-power-rust.o';shims=src.parent/'prepared-owner-v9/rust-panic-shims.S';raw=out/'hardware-input.bin';raw.write_bytes(graph[hw:hw+0x2718]);dest=out/'hardware-after-writer.bin'
 c=out/'preserve.c';c.write_text('''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
extern int m4rch_native_power_write(const uint32_t*,const uint32_t*,uint64_t,uint8_t*,uint8_t*,uint8_t*,uint8_t*,uint64_t,uint64_t,uint64_t);
void m4rch_full_power_panic(void){abort();}
int main(int argc,char**argv){assert(argc==3);uint8_t h[0x2718],p[0x6578]={0},r[0xe58]={0},a[0xe4]={0},keep[36],keep14[36];FILE*f=fopen(argv[1],"rb");assert(f&&fread(h,1,sizeof(h),f)==sizeof(h));fclose(f);memcpy(keep,h+0x7d0,36);memcpy(keep14,h+0x870,36);uint32_t pm[8]={0x10000,0x30002,0x60004,0xa0008,0xe000c,0xf,0,0},sm[8]={0x10000,0x30002,0x60004,0x90007,0xd000b,0xf,0,0};assert(m4rch_native_power_write(pm,sm,5564000000ULL,p,h,r,a,0xfffffc200014f000ULL,0xfffffc200012c000ULL,0xfffffc200014f100ULL)==0);assert(!memcmp(keep,h+0x7d0,36));assert(!memcmp(keep14,h+0x870,36));f=fopen(argv[2],"wb");assert(f&&fwrite(h,1,sizeof(h),f)==sizeof(h));fclose(f);return 0;}
''')
 cr=subprocess.run(['clang','-O2','-Wall','-Wextra','-Werror',str(c),str(obj),str(shims),'-o',str(out/'preserve')],capture_output=True,text=True);(out/'compile.log').write_text(cr.stdout+cr.stderr);assert cr.returncode==0,cr.stderr
 run=subprocess.run([str(out/'preserve'),str(raw),str(dest)],capture_output=True,text=True);(out/'run.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
 assert dest.read_bytes()[0x7d0:0x7f4]==descriptor
 report=dict(schema='m4rch.v24-slot10-saved-crash-and-replay.v1',boot_id=json.loads((w/'attempt.json').read_text())['boot_id'],hardware_actions=[],input_pins=[pin(w/n) for n in ['data-before.bin','data-retained.bin','text.bin','objects-after.bin','retained-ram-capture.json']]+[pin(src/'graph-before.bin'),pin(obj),pin(shims),pin(Path(__file__))],crash=dict(version=ver,bytes=size,flags=hex(flags),footer_valid=True,newly_written=before[0xa0000:0xa0000+size]!=b[:size],sections=sections),endpoint=dict(endpoint=1,type=1,event_bytes=4096,original_offer_bytes=32768,meaning='Crash notification after prior buffer negotiation; saved buffer has architectural fault'),fault=dict(pc=regs['pc'],far=regs['far'],esr=regs['esr'],read=True,translation_fault_level=0,base_register_x8=regs['x8'],selector_x1=regs['x1'],cached_virtual=hex(cached),slot=10,descriptor_gpu_va='0xfffffc20001087d0'),callback=dict(begin='0x25690',end='0x256c8',sha256=sha(code),reads=[hex(0x2b40+i*4) for i in range(4)],replays=replays),patched_writer=dict(compile_returncode=cr.returncode,run_returncode=run.returncode,descriptor_preserved=True,slot14_descriptor_preserved=True,object_sha256=sha(obj.read_bytes())),limits=['Saved RAM non-atomic; IOP cache freshness unproved.','Ordinary-RAM callback replay verifies address arithmetic, not hardware bank values/side effects.','Read-only leaf and descriptor flags are explicit Linux mapping policy.','No rendering, successful initialization, physical OFF or restart demonstrated.'])
 (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(pc=regs['pc'],far=regs['far'],slot10_null_fault_reproduced=True,slot10_mapped_read_replayed=True,descriptor_survives_actual_writer=True)))
if __name__=='__main__':main()
