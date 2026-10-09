#!/usr/bin/env python3
"""Compare initial zero baseline against modulo40 predecessor, offline only.

The initial hardware counter semantics are unverified. Retain installed queues,
shared context, selector1 and all actual native timestamp1 TA/3D work bytes.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
prep=json.loads((a.candidate/'preparation.json').read_text())
data=bytearray((a.candidate/'backing.bin').read_bytes());before=bytes(data)
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(data)==prep['data_sha256'] and len(data)==52*16384
mask=(1<<40)-1
for j,q in enumerate(prep['owned_scheduler']):
 off=(48+j*2)*16384;cfg=off+0x1000;nop=off+16384
 assert struct.unpack_from('<I',data,cfg+4)[0]==1
 assert struct.unpack_from('<I',data,cfg+0x1a)[0]==1
 assert struct.unpack_from('<I',data,cfg+0x26)[0]==1
 assert struct.unpack_from('<Q',data,cfg+0x2a)[0]==mask
 old=struct.unpack_from('<Q',data,nop+0x28)[0]
 assert old&mask==mask and (old>>40)&127==q['queue_id']
 struct.pack_into('<Q',data,cfg+0x2a,0)
 struct.pack_into('<Q',data,nop+0x28,old&~mask)
 assert data[nop+512:nop+1024]==before[nop+512:nop+1024]
 q.update(nop_previous='0x0',baseline='0x0')
shutil.copytree(a.candidate,a.output)
h=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
report=dict(before=hex(mask),after=0,changed_bytes=sum(x!=y for x,y in zip(before,data)),actual_work_unchanged=True,qualification='Initial hardware counter0 and NOP dependency0 are experimental, not proven. Compare against prior wrapped baseline with queue selector1/shared context held constant; integrated read-only live KSM status improves diagnosis.')
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),zero_baseline_trial=report)
(a.output/'backing.bin').write_bytes(data);(a.output/'render-data.h').write_text(h);(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print(json.dumps(report,indent=2))
