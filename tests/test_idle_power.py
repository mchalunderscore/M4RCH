import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'experiments/t6040-idle/power/compare.py'
s=importlib.util.spec_from_file_location('idle_power',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Power(unittest.TestCase):
 def test_only_new_faults_stop_comparison(self):
  before='existing Oops: historical\n'
  delta,bad=m.faults(before,before+'ordinary wake\n');self.assertFalse(bad);self.assertEqual(delta,'ordinary wake\n')
  self.assertTrue(m.faults(before,before+'CPU_PM_ENTER rejected\n')[1])
  self.assertTrue(m.faults(before,'rotated journal\nM4RCH_FAULT\n')[1])
 def test_disable_switch_readback(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'continuous'
   with patch.object(m,'SWITCH',p):
    m.write_switch(False);self.assertEqual(p.read_text(),'0\n')
    m.write_switch(True);self.assertEqual(p.read_text(),'1\n')
 def test_missing_telemetry_is_not_zero(self):
  with tempfile.TemporaryDirectory() as temp:
   self.assertIn('unavailable',m.read(Path(temp)/'absent'))
