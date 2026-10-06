import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('peripheral_map',ROOT/'experiments/peripheral-topology/map.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Topology(unittest.TestCase):
 def test_follow_phandle_and_keep_raw_resource(self):
  tree=[{'IORegistryEntryName':'root','IORegistryEntryChildren':[{'IORegistryEntryName':'isp0','iommu-parent':(12).to_bytes(4,'little'),'reg':b'\x01\x00\x00\x00','serial-number':'private'},{'IORegistryEntryName':'dart0','AAPL,phandle':(12).to_bytes(4,'little')}]}]
  rows=module.select(tree);by={r['path']:r for r in rows}
  self.assertIn('/root/dart0',by)
  self.assertEqual(by['/root/isp0']['scalar_phandle_links']['iommu-parent'],'/root/dart0')
  self.assertEqual(by['/root/isp0']['properties']['reg']['hex'],'01000000')
  self.assertNotIn('serial-number',by['/root/isp0']['properties'])
 def test_blobs_and_unrelated_nodes_excluded(self):
  rows=module.select([{'IORegistryEntryName':'isp0','reg':b'x'*513,'firmware':b'secret'},{'IORegistryEntryName':'unrelated'}])
  self.assertEqual(len(rows),1);self.assertNotIn('reg',rows[0]['properties']);self.assertNotIn('firmware',rows[0]['properties'])
 def test_string_compatibility_and_byte_order_are_explicit(self):
  self.assertEqual(module.value(b'cs42l84\0')['strings'],['cs42l84'])
  self.assertEqual(module.value(b'\x01\x00\x00\x00')['u32le'],[1])
