import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'experiments/t6040-idle/batch/run-allcores.py'
s=importlib.util.spec_from_file_location('batch_runner',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Runner(unittest.TestCase):
 def test_progress_bounds(self):
  good=''.join(f'cpu{c} attempts=4 completed=4 ' for c in range(12))+'budget=0 target=11\n'
  self.assertEqual(m.parse_progress(good)['completed'],dict.fromkeys(range(12),4))
  bad=[good.replace('cpu7','cpu6'),good.replace('cpu7 attempts=4 completed=4 ',''),good.replace('completed=4','completed=5',1),good.replace('attempts=4 completed=4','attempts=65 completed=65',1),good.replace('budget=0','budget=65'),good.replace('target=11','target=12'),'garbage'+good]
  for text in bad:
   with self.assertRaises(ValueError):m.parse_progress(text)
 def test_worker_validation_detects_corruption(self):
  import shutil,subprocess,tempfile
  cc=shutil.which('cc')
  if not cc:self.skipTest('no C compiler')
  src=P.parent/'state-worker-allcores.c'
  with tempfile.TemporaryDirectory() as temp:
   executable=Path(temp)/'test';subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-DWORKER_VALIDATION_TEST',str(src),'-o',str(executable)],check=True,capture_output=True);subprocess.run([str(executable)],check=True)
