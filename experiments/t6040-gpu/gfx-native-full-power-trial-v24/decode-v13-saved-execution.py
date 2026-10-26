#!/usr/bin/env python3
"""Decode retained v13 queue changes offline; no hardware access."""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('session',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
before=(a.candidate/'asc-graph-init/backing.bin').read_bytes();after=(a.session/'owned-after.bin').read_bytes();analysis=json.loads((a.session/'analysis/result.json').read_text())
prep=json.loads((a.candidate/'asc-graph-init/preparation.json').read_text());assert len(after)==176*0x4000 and len(before)==56*0x4000
rows=[]
for i,q in enumerate(prep['owned_scheduler']):
 page=48+i*2;old=before[page*0x4000:(page+1)*0x4000];new=after[(page+112)*0x4000:(page+113)*0x4000]
 changed=[{'offset':o,'before':old[o],'after':new[o]}for o in range(0x4000)if old[o]!=new[o]]
 ringold=before[(page+1)*0x4000:(page+2)*0x4000];ringnew=after[(page+113)*0x4000:(page+114)*0x4000]
 rows.append({'stage':q['stage'],'queue_id':q['queue_id'],'state_changed_bytes':changed,
 'accepted_pointer_read':struct.unpack_from('<I',new,0x100)[0],'accepted_pointer_done':struct.unpack_from('<I',new,0x130)[0],
 'hardware_ring_changed_offsets':[o for o in range(0x4000)if ringold[o]!=ringnew[o]],
 'nop_timestamp':q['nop_timestamp'],'nop_previous':q['nop_previous'],'config_baseline':q['baseline'],
 'scope':'Cursor acceptance and unchanged record bytes do not prove that hardware fetched or executed any entry.'})
d={'schema':'m4rch.v24-v13-saved-execution.v1','boot_id':analysis['boot_id'],
 'inputs':{'backing_sha256':sha(before),'owned_after_sha256':sha(after)},'queues':rows,
 'ksm_status':analysis['raw_post_submit_observations']['ksm-status'],
 'ksm_live':analysis['raw_post_submit_observations']['ksm-live'],
 'target_changed_pixels':analysis['whole_image']['changed_pixels'],'hardware_actions':[],
 'finding':'Both firmware pointer queues consumed. No KSM completion or pixels. Zero NOP previous/config baseline retained from earlier experimental trial. Root transport consumption alone cannot establish execution.',
 'joined_normal_caller_fix':'Use one retained per-lane event identity. Native conversion of epoch/event/initial must equal submitted KSM timeline; first previous derives conversion minus1. Donor TA event seed0xc00 and hardcoded epoch1 mismatch native initial timeline.',
 'hardware_cause_proved':False}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n');print(a.output)
