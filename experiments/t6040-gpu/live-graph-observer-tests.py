#!/usr/bin/env python3
"""Evidence integrity checks for the live owned-RAM observer."""
import json,tempfile,unittest
from pathlib import Path
from live_graph_observer import observe
class ObserverTests(unittest.TestCase):
 def test_changed_frame_and_object_attribution(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);raw=p/'raw';raw.write_bytes(bytes(32))
   class Done:
    count=0
    def is_set(self):return self.count>=2
    def wait(self,_):
     self.count+=1
     if self.count==1:raw.write_bytes(bytes(16)+b'\1'+bytes(15))
   r=observe(raw,p/'out',{'arena_bytes':32,'objects':[{'name':'a','arena_offset':0,'reserved_bytes':16},{'name':'b','arena_offset':16,'reserved_bytes':16}]},Done())
   self.assertEqual(len(r['frames']),2);self.assertEqual(r['errors'],[])
   self.assertEqual(r['frames'][1]['changed_objects'],[{'name':'b','changed_bytes':1}])
   self.assertEqual((p/'out/001.bin').read_bytes(),raw.read_bytes())
 def test_wrong_extent_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);raw=p/'raw';raw.write_bytes(bytes(7))
   class Done:
    def is_set(self):return False
    def wait(self,_):pass
   r=observe(raw,p/'out',{'arena_bytes':8,'objects':[]},Done())
   self.assertEqual(r['frames'],[]);self.assertEqual(r['errors'],['Live graph extent changed'])
if __name__=='__main__':unittest.main()
