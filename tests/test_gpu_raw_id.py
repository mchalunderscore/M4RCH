import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('raw_gpu_id',Path(__file__).resolve().parents[1]/'experiments/t6040-gpu/raw-id.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RawIds(unittest.TestCase):
 def test_native_capture_cross_check(self):
  r=m.decode(0x0a031100,0x0011020a,0x00040404,0x400c0c02)
  self.assertEqual((r['variant_field'],r['revision_field']),('S','B1'))
  self.assertEqual(r['counts_rule_cross_check']['total_slots'],20)
  self.assertIn('not read',r['active_core_masks'])
 def test_unrecognized_generation_and_variant_rejected(self):
  for v in [0,0xffffffff,0x06031100,0x0a021100]:
   with self.assertRaises(ValueError):m.decode(v,0x0011020a,0,0)
 def test_other_fuse_slot_layout_not_silently_accepted(self):
  with self.assertRaises(ValueError):m.decode(0x0a031100,0x0011020b,0,0)
if __name__=='__main__':unittest.main()
