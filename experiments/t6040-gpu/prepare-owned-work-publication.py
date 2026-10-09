#!/usr/bin/env python3
"""Join queue config/add-kicks pointer transport and root work notifications.

Offline experimental submission fixture. No live module loading or MMIO.
"""
from pathlib import Path
import argparse,hashlib,json,struct,shutil,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('scheduler_pair',type=Path);p.add_argument('structural_graph',type=Path);p.add_argument('output',type=Path);a=p.parse_args();kit=Path(__file__).resolve().parent;sys.path.insert(0,str(kit));from private_nop_body import patch_cached_body
sha=lambda b:hashlib.sha256(b).hexdigest();src=a.scheduler_pair/'graph';prep=json.loads((src/'preparation.json').read_text());data=bytearray((src/'backing.bin').read_bytes());assert prep['pages']==52 and sha(data)==prep['data_sha256']
a.output.mkdir(exist_ok=False);out=a.output/'graph';shutil.copytree(src,out)
for i,q in enumerate(prep['owned_scheduler']):
 metaoff=(48+i*2)*16384;ringoff=metaoff+16384;fw=int(q['state_fw'],0);kind=q['stage'];qid=q['queue_id']
 meta=bytearray(data[metaoff:metaoff+16384]);ring=bytearray(data[ringoff:ringoff+16384]);work=bytes(ring[:512]);ring[:8192]=bytes(8192)
 nop,nextts=patch_cached_body(bytes(512),0,qid,0,0,[0]*4,[0,0],16);assert nextts==1
 ring[:512]=nop;ring[512:1024]=work
 # Common native transport publisher40; reset50 is UINT_MAX, not producer.
 struct.pack_into('<I',meta,0x140,2);struct.pack_into('<I',meta,0x150,0xffffffff)
 # The full native caller overwrites getDataMaster255 with TA0/fragment1.
 cfg=0x1000;struct.pack_into('<I',meta,cfg+0x22,0 if kind=='ta' else 1)
 struct.pack_into('<I',meta,cfg+0x26,0);struct.pack_into('<Q',meta,cfg+0x2a,0)
 struct.pack_into('<Q',meta,cfg+0x36,0);struct.pack_into('<Q',meta,cfg+0x3e,0xffffffffffffffff)
 struct.pack_into('<I',meta,cfg+0x46,0xffffffff)
 struct.pack_into('<Q',meta,cfg+0x4a,fw+0x200) # explicit owner8b8 firmware-context hypothesis
 for off in [0x52,0x56,0x5a,0x5e]:struct.pack_into('<I',meta,cfg+off,0)
 # Exact fields from qualified native SKSM post-kick: opcode14,count2,oldts1.
 add=bytearray(64);struct.pack_into('<IHHBQI',add,0,14,qid,2,0,1,1)
 meta[0x1100:0x1140]=add
 struct.pack_into('<QQ',meta,0x400,fw+0x1000,fw+0x1100)
 assert struct.unpack_from('<I',meta,0x140)[0]==2 and struct.unpack_from('<I',meta,0x150)[0]==0xffffffff
 assert struct.unpack_from('<QQ',meta,0x400)==(fw+0x1000,fw+0x1100)
 data[metaoff:metaoff+16384]=meta;data[ringoff:ringoff+16384]=ring
 q.update(pointer_publications=[hex(fw+0x1000),hex(fw+0x1100)],pointer_producer_offset='0x40',pointer_producer=2,job_pointer_producer=2,pointer_sentinel_offset='0x50',ksm_work_records=2,nop_timestamp=0,work_timestamp=1,ksm_slot=1,config_data_master=0 if kind=='ta' else 1,config_owner_context='proposed owned firmware context; unqualified8b8 identity')
# Pair-zero firmware work channels0(TA)/1(fragment), one24-byte notification each.
blob=bytearray((a.structural_graph/'graph-before.bin').read_bytes());layout=json.loads((a.structural_graph/'graph-receipt.json').read_text());base=int(layout['base'],0)
for i,q in enumerate(prep['owned_scheduler']):
 ch=layout['empty_channel_fixture'][i];cursor=int(ch['cursors'][2],0)-base;ring=int(ch['ring'],0)-base
 assert struct.unpack_from('<I',blob,cursor)[0]==0 and not any(blob[ring:ring+24])
 struct.pack_into('<QQII',blob,ring,1,int(q['state_fw'],0),i,2|(1<<16)|(1<<24))
 struct.pack_into('<I',blob,cursor,1)
 assert struct.unpack_from('<Q',blob,ring+8)[0]==int(q['state_fw'],0)
for obj in layout['objects']:
 off=obj['arena_offset'];obj['input_sha256']=sha(blob[off:off+obj['input_bytes']])
layout['arena_sha256']=sha(blob);layout['joined_work_fixture']=dict(channels=[0,1],notifications=1,records_per_queue=['opcode15 config','opcode14 add2'],work_kind=['TA0','fragment1'],transport_kick='EP33 message0x0083000000000000',qualification='Initial root work producers1 with explicit provisional queue context/state defaults. A transmitted batch is not proof of valid draw or completion.')
(out/'graph-before.bin').write_bytes(blob);(out/'graph-receipt.json').write_text(json.dumps(layout,indent=2)+'\n')
# Preserve graph mapping/compile contract; replace only arena byte initializer.
g=(out/'graph-contract.h').read_text();marker='static const u8 graph_bytes[';assert marker in g
(out/'graph-contract.h').write_text(g.split(marker)[0]+f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join('['+hex(i)+']='+hex(v)+',\n' for i,v in enumerate(blob) if v)+'};\n')
h=(out/'render-data.h').read_text();marker='static const u8 render_bytes[';assert marker in h
h=h.split(marker)[0]+'static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n';(out/'render-data.h').write_text(h);(out/'backing.bin').write_bytes(data)
prep.update(data_sha256=sha(data),header_sha256=sha(h.encode()),work_publication=layout['joined_work_fixture'],qualification='Prepared combined config/add-kicks transport and native paired KSM work with explicit provisional state/context bindings; no hardware attempt, completion or rendering.')
(out/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n');report=dict(queues=prep['owned_scheduler'],publication=layout['joined_work_fixture'],owned_pages=170,submission_ready=False,hardware_trial=False,remaining=['cold guarded hardware publication and resulting object/cursor/fault/pixel capture','native firmware context/UAT association and service callbacks','shader launch and event/stamp retirement'])
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
