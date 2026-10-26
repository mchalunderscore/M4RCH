#!/usr/bin/env python3
"""Offline differential descriptor-field -> register observations, not semantics."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
# Reuse the hash-qualified RAM harness, without running its random audit loop.
checker=Path(__file__).with_name('audit-private-3d-input-generator.py');code=checker.read_text().split('rng=random.Random(604010);fixtures=[]')[0]
oldargv=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)];ns={'__name__':'field_trace','__file__':str(checker)}
try:exec(compile(code,str(checker),'exec'),ns)
finally:sys.argv=oldargv
m=ns['m'];c=ns['c'];D=ns['D'];C=ns['C'];A=ns['A'];O=ns['O'];u=ns['u']
initial=bytearray(0x1000)
for offset,value in [(0x440,0x800000000),(0x190,O),(0x918,O),(0xb90,ns['R1'])]:struct.pack_into('<Q',initial,offset,value)
for offset,value in [(0x4a4,32),(0x4a8,32),(0x8c8,1)]:struct.pack_into('<I',initial,offset,value)
ns['mapped']=0x820000000

def run(desc):
 m.mem_write(D,bytes(desc));m.mem_write(C,bytes(0x3000));m.mem_write(A+0x6d0,bytes(8));m.mem_write(O,bytes(0x100));ns['entries'].clear();ns['calls'].clear();ns['pending']=None;ns['map_calls']=0
 for reg in ns['regs']:m.reg_write(reg,0)
 for reg,value in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(reg,value)
 m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP'];assert ns['pending'] is None
 cmd=bytes(m.mem_read(C,0x3000));result=[]
 for phase in range(4):
  count=struct.unpack_from('<H',cmd,0x7a8+phase*0x720)[0];assert count*12<=0x708
  counters={};entries={}
  for i in range(count):
   header,value=struct.unpack_from('<IQ',cmd,0xa0+phase*0x720+12*i);reg=header&0x3fff8;flag=header&1;occ=counters.get((reg,flag),0);counters[(reg,flag)]=occ+1;entries[(reg,flag,occ)]=value
  result.append(entries)
 return result
baseline=run(initial);observations=[]
for offset in range(0x4b0,0x900,4):
 desc=bytearray(initial);struct.pack_into('<I',desc,offset,0x31415926);current=run(desc);changes=[]
 for phase,(before,after) in enumerate(zip(baseline,current)):
  for key in before.keys()|after.keys():
   if before.get(key)!=after.get(key):changes.append({'phase':phase,'register':hex(key[0]),'flag':key[1],'occurrence':key[2],'before':None if key not in before else hex(before[key]),'after':None if key not in after else hex(after[key])})
 observations.append({'descriptor_u32_offset':hex(offset),'fixture_value':'0x31415926','changes':changes})
report={'private_binary_sha256':ns['sha'],'harness_sha256':hashlib.sha256(checker.read_bytes()).hexdigest(),'native_generator_range':[hex(ns['START']),hex(ns['END'])],'baseline_register_counts':[len(b) for b in baseline],'perturbations':len(observations),'observations':observations,'qualification':'Differential native generator observations in emulator RAM. Hash-pinned harness reused without client copy. One synthetic low32 perturbation per numeric descriptor word; differences may involve bitfields, conditional entries, truncation and combined fields. Register meaning is not inferred from numerical similarity. Resource mapping/PAC handling inherited synthetic harness; no allocation/valid rendering/job/firmware execution proved. Counts are backing totals, not phase0 exported prefix count.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(f'{len(observations)} native differential descriptor trials returned; {sum(bool(o["changes"]) for o in observations)} words affect observed register lists')
