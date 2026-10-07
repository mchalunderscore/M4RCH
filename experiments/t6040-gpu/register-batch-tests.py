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
 def test_gfender_descriptor_and_partial_write_grant(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  values=struct.unpack_from('<QQIIQI',self.data,h+0x640+26*0x28)
  self.assertEqual(values[0],0x288d04000);self.assertEqual(values[2:],(0x8000,0x8000,0xd04000,1))
  self.assertEqual(values[1]%0x4000,0)
 def test_leaf_pages_are_disjoint_virtual_and_contained(self):
  leaves=self.receipt['mmio_leaves'];self.assertEqual(len(leaves),100);self.assertEqual(self.receipt['mapped_pages'],121)
  start=int(self.receipt['mmio_virtual_base'],16)
  self.assertEqual([v['gpu_va'] for v in leaves],sorted(set(v['gpu_va'] for v in leaves)))
  self.assertTrue(all(v['gpu_va']==start+v['physical']-0x288000000 for v in leaves if v['physical']<0x28b000000))
  self.assertTrue(all(v['gpu_va']>>25==int(self.receipt['base'],16)>>25 for v in leaves))
  self.assertTrue(all(v['physical']%0x4000==0 and 0x288000000<=v['physical']<0x28b758000 for v in leaves if v['physical']<0x500000000))
 def test_real_banks_and_narrow_write_permissions(self):
  self.assertNotIn('ram_register_surrogate',self.receipt)
  writable=[v['physical'] for v in self.receipt['mmio_leaves'] if not v['readonly']]
  self.assertEqual(writable,[0x288004000,0x288d04000,0x288d10000,0x288d40000,0x288d44000,0x288d4c000,0x288e00000,0x288e1c000,0x288e40000,0x502414000,0x5003d8000]+[base+offset for base in (0x28b000000,0x28b200000,0x28b400000,0x28b600000) for offset in (0,0x10000,0x20000,0x30000)])
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  for slot,physical in [(33,0x288d44000),(35,0x288e00000)]:
   values=struct.unpack_from('<QQIIQI',self.data,h+0x640+slot*0x28)
   self.assertEqual(values[0],physical);self.assertEqual(values[2],0x4000);self.assertEqual(values[-1],1)
  self.assertEqual(struct.unpack_from('<QQ',self.data,h+0x2560),(0xf6fdb,0))
  self.assertEqual(len(self.data)//0x4000,21)
  self.assertTrue(next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288d08000)['readonly'])
 def test_relative_arithmetic_and_shared_clock_counter_page(self):
  d={v['slot']:v for v in self.receipt['mmio_descriptors']};base=int(self.receipt['mmio_virtual_base'],16)
  self.assertEqual(int(d[29]['gpu_va'],16)-0xd10000,int(d[17]['gpu_va'],16))
  self.assertEqual(int(d[41]['gpu_va'],16)-int(d[40]['gpu_va'],16),0x3800)
  self.assertEqual(d[40]['effective_writable_pages'],['0x288e1c000'])
  self.assertEqual(d[41]['effective_writable_pages'],['0x288e1c000'])
  self.assertTrue(next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288e20000)['readonly'])
 def test_platform_exact_pairs_and_descriptors(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  for slot,pa,va in [(0,0x502414000,0xfffffc2001a00000),(11,0x5003d8000,0xfffffc2001b18000)]:
   self.assertEqual(struct.unpack_from('<QQIIQI',self.data,h+0x640+slot*0x28),(pa,va,0x4000,0x4000,0,1))
  self.assertFalse(any(d['slot'] in (9,10) for d in self.receipt['mmio_descriptors']))
 def test_afr_compacted_physical_ranges(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  self.assertEqual(struct.unpack_from('<QQIIQI',self.data,h+0x640+20*0x28),(0x28b000000,0xfffffc2001c00000,0x100000,0x40000,0,1))
  afr=[v for v in self.receipt['mmio_leaves'] if v['gpu_va']>=0xfffffc2001c00000]
  self.assertEqual(len(afr),64)
  for i,v in enumerate(afr):
   self.assertEqual(v['gpu_va'],0xfffffc2001c00000+i*0x4000)
   self.assertEqual(v['physical'],(0x28b000000,0x28b200000,0x28b400000,0x28b600000)[i//16]+(i%16)*0x4000)
   self.assertEqual(v['readonly'],bool(i%4))
  # All seven selector writes and all sixteen AFR accesses have RW backing.
  primary=next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288004000)
  self.assertFalse(primary['readonly'])
  self.assertTrue(next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288000000)['readonly'])
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
