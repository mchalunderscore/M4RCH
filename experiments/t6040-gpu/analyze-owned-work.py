#!/usr/bin/env python3
"""Decode a completed owned work candidate capture without inferring rendering.

Cursors and changed memory are intermediate evidence. GPU completion/pixels
require independent event/stamp and image-layout validation.
"""
from pathlib import Path
import argparse,json,struct,hashlib
from firmware_text_contract import qualify
p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
prep=json.loads((a.candidate/'preparation.json').read_text());before=(a.candidate/'backing.bin').read_bytes();owned=(a.capture/'owned-after.bin').read_bytes();attempt=json.loads((a.capture/'attempt.json').read_text());layout=json.loads((a.candidate/'graph-receipt.json').read_text());graph=(a.capture/'objects-after.bin').read_bytes()
assert prep['pages']==52 and len(owned)==170*16384 and len(before)==52*16384
assert hashlib.sha256(before).hexdigest()==prep['data_sha256']
# ARRAY_SIZE(owned) layout from matched command-pool-map.h; never physical scans.
render_first=112;after=owned[render_first*16384:(render_first+52)*16384];base=int(layout['base'],0)
root=[]
for index in [0,1,12]:
 c=layout['empty_channel_fixture'][index]['cursors'];root.append(dict(channel=index,cursors=[struct.unpack_from('<I',graph,int(v,0)-base)[0] for v in c]))
queues=[]
for j,q in enumerate(prep['owned_scheduler']):
 off=(48+j*2)*16384;meta=after[off:off+16384];old=before[off:off+16384];queues.append(dict(stage=q['stage'],chosen_queue_id=q['queue_id'],completed_cursor=struct.unpack_from('<I',meta,0x100)[0],prefetch_cursor=struct.unpack_from('<I',meta,0x130)[0],host_producer=struct.unpack_from('<I',meta,0x140)[0],sentinel50=hex(struct.unpack_from('<I',meta,0x150)[0]),state_firmware_cursors=[struct.unpack_from('<I',meta,v)[0] for v in [0x18,0x1c,0x20]],changed_bytes=sum(x!=y for x,y in zip(old,meta))))
changed=[]
for i in range(52):
 l=before[i*16384:(i+1)*16384];r=after[i*16384:(i+1)*16384];offsets=[k for k,(x,y) in enumerate(zip(l,r)) if x!=y]
 if offsets:changed.append(dict(page=i,device_va=prep['candidate_vas'][i],changed_bytes=len(offsets),first_changed_offsets=[hex(x) for x in offsets[:32]]))
target=after[20*16384:21*16384];initial=before[20*16384:21*16384];completion=after[47*16384:48*16384]
a.output.mkdir(exist_ok=False);(a.output/'target-after.bin').write_bytes(target);(a.output/'completion-after.bin').write_bytes(completion)
r=dict(boot_id=attempt['boot_id'],candidate_module_sha256=attempt['validated_build_receipt']['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],root_channels=root,queues=queues,changed_backing_pages=changed,target_changed_bytes=sum(x!=y for x,y in zip(initial,target)),target_sha256=hashlib.sha256(target).hexdigest(),completion_changed_bytes=sum(x!=y for x,y in zip(before[47*16384:48*16384],completion)),work_notification_sent='m4rch joined-work: EP33 notification' in (a.capture/'dmesg-after.log').read_text(),reboot_required=attempt['reboot_required'],qualification='Post-return non-atomic owned-memory capture. Root-channel consumption, job pointer prefetch/completion cursors and changed target storage are distinct evidence; none alone proves GPU execution, valid shader completion or a rendered triangle. Context/backing remain pinned.')
r['firmware_identity']=qualify((a.capture/'text.bin').read_bytes())
data=(a.capture/'data-after.bin').read_bytes()
prior=(a.capture/'data-before.bin').read_bytes()
def word(blob,address,fmt):return struct.unpack_from('<'+fmt,blob,address-0x60000)[0]
r['firmware_scheduler']=dict(queues=[],added_kick_counter_before=word(prior,0x13c390,'I'),added_kick_counter_after=word(data,0x13c390,'I'),crashlog_header_present=data[0xa0000:0xa0004]==b'EHLC',qualification='Matched opcode15 handler installs a40-byte row at13dbd8+queueID*40 only if config1a is nonzero. Opcode14 increments13c390 by its count; that counter does not prove hardware execution. These are post-shutdown snapshots.')
for j,q in enumerate(prep['owned_scheduler']):
 row=0x13dbd8+q['queue_id']*40
 r['firmware_scheduler']['queues'].append(dict(stage=q['stage'],queue_id=q['queue_id'],config_install_flag=word(before,0x60000+(48+j*2)*16384+0x101a,'I'),installed_flags=word(data,row,'B'),firmware_ring=hex(word(data,row+8,'Q')),device_ring=hex(word(data,row+16,'Q')),header_word=word(data,row+24,'I'),encoded_geometry=word(data,row+28,'I'),data_master=word(data,row+32,'I'),row_changed_bytes=sum(x!=y for x,y in zip(prior[row-0x60000:row-0x60000+40],data[row-0x60000:row-0x60000+40]))))
(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
