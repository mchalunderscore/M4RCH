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
 def test_runtime_and_native_allowlists_cover_qualified_batch(self):
  import re
  native=(KIT/'asc-graph-init/graph-map.h').read_text()
  runner=(KIT/'run-root-envelope.py').read_text()
  native_grants={int(x,16) for x in re.findall(r'pa!=(0x[0-9a-f]+)ULL',native)}
  runtime_tuple=re.search(r'pa in \((.*?)\)\)',runner).group(1)
  runtime_grants={int(x,16) for x in re.findall(r'0x[0-9a-f]+',runtime_tuple)}
  self.assertTrue(mods['batch'].WRITABLE_PAGES<=native_grants)
  self.assertEqual(mods['batch'].WRITABLE_PAGES,runtime_grants)
 def setUp(self):self.data,self.receipt=mods['batch'].extend(*mods['model'].graph_fixture(True),raw)
 def test_gfender_descriptor_and_partial_write_grant(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  values=struct.unpack_from('<QQIIQI',self.data,h+0x640+26*0x28)
  self.assertEqual(values[0],0x288d04000);self.assertEqual(values[2:],(0x8000,0x8000,0xd04000,1))
  self.assertEqual(values[1]%0x4000,0)
 def test_leaf_pages_are_disjoint_virtual_and_contained(self):
  leaves=self.receipt['mmio_leaves'];self.assertEqual(len(leaves),100);self.assertEqual(self.receipt['mapped_pages'],147)
  start=int(self.receipt['mmio_virtual_base'],16)
  self.assertEqual([v['gpu_va'] for v in leaves],sorted(set(v['gpu_va'] for v in leaves)))
  self.assertTrue(all(v['gpu_va']==start+v['physical']-0x288000000 for v in leaves if v['physical']<0x28b000000))
  self.assertTrue(all(v['gpu_va']>>25==int(self.receipt['base'],16)>>25 for v in leaves))
  self.assertTrue(all(v['physical']%0x4000==0 and 0x288000000<=v['physical']<0x28b758000 for v in leaves if v['physical']<0x500000000))
 def test_real_banks_and_narrow_write_permissions(self):
  self.assertNotIn('ram_register_surrogate',self.receipt)
  writable=[v['physical'] for v in self.receipt['mmio_leaves'] if not v['readonly']]
  self.assertEqual(writable,[0x288000000,0x288004000,0x288008000,0x28800c000,0x288010000,0x288014000,0x288018000,0x28801c000,0x288020000,0x288d04000,0x288d10000,0x288d40000,0x288d44000,0x288d4c000,0x288e00000,0x288e1c000,0x288e40000,0x289004000,0x502414000,0x5003d8000]+[base+offset for base in (0x28b000000,0x28b200000,0x28b400000,0x28b600000) for offset in (0,0x10000,0x20000,0x30000)])
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  for slot,physical in [(33,0x288d44000),(35,0x288e00000)]:
   values=struct.unpack_from('<QQIIQI',self.data,h+0x640+slot*0x28)
   self.assertEqual(values[0],physical);self.assertEqual(values[2],0x4000);self.assertEqual(values[-1],1)
  self.assertEqual(struct.unpack_from('<QQ',self.data,h+0x2560),(0xf6fdb,0))
  self.assertEqual(len(self.data)//0x4000,47)
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
  descriptor=next(v for v in self.receipt['mmio_descriptors'] if v['slot']==20)
  self.assertEqual(len(descriptor['effective_writable_pages']),16)
  for i,v in enumerate(afr):
   self.assertEqual(v['gpu_va'],0xfffffc2001c00000+i*0x4000)
   self.assertEqual(v['physical'],(0x28b000000,0x28b200000,0x28b400000,0x28b600000)[i//16]+(i%16)*0x4000)
   self.assertEqual(v['readonly'],bool(i%4))
  # All seven selector writes and all sixteen AFR accesses have RW backing.
  primary=next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288004000)
  self.assertFalse(primary['readonly'])
  self.assertFalse(next(v for v in self.receipt['mmio_leaves'] if v['physical']==0x288000000)['readonly'])
 def test_slot22_native_write_page_only(self):
  leaves={v['physical']:v for v in self.receipt['mmio_leaves']}
  self.assertTrue(leaves[0x289000000]['readonly'])
  self.assertFalse(leaves[0x289004000]['readonly'])
  d=next(x for x in self.receipt['mmio_descriptors'] if x['slot']==22)
  self.assertEqual(d['effective_writable_pages'],['0x289004000'])
  # Descriptor's opaque flag is retained; CPU HAL flags are not firmware flags.
  self.assertTrue(d['readonly'])
 def test_primary_table_register_batch(self):
  leaves={v['physical']:v for v in self.receipt['mmio_leaves']}
  for offset in (0x21108,0x21110,0x21118,0x21120,0x21008,0x211e0,0x103a8):
   self.assertFalse(leaves[(0x288000000+offset)&~0x3fff]['readonly'])
  self.assertFalse(leaves[0x288000000]['readonly'])
  for pa in (0x288008000,0x28800c000,0x288014000,0x288018000,0x28801c000):
   self.assertFalse(leaves[pa]['readonly'])
  self.assertFalse(leaves[(0x288000000+0x1ca20)&~0x3fff]['readonly'])
 def test_empty_channels_are_owned_disjoint_and_zero(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='main')
  base=int(self.receipt['base'],16);all_spans=[]
  for i in range(13):
   a,b,c,ring=struct.unpack_from('<4Q',self.data,h+0x20+i*0x20)
   self.assertEqual((b,c),(a+8,a+16));self.assertEqual(ring,a+0x4000)
   self.assertFalse(any(self.data[a-base:a-base+0x8000]))
   all_spans.append((a,ring+0x4000))
  for l,r in zip(all_spans,all_spans[1:]):self.assertLessEqual(l[1],r[0])
  self.assertLessEqual(all_spans[-1][1],min(v['gpu_va'] for v in self.receipt['mmio_leaves']))
  self.assertFalse(any(self.data[h+0x1c0:h+0x240]))
 def test_profile_a_columns_and_tail(self):
  h=next(o['arena_offset'] for o in self.receipt['objects'] if o['name']=='hardware')
  self.assertEqual(struct.unpack_from('<II',self.data,h+0x1008),(125,125))
  self.assertEqual(struct.unpack_from('<II',self.data,h+0x1008+0x40),(610,605))
  self.assertFalse(any(self.data[h+0x1008+11*0x40:h+0x1008+16*0x40]))
 def test_single_control_refresh_changes_only_opcode_and_producer(self):
  import copy
  from control_refresh import stage
  receipt=copy.deepcopy(self.receipt)
  data,receipt=stage(self.data,receipt)
  base=int(receipt['base'],16);channel=receipt['empty_channel_fixture'][12]
  producer=int(channel['cursors'][2],16)-base;ring=int(channel['ring'],16)-base
  self.assertEqual([i for i,(a,b) in enumerate(zip(self.data,data)) if a!=b],[producer,ring])
  self.assertEqual((data[producer],data[ring]),(1,0x16))
  self.assertEqual(receipt['mmio_leaves'],self.receipt['mmio_leaves'])
  for obj in receipt['objects']:
   start=obj['arena_offset']
   import hashlib
   self.assertEqual(obj['input_sha256'],hashlib.sha256(data[start:start+obj['input_bytes']]).hexdigest())
 def test_control_refresh_rejects_nonempty_state(self):
  from control_refresh import stage
  data=bytearray(self.data);base=int(self.receipt['base'],16)
  data[int(self.receipt['empty_channel_fixture'][12]['cursors'][0],16)-base]=1
  with self.assertRaises(ValueError):stage(data,self.receipt)
 def test_refresh_batch_bounds_and_record_isolation(self):
  import copy
  from control_refresh import stage
  base=int(self.receipt['base'],16);channel=self.receipt['empty_channel_fixture'][12]
  producer=int(channel['cursors'][2],16)-base;ring=int(channel['ring'],16)-base
  for count in (2,16,32):
   data,r=stage(self.data,copy.deepcopy(self.receipt),count)
   changed=[i for i,(a,b) in enumerate(zip(self.data,data)) if a!=b]
   self.assertEqual(changed,[producer]+[ring+i*0x40 for i in range(count)])
   self.assertEqual(struct.unpack_from('<I',data,producer)[0],count)
   self.assertEqual(r['mmio_leaves'],self.receipt['mmio_leaves'])
  for count in (0,33,-1,True,1.5):
   with self.assertRaises(ValueError):stage(self.data,copy.deepcopy(self.receipt),count)
 def test_changed_bus_translation_rejected(self):
  tree=mods['batch'].adt.parse(raw);old=mods['batch'].adt.parse
  tree['/device-tree/arm-io']['ranges']=bytes(len(tree['/device-tree/arm-io']['ranges']))
  from unittest.mock import patch
  with patch.object(mods['batch'].adt,'parse',lambda _:tree):
   with self.assertRaises(ValueError):mods['batch'].extend(*mods['model'].graph_fixture(True),raw)
 def test_receive14_extents_pointer_positions_and_no_overlap(self):
  import copy
  from receive14_fixture import extend
  data,r=extend(self.data,copy.deepcopy(self.receipt));base=int(r['base'],16)
  self.assertEqual(len(data)//0x4000,54);self.assertEqual(r['mapped_pages'],154)
  self.assertEqual(r['mmio_leaves'],self.receipt['mmio_leaves'])
  main=next(o['arena_offset'] for o in r['objects'] if o['name']=='main')
  objects=[o for o in r['objects'] if o['name'].startswith('receive14_')]
  self.assertEqual([o['input_bytes'] for o in objects],[0x30,0x9000,0x30,0x4800])
  for i,o in enumerate(objects):
   self.assertEqual(struct.unpack_from('<Q',data,main+0x1e0+i*8)[0],base+o['arena_offset'])
   self.assertFalse(any(data[o['arena_offset']:o['arena_offset']+o['reserved_bytes']]))
  self.assertFalse(any(data[main+0x1c0:main+0x1e0]));self.assertFalse(any(data[main+0x200:main+0x240]))
  with self.assertRaises(ValueError):extend(data,r)
 def test_receive13_sparse_spans_and_mapping_validation(self):
  import copy
  from receive14_fixture import extend as receive14
  from receive13_fixture import extend as receive13
  from owned_gpu_layout import validate
  data,r=receive13(*receive14(self.data,copy.deepcopy(self.receipt)))
  pages=validate(data,r);self.assertEqual(len(pages),69);self.assertEqual(r['mapped_pages'],169)
  self.assertEqual(r['mmio_leaves'],self.receipt['mmio_leaves'])
  objects=[o for o in r['objects'] if o['name'].startswith('receive13_')]
  self.assertEqual([o['input_bytes'] for o in objects],[0x30,0x4800,0x1b0,0x28800])
  ring=objects[-1];self.assertEqual(int(ring['gpu_va'],16),0xfffffc2000224000)
  self.assertEqual(ring['arena_offset']//0x4000,58)
  main=next(o['arena_offset'] for o in r['objects'] if o['name']=='main')
  for i,o in enumerate(objects):
   self.assertEqual(struct.unpack_from('<Q',data,main+0x1c0+i*8)[0],int(o['gpu_va'],16))
   self.assertFalse(any(data[o['arena_offset']:o['arena_offset']+o['reserved_bytes']]))
  self.assertFalse(any(data[main+0x200:main+0x240]))
  with self.assertRaises(ValueError):receive13(data,r)
  # Reject collisions, duplicate mappings, split objects and wrong encoded pointers.
  for index,va in [(58,0xfffffc2000200000),(58,pages[57]),(59,pages[59]+0x4000),(0,pages[0]+0x4000)]:
   bad=copy.deepcopy(r);bad['owned_page_vas'][index]=va
   with self.assertRaises(ValueError):validate(data,bad)
  bad=bytearray(data);struct.pack_into('<Q',bad,main+0x1d8,int(ring['gpu_va'],16)+0x4000)
  with self.assertRaises(ValueError):validate(bad,r)
 def test_original_and_receive14_owned_mapping_are_contiguous(self):
  import copy
  from receive14_fixture import extend
  from owned_gpu_layout import validate
  for data,r in ((self.data,self.receipt),extend(self.data,copy.deepcopy(self.receipt))):
   self.assertEqual(validate(data,r),[int(r['base'],16)+i*0x4000 for i in range(len(data)//0x4000)])
 def test_retirement_ignores_prior_shadow_allocations_and_requires_complete_final_group(self):
  from retirement_proof import last_allocation
  log=''.join(f'owned page {i} physical={0x800000000+i*0x4000:#x}\n' for i in range(3))
  log+=''.join(f'owned page {i} physical={0x810000000+i*0x4000:#x}\n' for i in range(3))
  self.assertEqual(last_allocation(log,3),[0x810000000+i*0x4000 for i in range(3)])
  with self.assertRaises(ValueError):last_allocation(log+'owned page 0 physical=0x820000000\n',3)
 def test_post_unload_rejects_lingering_reference_and_broken_loader_path(self):
  from retirement_proof import check,BASE,ROOT
  table=bytearray(0x40000);l2=bytes(0x4000)
  for offset,value in [(0,(BASE+0x4000)|3),(0x4000,(BASE+0x8000)|3),(0x8000,0x10000be4000|3),
                       (0x8000+24*8,0x10001d44000|3),(((ROOT>>36)&63)*8,0x200105fff744cb)]:
   struct.pack_into('<Q',table,offset,value)
  log=''.join(f'owned page {i} physical={0x800000000+i*0x4000:#x}\n' for i in range(3))
  self.assertTrue(check(table,l2,bytes(0x40000),log,1)['post_unload_verified'])
  self.assertTrue(check(table,l2,table,log,1)['post_unload_verified'])
  cleared=bytearray(table);struct.pack_into('<Q',cleared,((ROOT>>36)&63)*8,0)
  self.assertTrue(check(cleared,l2,bytes(0x40000),log,1)['post_unload_verified'])
  self.assertTrue(check(cleared,l2,table,log,1)['post_unload_verified'])
  unknown=bytearray(table);struct.pack_into('<Q',unknown,((ROOT>>36)&63)*8,0x200105fff784cb)
  self.assertFalse(check(unknown,l2,bytes(0x40000),log,1)['post_unload_verified'])
  dirty=bytearray(l2);struct.pack_into('<Q',dirty,0,0x800008000|3)
  self.assertFalse(check(table,dirty,table,log,1)['post_unload_verified'])
  dirty=bytearray(table);struct.pack_into('<Q',dirty,0x8000,0x10000be8000|3)
  self.assertFalse(check(dirty,l2,bytes(0x40000),log,1)['post_unload_verified'])
  dirty=bytearray(table);struct.pack_into('<Q',dirty,0x1000,0x800004000|3)
  self.assertFalse(check(dirty,l2,bytes(0x40000),log,1)['post_unload_verified'])
if __name__=='__main__':unittest.main()
