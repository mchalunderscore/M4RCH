import importlib.util
from pathlib import Path
import struct
import unittest


spec = importlib.util.spec_from_file_location(
    'agx_pio', Path(__file__).resolve().parents[1] / 'tools/gpu/extract-agx-pio.py')
pio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pio)


def fixture():
    data = bytearray(512)
    struct.pack_into('<8I', data, 0, 0xfeedfacf, 0x100000c, 0, 11, 2, 96, 0, 0)
    struct.pack_into('<II16sQQQQiiII', data, 32, 0x19, 72, b'__TEXT',
                     0x1000, 32, 256, 32, 1, 1, 0, 0)
    name = b'\0__ZL35AGFPIOGFXHALRelativeOffsetTableG16X\0'
    struct.pack_into('<6I', data, 104, 2, 24, 320, 1, 352, len(name))
    struct.pack_into('<IBBHQ', data, 320, 1, 0x0e, 1, 0, 0x1000)
    data[352:352 + len(name)] = name
    struct.pack_into('<IIQIIQ', data, 256, 33, 0xd44000, 0x4000, 0xdadadada, 0, 0)
    return data


class AgxPioTests(unittest.TestCase):
    def test_numeric_records_are_not_pointer_rebased(self):
        result = pio.extract(fixture(), 1)
        record = result['records'][0]
        self.assertEqual(record['hal_resource_id'], 33)
        self.assertEqual(record['relative_offset'], '0xd44000')
        self.assertEqual(record['length'], '0x4000')
        self.assertEqual(record['alternate_offset'], '0xdadadada')

    def test_reject_table_crossing_file_backed_segment(self):
        with self.assertRaises(ValueError):
            pio.extract(fixture(), 2)

    def test_reject_undefined_table_symbol(self):
        data = fixture()
        data[324] = 1
        with self.assertRaises(ValueError):
            pio.extract(data, 1)

    def test_reject_truncated_command(self):
        with self.assertRaises(ValueError):
            pio.extract(fixture()[:110], 1)


if __name__ == '__main__':
    unittest.main()
