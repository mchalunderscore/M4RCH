import configparser
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('fix_zoom', Path(__file__).resolve().parents[1]/'tools/display/fix-zoom.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ZoomFix(unittest.TestCase):
    def test_preserves_compositing_scaling_and_other_settings(self):
        before = '[Compositing]\nEnabled=true\n[Effect-zoom]\nInitialZoom=1.1959\n[Tiling][abc]\npadding=4\n[Xwayland]\nScale=2\n'
        after = m.changed_config(before)
        c = configparser.ConfigParser()
        c.read_string(after)
        self.assertEqual(c['Effect-zoom']['InitialZoom'], '1')
        self.assertEqual(c['Plugins']['zoomEnabled'], 'false')
        self.assertEqual(c['Compositing']['Enabled'], 'true')
        self.assertEqual(c['Xwayland']['Scale'], '2')
        self.assertEqual(c['Tiling][abc']['padding'], '4')
        self.assertEqual(m.changed_config(after), after)
