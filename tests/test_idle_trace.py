"""Validate the applied diagnostic path, not merely its patch text."""
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
from hardware_profile import IDLE_OPTIN, IDLE_TRACE, EARLY_FAULT

class IdleTrace(unittest.TestCase):
    def test_applied_trace_and_original_sequence(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / IDLE_TRACE['source']
            source.parent.mkdir(parents=True)
            source.write_bytes((ROOT / 'tests/fixtures/cpuidle-apple-base.c').read_bytes())
            original = None
            for desc in (IDLE_OPTIN, IDLE_TRACE):
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), desc['base_source_sha256'])
                subprocess.run(['git','apply','--whitespace=error-all',str(ROOT / desc['path'])],cwd=temp,check=True,capture_output=True)
                text=source.read_text()
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), desc['result_source_sha256'])
                first=text[text.index('asm('):text.index(');',text.index('asm('))+2]
                if original is None: original=first
                else: self.assertEqual(first,original)
            trace=text[text.index('m4rch_cpu_deep_wfi_trace, @function'):text.index('void m4rch_cpu_deep_wfi_trace')]
            self.assertEqual(trace.count('str x0, [sp, #-16]!'),7)
            self.assertEqual(trace.count('ldr x0, [sp], #16'),7)
            self.assertEqual(trace.count('bl m4rch_idle_checkpoint'),7)
            self.assertEqual(trace.count('mrs x0, s3_5_c15_c5_0'),2)
            self.assertEqual(trace.count('msr s3_5_c15_c5_0, x0'),2)
            self.assertEqual(trace.count('"wfi'),1)
            self.assertIn('smp_processor_id() != 4 || READ_ONCE(trace_attempted)',text)
            self.assertLess(text.index('WRITE_ONCE(trace_attempted, true)'),text.index('if (cpu_pm_enter())'))
            self.assertIn('test_and_set_bit(stage, &trace_seen)',text)
            self.assertIn('static bool experimental_t6040_idle_trace;',text)
            for stage in range(3,10): self.assertIn(f'mov x0, #{stage}',trace)

    def test_early_fault_uses_saved_frame_only(self):
        patch=(ROOT / EARLY_FAULT['path']).read_text()
        added='\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        self.assertIn('regs->pc',added)
        self.assertIn('regs->regs[30]',added)
        self.assertNotIn('read_sysreg',added)
        self.assertNotIn('get_kernel_nofault',added)
        self.assertLess(patch.index('M4RCH_FAULT'),patch.index('notify_die'))
