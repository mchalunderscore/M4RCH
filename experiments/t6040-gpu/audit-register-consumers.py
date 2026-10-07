#!/usr/bin/env python3
"""Conservative local data-flow inventory from LLVM firmware disassembly.
Only locally resolved ADRP/ADD/MOV and cached virtual loads are followed.
Branches end a region; this is neither complete CFG analysis nor address proof.
"""
import re,json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('disassembly',type=Path);p.add_argument('register_audit',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
names={r['slot']:r['name'] for r in json.loads(a.register_audit.read_text())['slots']}
state={};events=[]
def reg(s):return re.sub(r'^w','x',s.strip())
for line in a.disassembly.read_text().splitlines():
 m=re.match(r'\s*([0-9a-f]+):\s*([0-9a-f]{8})\s+(\S+)\s*(.*)',line)
 if not m:continue
 pc=int(m[1],16);op=m[3];args=m[4].split(' <')[0];parts=[x.strip() for x in args.split(',')];dest=reg(parts[0]);new=None
 if op=='adrp' and len(parts)==2:
  try:new=('abs',int(parts[1],0))
  except ValueError:pass
 elif op=='mov' and len(parts)==2:new=state.get(reg(parts[1]))
 elif op=='add' and len(parts)==3 and parts[2].startswith('#'):
  old=state.get(reg(parts[1]))
  if old:
   try:new=(*old[:-1],old[-1]+int(parts[2][1:],0))
   except ValueError:pass
 mem=re.search(r'\[(x\d+)(?:, #(0x[0-9a-f]+|[0-9]+))?\]',args)
 if mem:
  old=state.get(reg(mem[1]));off=int(mem[2] or '0',0)
  if old and old[0]=='abs' and op=='ldr' and dest.startswith('x'):
   absolute=old[1]+off;relative=absolute-0x18f420-8
   if relative>=0 and relative%0x28==0 and relative//0x28 in names:new=('slot',relative//0x28,0)
  if old and old[0]=='slot' and op.startswith(('ld','st')):
   events.append({'pc':hex(pc),'word':m[2],'slot':old[1],'name':names[old[1]],'operation':op,'offset':hex(old[2]+off),'operands':args,'direction':'write' if op.startswith('st') else 'read'})
 # Loads overwrite their destination, stores/comparisons do not.
 if dest.startswith('x') and op not in ['cmp','cmn','tst'] and not (op.startswith(('st','cb','tb')) or op in ['b','bl','blr','blraaz','br']):
  if new:state[dest]=new
  else:state.pop(dest,None)
 if op=='ldp' and len(parts)>1:state.pop(reg(parts[1]),None)
 if op.startswith(('b.','cb','tb')) or op in ['b','bl','blr','blraaz','br','ret','retab']:state={}
result={'qualification':__doc__,'events':events,'slots':sorted(set(e['slot'] for e in events))}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(f'{len(events)} locally resolved accesses across {len(result["slots"])} slots')
