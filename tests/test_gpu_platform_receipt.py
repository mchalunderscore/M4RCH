import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('receipt_check', Path(__file__).resolve().parents[1] / 'tools/gpu/check-platform-receipt.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReceiptCheck(unittest.TestCase):
    def fixture(self):
        arena = bytearray(m.PAGE)
        obj = {'name': 'hardware', 'arena_offset': 0, 'gpu_va': hex(m.ROOT),
               'input_bytes': m.PAGE, 'reserved_bytes': m.PAGE}
        baseline = {'base': hex(m.ROOT), 'mmio_virtual_base': hex(m.MMIO),
                    'arena_bytes': m.PAGE, 'static_map_sha256': 'static',
                    'voltage_adt_sha256': 'adt', 'voltage_input_sha256': {},
                    'mmio_leaves': [], 'mmio_descriptors': [], 'objects': [dict(obj)]}
        receipt = copy.deepcopy(baseline)
        for slot, (pa, va) in m.PLATFORM.items():
            receipt['mmio_leaves'].append({'physical': pa, 'gpu_va': va, 'readonly': False})
            receipt['mmio_descriptors'].append({'slot': slot, 'physical': hex(pa),
                                               'gpu_va': hex(va), 'size': hex(m.PAGE), 'readonly': False})
            struct.pack_into('<QQII', arena, 0x640 + slot * 40, pa, va, m.PAGE, m.PAGE)
        receipt['mapped_pages'] = 3
        receipt['arena_sha256'] = hashlib.sha256(arena).hexdigest()
        receipt['objects'][0]['input_sha256'] = receipt['arena_sha256']
        return baseline, receipt, arena

    def test_exact_candidate(self):
        self.assertEqual(m.check(*self.fixture())['result'], 'PASS')

    def test_unexpected_mapping(self):
        b, r, a = self.fixture()
        r['mmio_leaves'].append({'physical': 0x502418000, 'gpu_va': 0xfffffc2001b1c000, 'readonly': False})
        with self.assertRaisesRegex(ValueError, 'exactly two'):
            m.check(b, r, a)

    def test_readonly_platform(self):
        b, r, a = self.fixture()
        r['mmio_leaves'][0]['readonly'] = True
        with self.assertRaisesRegex(ValueError, 'exactly two'):
            m.check(b, r, a)

    def test_arena_disagrees_with_receipt(self):
        b, r, a = self.fixture()
        struct.pack_into('<Q', a, 0x640, 0)
        r['arena_sha256'] = hashlib.sha256(a).hexdigest()
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            m.check(b, r, a)
