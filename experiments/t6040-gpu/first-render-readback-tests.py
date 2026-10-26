#!/usr/bin/env python3
"""Verify rejection of untouched/partial/corrupt target captures; no GPU access."""
import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('readback',Path(__file__).with_name('check-first-render-readback.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
receipt=json.loads((Path(__file__).resolve().parents[2]/'docs/evidence/2026-10-08-apple9-target-preparation.json').read_text())
def fixture():
 bg=bytes(round(max(0,min(1,f))*255) for f in receipt['background_candidate']['float_rgba']);b=bytearray(bg*(receipt['target']['bytes']//4))
 for r in receipt['interior_reference_samples']:b[r['linear_offset']:r['linear_offset']+4]=bytes(r['rgba8_nearest'])
 return b
class Checks(unittest.TestCase):
 def test_reference(self):self.assertTrue(m.check(receipt,fixture())['passed'])
 def test_sentinel(self):self.assertFalse(m.check(receipt,bytes([165])*16384)['passed'])
 def test_short(self):self.assertFalse(m.check(receipt,bytes(16380))['passed'])
 def test_extra(self):self.assertFalse(m.check(receipt,bytes(16388))['passed'])
 def test_partial(self):
  b=bytearray(bytes([165])*16384);r=receipt['interior_reference_samples'][0];b[r['linear_offset']:r['linear_offset']+4]=bytes(r['rgba8_nearest']);self.assertFalse(m.check(receipt,b)['passed'])
 def test_every_sample_channel(self):
  for sample in m.check(receipt,fixture())['samples']:
   for channel in range(4):
    b=fixture();x,y=sample['pixel_y_up'];off=y*256+x*4+channel;b[off]=(b[off]+64)&255
    with self.subTest(pixel=[x,y],channel=channel):self.assertFalse(m.check(receipt,b)['passed'])
 def test_quantization_tolerance(self):
  b=fixture();r=receipt['interior_reference_samples'][0];b[r['linear_offset']]+=2;self.assertTrue(m.check(receipt,b)['passed']);b[r['linear_offset']]+=1;self.assertFalse(m.check(receipt,b)['passed'])
 def test_wrong_stride(self):
  r=json.loads(json.dumps(receipt));r['target']['stride_bytes']=128;self.assertFalse(m.check(r,fixture())['passed'])
unittest.main()
