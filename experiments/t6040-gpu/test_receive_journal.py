#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('receive_journal', Path(__file__).with_name('decode-receive-journal.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def snapshot(records=(), *, flags=0, doorbells=0):
    result = bytearray(decoder.HEADER.size + decoder.CAPACITY * decoder.ENTRY.size)
    decoder.HEADER.pack_into(result, 0, decoder.MAGIC, decoder.VERSION,
                            decoder.ENTRY.size, decoder.CAPACITY, len(records),
                            flags, doorbells, 0, 0, 0, 0, 0)
    for sequence, (ring_id, ring_index, raw) in enumerate(records):
        decoder.ENTRY.pack_into(result, decoder.HEADER.size + sequence * decoder.ENTRY.size,
                                ring_id, ring_index, sequence, raw)
    return result


class ReceiveJournalDecode(unittest.TestCase):
    def test_record_metadata_and_unknown_type_preserved(self):
        raw = struct.pack('<I', 0xdeadbeef) + bytes(range(68))
        source = snapshot([(0, 255, raw), (9, 17, raw), (10, 511, raw), (11, 0, raw)], doorbells=7)
        before = bytes(source)
        report = decoder.decode(source)
        self.assertEqual(report['header']['doorbells'], 7)
        self.assertEqual(report['header']['used'], 4)
        self.assertEqual([e['sequence'] for e in report['entries']], [0, 1, 2, 3])
        self.assertEqual([e['ring_id'] for e in report['entries']], [0, 9, 10, 11])
        self.assertEqual([e['ring_index'] for e in report['entries']], [255, 17, 511, 0])
        self.assertEqual(report['entries'][1]['ring_name'], 'rx13_type2_validator_8')
        self.assertTrue(all(e['type'] == 0xdeadbeef and e['raw_hex'] == raw.hex()
                            for e in report['entries']))
        self.assertEqual(bytes(source), before)

    def test_empty_journal(self):
        report = decoder.decode(snapshot())
        self.assertEqual(report['entries'], [])
        self.assertEqual(report['authoritative_records_sha256'], hashlib.sha256(b'').hexdigest())
        self.assertFalse(report['overflow'])
        self.assertFalse(report['error'])

    def test_status_flags_preserved(self):
        report = decoder.decode(snapshot(flags=0x8f))
        self.assertTrue(report['overflow'])
        self.assertTrue(report['error'])
        self.assertTrue(report['invalid_cursors'])
        self.assertTrue(report['unexpected_record_or_message'])
        self.assertEqual(report['unknown_status_flags'], 0x80)
        self.assertEqual(report['header']['status_flags'], 0x8f)
        for flags, name in ((1, 'error'), (2, 'overflow'), (4, 'invalid_cursors'),
                            (8, 'unexpected_record_or_message')):
            with self.subTest(flags=flags):
                report = decoder.decode(snapshot(flags=flags))
                self.assertEqual([key for key in ('error', 'overflow', 'invalid_cursors',
                                                  'unexpected_record_or_message') if report[key]], [name])

    def test_only_used_prefix_is_authoritative(self):
        source = snapshot([(10, 256, bytes(72))])
        report = decoder.decode(source)
        tail = decoder.HEADER.size + decoder.ENTRY.size
        source[tail:tail + decoder.ENTRY.size] = bytes([0xff]) * decoder.ENTRY.size
        self.assertEqual(decoder.decode(source), report)
        decoder.ENTRY.pack_into(source, tail, 11, 255, 1, bytes([0x5a]) * 72)
        self.assertEqual(decoder.decode(source), report)
        struct.pack_into('<I', source, 16, 2)
        appended = decoder.decode(source)
        self.assertEqual(appended['entries'][:1], report['entries'])
        self.assertEqual(appended['entries'][1]['sequence'], 1)
        self.assertNotEqual(appended['authoritative_records_sha256'], report['authoritative_records_sha256'])

    def test_truncated_header_and_full_snapshot_rejected(self):
        source = snapshot()
        for length in (0, decoder.HEADER.size-1, decoder.HEADER.size, len(source)-1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                decoder.decode(source[:length])
        with self.assertRaises(ValueError):
            decoder.decode(source + b'\0')

    def test_bad_header_geometry_and_identity_rejected(self):
        for offset, value in ((0, 0), (4, 2), (8, 72), (12, decoder.CAPACITY-1),
                              (16, decoder.CAPACITY+1), (28, 1), (32, 1)):
            with self.subTest(offset=offset):
                source = snapshot()
                struct.pack_into('<I', source, offset, value)
                with self.assertRaises(ValueError):
                    decoder.decode(source)

    def test_sequence_corruption_rejected(self):
        source = snapshot([(0, 0, bytes(72)), (0, 1, bytes(72))])
        for sequence in (0, 2, 0xffffffff):
            with self.subTest(sequence=sequence):
                struct.pack_into('<I', source, decoder.HEADER.size + decoder.ENTRY.size + 4, sequence)
                with self.assertRaisesRegex(ValueError, 'sequence mismatch'):
                    decoder.decode(source)

    def test_ring_id_and_per_ring_index_bounds(self):
        for ring_id, index in ((12, 0), (0, 256), (1, 256), (9, 256), (10, 512), (11, 256)):
            with self.subTest(ring_id=ring_id, index=index), self.assertRaises(ValueError):
                decoder.decode(snapshot([(ring_id, index, bytes(72))]))
        for ring_id in range(12):
            maximum = 511 if ring_id == 10 else 255
            with self.subTest(ring_id=ring_id):
                self.assertEqual(decoder.decode(snapshot([(ring_id, maximum, bytes(72))]))
                                 ['entries'][0]['ring_index'], maximum)

    def test_cli_writes_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'receive-journal.bin'
            output = Path(directory) / 'receive-journal.json'
            source.write_bytes(snapshot([(11, 254, struct.pack('<I', 0x19) + bytes(68))]))
            result = subprocess.run([sys.executable, spec.origin, str(source), str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['entries'][0]['type'], 0x19)
            self.assertEqual(report['entries'][0]['ring_index'], 254)


if __name__ == '__main__':
    unittest.main()
