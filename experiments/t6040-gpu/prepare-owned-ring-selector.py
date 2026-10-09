#!/usr/bin/env python3
"""Align the KSM ring header selector with the owned context1 trial.

Offline only. Header bit48 packing matches the observed ASID encoding, but
its hardware selector meaning remains an explicit experimental hypothesis.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from firmware_text_contract import qualify
p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('firmware_text',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
text=a.firmware_text.read_bytes();identity=qualify(text)
assert text[0x19214:0x19218]==bytes.fromhex('760640b9')
assert text[0x198a0:0x198a8]==bytes.fromhex('4d977b92adc116aa')
prep=json.loads((a.candidate/'preparation.json').read_text());data=bytearray((a.candidate/'backing.bin').read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(data)==prep['data_sha256'] and len(data)==52*16384
shutil.copytree(a.candidate,a.output)
for j,q in enumerate(prep['owned_scheduler']):
 off=(48+j*2)*16384+0x1004
 assert struct.unpack_from('<I',data,off)[0]==0
 struct.pack_into('<I',data,off,1);q['ring_header_selector']=1
h=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
report=dict(firmware=identity,config_field='0x4',before=0,after=1,packing='GPU ring address masked to43-bit aligned address, header word shifted48; written by firmware to SGX21008',owned_ttbr_slot=1,qualification='Candidate ring translation-selector alignment, inferred from matched bit48 packing and native TTBR ASID encoding. Actual hardware field meaning not independently established. Keep installed queues, accepted shared context/baselines and native work unchanged; no live attempt.')
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),ring_selector_trial=report)
(a.output/'backing.bin').write_bytes(data);(a.output/'render-data.h').write_text(h);(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n');print(json.dumps(report,indent=2))
