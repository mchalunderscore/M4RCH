#!/usr/bin/env python3
"""Check new MMIO mapping geometry against the independently captured ADT."""
import importlib.util,sys,struct,unittest
from pathlib import Path
KIT=Path(__file__).resolve().parent
mods={}
for name,file in [('model','emulate-init-parser.py'),('batch','graph-register-batch.py')]:
 spec=importlib.util.spec_from_file_location(name,KIT/file);mods[name]=importlib.util.module_from_spec(spec);spec.loader.exec_module(mods[name])
raw=Path(sys.argv.pop(1)).read_bytes()
class BatchTests(unittest.TestCase):
 def setUp(self):self.data,self.receipt=mods['batch'].extend(*mods['model'].graph_fixture(True),raw)
 def test_gfender_descriptor_and_readonly_flag(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  values=struct.unpack_from('<QQIIQI',self.data,h+0x640+26*0x28)
  self.assertEqual(values[0],0x288d04000);self.assertEqual(values[2:],(0x8000,0x8000,0xd04000,0))
  self.assertEqual(values[1]%0x4000,0)
 def test_leaf_pages_are_disjoint_virtual_and_contained(self):
  leaves=self.receipt['mmio_leaves'];self.assertEqual(len(leaves),24);self.assertEqual(self.receipt['mapped_pages'],45)
  start=int(self.receipt['base'],16)+len(self.data)
  self.assertEqual([v['gpu_va'] for v in leaves],[start+i*0x4000 for i in range(24)])
  self.assertTrue(all(v['readonly'] and v['physical']%0x4000==0 and 0x288000000<=v['physical']<0x28b758000 for v in leaves))
 def test_profile_a_columns_and_tail(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  self.assertEqual(struct.unpack_from('<II',self.data,h+0x1008),(125,125))
  self.assertEqual(struct.unpack_from('<II',self.data,h+0x1008+0x40),(610,605))
  self.assertFalse(any(self.data[h+0x1008+11*0x40:h+0x1008+16*0x40]))
 def test_changed_bus_translation_rejected(self):
  tree=mods['batch'].adt.parse(raw);old=mods['batch'].adt.parse
  tree['/device-tree/arm-io']['ranges']=bytes(len(tree['/device-tree/arm-io']['ranges']))
  from unittest.mock import patch
  with patch.object(mods['batch'].adt,'parse',lambda _:tree):
   with self.assertRaises(ValueError):mods['batch'].extend(*mods['model'].graph_fixture(True),raw)
if __name__=='__main__':unittest.main()
