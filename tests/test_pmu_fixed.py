import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'experiments/pmu-fixed/collect.py'
spec=importlib.util.spec_from_file_location('pmu_fixed_collect',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class FixedCounterCaptureTests(unittest.TestCase):
    def raw(self):
        head='cpu=0 midr=611f0551 status=0 timer_hz=24000000 pmcr0=0000000000000000 pmcr1=0000000000000000 final0=0000000000000000 final1=0000000000000000\n'
        return head+'\n'.join(f'loops={n} cycles={n*2} instructions={n*3+10} ticks={n//64}' for n in (256,4096,65536))+'\n'

    def test_valid_counts_keep_measurement_limit(self):
        result=module.analyze(self.raw(),0)
        self.assertTrue(result['control_restored'])
        self.assertEqual(result['samples'][2]['instructions'],196618)
        self.assertIn('not a task perf event',result['limit'])

    def test_refusals_and_failed_restoration_cannot_become_frequency_results(self):
        raw=self.raw()
        for bad in (raw.replace('status=0','status=-16'),
                    raw.replace('final0=0000000000000000','final0=0000000000000001'),
                    raw.replace('cycles=512','cycles=0'),
                    raw.replace('instructions=778','instructions=1'),
                    raw.replace('instructions=778','instructions=2000'),
                    raw.replace('ticks=4','ticks=999999'),
                    raw.replace('timer_hz=24000000','timer_hz=0'),
                    '\n'.join(raw.splitlines()[:-1]),''):
            with self.subTest(raw=bad):
                with self.assertRaises(ValueError):module.analyze(bad,0)
        with self.assertRaises(ValueError):module.analyze(raw,1)
