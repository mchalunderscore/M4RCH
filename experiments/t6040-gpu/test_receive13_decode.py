#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import struct
import unittest
spec = importlib.util.spec_from_file_location('decoder', Path(__file__).with_name('decode-receive13.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReceiveDecode(unittest.TestCase):
    def test_wrap_and_limit_without_mutation(self):
        state, ring = bytearray(48), bytearray(256*72)
        struct.pack_into('<I', state, 0, 254)
        struct.pack_into('<I', state, 32, 2)
        for i in [254, 255, 0, 1]: struct.pack_into('<I', ring, i*72, i+100)
        before = bytes(state), bytes(ring)
        result = module.decode_ring(state, ring, 3)
        self.assertEqual([e['index'] for e in result['entries']], [254, 255, 0])
        self.assertEqual([e['type'] for e in result['entries']], [354, 355, 100])
        self.assertEqual(result['pending_modulo_256'], 4)
        self.assertTrue(result['truncated'])
        self.assertEqual(before, (bytes(state), bytes(ring)))
    def test_cursor_and_extent_rejected(self):
        state = bytearray(48)
        struct.pack_into('<I', state, 32, 256)
        with self.assertRaises(ValueError): module.decode_ring(state, bytes(256*72))
        with self.assertRaises(ValueError): module.decode_ring(bytes(47), bytes(256*72))
    def test_equal_cursors_empty(self):
        self.assertEqual(module.decode_ring(bytes(48), bytes(256*72))['entries'], [])

if __name__ == '__main__': unittest.main()
