#!/usr/bin/env python3
"""Offline shader/state fixture -> native client-copy -> native 3D registers."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('target',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
checker=Path(__file__).with_name('audit-private-3d-input-generator.py');prefix=checker.read_text().split('rng=random.Random(604010);fixtures=[]')[0]
argv=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)];ns={'__name__':'bridge','__file__':str(checker)}
try:exec(compile(prefix,str(checker),'exec'),ns)
finally:sys.argv=argv
m=ns['m'];c=ns['c'];A,C,D,O=map(ns.get,('A','C','D','O'))
target=json.loads((a.target/'receipt.json').read_text());store=int(target['tile_store']['launch_offset'],0);background=int(target['background_candidate']['launch_byte_offset'],0)
common=bytearray(0x400);scissor=0x1000002000;depth_bias=0x1000002040
# Pair roles corroborated by differential native outputs and pinned Gravity register labels.
for off,value in [(0xa0,0),(0xa8,background),(0xc0,0),(0xc8,store),(0xe0,scissor),(0xe8,depth_bias)]:struct.pack_into('<Q',common,off,value)
struct.pack_into('<II',common,0x1c8,64,64)
desc=bytearray(0x1000)
for off,value in [(0x440,0x800050000),(0x190,O),(0x918,O),(0xb90,ns['R1']),(0x638,0),(0x640,background),(0x780,0),(0x788,store)]:struct.pack_into('<Q',desc,off,value)
for off,value in [(0x4a4,32),(0x4a8,32),(0x8c8,1)]:struct.pack_into('<I',desc,off,value)
m.mem_write(D,bytes(desc));m.mem_write(0x232000,bytes(common))
for reg in ns['regs']:m.reg_write(reg,0)
m.reg_write(c.UC_ARM64_REG_X0,D);m.reg_write(c.UC_ARM64_REG_X1,0x232000);m.reg_write(c.UC_ARM64_REG_X30,ns['STOP']);m.emu_start(0xfffffe00089ebbe4,ns['STOP'],count=500)
assert bytes(m.mem_read(D,0x1000))==ns['copy_common'](desc,common)
m.mem_write(C,bytes(0x3000));m.mem_write(A+0x6d0,bytes(8));m.mem_write(O,bytes(0x100));ns['mapped']=0x820000000;ns['pending']=None
for reg in ns['regs']:m.reg_write(reg,0)
for reg,value in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(reg,value)
m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP'];assert ns['pending'] is None
cmd=bytes(m.mem_read(C,0x3000));phases=[]
for phase in range(4):
 count=struct.unpack_from('<H',cmd,0x7a8+phase*0x720)[0];records=[]
 for i in range(count):
  header,value=struct.unpack_from('<IQ',cmd,0xa0+phase*0x720+12*i);records.append({'register':hex(header&0x3fff8),'flag':header&1,'value':hex(value)})
 phases.append(records)
expected={0:{0x15368:0,0x15370:background,0x15378:0,0x15380:store,0x15108:scissor,0x15100:depth_bias,0x15210:64|(64<<32)},1:{0x15378:0,0x15380:store},2:{0x15368:0,0x15370:background,0x15378:0,0x15380:store},3:{0x15368:0,0x15370:background}}
checks=0
for phase,fields in expected.items():
 for reg,value in fields.items():
  actual=[int(r['value'],0) for r in phases[phase] if int(r['register'],0)==reg];assert actual==[value],(phase,hex(reg),actual,hex(value));checks+=1
report={'private_binary_sha256':ns['sha'],'target_receipt_sha256':hashlib.sha256((a.target/'receipt.json').read_bytes()).hexdigest(),'native_harness_sha256':hashlib.sha256(checker.read_bytes()).hexdigest(),'checked_register_values':checks,'common_qwords':{hex(off):hex(struct.unpack_from('<Q',common,off)[0]) for off in [0xa0,0xa8,0xc0,0xc8,0xe0,0xe8]},'phases':phases,'qualification':'Native client copier and native 3D generator consume offline candidate background/EOT byte-offsets, scissor/depth-bias synthetic addresses and dimensions. Selected register values independently checked. Gravity register roles corroborate labels; do not establish valid T6040 hardware state. No shader execution, USC-base provenance, target/parameter/tile allocation, firmware microsequence, live completion or readback. Complete register output recorded, not independently validated recipe. GPU addresses are fixtures; no live mappings. Not a complete submittable job.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(f'{checks} selected native register values match candidate shader/state fixtures; no GPU access')
