#!/usr/bin/env python3
"""Exercise capture decoder wrap, missing backing, bad status and opaque payloads."""
import importlib.util,struct,unittest
from pathlib import Path
from firmware_completion import describe,decode_entry
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('decode-completion-capture.py'))
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)

class CaptureTests(unittest.TestCase):
 def test_wrapping(self):
  hw=bytearray(0x4000);ring=b''.join(struct.pack('<8Q',i,0,0,0,0,0,0,0) for i in range(3))
  hw[0x2620:0x2640]=struct.pack('<QQIIII',0x10000,0x20000,3,64,0,2)
  decoded=capture.decode(hw,[(2<<16)|2,0,0,0],[ring,None,None,None]);q=decoded['queues'][0]
  self.assertEqual(q['entry_offsets'],[128,0]);self.assertEqual(q['next_cursor'],1)
  self.assertEqual(q['invalidate_ranges'],[(128,64),(0,64)]);self.assertFalse(decoded['retirement_verified'])
  self.assertEqual([e['low_kind'] for e in q['entries']],[2,0])
 def test_bad_capture(self):
  hw=bytearray(0x4000);hw[0x2620:0x2640]=struct.pack('<QQIIII',1,2,3,64,0,0)
  for status in [4<<16,3,0]:
   with self.assertRaises(ValueError):capture.decode(hw,[status,0,0,0],[None]*4)
  with self.assertRaises(ValueError):capture.decode(hw,[0]*4,[bytes(64),None,None,None])
  with self.assertRaises(ValueError):capture.decode(hw,[True,0,0,0],[bytes(192),None,None,None])
 def test_metadata(self):
  word=(0xab<<48)|(0x12345678<<16)|(127<<9)|(3<<6)|(2<<4)|1
  decoded=decode_entry(struct.pack('<8Q',word,0,0,0,(1<<64)-1,(1<<63),0x8001,0x9000))
  self.assertEqual(decoded['epoch'],0x12345678ab);self.assertEqual(decoded['metadata_offset'],0xab*512)
  self.assertEqual((decoded['queue_id'],decoded['phase'],decoded['mode']),(127,2,3))
  self.assertEqual((decoded['pointer30'],decoded['flag30'],decoded['pointer38']),(0x8000,1,0x9000))
 def test_full_ring(self):
  plan=describe(struct.pack('<QQIIII',1,2,3,64,0,2),(3<<16)|0)
  self.assertEqual(plan['entry_offsets'],[128,0,64]);self.assertEqual(plan['next_cursor'],2)
  self.assertFalse(plan['cursor_agrees_with_head']);self.assertEqual(plan['invalidate_ranges'],[(0,192),(128,0),(0,0)])

if __name__=='__main__':unittest.main()
