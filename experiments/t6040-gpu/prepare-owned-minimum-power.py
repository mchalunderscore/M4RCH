#!/usr/bin/env python3
"""Stage a minimum-active-state integrated draw hypothesis, never publish it.

Native producer offsets are pinned to 25G83; choosing ADT group1 and cap1 is an
experimental policy, not a reconstruction of Apple's complete power setup.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
import adt,contract
p=argparse.ArgumentParser(description=__doc__)
for n in ['candidate','adt','macho','output']:p.add_argument(n,type=Path)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
raw=a.macho.read_bytes()
assert sha(raw)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
prep=json.loads((a.candidate/'preparation.json').read_text());layout=json.loads((a.candidate/'graph-receipt.json').read_text())
before=(a.candidate/'graph-before.bin').read_bytes();blob=bytearray(before)
assert sha(blob)==layout['arena_sha256']
hw=next(x for x in layout['objects'] if x['name']=='hardware')['arena_offset']
tree=adt.parse(a.adt.read_bytes());gpu=tree['/device-tree/arm-io/sgx']
count=int.from_bytes(gpu['perf-state-count'],'little');clusters=int.from_bytes(gpu['perf-state-table-count'],'little')
assert (count,clusters)==(16,2)
core=contract.tables(gpu['perf-states'],count,clusters);sram=contract.tables(gpu['perf-states-sram'],count,clusters)
groups=[contract.ladder(c,s) for c,s in zip(core,sram)]
assert all(len(g)==11 and g[0]['frequency_high_mhz']==0 and g[1]['frequency_low_mhz']==338 and g[1]['frequency_high_mhz']==338 for g in groups)
for j,g in enumerate(groups):
 assert struct.unpack_from('<I',blob,hw+0x1008+0x40+j*4)[0]==g[1]['core_voltage_raw']
 assert struct.unpack_from('<I',blob,hw+0x1408+0x40+j*4)[0]==g[1]['sram_voltage_raw']
# All hardware initialization words below were zero in the preceding fixture.
# Native constants: cd150,cd164,cd16c,cd5a4; topology: cd7c8.
words={0xed0:24000,0xee0:1,0xee4:1,0xee8:1,0xf04:31,0xfc4:1,0xfcc:338,0x2570:16}
changes=[]
for off,val in words.items():
 assert struct.unpack_from('<I',blob,hw+off)[0]==0
 struct.pack_into('<I',blob,hw+off,val);changes.append(dict(hardware_offset=hex(off),before=0,after=val))
assert struct.unpack_from('<16I',blob,hw+0xfc8)==(0,338)+(0,)*14
assert struct.unpack_from('<Q',blob,hw+0x2560)[0]==0xf6fdb
shutil.copytree(a.candidate,a.output)
for obj in layout['objects']:obj['input_sha256']=sha(blob[obj['arena_offset']:obj['arena_offset']+obj['input_bytes']])
layout['arena_sha256']=sha(blob)
report=dict(binary_sha256=sha(raw),adt_sha256=sha(a.adt.read_bytes()),changes=changes,changed_bytes=sum(x!=y for x,y in zip(before,blob)),active_frequency_mhz=338,max_state=1,
 producer={'frequency':'89a8a84/89a8aa4/89a8ac4; Hz->MHz multiply431bde83 shift50','constants':'89cd150/89cd164/89cd16c/89cd5a4','enabled_core_count':'89cd7c8'},
 consumers={'frequency_array':'matched firmware2f518','max_state':'c660/c678; zero bypasses state-selection path'},
 hypothesis='Zero state cap/frequencies may keep execution inactive despite working firmware controls. Enable only the first active ADT group; native constant fields fill known gaps. Complete power tuning and hardware behavior remain unqualified.',
 qualification='Offline integrated experimental draw candidate, cap1 policy is not native whole-constructor proof; secondary profile disabled, no MMIO override, GPU execution/rendering unverified.')
layout['minimum_power_trial']=report;prep['minimum_power_trial']=report
h=(a.output/'graph-contract.h').read_text();marker='static const u8 graph_bytes['
h=h.split(marker)[0]+f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join('['+hex(i)+']='+hex(v)+',\n' for i,v in enumerate(blob) if v)+'};\n'
(a.output/'graph-contract.h').write_text(h);(a.output/'graph-before.bin').write_bytes(blob)
(a.output/'graph-receipt.json').write_text(json.dumps(layout,indent=2)+'\n');(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print(json.dumps(report,indent=2))
