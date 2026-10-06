import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'experiments/t6040-idle/batch/run-batches.py'
s=importlib.util.spec_from_file_location('batch_runner',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Runner(unittest.TestCase):
 def test_progress_bounds(self):
  p=m.parse_progress('cpu4 attempts=32 completed=32 cpu5 attempts=1 completed=1 budget=0 target=5\n')
  self.assertEqual(p['completed'],{4:32,5:1})
  for text in ['cpu4 attempts=1 completed=2 cpu5 attempts=0 completed=0 budget=0 target=4','cpu4 attempts=65 completed=65 cpu5 attempts=0 completed=0 budget=0 target=4','cpu4 attempts=0 completed=0 cpu5 attempts=0 completed=0 budget=1 target=6','garbage']:
   with self.assertRaises(ValueError):m.parse_progress(text)
 def test_worker_validation_detects_corruption(self):
  import shutil,subprocess,tempfile
  cc=shutil.which('cc')
  if not cc:self.skipTest('no C compiler')
  src=P.parent/'state-worker.c'
  with tempfile.TemporaryDirectory() as temp:
   executable=Path(temp)/'test';subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-DWORKER_VALIDATION_TEST',str(src),'-o',str(executable)],check=True,capture_output=True);subprocess.run([str(executable)],check=True)
