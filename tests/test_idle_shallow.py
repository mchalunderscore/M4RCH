from pathlib import Path
import subprocess
import tempfile
import test_wfi_continuous as continuous
class Shallow(continuous.Continuous):
 shallow=True
 def source(self):
  base,current=super().source()
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'drivers/cpuidle/cpuidle-apple.c';p.parent.mkdir(parents=True);p.write_text(current)
   subprocess.run(['git','apply','--whitespace=error-all',str(continuous.ROOT/'experiments/t6040-idle/shallow-wfi.patch')],cwd=temp,check=True,capture_output=True)
   source=p.read_text()
   self.assertIn('apple_idle_driver.state_count = 1;',source)
   self.assertIn('states[STATE_WFI].enter = apple_enter_idle;',source)
   return base,source
