import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import subprocess

SPEC = importlib.util.spec_from_file_location('cpufreq_capture', Path(__file__).resolve().parents[1] / 'experiments/cpufreq-snapshot/collect.py')
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


def sample():
    return {'schema': 1, 'atomic': False, 'policy_cpu': 0, 'init_cpus': '0,5-7',
            'compatible': 'apple,t8112-cluster-cpufreq', 'max_pstate': 31, 'has_ps2': False,
            'command': {'offset': 32, 'width': 64, 'raw': '0x0000000002000013',
                        'begin_ns': 100, 'end_ns': 110, 'mask': '0x1f', 'shift': 0,
                        'state': 19, 'frequency_khz': 4512000, 'busy': False, 'set': True},
            'status': {'available': True, 'offset': 80, 'width': 32, 'raw': '0x000001c0',
                       'begin_ns': 111, 'end_ns': 120, 'mask': '0x3e0', 'shift': 5},
            'get_rate_state': 14, 'get_rate_khz': 3924000, 'policy_cur_khz': 4512000,
            'policy_begin_ns': 121, 'policy_end_ns': 130,
            'opps': [{'state': 14, 'frequency_khz': 3924000, 'flags': 0},
                     {'state': 19, 'frequency_khz': 4512000, 'flags': 0}]}


class SnapshotTests(unittest.TestCase):
    def test_high_command_lower_status_is_preserved(self):
        r = capture.analyze(json.dumps(sample()))
        self.assertEqual((r['command_khz'], r['get_rate_khz']), (4512000, 3924000))
        self.assertFalse(r['mapping_missing'])

    def test_raw_decode_disagreement_is_rejected(self):
        d = sample(); d['get_rate_state'] = 19; d['get_rate_khz'] = 4512000
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))

    def test_fallback_does_not_claim_status_read(self):
        d = sample(); d['status'].update(available=False, raw='0x0', mask='0x0', shift=0, begin_ns=0, end_ns=0)
        d.update(get_rate_state=19, get_rate_khz=4512000)
        self.assertEqual(capture.analyze(json.dumps(d))['get_rate_khz'], 4512000)
        d['status']['raw'] = '0x1'
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))

    def test_unknown_state_kept_as_mapping_diagnostic(self):
        d = sample(); d['status']['raw'] = '0x3e0'; d.update(get_rate_state=31, get_rate_khz=0)
        self.assertTrue(capture.analyze(json.dumps(d))['mapping_missing'])

    def test_reversed_read_timestamps_are_rejected(self):
        d = sample(); d['status']['begin_ns'] = 90
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))

    def test_duplicate_opp_and_oversized_register_rejected(self):
        d = sample(); d['opps'].append(copy.deepcopy(d['opps'][0]))
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))
        d = sample(); d['command']['raw'] = '0x10000000000000000'
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))

    def test_policy_cpu_must_be_in_membership(self):
        d = sample(); d['policy_cpu'] = 8
        with self.assertRaises(ValueError): capture.analyze(json.dumps(d))


    def test_timeout_preserves_partial_raw(self):
        with patch.object(capture.time, 'CLOCK_BOOTTIME', 1, create=True), patch.object(capture.time, 'clock_gettime_ns', side_effect=[100,200]), patch.object(capture.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['cat'], 3, output=b'partial')):
            r = capture.read_snapshot(Path('/unused'))
        self.assertEqual(r['raw'], 'partial')
        self.assertIn('timeout', r['error'])

    def test_failed_unload_is_logged_without_retry(self):
        with tempfile.TemporaryDirectory() as d, patch.object(capture.time, 'CLOCK_BOOTTIME', 1, create=True), patch.object(capture.time, 'clock_gettime_ns', return_value=100), patch.object(capture.subprocess, 'run', return_value=subprocess.CompletedProcess(['rmmod'], 1, '', 'busy')) as run:
            with self.assertRaises(RuntimeError): capture.unload_probe(Path(d))
            self.assertEqual(run.call_count, 1)
            r = json.loads((Path(d)/'cleanup.jsonl').read_text())
            self.assertEqual(r['stderr'], 'busy')

    def test_unload_timeout_is_logged(self):
        with tempfile.TemporaryDirectory() as d, patch.object(capture.time, 'CLOCK_BOOTTIME', 1, create=True), patch.object(capture.time, 'clock_gettime_ns', return_value=100), patch.object(capture.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['rmmod'], 10)):
            with self.assertRaises(RuntimeError): capture.unload_probe(Path(d))
            self.assertIn('timeout', json.loads((Path(d)/'cleanup.jsonl').read_text())['error'])

if __name__ == '__main__': unittest.main()
