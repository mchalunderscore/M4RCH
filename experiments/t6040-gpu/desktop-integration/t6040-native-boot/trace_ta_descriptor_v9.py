import sys,json,struct,importlib.util
from pathlib import Path
root=Path('/home/alice/Desktop/m4rch');sys.path.insert(0,str(root/'experiments/t6040-gpu'))
spec=importlib.util.spec_from_file_location('p',root/'experiments/t6040-gpu/prepare-native-sksm-registers.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
out=root/'out/gpu-gravity-native-descriptor-map-v9';out.mkdir(exist_ok=False)
ns=p.harness(Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'),out/'setup.json','ta');m,c=ns['m'],ns['c']; A,C,D=(ns[k] for k in ('A','C','D'))
initial=bytearray(0x1800)
for o,v in [(0x190,ns['O']),(0xfa0,0x830000000),(0x1230,0x238000),(0x1428,ns['R1'])]:struct.pack_into('<Q',initial,o,v)
initial[0x960]=2

def run(d):
 m.mem_write(D,bytes(d));m.mem_write(C,bytes(0x3000));m.mem_write(ns['O'],bytes(0x100));m.mem_write(0x238000,bytes(0x100));m.mem_write(A+0x6d0,bytes(8));ns['mapped']=0x870000000;ns['pending']=None;ns['entries'].clear();ns['calls'].clear()
 for r in ns['regs']:m.reg_write(r,0)
 for r,v in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(r,v)
 m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP']
 cmd=bytes(m.mem_read(C,0x3000)); n=struct.unpack_from('<H',cmd,0x768)[0];seen={};r={}
 for i in range(n):
  h,v=struct.unpack_from('<IQ',cmd,0x60+i*12); k=(h&0x3fff8,h&1); occ=seen.get(k,0);seen[k]=occ+1;r[(k[0],k[1],occ)]=v
 return r
base=run(initial); rows=[]
for o in range(0xff0,0x1228,4):
 d=bytearray(initial);struct.pack_into('<I',d,o,0x13579bdf)
 try: r=run(d)
 except Exception as e:rows.append({'offset':hex(o),'refusal':str(e)});continue
 changes=[{'register':hex(k[0]),'flag':k[1],'occurrence':k[2],'before':hex(base[k]) if k in base else None,'after':hex(r[k]) if k in r else None} for k in base.keys()|r.keys() if base.get(k)!=r.get(k)]
 if changes:rows.append({'offset':hex(o),'changes':changes})
(out/'ta-field-map.json').write_text(json.dumps({'marker':hex(0x13579bdf),'observations':rows,'hardware_actions':[],'scope':'Targeted numeric TA descriptor dependency tracing, not semantic completeness'},indent=2)+'\n')
for r in rows: print(r)
