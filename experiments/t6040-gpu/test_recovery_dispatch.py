"""Offline adversarial checks for recovery chronology and dispatch pairing."""
import importlib.util
import struct
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'recovery_dispatch', Path(__file__).with_name('analyze-recovery-dispatch.py'))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)
J = D.PROGRESS.JOURNAL
PRIOR = '[1.0] before\n'


def record(event, timestamp, args, function=0):
    raw = bytearray(72)
    struct.pack_into('<IQ4Q2I', raw, 0, 5, timestamp, *args, event, function)
    return raw


def marker(timestamp=100):
    return record(0x04000046, timestamp, (0, 0x1000, 4, 0))


def entry(timestamp=200, mask=D.BIT25):
    return record(0x12f, timestamp, (mask, mask, 0, 0))


def leave(timestamp=300, mask=D.BIT25):
    return record(0x130, timestamp, (mask, 0, 0, 0))


def journal(records, flags=0):
    data = bytearray(J.HEADER.size + J.CAPACITY * J.ENTRY.size)
    J.HEADER.pack_into(data, 0, J.MAGIC, J.VERSION, J.ENTRY.size, J.CAPACITY,
                       len(records), flags, 0, 0, 0, 0, 0, 0)
    for index, raw in enumerate(records):
        J.ENTRY.pack_into(data, J.HEADER.size + index * J.ENTRY.size,
                          10, index % 512, index, raw)
    return data


def pre(cycle=1, counter=1, token=0, control=32, prefix=0):
    return (f'[2.0] m4rch recovery-send: endpoint=33 packet={0x0086000000000000 | token:#x}\n'
            f'[2.1] m4rch recovery-state: cycle={cycle} phase=pre counter={counter} '
            f'state=1 host_stop=1 request_state=2 request_flag=1 control={control}/{control}/{control}\n'
            f'[2.2] m4rch recovery-trace-boundary: cycle={cycle} '
            f'before_host_phase2_records={prefix} status=0x0\n')


def post(cycle=1, counter=1, control=32):
    return (f'[3.0] m4rch recovery-state: cycle={cycle} phase=post counter={counter} '
            f'state=3 host_stop=1 request_state=0 request_flag=1 control={control}/{control}/{control}\n'
            f'[3.1] m4rch recovery-state: cycle={cycle} phase=fresh-control-consumed counter={counter} '
            f'state=0 host_stop=1 request_state=0 request_flag=0 control={control+1}/{control+1}/{control+1}\n')


def analyze(records, suffix=None, flags=0):
    return D.analyze(journal(records, flags), PRIOR, PRIOR + (suffix if suffix is not None else pre()))


class RecoveryDispatchTests(unittest.TestCase):
    def test_ordered_pair_is_conditional_and_cannot_authorize_retirement(self):
        result = analyze([marker(), entry(), leave()], pre() + post())
        cycle = result['cycles'][0]
        self.assertTrue(cycle['observation_checks_passed'])
        self.assertTrue(all(cycle['conditional_support'].values()))
        self.assertEqual(len(cycle['later_bit25_pairs']), 1)
        self.assertEqual(len(cycle['post_phase_observations']), 1)
        self.assertEqual(len(cycle['fresh_control_observations']), 1)
        self.assertFalse(cycle['marker_source_manually_verified'])
        self.assertFalse(cycle['semaphore_consumption_verified'])
        self.assertFalse(cycle['final_power_ack_verified'])
        for key in ('recovery_reuse_verified', 'dma_retirement_verified', 'rendering_verified'):
            self.assertFalse(result[key])

    def test_pre_prefix_records_are_excluded(self):
        result = analyze([marker(10), entry(20), leave(30), marker(100)], pre(prefix=3))
        cycle = result['cycles'][0]
        self.assertEqual([r['sequence'] for r in cycle['marker_candidates']], [3])
        self.assertTrue(cycle['conditional_support']['after_first_power_wait'])
        self.assertFalse(cycle['conditional_support']['sampler_wait_passed'])

    def test_wrong_role_function_or_marker_arguments_cannot_supply_evidence(self):
        for raw in (record(0x03000046, 100, (0, 0x1000, 4, 0)),
                    record(0x04000046, 100, (0, 0x1000, 4, 0), 1),
                    record(0x04000046, 100, (0, 0x1000, 7, 0))):
            with self.subTest(raw=raw.hex()):
                cycle = analyze([raw, entry(), leave()])['cycles'][0]
                self.assertFalse(any(cycle['conditional_support'].values()))

    def test_ambiguous_duplicate_marker_blocks_conditional_support(self):
        cycle = analyze([marker(100), marker(150), entry(), leave()])['cycles'][0]
        self.assertEqual(len(cycle['marker_candidates']), 2)
        self.assertFalse(any(cycle['conditional_support'].values()))

    def test_backwards_or_duplicate_timestamps_block_support(self):
        for timestamp in (99, 100):
            with self.subTest(timestamp=timestamp):
                result = analyze([marker(), entry(timestamp), leave()])
                self.assertFalse(result['trace_timestamps_strictly_increasing'])
                self.assertFalse(any(result['cycles'][0]['conditional_support'].values()))

    def test_entry_before_marker_cannot_be_a_later_ack(self):
        cycle = analyze([entry(90), marker(), leave()])['cycles'][0]
        self.assertEqual(cycle['later_bit25_entries'], [])
        self.assertEqual(cycle['later_bit25_pairs'], [])

    def test_unmatched_or_nested_dispatch_has_no_paired_ack_return(self):
        for records in ([marker(), entry()],
                        [marker(), entry(), leave(mask=1)],
                        [marker(), entry(), entry(250, mask=1), leave()]):
            with self.subTest(records=[r.hex() for r in records]):
                cycle = analyze(records)['cycles'][0]
                self.assertTrue(cycle['conditional_support']['sampler_wait_passed'])
                self.assertFalse(cycle['conditional_support']['scheduler_ack_handler_returned'])
                self.assertTrue(cycle['dispatch_pairing_errors'])

    def test_duplicate_same_mask_entries_cannot_supply_a_paired_return(self):
        cycle = analyze([marker(), entry(), entry(250), leave()])['cycles'][0]
        self.assertEqual(cycle['later_bit25_pairs'], [])
        self.assertFalse(cycle['conditional_support']['scheduler_ack_handler_returned'])
        self.assertTrue(cycle['dispatch_pairing_errors'])

    def test_native_pending_mask_invariants_are_checked(self):
        for records in ([marker(), record(0x12f, 200, (D.BIT25, 0, 0, 0)), leave()],
                        [marker(), entry(), record(0x130, 300, (D.BIT25, D.BIT25, 0, 0))]):
            cycle = analyze(records)['cycles'][0]
            self.assertFalse(cycle['conditional_support']['scheduler_ack_handler_returned'])
            self.assertTrue(cycle['dispatch_pairing_errors'])

    def test_invalid_entry_does_not_clear_pairing_ambiguity(self):
        invalid = record(0x12f, 250, (D.BIT25, 0, 0, 0))
        for prefix in ([marker(), entry()], [marker()]):
            cycle = analyze(prefix + [invalid, entry(275), leave()])['cycles'][0]
            self.assertEqual(cycle['later_bit25_pairs'], [])
            self.assertFalse(cycle['conditional_support']['scheduler_ack_handler_returned'])
            self.assertTrue(cycle['dispatch_pairing_errors'])

    def test_wrong_token_or_incomplete_pre_phase_blocks_support(self):
        for suffix in (pre(counter=2),
                       pre().replace('request_state=2', 'request_state=0'),
                       pre().replace('control=32/32/32', 'control=31/32/32'),
                       pre(control=128),
                       '\n'.join(pre().splitlines()[1:]) + '\n'):
            with self.subTest(suffix=suffix):
                cycle = analyze([marker(), entry(), leave()], suffix)['cycles'][0]
                self.assertFalse(cycle['observation_checks_passed'])
                self.assertFalse(any(cycle['conditional_support'].values()))

    def test_repeated_cycle_numbers_are_separated_by_prefix_and_token(self):
        suffix = pre() + post() + pre(counter=2, token=1, control=33, prefix=3) + post(counter=2, control=33)
        result = analyze([marker(), entry(), leave(), marker(400), entry(500), leave(600)], suffix)
        self.assertEqual([c['cycle'] for c in result['cycles']], [1, 1])
        self.assertEqual([c['request']['token'] for c in result['cycles']], [0, 1])
        self.assertEqual([[p['entry']['sequence'] for p in c['later_bit25_pairs']]
                          for c in result['cycles']], [[1], [4]])
        self.assertEqual([[s['control'][0] for s in c['fresh_control_observations']]
                          for c in result['cycles']], [[33], [34]])

    def test_a_later_boundary_cannot_borrow_an_earlier_recovery_request(self):
        second = '\n'.join(pre(prefix=3).splitlines()[1:]) + '\n'
        result = analyze([marker(), entry(), leave(), marker(400), entry(500), leave(600)],
                         pre() + post() + second)
        self.assertIsNone(result['cycles'][1]['request'])
        self.assertFalse(any(result['cycles'][1]['conditional_support'].values()))

    def test_new_request_with_stale_counter_is_rejected(self):
        result = analyze([marker(), entry(), leave(), marker(400), entry(500), leave(600)],
                         pre() + post() + pre(prefix=3))
        self.assertFalse(any(result['cycles'][1]['conditional_support'].values()))

    def test_stale_post_or_wrong_control_advance_is_excluded(self):
        for suffix in (pre() + post(counter=2),
                       pre() + post().replace('control=33/33/33', 'control=34/34/34'),
                       pre() + post().replace('request_flag=0', 'request_flag=1')):
            cycle = analyze([marker(), entry(), leave()], suffix)['cycles'][0]
            self.assertEqual(cycle['fresh_control_observations'], [])

    def test_missing_or_old_log_boundary_has_no_attribution(self):
        for prior, logs in ((PRIOR, PRIOR), (PRIOR + pre(), PRIOR + pre() + '[9.0] later\n'),
                            (PRIOR, '[9.0] rotated\n')):
            result = D.analyze(journal([marker()]), prior, logs)
            self.assertEqual(result['cycles'], [])
            self.assertTrue(result['observation_errors'])

    def test_invalid_journal_and_boundary_status_cannot_support_progress(self):
        for flags in (1, 2, 4, 8, 128):
            result = analyze([marker(), entry(), leave()], flags=flags)
            self.assertFalse(any(result['cycles'][0]['conditional_support'].values()))
        result = analyze([marker()], pre().replace('status=0x0', 'status=0x1'))
        self.assertFalse(result['cycles'][0]['observation_checks_passed'])
        with self.assertRaisesRegex(ValueError, 'full receive journal snapshot'):
            D.analyze(journal([])[:-1], PRIOR, PRIOR)


if __name__ == '__main__':
    unittest.main()
