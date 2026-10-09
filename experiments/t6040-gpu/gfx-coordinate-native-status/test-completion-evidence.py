#!/usr/bin/env python3
"""RAM-only catalog/capture integration; no claims of observed GPU completion."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import shutil
import tempfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=HERE/'analyze-completion-evidence.py';spec=importlib.util.spec_from_file_location('completion_catalog',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 candidate=ROOT/'out/gfx-coordinate-native-status/candidate';g=candidate/'asc-graph-init'
 prep=json.loads((g/'preparation.json').read_text());layout=json.loads((g/'graph-receipt.json').read_text())
 graph=(g/'graph-before.bin').read_bytes();backing=(g/'backing.bin').read_bytes();header=(g/'job-data.h').read_text()
 owned=bytearray(174*16384);owned[112*16384:168*16384]=backing
 cases=[]
 def run(name,gr=graph,ow=None,pp=None,lg=''):
  result=m.catalog(prep if pp is None else pp,layout,graph,backing,gr,owned if ow is None else ow,header,lg)
  assert result['gpu_execution_verified'] is False and result['retirement_verified'] is False
  assert result['entries_confirmed_available_or_consumed'] is False
  cases.append(name);return result
 zero=run('unchanged-four-rings');assert zero['changed_slot_count']==0
 commands=zero['prepared_commands'];cmd=next(x for x in commands if x['stage']=='3d')
 for ring in range(4):
  for slot in [0,63]:
   b=bytearray(owned);entry=bytearray(64)
   word=(cmd['chosen_queue_id']<<9)|((cmd['timestamp_low40']>>8)<<16)|((cmd['timestamp_low40']&255)<<48)|0x10
   struct.pack_into('<Q',entry,0,word);struct.pack_into('<Q',entry,0x30,cmd['command_fw']|1)
   off=(112+52+ring)*16384+slot*64;b[off:off+64]=entry
   r=run(f'numeric-command-association-ring{ring}-slot{slot}',ow=b)
   assert r['changed_slot_count']==1
   assoc=r['rings'][ring]['changed_slots'][0]['numeric_prepared_pointer_associations']
   assert assoc==[{'stage':'3d','queue_id_equal':True,'epoch_low40_equal':True,'expected_command_kind':1}]
 b=bytearray(owned);off=(112+52)*16384;struct.pack_into('<Q',b,off+0x30,0xdeadbeef)
 r=run('unrelated-pointer-is-not-associated',ow=b);assert not r['rings'][0]['changed_slots'][0]['numeric_prepared_pointer_associations']
 for which,word in [('queue',0),('epoch',1<<49)]:
  b=bytearray(owned);struct.pack_into('<Q',b,off,word);struct.pack_into('<Q',b,off+0x30,cmd['command_fw'])
  r=run('pointer-equal-'+which+'-mismatch',ow=b);assoc=r['rings'][0]['changed_slots'][0]['numeric_prepared_pointer_associations'][0]
  assert not assoc['queue_id_equal'] if which=='queue' else not assoc['epoch_low40_equal']
 b=bytearray(owned);b[off+4096]=1;r=run('unused-tail-change-is-separate',ow=b)
 assert r['changed_slot_count']==0 and r['rings'][0]['unused_page_tail_changed_bytes']==1
 hw=next(o for o in layout['objects'] if o['name']=='hardware')['arena_offset']
 for field,value,label in [(16,63,'capacity'),(20,32,'stride'),(24,3,'index'),(28,64,'cursor')]:
  gr=bytearray(graph);struct.pack_into('<I',gr,hw+0x2620+field,value)
  r=run('observed-invalid-'+label+'-preserved-as-evidence',gr=gr)
  assert not r['rings'][0]['descriptor_static_fields_equal'] if label!='cursor' else not r['rings'][0]['observed_cursor_in_capacity']
 log='m4rch hw-completion-register: phase=sample queue=0 config=0x1 status=0x10000\n'
 r=run('separate-status-is-never-paired-atomically',lg=log);assert len(r['logged_hardware_register_observations'])==1 and r['status_and_descriptor_snapshot_atomic'] is False
 for label,gr,ow in [('short-graph',graph[:-1],owned),('short-owned',graph,owned[:-1])]:
  try:m.catalog(prep,layout,graph,backing,gr,ow,header,'')
  except AssertionError:cases.append(label+'-refused')
  else:raise AssertionError(label+' accepted')
 with tempfile.TemporaryDirectory(prefix='gfx-completion-catalog-ram-') as tmp:
  cap=Path(tmp);blobs={'objects-after.bin':graph,'owned-after.bin':bytes(owned),'dmesg-after.log':b''}
  for name,b in blobs.items():(cap/name).write_bytes(b)
  receipt=json.loads((candidate/'asc-root-envelope/build-receipt.json').read_text())
  report={'boot_id':'RAM-ONLY-NO-HARDWARE','validated_build_receipt':receipt,'submit_attempted':True,
   'final_capture':{k:{'sha256':sha(blobs[n])} for k,n in [('objects','objects-after.bin'),('owned','owned-after.bin'),('dmesg','dmesg-after.log')]}}
  def save():(cap/'attempt.json').write_text(json.dumps(report))
  save();r=m.analyze(candidate,cap);assert r['changed_slot_count']==0;cases.append('actual-bound-analysis-pipeline-in-RAM')
  for name in blobs:
   original=(cap/name).read_bytes();(cap/name).write_bytes(original+b'X')
   try:m.analyze(candidate,cap)
   except AssertionError:cases.append('changed-capture-'+name+'-refused')
   else:raise AssertionError('Changed capture accepted')
   (cap/name).write_bytes(original)
  clone=cap/'candidate-clone';shutil.copytree(candidate,clone)
  metadata=clone/'asc-graph-init/graph-receipt.json';original=metadata.read_bytes()
  changed=json.loads(original);changed['objects'][0]['arena_offset']+=4;metadata.write_text(json.dumps(changed))
  try:m.analyze(clone,cap)
  except AssertionError:cases.append('changed-in-bounds-graph-metadata-refused')
  else:raise AssertionError('Changed graph metadata accepted')
  metadata.write_bytes(original)
  fixture=clone/'asc-graph-init/graph-before.bin';original=fixture.read_bytes();fixture.write_bytes(b'X'+original[1:])
  try:m.analyze(clone,cap)
  except AssertionError:cases.append('changed-graph-fixture-refused')
  else:raise AssertionError('Changed graph fixture accepted')
  report['submit_attempted']=False;save()
  try:m.analyze(candidate,cap)
  except AssertionError:cases.append('no-work-intent-refused')
  else:raise AssertionError('No-work capture accepted')
 files=[p,Path(__file__),HERE.parent/'firmware_completion.py',candidate/'asc-root-envelope/build-receipt.json',candidate/'native-status-preparation.json']+[g/n for n in ['preparation.json','graph-receipt.json','graph-before.bin','backing.bin','job-data.h']]
 result={'schema':'m4rch.gfx-native-status-completion-evidence-qualification.v1','passed':True,'hardware_access':False,
  'case_count':len(cases),'cases':cases,'fixtures':'Synthetic RAM only using immutable prepared bytes. No new GPU execution/capture.',
  'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in files],
  'qualification':'Actual catalog/capture pipeline. Numeric pointer/epoch matches remain explicitly unverified completion; changed slots, tail changes and separate non-atomic status preserve evidence. No live read, write, publication, callback or retirement.'}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'case_count':len(cases),'receipt':str(a.output),'hardware_access':False}))


if __name__=='__main__':main()
