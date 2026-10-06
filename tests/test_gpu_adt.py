import importlib.util,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('adt',ROOT/'experiments/t6040-gpu/adt.py');adt=importlib.util.module_from_spec(spec);spec.loader.exec_module(adt)
def prop(name,value):return name.encode().ljust(32,b'\0')+struct.pack('<I',len(value))+value+b'\0'*((-len(value))%4)
def node(name,values=None,children=()):
 values={'name':name.encode()+b'\0',**(values or {})};return struct.pack('<II',len(values),len(children))+b''.join(prop(k,v) for k,v in values.items())+b''.join(children)
class ADT(unittest.TestCase):
 def test_parses_nested_sgx_and_preserves_little_endian_bytes(self):
  data=node('',children=[node('arm-io',children=[node('sgx',{'perf-state-count':b'\x10\0\0\0'})])]);tree=adt.parse(data);self.assertEqual(tree['/arm-io/sgx']['perf-state-count'],b'\x10\0\0\0');self.assertIn('/arm-io/sgx',adt.selected(tree))
 def test_truncated_tree_and_oversized_counts_rejected(self):
  for data in (node('')[:-1],struct.pack('<II',5000,0)):
   with self.assertRaises(ValueError):adt.parse(data)
 def test_chosen_selection_excludes_unneeded_secrets(self):
  tree=adt.parse(node('',children=[node('chosen',{'firmware-version':b'mBoot-test\0','boot-nonce':b'private'})]));chosen=adt.selected(tree)['/chosen'];self.assertIn('firmware-version',chosen);self.assertNotIn('boot-nonce',chosen)
 def test_ram_reader_has_read_only_attribute_and_system_ram_gate(self):
  s=(ROOT/'experiments/t6040-gpu/m4rch_gpu_adt.c').read_text();self.assertIn('.mode = 0400',s);self.assertNotIn('.write =',s);self.assertIn('IORESOURCE_SYSTEM_RAM',s);self.assertIn('"reserved-memory"',s);self.assertIn('strcmp(label, "adt")',s);self.assertNotIn('ioremap(',s)
if __name__=='__main__':unittest.main()
