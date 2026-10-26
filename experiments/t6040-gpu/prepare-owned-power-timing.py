#!/usr/bin/env python3
"""Stage native power timing and constant prefix defaults; never publish.

Matched private binary producers qualify offsets, not full power initialization.
Retains the preceding lowest-active-state experimental policy and draw backing.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
import adt
p=argparse.ArgumentParser(description=__doc__)
for name in ['candidate','adt','macho','output']:p.add_argument(name,type=Path)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
raw=a.macho.read_bytes();assert sha(raw)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,size=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=size
def native(address,length):
 for vm,_,off,size in segments:
  if vm<=address and address+length<=vm+size:return raw[off+address-vm:off+address-vm+length]
 raise ValueError('Native input not file backed')
# Actual stores and getter instructions, not symbol-name inference alone.
for address,word in [(0xfffffe00089a86ac,0x29008100),(0xfffffe00089cd1f8,0xb90ed900),(0xfffffe00089e8b1c,0x529db608),(0xfffffe00089e8b30,0x529db588)]:
 assert struct.unpack('<I',native(address,4))[0]==word
node=adt.parse(a.adt.read_bytes())['/device-tree/arm-io/sgx']
clocks=int.from_bytes(node['gpu-pwr-sample-period-aic-clks'],'little');milliseconds=int.from_bytes(node['gpu-power-sample-period'],'little')
assert (clocks,milliseconds)==(200000,8)
layout=json.loads((a.candidate/'graph-receipt.json').read_text());prep=json.loads((a.candidate/'preparation.json').read_text())
assert prep['minimum_power_trial']['max_state']==1 and prep['minimum_power_trial']['active_frequency_mhz']==338
before=(a.candidate/'graph-before.bin').read_bytes();blob=bytearray(before);assert sha(blob)==layout['arena_sha256']
objects={o['name']:o for o in layout['objects']}
constant8=native(0xfffffe000712d7d0,8);constant16=native(0xfffffe000712dd00,16)
# Native base constructor 89a86ac..89a8708; zeroed prefix initialization.
fields=[('power',4,struct.pack('<II',clocks,clocks)),('hardware',0xed8,struct.pack('<I',milliseconds)),
 ('power',0xc,constant8),('power',0x14,struct.pack('<Q',0x3f800000)),('power',0x2c,struct.pack('<II',1,1)),
 ('power',0x50,struct.pack('<I',100)),('power',0x5c,constant8),('power',0x64,struct.pack('<I',0x3f800000)),
 ('power',0x68,constant16),('power',0x90,struct.pack('<I',100))]
changes=[]
for name,offset,data in fields:
 o=objects[name];assert offset+len(data)<=o['input_bytes'];start=o['arena_offset']+offset
 old=bytes(blob[start:start+len(data)]);assert not any(old)
 blob[start:start+len(data)]=data;changes.append(dict(object=name,offset=hex(offset),before=old.hex(),after=data.hex()))
shutil.copytree(a.candidate,a.output)
report=dict(binary_sha256=sha(raw),adt_sha256=sha(a.adt.read_bytes()),changes=changes,changed_bytes=sum(x!=y for x,y in zip(before,blob)),period_aic_clocks=clocks,period_ms=milliseconds,
 producer_offsets=['89a86ac:power4/8','89cd1f8:hardwareed8','89a86d4..89a8708:power constant prefix'],
 qualification='Integrated experimental draw with native timing/static defaults; dynamic tuning and complete constructor remain unqualified. No GPU execution, timing effect or rendered output proved.')
layout['power_timing_trial']=report;prep['power_timing_trial']=report
for o in layout['objects']:o['input_sha256']=sha(blob[o['arena_offset']:o['arena_offset']+o['input_bytes']])
layout['arena_sha256']=sha(blob)
h=(a.output/'graph-contract.h').read_text().split('static const u8 graph_bytes[')[0]
h+=f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join('['+hex(i)+']='+hex(v)+',\n' for i,v in enumerate(blob) if v)+'};\n'
(a.output/'graph-contract.h').write_text(h);(a.output/'graph-before.bin').write_bytes(blob)
(a.output/'graph-receipt.json').write_text(json.dumps(layout,indent=2)+'\n');(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print(json.dumps(report,indent=2))
