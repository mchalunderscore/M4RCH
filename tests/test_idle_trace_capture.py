"""Guard the one-shot collector against wrong kernels and accidental workloads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'experiments/t6040-idle/collect-trace.py'
spec=importlib.util.spec_from_file_location('idle_trace_capture',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class IdleTraceCapture(unittest.TestCase):
    def test_wrong_build_stops_before_creating_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'capture'
            with patch.object(m.platform,'machine',return_value='aarch64'), patch.object(m,'kernel_build_id',return_value='wrong'), patch.object(Path,'read_text',return_value=json.dumps({'build_id':'expected'})), patch('sys.argv',['collect-trace.py',str(output)]):
                with self.assertRaisesRegex(ValueError,'exact CPU4'):m.main()
            self.assertFalse(output.exists())

    def test_read_only_capture_has_no_worker_or_control_path(self):
        source=SCRIPT.read_text()
        for forbidden in ('sched_setaffinity','wake_task','ThreadPool','time.sleep','modprobe','/dev/mem'):
            self.assertNotIn(forbidden,source)
        self.assertIn('experimental_t6040_idle_trace',source)
        self.assertIn('m4rch_pmu_fixed',source)
        self.assertIn("['journalctl', '-b', '-k', '--no-pager']",source)
