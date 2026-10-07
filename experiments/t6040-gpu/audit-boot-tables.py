#!/usr/bin/env python3
"""Walk captured reserved UAT tables offline; no hardware access or writes."""
import argparse,json,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
w=a.workspace;receipt=json.loads((w/'graph-sample-receipt.json').read_text())
region=next(r for r in receipt['samples'] if r['tag']=='pagetables')
base=region['address'];data=(w/'sample-pagetables/sample.bin').read_bytes()
assert len(data)==region['bytes']
mask=((1<<42)-1)&~0x3fff
def read(address):
    if address<base or address+8>base+len(data):raise ValueError('Table outside captured reservation')
    return struct.unpack_from('<Q',data,address-base)[0]
def translate(va):
    table=base;trace=[]
    for level,shift in enumerate([36,25,14]):
        index=(va>>shift)&(63 if level==0 else 2047)
        entry=read(table+index*8);trace.append({'level':level,'table':hex(table),'index':index,'entry':hex(entry)})
        if not entry&1:return {'physical':None,'trace':trace}
        if entry&3!=3:raise ValueError('Block descriptor not supported by this audit')
        table=entry&mask
    return {'physical':hex(table+(va&0x3fff)),'trace':trace}
checks={}
for name,va in [('firmware_text',0xfffffc0000000000),('firmware_data',0xfffffc0000060000),('candidate_root',0xfffffc2000100000),('candidate_bundle',0xfffffc20c04d8000)]:checks[name]=translate(va)
assert checks['firmware_text']['physical']=='0x10000be4000'
assert checks['firmware_data']['physical']=='0x10001d44000'
r={'boot_id':receipt['boot_id'],'geometry':{'page_bytes':0x4000,'shifts':[36,25,14],'address_bits':42},'checks':checks,
   'zero_regions':[x['tag'] for x in receipt['samples'] if not any((w/('sample-'+x['tag'])/'sample.bin').read_bytes())],
   'qualification':'Snapshot translations at these addresses only. Not a full free-space/collision audit, allocation authorization, cache-coherency test or initialized GPU qualification.'}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
