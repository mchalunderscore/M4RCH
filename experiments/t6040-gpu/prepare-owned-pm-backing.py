#!/usr/bin/env python3
"""Add native-regenerated PM block/page-list backing to checked render allocations."""
import argparse,json,hashlib,struct,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('render',type=Path);p.add_argument('pm_profile',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
r=json.loads((a.render/'preparation.json').read_text());data=(a.render/'backing.bin').read_bytes();header=(a.render/'render-data.h').read_text()
assert r['pages']==31 and r['submission_ready'] is False and sha(data)==r['data_sha256'] and sha(header.encode())==r['header_sha256']
pm=json.loads(a.pm_profile.read_text());assert pm['submission_ready'] is False
for f in pm['files'].values():
 b=(a.pm_profile.parent/f['file']).read_bytes();assert len(b)==f['bytes'] and sha(b)==f['sha256']
block=int(pm['candidate_block_device_va'],0);assert block==int(pm['block_mapping_fixture'],0)
assert block%32768==0 and pm['capacities']['block_memory_bytes']==131072 and pm['capacities']['page_list_resource_bytes']==32
frame=block>>15;frames=list(range(frame,frame+4));assert frames==pm['frame_indices']
page_list=(a.pm_profile.parent/pm['files']['page-list']['file']).read_bytes();assert page_list[:16]==struct.pack('<4I',*frames)
# Only the native-written prefix is reused. Random untouched fixture bytes are excluded.
block_bytes=bytes(131072);list_bytes=page_list[:16]+bytes(16384-16)
import re
vlist=re.search(r'static const u64 render_vas\[\]=\{([^}]+)\}',header).group(1)
vas=[int(x.removesuffix('ULL'),0) for x in vlist.split(',')]
newvas=[block+i*16384 for i in range(8)]+[block+131072]
assert len(vas)==31 and not set(vas)&set(newvas)
assert all(v>>25==int(r['state_va'],0)>>25 for v in newvas)
vas+=newvas;data+=block_bytes+list_bytes
header='#define RENDER_BACKING_PAGES '+str(len(vas))+'U\n#define RENDER_EXTRA_PAGES '+str(len(vas)+6)+'U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,'+str(len(vas)-21)+'};\nstatic const u64 render_vas[]={'+','.join(hex(v)+'ULL' for v in vas)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
a.output.mkdir(exist_ok=False);(a.output/'render-data.h').write_text(header);(a.output/'backing.bin').write_bytes(data)
r.update(pages=len(vas),bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),pm_profile_sha256=sha(a.pm_profile.read_bytes()),candidate_vas=[hex(v) for v in vas],pm_backing={'parameter_block_va':hex(block),'parameter_block_bytes':len(block_bytes),'page_list_va':hex(newvas[-1]),'page_list_logical_bytes':32,'native_written_bytes':16,'frame_indices':frames,'unwritten_page_list_bytes':'zero placeholder; unused-entry policy unqualified'},qualification='Authored render backing plus native-derived ring/GTP allocation and parameter-block/page-list candidate. Native-written page prefix regenerated for candidate mapping; untouched random fixture bytes excluded. Parameter block initially zero allocation backing. State/scene/config/event/cache initialization, FW aliases, actual GPU lookup and complete work remain unproved. No publication.')
(a.output/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');print('Prepared',len(vas),'data pages')
