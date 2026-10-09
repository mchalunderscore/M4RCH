#!/usr/bin/env python3
"""Enable first KSM queue installation in an existing owned work candidate.

Offline only. Firmware-consumer evidence qualifies the installation flag, not
other provisional queue geometry, context, baseline or rendering fields.
"""
import argparse, hashlib, json, shutil, struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('candidate',type=Path); p.add_argument('firmware_text',type=Path); p.add_argument('output',type=Path)
a=p.parse_args()
from firmware_text_contract import qualify
text=a.firmware_text.read_bytes(); identity=qualify(text)
# Matched work-command jump table, opcode15 cache-prefix and install branch.
assert struct.unpack_from('<i',text,0x1a4fc+15*4)[0]+0x190ec==0x191f8
assert text[0x1926c:0x19274]==bytes.fromhex('68a241b888480034')
assert text[0x19754:0x1975c]==bytes.fromhex('6b0a40f9ebe a00a9'.replace(' ',''))
prep=json.loads((a.candidate/'preparation.json').read_text())
data=bytearray((a.candidate/'backing.bin').read_bytes())
sha=lambda b:hashlib.sha256(b).hexdigest()
assert len(data)==52*16384 and sha(data)==prep['data_sha256']
shutil.copytree(a.candidate,a.output)
changes=[]
for j,q in enumerate(prep['owned_scheduler']):
 off=(48+j*2)*16384+0x1000+0x1a
 assert struct.unpack_from('<I',data,off)[0]==0
 struct.pack_into('<I',data,off,1)
 q['first_queue_install']=True
 changes.append(dict(stage=q['stage'],backing_offset=hex(off),config_field='0x1a',before=0,after=1))
h=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),queue_bind_trial=dict(changes=changes,firmware=identity,install_branch='0x1926c..0x19274',queue_pair_store='0x19754..0x1975c',qualification='Flag1 enables native firmware queue installation; geometry/context/baseline remain experimental. No rendering established.'))
(a.output/'backing.bin').write_bytes(data);(a.output/'render-data.h').write_text(h);(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print(json.dumps(prep['queue_bind_trial'],indent=2))
