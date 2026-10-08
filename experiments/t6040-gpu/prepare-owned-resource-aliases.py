#!/usr/bin/env python3
"""Extend checked owned PM backing with allocation-only shared resource aliases."""
from pathlib import Path
import argparse,json,struct,hashlib,re
p=argparse.ArgumentParser();p.add_argument('backing',type=Path);p.add_argument('pair',type=Path);p.add_argument('output',type=Path);a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
r=json.loads((a.backing/'preparation.json').read_text());pair=json.loads((a.pair/'receipt.json').read_text());data=(a.backing/'backing.bin').read_bytes();header=(a.backing/'render-data.h').read_text()
assert r['pages']==40 and sha(data)==r['data_sha256'] and sha(header.encode())==r['header_sha256'] and pair['submission_ready'] is False
vas=[int(v,0) for v in r['candidate_vas']];aliases=[0]*len(vas)
for index in range(22,30):aliases[index]=0xfffffc2000a00000+(index-22)*16384
aliases[30]=0xfffffc2000a20000
for resource in pair['resource_ranges']:
 va=int(resource['device_base'],0);fw=int(resource['fw_base'],0)
 assert resource['bytes']<=16384 and va not in vas and fw not in aliases
 assert va>>25==vas[21]>>25 and fw>>25==0xfffffc2000100000>>25
 vas.append(va);aliases.append(fw);data+=bytes(16384)
assert len(vas)==42
header='#define RENDER_FW_ALIASES 1\n#define RENDER_BACKING_PAGES 42U\n#define RENDER_EXTRA_PAGES 48U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,21};\nstatic const u64 render_vas[]={'+','.join(hex(v)+'ULL' for v in vas)+'};\nstatic const u64 render_fw_aliases[]={'+','.join(hex(v)+'ULL' for v in aliases)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
a.output.mkdir(exist_ok=False);(a.output/'render-data.h').write_text(header);(a.output/'backing.bin').write_bytes(data)
r.update(pages=42,bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),candidate_vas=[hex(v) for v in vas],firmware_aliases=[hex(v) for v in aliases],resource_pair_receipt_sha256=sha((a.pair/'receipt.json').read_bytes()),qualification='Allocation-only shared backing aliases for native ring/GTP plus aux/scene record resources. All added aux/scene data zero placeholders; no raw randomized host snapshot reused. CPU shadow walks and copies only, no GPU translation or firmware publication. Resource lifecycle/initialization remains unresolved.')
(a.output/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');print('Prepared42 data pages and11 shared aliases')
