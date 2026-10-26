#!/usr/bin/env python3
"""Reject input truncation and geometry errors before scheduler serialization."""
import copy,json,unittest
from pathlib import Path
from native_scheduler_candidate import prepare
root=Path(__file__).resolve().parents[2]
binding=json.loads((root/'docs/evidence/2026-10-08-native-scheduler-candidate.json').read_text())['examples'][0]['binding']
class CandidateValidation(unittest.TestCase):
 def test_valid_zero_backing(self):
  work,queue,receipt=prepare(binding);self.assertEqual(len(work),0x200);self.assertEqual(len(queue),0x100);self.assertFalse(receipt['submission_ready'])
 def test_reject_loss_and_invalid_geometry(self):
  changes=[(('queue','id'),128),(('queue','priority'),4),(('queue','capacity'),0),(('queue','capacity'),257),(('queue','pending'),binding['queue']['capacity']),(('queue','pending'),-1),(('queue','timestamp'),1<<64),(('queue','id'),2.5),(('queue','id'),True),(('aperture','count'),65),(('aperture','index'),64),(('aperture','address'),1),(('qos',0),256),(('qos',1),65536),(('qos',2),32),(('rce_kind',),4),(('extra_flag',),1),(('alternate_kind',),0),(('register_lists',0,'count'),128),(('register_lists',0,'address'),3),(('register_lists',0,'address'),0),(('register_lists',0,'count'),0)]
  for path,value in changes:
   b=copy.deepcopy(binding);obj=b
   for key in path[:-1]:obj=obj[key]
   obj[path[-1]]=value
   if path==('aperture','address'):b['aperture']['count']=1
   with self.subTest(path=path,value=value):
    with self.assertRaises(ValueError):prepare(b)
 def test_dependency_boundaries(self):
  for d in [dict(event=1<<32,index=0,epoch=0),dict(event=0,index=24,epoch=0),dict(event=0,index=0,epoch=1<<64)]:
   b=copy.deepcopy(binding);b['dependencies']=[d]
   with self.subTest(dependency=d):
    with self.assertRaises(ValueError):prepare(b)
  b=copy.deepcopy(binding);b['dependencies']=[dict(event=0,index=0,epoch=0)]*9
  with self.assertRaises(ValueError):prepare(b)
if __name__=='__main__':unittest.main()
