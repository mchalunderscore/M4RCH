#!/usr/bin/env python3
"""Stage native fragment bit254 hold and opcode16 release, offline only.

This optional native sequence is an experimental comparison to the no-hold path,
not a proven required initialization fix. Preserve actual command/register data.
"""
from pathlib import Path
import argparse,hashlib,json,struct,shutil
from firmware_text_contract import qualify
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('candidate',type=Path);p.add_argument('firmware_text',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
identity=qualify(a.firmware_text.read_bytes())
prep=json.loads((a.candidate/'preparation.json').read_text());data=bytearray((a.candidate/'backing.bin').read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(data)==prep['data_sha256'] and len(data)==52*16384
q=prep['owned_scheduler'][1];assert q['queue_id']==1
meta=50*16384;work=51*16384+512;fw=int(q['state_fw'],0)
assert struct.unpack_from('<Q',data,work+0x140)[0]==0
struct.pack_into('<Q',data,work+0x140,1<<62)
assert not any(data[meta+0x1200:meta+0x1240])
struct.pack_into('<IHQI',data,meta+0x1200,16,1,1,254)
assert struct.unpack_from('<I',data,meta+0x140)[0]==2
struct.pack_into('<I',data,meta+0x140,3)
struct.pack_into('<Q',data,meta+0x410,fw+0x1200)
shutil.copytree(a.candidate,a.output)
h=(a.output/'render-data.h').read_text();marker='static const u8 render_bytes['
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
q.update(pointer_publications=q['pointer_publications']+[hex(fw+0x1200)],pointer_producer=3,job_pointer_producer=3,entry_signal=dict(timestamp=1,bit=254,held_word='0x140',held_bit=62))
blob=bytearray((a.output/'graph-before.bin').read_bytes());layout=json.loads((a.output/'graph-receipt.json').read_text());base=int(layout['base'],0);ch=layout['empty_channel_fixture'][1];ring=int(ch['ring'],0)-base
assert struct.unpack_from('<I',blob,ring+20)[0]==2|(1<<16)|(1<<24)
struct.pack_into('<I',blob,ring+20,3|(1<<16)|(1<<24))
for o in layout['objects']:o['input_sha256']=sha(blob[o['arena_offset']:o['arena_offset']+o['input_bytes']])
layout['arena_sha256']=sha(blob);layout['joined_work_fixture']['records_per_queue']=['TA config15/add2','fragment config15/add2/entry-signal16'];layout['joined_work_fixture']['qualification']='Native optional fragment hold254/release16 comparison; no presumed required fix or draw proof.'
g=(a.output/'graph-contract.h').read_text();marker2='static const u8 graph_bytes['
g=g.split(marker2)[0]+f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join('['+hex(i)+']='+hex(v)+',\n' for i,v in enumerate(blob) if v)+'};\n'
report=dict(firmware=identity,queue=1,timestamp=1,signal_bit=254,held_word='0x140',held_bit=62,transport_order=['config15','add-kicks14 count2','entry-signal16'],qualification='Native optional hold/release path. Matched firmware195c8/19618/196ac clears bit254 in selected512-byte record, pauses/unpauses scheduling and refreshes211d8/211e0. No direct host scheduling write. Translation/execution/completion remain unproved.')
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),work_publication=layout['joined_work_fixture'],entry_signal_trial=report)
for n,b in [('backing.bin',data),('graph-before.bin',blob)]: (a.output/n).write_bytes(b)
for n,t in [('render-data.h',h),('graph-contract.h',g)]: (a.output/n).write_text(t)
(a.output/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n');(a.output/'graph-receipt.json').write_text(json.dumps(layout,indent=2)+'\n');print(json.dumps(report,indent=2))
