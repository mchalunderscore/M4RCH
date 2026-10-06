import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/'experiments/t6040-sme'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class SMETrial(unittest.TestCase):
 def test_idle_progress_requires_all_cores(self):
  r=load('sme_runner','run.py')
  text=''.join(f'cpu{c} attempts=10 completed={c+1}\n' for c in range(12))
  self.assertEqual(r.progress(text)[11],12)
  with self.assertRaises(ValueError):r.progress('cpu4 attempts=10 completed=10\n')
 def test_cpio_preserves_modes_names_and_payload(self):
  r=load('sme_repack','repack-initrd.py')
  members=[(b'init\0',[1,0o100755,0,0,1,0,3,0,0,0,0,5,0],b'abc'),(b'TRAILER!!!\0',[0]*13,b'')]
  encoded=r.encode(members);items,end=r.parse(encoded)
  self.assertEqual(items[0][0],b'init\0');self.assertEqual(items[0][1][1],0o100755)
  self.assertEqual(items[0][2],b'abc');self.assertEqual(end,len(encoded))
 def test_cpio_rejects_truncated_payload(self):
  r=load('sme_repack_bad','repack-initrd.py')
  with self.assertRaises(ValueError):r.parse(b'not an archive')
