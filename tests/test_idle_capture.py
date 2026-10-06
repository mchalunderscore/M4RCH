import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('idle_capture',Path(__file__).resolve().parents[1]/'experiments/t6040-idle/collect.py')
capture=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)

class IdleCapture(unittest.TestCase):
    def test_arithmetic_and_task_wakes(self):
        expected=capture.arithmetic()
        self.assertEqual(len(expected),64)
        with patch.object(capture.os,'sched_setaffinity',create=True) as set_affinity,patch.object(capture.os,'sched_getaffinity',return_value={8},create=True),patch.object(capture.time,'sleep') as sleep:
            result=capture.wake_task(8,expected)
            set_affinity.assert_called_once_with(0,{8})
            self.assertEqual(sleep.call_count,40)
            self.assertTrue(result['arithmetic_passed'])

    def test_integrity_or_affinity_failure_stops(self):
        for expected,affinity in [('wrong',{0}),(capture.arithmetic(),{1})]:
            with patch.object(capture.os,'sched_setaffinity',create=True),patch.object(capture.os,'sched_getaffinity',return_value=affinity,create=True),patch.object(capture.time,'sleep') as sleep:
                with self.assertRaises(ValueError):capture.wake_task(0,expected)
                sleep.assert_not_called()

if __name__=='__main__':unittest.main()
