#!/usr/bin/env python3
"""Regression tests against captured instructions, including an undersized object."""
import importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch
KIT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('model',KIT/'emulate-init-parser.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
capture=Path(sys.argv.pop(1))
TEXT=(capture/'text.bin').read_bytes();DATA=(capture/'data-before.bin').read_bytes()
class ParserTests(unittest.TestCase):
 def test_disabled_matches_observed_native_rejection(self):
  result=model.run(TEXT,DATA)
  self.assertEqual(result['outcome'],'firmware-fatal-path')
  fatal=next(e for e in result['substituted_or_omitted_operations'] if e['kind']=='fatal-diagnostic')
  self.assertIn('Host-mapped FW allocations are disabled',fatal['format'])
  self.assertFalse(any(a['object']!='root' for a in result['object_accesses']))
 def test_enabled_returns_without_extent_violation(self):
  result=model.run(TEXT,DATA,True)
  self.assertEqual(result['outcome'],'root-parser-return')
  self.assertIsNone(result['emulator_error'])
  self.assertTrue(all(a['within_explicit_template'] for a in result['object_accesses']))
  self.assertTrue(any(a['object']=='status_b' and int(a['offset'],16)>=0xe434 for a in result['object_accesses']))
 def test_old_two_page_status_buffer_is_rejected(self):
  fixture=model.graph_fixture
  def undersized(enabled):
   arena,receipt=fixture(enabled)
   next(o for o in receipt['objects'] if o['name']=='status_b')['input_bytes']=0x8000
   return arena,receipt
  with patch.object(model,'graph_fixture',undersized):result=model.run(TEXT,DATA,True)
  self.assertEqual(result['outcome'],'access-beyond-explicit-template')
  self.assertEqual(result['object_accesses'][-1]['object'],'status_b')
if __name__=='__main__':unittest.main()
