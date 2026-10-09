#!/usr/bin/env python3
"""Stage an experimental first timeline and shared TA/3D context association.

No live loading. Preserve installed queues and native work/register/shader data.
The wrapped baseline and base-M4 context seed are hypotheses, not M4 Pro defaults.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from firmware_text_contract import qualify
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('candidate',type=Path);p.add_argument('firmware_text',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
text=a.firmware_text.read_bytes();identity=qualify(text)
# Matched configuration consumer: baseline and owner-context branch checks.
assert text[0x1922c:0x19238]==bytes.fromhex('686242b8e80100347ba242f8')
assert text[0x19b80:0x19b8c]==bytes.fromhex('682245b8482e003479a244f8')
prep=json.loads((a.candidate/'preparation.json').read_text());before=(a.candidate/'backing.bin').read_bytes();data=bytearray(before)
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(data)==prep['data_sha256'] and len(data)==52*16384
shutil.copytree(a.candidate,a.output)
shared=int(prep['owned_scheduler'][0]['context_fw'],0);mask=(1<<40)-1
for j,q in enumerate(prep['owned_scheduler']):
 off=(48+j*2)*16384;cfg=off+0x1000;nop=off+16384
 assert struct.unpack_from('<I',data,cfg+0x1a)[0]==1
 assert struct.unpack_from('<Q',data,nop+0x20)[0]&255==1
 old=struct.unpack_from('<Q',data,nop+0x28)[0]
 assert old&mask==0 and (old>>40)&127==q['queue_id']
 # Before timestamp0: wrapped predecessor, preserving queue ID bits40..46.
 struct.pack_into('<Q',data,nop+0x28,(old&~mask)|mask)
 struct.pack_into('<I',data,cfg+0x26,1);struct.pack_into('<Q',data,cfg+0x2a,mask)
 struct.pack_into('<Q',data,off+0x9c,shared);struct.pack_into('<Q',data,cfg+0x4a,shared)
 struct.pack_into('<I',data,cfg+0x52,1)
 q.update(context_fw=hex(shared),nop_previous=hex(mask),baseline_update_flag=1,baseline=hex(mask),owner_context_update_flag=1)
 # Keep actual timestamp1 work, command pointers and dependencyTA1 unchanged.
 assert data[nop+512:nop+1024]==before[nop+512:nop+1024]
header=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
header=header.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
report=dict(firmware=identity,shared_context_fw=hex(shared),timeline=dict(nop=0,nop_predecessor=hex(mask),work=1,ta_predecessor=0,fragment_dependency=dict(queue=0,timestamp=1),fragment_predecessor=0),context_flags=dict(config52=1,config56=0,config5a=0,config5e=0),changed_bytes=sum(x!=y for x,y in zip(before,data)),qualification='Explicit experimental modulo40 baseline and shared owner-context activation. Gravity seed retained; raw service fields56/5a/5e remain zero hypotheses, not asserted ASID or native defaults. Context association is separate from UAT context1. No hardware attempt or completion.')
prep.update(data_sha256=sha(data),header_sha256=sha(header.encode()),scheduler_start_trial=report)
(a.output/'backing.bin').write_bytes(data);(a.output/'render-data.h').write_text(header);(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print(json.dumps(report,indent=2))
