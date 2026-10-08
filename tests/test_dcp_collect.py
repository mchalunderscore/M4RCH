import importlib.util
import tempfile
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('dcp_collect', Path(__file__).resolve().parents[1]/'experiments/t6040-dcp/collect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DCPCollection(unittest.TestCase):
    def test_selected_properties_keep_raw_cell_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            node = root/'soc/dcp@402e00000'
            node.mkdir(parents=True)
            (node/'reg').write_bytes(bytes.fromhex('0000000402e00000'))
            (node/'serial-number').write_bytes(b'private')
            other = root/'soc/other'
            other.mkdir()
            (other/'reg').write_bytes(b'ignored')
            result = m.collect_dt(root)
            self.assertEqual(list(result), ['soc/dcp@402e00000/reg'])
            self.assertEqual(result['soc/dcp@402e00000/reg']['hex'], '0000000402e00000')

    def test_symlinks_are_not_properties(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'dcp').mkdir()
            (root/'outside').write_bytes(b'private')
            (root/'dcp/reg').symlink_to(root/'outside')
            self.assertEqual(m.collect_dt(root), {})
