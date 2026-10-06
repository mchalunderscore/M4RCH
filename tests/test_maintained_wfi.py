from pathlib import Path
import hashlib,subprocess,tempfile,unittest,sys,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
from hardware_profile import MAINTAINED_WFI
class MaintainedWFI(unittest.TestCase):
 def source(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/MAINTAINED_WFI['source'];p.parent.mkdir(parents=True);p.write_bytes((ROOT/'tests/fixtures/cpuidle-apple-base.c').read_bytes());subprocess.run(['git','apply',str(ROOT/MAINTAINED_WFI['path'])],cwd=root,check=True,capture_output=True);source=p.read_text();self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),MAINTAINED_WFI['result_source_sha256']);return source
 def test_board_scope_shallow_state_and_suspend_exclusion(self):
  s=self.source();self.assertIn('static bool saved_wfi = true',s);self.assertIn('of_machine_is_compatible("apple,t6040") &&',s);self.assertIn('of_machine_is_compatible("apple,j614s")',s);self.assertIn('state_count = 1',s);self.assertIn('target_residency = 1',s);self.assertIn('enter_s2idle = NULL',s)
 def test_saved_assembly_preserves_all_gprs_and_has_no_control_registers(self):
  s=self.source();a=s.index('".type apple_cpu_saved_wfi');b=s.index('void apple_cpu_saved_wfi',a);body=s[a:b]
  for reg in range(0,30,2):
   self.assertIn(f'stp x{reg}, x{reg+1}, [sp, #{reg*8}]',body);self.assertIn(f'ldp x{reg}, x{reg+1}, [sp, #{reg*8}]',body)
  self.assertIn('str x30, [sp, #240]',body);self.assertIn('ldr x30, [sp, #240]',body);self.assertIn('sub sp, sp, #256',body);self.assertIn('add sp, sp, #256',body);self.assertEqual(body.count('"wfi'),1);self.assertNotIn('s3_5_c15_c5_0',body)
 def test_actual_entry_order_and_runtime_disable(self):
  s=self.source();a=s.index('static __cpuidle int apple_enter_idle');body=s[a:s.index('static struct cpuidle_driver',a)];branch=body[:body.index('/*\n')]
  self.assertLess(branch.index('!READ_ONCE(saved_wfi)'),branch.index('cpu_pm_enter()'));self.assertNotIn('apple_cpu_deep_wfi',branch)
  calls=['cpu_pm_enter()','ct_cpuidle_enter()','apple_cpu_saved_wfi()','ct_cpuidle_exit()','cpu_pm_exit()'];self.assertEqual(sorted(calls,key=branch.index),calls)
