#!/usr/bin/env python3
"""Meaningful boundary checks for offline graph packing and relocations."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('assembler', Path(__file__).with_name('assemble-init-graph.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
BASE = 0xfffffc2000100000


def fixture():
    # Marker data verifies opaque fields survive. Unknown target is explicitly
    # sized only for this test, not claimed as a firmware layout.
    return {obj['name']: bytes([0x5a]) * (obj['extent'] or 0x100)
            for obj in a.graph_plan.plan()['objects']}


class GraphTests(unittest.TestCase):
    def test_two_page_status_and_every_pointer_resolves(self):
        arena, receipt = a.assemble(fixture(), BASE)
        objects = {o['name']: o for o in receipt['objects']}
        self.assertEqual(objects['status_b']['reserved_bytes'], 0x8000)
        self.assertEqual(objects['power']['reserved_bytes'], 0x8000)
        self.assertEqual(len(arena), 19 * 0x4000)
        for edge in receipt['pointers']:
            position = objects[edge['parent']]['arena_offset'] + edge['byte_offset']
            self.assertEqual(struct.unpack_from('<Q', arena, position)[0],
                             BASE + objects[edge['target']]['arena_offset'])
        self.assertFalse(receipt['publishable'])

    def test_unknown_bytes_survive_and_allocations_do_not_alias(self):
        templates = fixture()
        arena, receipt = a.assemble(templates, BASE)
        patched = {o['name']: set() for o in receipt['objects']}
        for edge in receipt['pointers']:
            patched[edge['parent']].update(range(edge['byte_offset'], edge['byte_offset'] + 8))
        end = 0
        for obj in receipt['objects']:
            start = obj['arena_offset']
            self.assertGreaterEqual(start, end)
            data = templates[obj['name']]
            for i, byte in enumerate(data):
                if i not in patched[obj['name']]:
                    self.assertEqual(arena[start + i], byte)
            end = start + obj['reserved_bytes']

    def test_missing_unknown_target_does_not_get_zero_default(self):
        templates = fixture()
        del templates['extra_root_1']
        with self.assertRaises(ValueError):
            a.assemble(templates, BASE)

    def test_small_status_rejected_even_when_one_page_would_fit(self):
        templates = fixture()
        templates['status_b'] = bytes(0x4000)
        with self.assertRaises(ValueError):
            a.assemble(templates, BASE)

    def test_address_alignment_window_and_overflow(self):
        for base in (BASE + 1, 0x100000, 0xfffffc3fffffc000):
            with self.assertRaises(ValueError):
                a.assemble(fixture(), base)


if __name__ == '__main__':
    unittest.main()
