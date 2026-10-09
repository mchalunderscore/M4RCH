#!/usr/bin/env python3
"""Stage four owned hardware completion rings and native descriptors; offline only.

Capacity64 and mapping context are experimental. Native producers and consumers
qualify layout, not successful completion routing or graphics execution.
"""
from pathlib import Path
import argparse,hashlib,json,struct,shutil
from private_completion_queue import populate,allocation_bytes
from firmware_text_contract import qualify
p=argparse.ArgumentParser(description=__doc__)
for n in ['candidate','firmware_text','macho','output']:p.add_argument(n,type=Path)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
raw=a.macho.read_bytes();assert sha(raw)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
text=a.firmware_text.read_bytes();identity=qualify(text)
# Firmware first descriptor pointer drives device register programming.
assert struct.unpack_from('<I',text,0x15f18)[0]==0xf95312cf
assert struct.unpack_from('<I',text,0x15f1c)[0]==0x927b95ef
prep=json.loads((a.candidate/'preparation.json').read_text());layout=json.loads((a.candidate/'graph-receipt.json').read_text())
before=(a.candidate/'graph-before.bin').read_bytes();blob=bytearray(before);backing=(a.candidate/'backing.bin').read_bytes()
assert prep['pages']==52 and len(backing)==52*16384 and sha(backing)==prep['data_sha256']
hw=next(o for o in layout['objects'] if o['name']=='hardware')['arena_offset'];off=hw+0x2620
assert not any(blob[off:off+0x80])
capacity=64;assert allocation_bytes(capacity)==4096
vas=[int(v,0) for v in prep['candidate_vas']];aliases=[int(v,0) for v in prep['firmware_aliases']]
newvas=[0x10000d8000+i*16384 for i in range(4)];newaliases=[0xfffffc2000b28000+i*16384 for i in range(4)]
assert not set(newvas)&set(vas) and not set(newaliases)&set(aliases)
assert all(v>>36==vas[-1]>>36 and v>>25==vas[-1]>>25 for v in newvas)
reserved=set(layout.get('owned_page_vas',[]))|{x['gpu_va'] for x in layout.get('mmio_leaves',[])}
assert not set(newaliases)&reserved
# Firmware programs first address into completion ring MMIO; second address is
# the owned firmware alias for CPU-side consumption. This mapping role pairing
# remains a hardware hypothesis, not proof of native provider identity.
blob[off:off+0x80]=populate(bytes(0x80),capacity,list(zip(newvas,newaliases)))
backing+=bytes(4*16384);vas+=newvas;aliases+=newaliases
shutil.copytree(a.candidate,a.output)
for o in layout['objects']:o['input_sha256']=sha(blob[o['arena_offset']:o['arena_offset']+o['input_bytes']])
layout['arena_sha256']=sha(blob)
report=dict(firmware=identity,binary_sha256=sha(raw),capacity=capacity,entry_bytes=64,allocation_bytes=4096,owned_backing_pages=4,
 descriptors=[dict(index=i,hardware_offset=hex(0x2620+i*32),device_va=hex(newvas[i]),firmware_alias=hex(newaliases[i]),backing_page=52+i) for i in range(4)],
 producers=['89cd420..89cd448 virtuald68','G16X vtable ->89d76c0 populateKSMCompletionQueue','private_completion_queue.populate checked numeric layout'],
 consumers=['15ed0..16070 completion ring programming','15dxx completion drain'],
 changed_graph_bytes=sum(x!=y for x,y in zip(before,blob)),
 qualification='Four owned 64-entry rings, descriptors in native layout. Capacity64 and device/FW mapping roles experimental; controller routing/teardown/valid GPU completion/rendering unverified. Native TA/3D/NOP work unchanged.')
layout['hardware_completion_trial']=report;prep['hardware_completion_trial']=report
prep.update(pages=56,bytes=len(backing),data_sha256=sha(backing),candidate_vas=[hex(v) for v in vas],firmware_aliases=[hex(v) for v in aliases])
h='#define RENDER_HW_COMPLETION_FIRST 52U\n#define RENDER_FW_ALIASES 1\n#define RENDER_BACKING_PAGES 56U\n#define RENDER_EXTRA_PAGES 62U\n'
h+='static const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,35};\n'
for name,values in [('render_vas',vas),('render_fw_aliases',aliases)]:h+='static const u64 '+name+'[]={'+','.join(hex(v)+'ULL' for v in values)+'};\n'
h+='static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(backing) if v)+'};\n'
prep['header_sha256']=sha(h.encode())
g=(a.output/'graph-contract.h').read_text().split('static const u8 graph_bytes[')[0]
g+=f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join('['+hex(i)+']='+hex(v)+',\n' for i,v in enumerate(blob) if v)+'};\n'
for name,data in [('backing.bin',backing),('graph-before.bin',blob)]: (a.output/name).write_bytes(data)
for name,data in [('render-data.h',h),('graph-contract.h',g)]: (a.output/name).write_text(data)
for name,data in [('preparation.json',prep),('graph-receipt.json',layout)]: (a.output/name).write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(report,indent=2))
