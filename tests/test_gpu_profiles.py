"""Compile the metadata helpers; these are not GPU execution tests."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/t6040-gpu'
class Profiles(unittest.TestCase):
 @unittest.skipUnless(shutil.which('rustc'),'rustc required')
 def test_captured_ladders_and_invalid_inputs(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'profiles'
   subprocess.run(['rustc','--test',str(EXP/'profile-tests.rs'),'-o',str(exe)],check=True,capture_output=True)
   r=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
   self.assertIn('6 passed; 0 failed',r.stdout)
 @unittest.skipUnless(shutil.which('cc'),'C compiler required')
 def test_mesa_topology_and_unqualified_layout_gate(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'model'
   subprocess.run(['cc','-Wall','-Wextra','-Werror',str(EXP/'model-tests.c'),'-o',str(exe)],check=True,capture_output=True)
   subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
