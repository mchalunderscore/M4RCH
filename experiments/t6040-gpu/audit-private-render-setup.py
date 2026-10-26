#!/usr/bin/env python3
"""Qualify complete contiguous native payload copy including its common helper."""
import argparse,hashlib,json,random,struct,sys
from pathlib import Path
from private_render_setup import copy_payload,HEAD,FLAGS,LIFE,TAIL
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
checker=Path(__file__).with_name('audit-private-3d-input-generator.py');ns={'__file__':str(checker)};old=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)]
try:exec(compile(checker.read_text().split('rng=random.Random(604010);fixtures=[]')[0],str(checker),'exec'),ns)
finally:sys.argv=old
m=ns['m'];c=ns['c'];D=ns['D'];S,W=0x238000,0x23c000;START,END=0xfffffe0008998198,0xfffffe0008998504
m.mem_map(0xfffffe0008998000,4096);m.mem_write(START,ns['read'](START,END-START));rng=random.Random(604019)
for i in range(1024):
 desc=rng.randbytes(0x1800);payload=rng.randbytes(0x900);wrapper=bytearray(rng.randbytes(0x300));struct.pack_into('<Q',wrapper,0x18,S)
 m.mem_write(D,desc);m.mem_write(S,payload);m.mem_write(W,bytes(wrapper))
 for reg in ns['regs']:m.reg_write(reg,0)
 for reg,value in [(c.UC_ARM64_REG_X25,D),(c.UC_ARM64_REG_X23,D+0x79c),(c.UC_ARM64_REG_X26,W),(c.UC_ARM64_REG_SP,ns['STACK'])]:m.reg_write(reg,value)
 m.emu_start(START,END,count=3000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 actual=bytes(m.mem_read(D,len(desc)));expected=copy_payload(desc,payload)
 assert actual==expected,(i,[(hex(j),hex(actual[j]),hex(expected[j])) for j in range(len(actual)) if actual[j]!=expected[j]][:20])
 assert bytes(m.mem_read(S,len(payload)))==payload and bytes(m.mem_read(W,len(wrapper)))==bytes(wrapper)
report={'private_binary_sha256':ns['sha'],'range':[hex(START),hex(END)],'range_sha256':hashlib.sha256(ns['read'](START,END-START)).hexdigest(),'cases':1024,'copy_tables':{'head':HEAD,'masked_lowbit_flags':FLAGS,'lifecycle':LIFE,'tail':TAIL},'findings':['wrapper+18 supplies raw payload; native common copier receives payload+2d0','payload810 goes to descriptor86c; payload814 lowbit goes to868; payload818 qword goes to870','payload820 lowbit goes to88d and113e; payload830 qword goes to950;838 u32 to958','partial BG descriptor638/640 comes from payload6e8/6f0; partial EOT780/788 from708/710','payload7d8..7db each lowbit to descriptor88e..891; their register effects must be traced separately'],'qualification':'Complete contiguous processRenderSetup data-copy slice executes including actual native common helper. Full descriptor bytes independently modeled in1024 random cases; source/wrapper unchanged. PAC handling inherited pinned harness. X23 explicitly supplied as X25+79c; preceding caller alias selection, payload size/validation, resource binding, PM setup and later allocation/event/lifecycle work excluded. Raw input records are synthetic, not native live data or valid jobs. No GPU execution.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print('1024 full native payload-copy slices matched; helper and lifecycle/partial fields included')
