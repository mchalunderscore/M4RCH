import importlib.util
from pathlib import Path
import unittest
s=importlib.util.spec_from_file_location('hdmi_diff',Path(__file__).resolve().parents[1]/'experiments/peripheral-topology/hdmi-diff.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class HDMI(unittest.TestCase):
 def test_hpd_and_edid_reduced_without_serials(self):
  row=m.collect({'IORegistryEntryName':'dcpext0','HDMI_HPD':True,'EDID':b'private monitor serial','DisplaySerialNumber':123})
  props=row['/dcpext0'];self.assertTrue(props['HDMI_HPD']);self.assertNotIn('DisplaySerialNumber',props);self.assertNotIn('hex',props['EDID']);self.assertEqual(props['EDID']['bytes'],22)
 def test_unrelated_device_excluded(self):
  self.assertEqual(m.collect([{'IORegistryEntryName':'usb','EDID':b'x'}]),{})
