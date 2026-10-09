#!/usr/bin/env python3
"""Diagnostic first-NOP dependency bypass in the integrated draw candidate.

Hardware snapshot21020 remains wrapped40 predecessor. Native NOP always inserts
an own-queue dependency; zero-dependency NOP acceptance is unverified hardware.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct
p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
prep=json.loads((a.candidate/'preparation.json').read_text());data=bytearray((a.candidate/'backing.bin').read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(data)==prep['data_sha256'] and len(data)==52*16384
before=bytes(data)
for j,q in enumerate(prep['owned_scheduler']):
 nop=(49+j*2)*16384
 assert struct.unpack_from('<Q',data,nop)[0]&3==2
 assert struct.unpack_from('<Q',data,nop+0x20)[0]==1
 struct.pack_into('<Q',data,nop+0x20,0)
 assert data[nop+512:nop+1024]==before[nop+512:nop+1024]
 q['first_nop_dependency_bitmap']=0
assert sum(x!=y for x,y in zip(before,data))==2
shutil.copytree(a.candidate,a.output)
h=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
report=dict(changed_bytes=2,fields=['TA NOP0+20 dependency bitmap','fragment NOP0+20 dependency bitmap'],hardware_snapshot21020='0xffffffffff',qualification='Explicit diagnostic departure from native unconditional own dependency; zero-dependency NOP semantics unverified. Keep actual native timestamp1 work, mappings/context/hold-release/shaders and target unchanged. No hardware attempt.')
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),first_nop_ready_trial=report)
(a.output/'render-data.h').write_text(h);(a.output/'backing.bin').write_bytes(data);(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n');print(json.dumps(report,indent=2))
