"""Audit the actual alternate idle implementation and its activation gate."""
from pathlib import Path
import hashlib,re,subprocess,tempfile,unittest,sys,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
from hardware_profile import IDLE_OPTIN,IDLE_TRACE,SAVED_WFI
class SavedWfi(unittest.TestCase):
 def source(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp)/SAVED_WFI['source'];source.parent.mkdir(parents=True);source.write_bytes((ROOT/'tests/fixtures/cpuidle-apple-base.c').read_bytes())
   for desc in (IDLE_OPTIN,IDLE_TRACE,SAVED_WFI):
    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),desc['base_source_sha256'])
    subprocess.run(['git','apply','--whitespace=error-all',str(ROOT/desc['path'])],cwd=temp,check=True,capture_output=True)
    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),desc['result_source_sha256'])
   return source.read_text()
 def test_full_frame_and_no_control_access(self):
  source=self.source();a=source.index('".type m4rch_cpu_saved_wfi_trace');b=source.index('void m4rch_cpu_saved_wfi_trace',a);asm=source[a:b]
  self.assertNotIn('mrs',asm);self.assertNotIn('msr',asm);self.assertNotIn('ISR_EL1',asm)
  self.assertEqual(asm.count('"wfi'),1)
  self.assertNotIn('cbz',asm)
  self.assertIn('sub sp, sp, #256',asm);self.assertIn('add sp, sp, #256',asm)
  for x in range(0,30,2):
   self.assertIn(f'stp x{x}, x{x+1}, [sp, #{x*8}]',asm)
   self.assertIn(f'ldp x{x}, x{x+1}, [sp, #{x*8}]',asm)
  self.assertIn('str x30, [sp, #240]',asm);self.assertIn('ldr x30, [sp, #240]',asm)
  after=asm[asm.index('"wfi'):];self.assertNotIn('"bl ',after)
  self.assertIn('trace && experimental_t6040_idle_wfi_only',source)
  self.assertIn('smp_processor_id() != 4 || READ_ONCE(trace_attempted)',source)
  self.assertLess(source.index('cpu_pm_enter()'),source.index('m4rch_cpu_saved_wfi_trace();'))
 def test_reject_partial_or_wrong_board_activation(self):
  source=self.source();match=re.search(r'if \((experimental_t6040_idle_wfi_only.*?)\) \{\n\t\tpr_err',source,re.S);self.assertIsNotNone(match)
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  program='''#include <stdbool.h>
#include <string.h>
#include <assert.h>
static bool experimental_t6040_idle_wfi_only,experimental_t6040_idle,experimental_t6040_idle_trace;
static const char *soc,*board;
static bool of_machine_is_compatible(const char*s){return !strcmp(s,soc)||!strcmp(s,board);}
static bool rejected(void){return ('''+match[1]+''');}
int main(void){soc="apple,t6040";board="apple,j614s";
assert(!rejected());experimental_t6040_idle_wfi_only=true;assert(rejected());
experimental_t6040_idle=true;assert(rejected());experimental_t6040_idle_trace=true;assert(!rejected());
board="apple,j616s";assert(rejected());board="apple,j614s";soc="apple,t6041";assert(rejected());}
'''
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'gate.c').write_text(program);subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',str(p/'gate.c'),'-o',str(p/'gate')],check=True,capture_output=True);subprocess.run([str(p/'gate')],check=True)
