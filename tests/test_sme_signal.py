import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('signal_variant',ROOT/'experiments/t6040-sme/prepare-signal.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SignalVariants(unittest.TestCase):
 def setUp(self):
  self.source='prefix\nfunction irritator_handler\n\t// Corrupt some random Z-regs\n\tmovi\tv0.8b, #1\n\tptrue\tp0.d\n\tret\nendfunction\nsuffix\n'
 def test_neon_variant_omits_only_sve_predicate(self):
  out=module.transform(self.source,False)
  self.assertNotIn('\tptrue',out);self.assertIn('\tmovi',out);self.assertTrue(out.endswith('suffix\n'))
 def test_streaming_handler_brackets_vector_instructions(self):
  out=module.transform(self.source,True)
  self.assertLess(out.index('\tsmstart_sm'),out.index('\tptrue'))
  self.assertLess(out.index('\tptrue'),out.index('\tsmstop'))
  self.assertLess(out.index('\tsmstop'),out.index('\tret'))
 def test_drift_rejected(self):
  with self.assertRaises(ValueError):module.transform(self.source.replace('\tptrue\tp0.d',''),True)
