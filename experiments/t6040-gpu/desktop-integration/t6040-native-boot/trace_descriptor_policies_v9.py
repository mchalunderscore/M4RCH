#!/usr/bin/env python3
"""New targeted lifecycle/policy dependency trace; offline native RAM only."""
import sys,json,struct,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
spec=importlib.util.spec_from_file_location('p',ROOT/'experiments/t6040-gpu/prepare-native-sksm-registers.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
OUT=ROOT/'out/gpu-gravity-native-descriptor-policy-v9';OUT.mkdir(exist_ok=False)
rows=[]
for kind in ['ta','3d']:
 ns=p.harness(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'),OUT/'setup.json',kind)
 descriptor=bytearray(0x1800);struct.pack_into('<II',descriptor,0x4a4,32,32);struct.pack_into('<I',descriptor,0x8c8,1)
 def run(d,context=bytes(0x100),scene=bytes(0x100)):
  result=p.produce(ns,kind,d,0xfffffc2000200000,0xfffffc2000300000,context,scene,False)[0]
  # produce returns tuple containing command? inspect output shape separately
  return result
 # Use direct generator to avoid preparation envelope assertions.
 def regs(d,context=bytes(0x100),scene=bytes(0x100)):
  m,c=ns['m'],ns['c'];A,C,D=(ns[k] for k in ('A','C','D'))
  d=bytearray(d)
  for o,v in [(0x190,ns['O']),(0xb90,ns['R1']),(0x918,0x238000),(0x1230,0x238000),(0x1428,ns['R1']),(0xfa0,0xfffffc2000200000),(0x440,0xfffffc2000200000)]:struct.pack_into('<Q',d,o,v)
  m.mem_write(D,bytes(d));m.mem_write(C,bytes(0x3000));m.mem_write(ns['O'],context);m.mem_write(0x238000,scene);m.mem_write(A+0x6d0,bytes(8));ns['mapped']=0xfffffc2000300000;ns['pending']=None;ns['entries'].clear();ns['calls'].clear()
  for r in ns['regs']:m.reg_write(r,0)
  for r,v in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(r,v)
  m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP']
  cmd=bytes(m.mem_read(C,0x3000));result={}
  for phase in range(1 if kind=='ta' else 4):
   off=0x60 if kind=='ta' else 0xa0+phase*0x720;meta=0x768 if kind=='ta' else 0x7a8+phase*0x720
   n=struct.unpack_from('<H',cmd,meta)[0];seen={}
   for i in range(n):
    h,v=struct.unpack_from('<IQ',cmd,off+i*12);k=(phase,h&0x3fff8,h&1);occ=seen.get(k,0);seen[k]=occ+1;result[k+(occ,)]=v
  return result
 baseline=regs(descriptor)
 targets=[('descriptor',o,4,0x13579bdf) for o in list(range(0x7e0,0x828,4))+list(range(0x86c,0x980,4))+list(range(0x1100,0x1148,4))+list(range(0x1218,0x1288,4))+list(range(0x13c0,0x155c,4)) if o not in [0x918,0x91c,0x1230,0x1234,0x1428,0x142c]]
 targets += [(domain,o,4,0x13579bdf) for domain in ['context','scene'] for o in range(0,0x100,4)]
 for domain,o,n,v in targets:
  d=bytearray(descriptor);context=bytearray(0x100);scene=bytearray(0x100);target={'descriptor':d,'context':context,'scene':scene}[domain];target[o:o+n]=v.to_bytes(n,'little')
  try:current=regs(d,bytes(context),bytes(scene))
  except Exception as e:rows.append({'kind':kind,'domain':domain,'offset':hex(o),'refusal':str(e)});continue
  changes=[{'phase':k[0],'register':hex(k[1]),'flag':k[2],'occurrence':k[3],'before':hex(baseline[k]) if k in baseline else None,'after':hex(current[k]) if k in current else None} for k in baseline.keys()|current.keys() if baseline.get(k)!=current.get(k)]
  if changes:rows.append({'kind':kind,'domain':domain,'offset':hex(o),'changes':changes})
(OUT/'dependency-trace.json').write_text(json.dumps({'scope':'Numeric source dependence; policy semantics not inferred solely from register identity','hardware_actions':[],'rows':rows},indent=2)+'\n')
for row in rows:
 selected=[c for c in row.get('changes',[]) if c['register'] in ['0x1c830','0x1ca30','0x16c38','0x1c910','0xa5a0','0x1ca10','0x14a0','0xa348','0x10208','0x1c9f0','0x14320','0x14308','0x14318','0x1c838','0x1ca28','0xa5a8','0x160e0','0x1498','0xa340','0x10210','0x10420','0x14048','0x14080','0x10120','0x10038','0x10050']]
 if selected or row['domain']!='descriptor':print(row['kind'],row['domain'],row['offset'],selected or row.get('changes') or row.get('refusal'))
