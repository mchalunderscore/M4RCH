#!/usr/bin/env python3
"""Summarize a completed native capture against its exact pre-trial fixture.

Read-only/offline; cursor consumption does not establish rendering readiness.
"""
import argparse, hashlib, json, struct
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('capture',type=Path)
p.add_argument('candidate',type=Path)
p.add_argument('output',type=Path)
a=p.parse_args()
receipt=json.loads((a.candidate/'graph-receipt.json').read_text())
attempt=json.loads((a.capture/'attempt.json').read_text())
before=(a.capture/'objects-before.bin').read_bytes()
after=(a.capture/'objects-after.bin').read_bytes()
fixture=(a.candidate/'graph-before.bin').read_bytes()
digest=hashlib.sha256(fixture).hexdigest()
if before!=fixture or digest!=attempt['validated_build_receipt']['graph_fixture_sha256']:
 raise ValueError('Candidate does not match the actual native trial')
if len(after)!=receipt['arena_bytes']:raise ValueError('Wrong object capture extent')
base=int(receipt['base'],16);channel=receipt['empty_channel_fixture'][12]
def cursors(data):return [struct.unpack_from('<I',data,int(x,16)-base)[0] for x in channel['cursors']]
count=receipt['control_refresh'].get('count',1)
ring=int(channel['ring'],16)-base
if cursors(before)!=[0,0,count] or not 1<=count<=32:raise ValueError('Unqualified producer/cursors')
for i in range(count):
 if before[ring+i*64:ring+(i+1)*64]!=struct.pack('<I',0x16)+bytes(60):
  raise ValueError('Unexpected control record')
data=(a.capture/'data-after.bin').read_bytes()
log=(a.capture/'dmesg-after.log').read_text()
live=attempt['live_observation']
result=dict(boot_id=attempt['boot_id'],trial_fixture_sha256=digest,
 trial_module_sha256=attempt['validated_build_receipt']['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],
 load_returncode=attempt['load_returncode'],root_published=attempt['root_published'],
 command=dict(opcode='0x16',records=count,record_bytes=64),
 control_cursors_before=cursors(before),control_cursors_after=cursors(after),
 all_control_records_consumed=cursors(after)==[count]*3,
 control_records_unchanged=after[ring:ring+count*64]==before[ring:ring+count*64],
 crashlog_header_present=data[0xa0000:0xa0004]==b'EHLC',
 observation_log=[line for line in log.splitlines() if 'observation messages=' in line],
 live_frames=len(live['frames']),unique_frame_hashes=sorted({f['sha256'] for f in live['frames']}),
 observer_errors=live['errors'],changed_objects=[o for o in attempt['object_changes'] if o['changed_bytes']],
 refresh_private_state={hex(off):struct.unpack_from('<I',data,off-0x60000)[0] for off in (0x18eec8,0x146908,0x146914)},
 reboot_required=attempt['reboot_required'],
 qualification='Native consumption of the operand-free initial refresh fixture only. No crash header/fatal notification during this bounded capture is not proof of full initialization, receive channels, job execution, interrupts, GPU acceleration or safe retirement.')
a.output.write_text(json.dumps(result,indent=2)+'\n')
print('Control cursors',result['control_cursors_after'],'consumed',result['all_control_records_consumed'],'crash header',result['crashlog_header_present'])
