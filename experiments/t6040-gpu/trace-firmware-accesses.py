#!/usr/bin/env python3
"""Conservative straight-line firmware pointer-access hints, not decompilation.

Registers are forgotten at every branch/call/return. Unknown destination writes
invalidate provenance. Only address arithmetic, register copies and simple
loads/stores are modelled; results require manual instruction review.
"""
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('disassembly',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rx=re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+([\w.]+)\s*(.*)$')
regs={};accesses=[]
def regname(r):return 'x'+r[1:] if r.startswith('w') else r
def number(s):return int(s.strip().lstrip('#'),0)
def width(r):return {'x':8,'w':4,'q':16,'d':8,'s':4,'b':1,'h':2}.get(r[0],0)
for line in a.disassembly.read_text().splitlines():
 m=rx.match(line)
 if not m:continue
 pc=int(m[1],16);op=m[3];arg=m[4].split('//')[0].strip();args=[x.strip() for x in arg.split(',')]
 if op in ['bl','blr','blraaz','braa','br','ret','retaa','retab','cbz','cbnz','tbz','tbnz','b'] or op.startswith('b.'):
  regs={};continue
 if op in ['pacibsp','autibsp','nop','cmp','cmn','tst','dsb','isb','dmb']:continue
 if op=='adrp':
  try:regs[args[0]]=('absolute',int(args[1].split()[0],0))
  except (ValueError,IndexError):regs.pop(args[0],None)
  continue
 if op in ['add','sub'] and len(args)==3 and args[2].startswith('#'):
  source=regs.get(regname(args[1]));dest=regname(args[0]);regs.pop(dest,None)
  if source:
   try:regs[dest]=(source[0],source[1]+number(args[2])*(1 if op=='add' else -1))
   except ValueError:pass
  continue
 if op=='mov' and len(args)==2 and args[0].startswith('x') and args[1].startswith('x'):
  source=regs.get(args[1]);regs.pop(args[0],None)
  if source:regs[args[0]]=source
  continue
 mem=re.search(r'\[(x\d+)(?:,\s*(#[^\]]+))?\]',arg)
 isload=op in ['ldr','ldur','ldrb','ldrh','ldrsw','ldp'];isstore=op in ['str','stur','strb','strh','stp']
 if mem and (isload or isstore):
  base=regs.get(mem[1]);offset=0
  try:offset=number(mem[2]) if mem[2] else 0
  except ValueError:base=None
  dests=args[:2] if op in ['ldp','stp'] else args[:1]
  if base:
   for i,dest in enumerate(dests):
    size=1 if op.endswith('b') else 2 if op.endswith('h') else width(dest)
    off=base[1]+offset+i*size
    origin=base[0]
    if origin!='absolute':accesses.append(dict(pc=hex(pc),origin=origin,offset=hex(off),bytes=size,mode='load' if isload else 'store',instruction=line.strip()))
    if isload:
     key=regname(dest);regs.pop(key,None)
     if size==8:
      if origin=='absolute' and off==0x18e4c0:regs[key]=('main',0)
      elif origin=='absolute' and off==0x195748:regs[key]=('region_c',0)
      elif origin!='absolute':regs[key]=(origin+'->'+hex(off),0)
  elif isload:
   for dest in dests:regs.pop(regname(dest),None)
  # Writeback addressing is deliberately not tracked.
  if ']!' in arg or '], ' in arg:regs.pop(mem[1],None)
  continue
 if op.startswith('st'):continue
 if args and re.fullmatch(r'[xwqdsbh]\d+',args[0]):regs.pop(regname(args[0]),None)
r={'qualification':__doc__,'accesses':accesses}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(f'{len(accesses)} conservative access hints')
