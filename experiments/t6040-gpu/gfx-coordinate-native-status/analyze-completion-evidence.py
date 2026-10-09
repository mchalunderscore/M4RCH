#!/usr/bin/env python3
"""Decode saved owned completion slots; numeric associations, no GPU/retirement claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
from firmware_completion import decode_entry
sys.path.insert(0,str(HERE))
from gfx_native_status_contract import validate_receipt
PAGE=16384
RENDER_FIRST=112


def sha(data):return hashlib.sha256(data).hexdigest()


def prepared_commands(header,prep):
 count=int(re.search(r'#define JOB_COUNT (\d+)U',header).group(1))
 extent=int(re.search(r'#define COMMAND_BYTES (0x[0-9a-f]+)U',header).group(1),0)
 base=int(re.search(r'#define FW_BASE (0x[0-9a-f]+)ULL',header).group(1),0)
 assert (count,extent)==(64,0x2240),'Unqualified command pool layout'
 body=header.split('static const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={',1)[1]
 records=re.findall(r'\{([^{}]*)\}',body);assert len(records)==count
 commands=[]
 for index,record in enumerate(records[:2]):
  command=bytearray(extent);seen=set()
  for offset,value in re.findall(r'\[(0x[0-9a-f]+)\]=(0x[0-9a-f]+)',record):
   offset,value=int(offset,0),int(value,0)
   assert offset not in seen and offset<extent and value<=255
   seen.add(offset);command[offset]=value
  assert sha(command)==prep['integrated_pair']['command_sha256'][index]
  stage='3d' if index==0 else 'ta'
  matches=[q for q in prep['owned_scheduler'] if q['stage']==stage];assert len(matches)==1
  commands.append({'stage':stage,'command_fw':base+index*extent,
   'command_kind':struct.unpack_from('<I',command)[0],
   'timestamp_low40':struct.unpack_from('<Q',command,0x2160 if index==0 else 0x7a8)[0]&((1<<40)-1),
   'chosen_queue_id':matches[0]['queue_id'],'sha256':sha(command)})
 return commands


def catalog(prep,layout,initial_graph,initial_backing,graph,owned,header,log):
 assert prep['pages']==56 and len(initial_backing)==56*PAGE
 assert len(owned)==174*PAGE and len(graph)==len(initial_graph)==layout['arena_bytes']
 assert sha(initial_backing)==prep['data_sha256'] and sha(initial_graph)==layout['arena_sha256']
 hardware=[o for o in layout['objects'] if o['name']=='hardware'];assert len(hardware)==1
 h=hardware[0];assert h['reserved_bytes']==PAGE and h['input_bytes']>=0x26a0
 start=h['arena_offset'];commands=prepared_commands(header,prep);render=owned[RENDER_FIRST*PAGE:(RENDER_FIRST+56)*PAGE]
 descriptors=prep['hardware_completion_trial']['descriptors'];assert len(descriptors)==4
 queues=[]
 for index,descriptor in enumerate(descriptors):
  assert descriptor['index']==index and descriptor['backing_page']==52+index
  off=start+int(descriptor['hardware_offset'],0);assert off==start+0x2620+index*32
  original=struct.unpack_from('<QQIIII',initial_graph,off)
  assert original==(int(descriptor['device_va'],0),int(descriptor['firmware_alias'],0),64,64,index,0)
  observed=struct.unpack_from('<QQIIII',graph,off)
  page=52+index;before=initial_backing[page*PAGE:(page+1)*PAGE];after=render[page*PAGE:(page+1)*PAGE]
  slots=[]
  for slot in range(64):
   b=before[slot*64:(slot+1)*64];a=after[slot*64:(slot+1)*64]
   if a==b:continue
   decoded=decode_entry(a)
   associations=[]
   for command in commands:
    if decoded['pointer30']==command['command_fw']:
     associations.append({'stage':command['stage'],'queue_id_equal':decoded['queue_id']==command['chosen_queue_id'],
      'epoch_low40_equal':decoded['epoch']==command['timestamp_low40'],'expected_command_kind':command['command_kind']})
   slots.append({'slot':slot,'changed_bytes':sum(x!=y for x,y in zip(a,b)),'sha256':sha(a),
    'decoded':decoded,'numeric_prepared_pointer_associations':associations})
  queues.append({'ring':index,'backing_page':page,'descriptor_words':list(observed),
   'descriptor_static_fields_equal':observed[:5]==original[:5],
   'observed_cursor_in_capacity':observed[5]<64,'observed_cursor':observed[5],
   'active_ring_changed_bytes':sum(x!=y for x,y in zip(before[:4096],after[:4096])),
   'unused_page_tail_changed_bytes':sum(x!=y for x,y in zip(before[4096:],after[4096:])),
   'changed_slots':slots})
 statuses=[]
 pattern=r'm4rch hw-completion-register: phase=(\S+) queue=(\d+) config=(0x[0-9a-f]+|0) status=(0x[0-9a-f]+|0)'
 for match in re.finditer(pattern,log):
  phase,index,config,status=match.groups();statuses.append({'phase':phase,'ring':int(index),'config':int(config,0),'status':int(status,0)})
 return {'schema':'m4rch.gfx-native-status-owned-completion-evidence.v1','prepared_commands':commands,
  'rings':queues,'logged_hardware_register_observations':statuses,'changed_slot_count':sum(len(q['changed_slots']) for q in queues),
  'status_and_descriptor_snapshot_atomic':False,'entries_confirmed_available_or_consumed':False,
  'gpu_execution_verified':False,'retirement_verified':False,
  'qualification':'Saved owned-RAM catalog only. Changed slots may be stale, partial, already consumed or unrelated. Pointer/queue/epoch equality is numeric association, not completed-job identity, eligibility, callback delivery or retirement. Logged MMIO status and final descriptor/ring snapshots are separate non-atomic observations; no read acknowledgement, ring cursor mutation or hardware access.'}


def analyze(candidate,capture):
 receipt_path=candidate/'asc-root-envelope/build-receipt.json';receipt=json.loads(receipt_path.read_text())
 assert validate_receipt(receipt),'Distinct native-status candidate required'
 bound=json.loads((candidate/'native-status-preparation.json').read_text());assert sha(receipt_path.read_bytes())==bound['candidate_receipt_sha256']
 for name,expected in receipt['artifact_sha256'].items():assert sha((candidate/name).read_bytes())==expected,name
 for name,expected in receipt['graph_source_sha256'].items():assert sha((candidate/'asc-graph-init'/name).read_bytes())==expected,name
 for row in bound['analysis_input_pins']:assert sha((candidate/row['relative']).read_bytes())==row['sha256']
 report=json.loads((capture/'attempt.json').read_text());assert report['validated_build_receipt']==receipt
 assert report['submit_attempted'] is True,'No saved work intent'
 for key,name in [('objects','objects-after.bin'),('owned','owned-after.bin'),('dmesg','dmesg-after.log')]:
  assert sha((capture/name).read_bytes())==report['final_capture'][key]['sha256'],name
 graph=candidate/'asc-graph-init'
 assert sha((graph/'graph-before.bin').read_bytes())==receipt['graph_fixture_sha256'],'Graph fixture changed'
 assert sha((graph/'graph-receipt.json').read_bytes())==receipt['graph_receipt_sha256'],'Graph receipt changed'
 result=catalog(json.loads((graph/'preparation.json').read_text()),json.loads((graph/'graph-receipt.json').read_text()),
  (graph/'graph-before.bin').read_bytes(),(graph/'backing.bin').read_bytes(),
  (capture/'objects-after.bin').read_bytes(),(capture/'owned-after.bin').read_bytes(),
  (graph/'job-data.h').read_text(),(capture/'dmesg-after.log').read_text())
 result.update(boot_id=report['boot_id'],candidate_receipt_sha256=sha(receipt_path.read_bytes()),
  input_pins=[{'path':str(p),'sha256':sha(p.read_bytes())} for p in [Path(__file__),HERE.parent/'firmware_completion.py',receipt_path,
   candidate/'native-status-preparation.json',capture/'attempt.json',capture/'objects-after.bin',capture/'owned-after.bin',capture/'dmesg-after.log']])
 return result


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ['candidate','capture','output']:ap.add_argument(name,type=Path)
 a=ap.parse_args();candidate=a.candidate.resolve();output=a.output.resolve()
 assert not output.exists(),'Preserve existing analysis'
 assert output!=candidate and candidate not in output.parents,'Output must be outside the frozen candidate'
 result=analyze(candidate,a.capture.resolve());a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'output':str(a.output),'changed_slot_count':result['changed_slot_count'],'gpu_execution_verified':False,'retirement_verified':False}))


if __name__=='__main__':main()
