#!/usr/bin/env python3
"""Bind paired commands and experimental scene initialization to one owned graph."""
from pathlib import Path
import argparse,json,hashlib,struct,shutil
p=argparse.ArgumentParser();p.add_argument('backing',type=Path);p.add_argument('pair',type=Path);p.add_argument('output',type=Path);a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
r=json.loads((a.backing/'preparation.json').read_text());data=bytearray((a.backing/'backing.bin').read_bytes());assert r['pages']==42 and sha(data)==r['data_sha256']
vas=[int(v,0) for v in r['candidate_vas']];aliases=[int(v,0) for v in r['firmware_aliases']]
aux=(a.pair/'aux-resource-candidate.bin').read_bytes();scene=(a.pair/'scene-resource-candidate.bin').read_bytes();assert len(aux)==2176 and len(scene)==2048
for index,b in [(40,aux),(41,scene)]:data[index*16384:index*16384+len(b)]=b
for j in range(5):vas.append(0x10000b0000+j*16384);aliases.append(0xfffffc2000b00000+j*16384);data+=bytes(16384)
assert len(vas)==47 and len(set(vas))==47 and len({v for v in aliases if v})==16
header='#define RENDER_FW_ALIASES 1\n#define RENDER_BACKING_PAGES 47U\n#define RENDER_EXTRA_PAGES 53U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,26};\nstatic const u64 render_vas[]={'+','.join(hex(v)+'ULL' for v in vas)+'};\nstatic const u64 render_fw_aliases[]={'+','.join(hex(v)+'ULL' for v in aliases)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
a.output.mkdir(exist_ok=False)
for name in ('Makefile','asc-graph-init.c','boot-contract.h','command-pool-map.h','graph-contract.h','graph-map.h','render-backing-map.h'):shutil.copy2(a.backing/name,a.output/name)
commands=[]
for kind in ('3d','ta'):
 b=(a.pair/'pair'/(kind+'-construction-candidate.bin')).read_bytes();assert len(b)==(0x2240 if kind=='3d' else 0x9c0);commands.append(b+bytes(0x2240-len(b)))
commands+= [bytes(0x2240)]*62
jhead='#define JOB_COUNT 64U\n#define COMMAND_BYTES 0x2240U\n#define POOL_BYTES 573440U\n#define POOL_PAGES 35U\n#define DEVICE_BASE 0x850000000ULL\n#define FW_BASE 0xfffffc2000800000ULL\nstatic const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={\n'+',\n'.join('{'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(b) if v)+'}' for b in commands)+'\n};\n'
(a.output/'job-data.h').write_text(jhead);(a.output/'render-data.h').write_text(header);(a.output/'backing.bin').write_bytes(data)
r.update(pages=47,bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),candidate_vas=[hex(v) for v in vas],firmware_aliases=[hex(v) for v in aliases],integrated_pair={'3d_slot':0,'ta_slot':1,'3d_gpu':'0x850000000','ta_gpu':'0x850002240','scene_payload_logical_bytes':69824,'scene_payload_backing_bytes':81920,'command_sha256':[sha(b) for b in commands[:2]],'initialization':'aux zero; scene registration/page-list/generation experimental, known native scene mapping; PM scene payload zero hypothesis'},qualification='Paired native-produced commands staged together with authored shader/state/target and experimental initialized scene/aux/parameter backing in one owned CPU shadow graph. Allocation-only, no GPU publication or execution.')
(a.output/'preparation.json').write_text(json.dumps(r,indent=2)+'\n')
