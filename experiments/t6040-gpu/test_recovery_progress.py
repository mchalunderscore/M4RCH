"""RAM-only checks of marker shape, journal validation and prefix selection."""
import importlib.util
import struct
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'recovery_progress', Path(__file__).with_name('analyze-recovery-progress.py'))
PROGRESS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROGRESS)
J = PROGRESS.JOURNAL
PRIOR = '[1.0] before\n'


def record(packed=0x04000046, args=(0, 0x1000, 7, 0), function=0):
    raw = bytearray(72)
    struct.pack_into('<IQ4Q2I', raw, 0, 5, 123, *args, packed, function)
    return raw


def journal(records, flags=0):
    data = bytearray(J.HEADER.size + J.CAPACITY * J.ENTRY.size)
    J.HEADER.pack_into(data, 0, J.MAGIC, J.VERSION, J.ENTRY.size, J.CAPACITY,
                       len(records), flags, 0, 0, 0, 0, 0, 0)
    for i, raw in enumerate(records):
        J.ENTRY.pack_into(data, J.HEADER.size + i * J.ENTRY.size, 10, i % 512, i, raw)
    return data


def boundary(cycle, prefix, status=0):
    return (f'[2.0] m4rch recovery-trace-boundary: cycle={cycle} '
            f'before_host_phase2_records={prefix} status={status:#x}\n')


class RecoveryProgressTests(unittest.TestCase):
    def test_wrong_role_argument_function_and_pre_prefix_are_excluded(self):
        data = journal([record(), record(packed=0x03000046),
                        record(args=(0, 0x400, 7, 0)), record(function=1),
                        record(args=(0, 0x1000, 0x100000000, 0)), record()])
        result = PROGRESS.analyze(data, PRIOR, PRIOR + boundary(1, 1))
        self.assertTrue(result['attribution_qualified'])
        self.assertEqual([r['sequence'] for r in result['attributions'][0]['matching_records']], [5])
        self.assertEqual(result['trace_records'][5]['args'], [0, 0x1000, 7, 0])
        self.assertEqual(result['trace_records'][5]['timestamp'], 123)
        self.assertEqual(result['attribution_scope'], 'host-journal-prefix-selection')
        self.assertFalse(result['phase_token_timestamp_chronology_verified'])
        self.assertTrue(result['manual_chronology_review_required'])

    def test_each_cycle_stops_at_next_prefix(self):
        result = PROGRESS.analyze(journal([record()] * 5), PRIOR,
                                  PRIOR + boundary(1, 1) + boundary(2, 3))
        self.assertEqual([[r['sequence'] for r in a['matching_records']]
                          for a in result['attributions']], [[1, 2], [3, 4]])

    def test_journal_or_boundary_status_blocks_attribution(self):
        for flags, status in ((8, 0), (0, 1)):
            with self.subTest(flags=flags, status=status):
                result = PROGRESS.analyze(journal([record()], flags), PRIOR,
                                          PRIOR + boundary(1, 0, status))
                self.assertFalse(result['attribution_qualified'])
                self.assertEqual(result['attributions'], [])

    def test_malformed_journal_is_rejected_by_shared_decoder(self):
        data = journal([record()])
        struct.pack_into('<I', data, J.HEADER.size + 4, 9)
        with self.assertRaisesRegex(ValueError, 'sequence mismatch'):
            PROGRESS.analyze(data, PRIOR, PRIOR + boundary(1, 0))
        with self.assertRaisesRegex(ValueError, 'full receive journal snapshot'):
            PROGRESS.analyze(journal([])[:-1], PRIOR, PRIOR)

    def test_absent_or_old_boundary_cannot_attribute(self):
        for prior, logs in ((PRIOR, PRIOR + '[2.0] no boundary\n'),
                            (PRIOR + boundary(1, 0), PRIOR + boundary(1, 0) + '[3.0] later\n'),
                            (PRIOR, '[4.0] unrelated wrapped log\n')):
            with self.subTest(logs=logs):
                result = PROGRESS.analyze(journal([record()]), prior, logs)
                self.assertFalse(result['attribution_qualified'])
                self.assertEqual(result['attributions'], [])

    def test_invalid_or_backwards_prefix_cannot_attribute(self):
        for suffix in (boundary(1, 2), boundary(1, 1) + boundary(2, 0)):
            result = PROGRESS.analyze(journal([record()]), PRIOR, PRIOR + suffix)
            self.assertFalse(result['attribution_qualified'])
            self.assertEqual(result['attributions'], [])


if __name__ == '__main__':
    unittest.main()
