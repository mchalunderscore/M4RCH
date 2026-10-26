#!/usr/bin/env python3
"""Attribute saved RX14 progress markers to bounded recovery log intervals.

No hardware access. A marker is an observation, not a live PC, completed
recovery, rendered triangle, or resource retirement.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROOF = HERE.parents[1] / 'docs/evidence/2026-10-09-native-recovery-progress-trace.json'
PROOF_SHA256 = 'd258e8c24bdbcb26051a71e334cfb8c4237361f4d6cc6da55559081f45374881'
JOURNAL_NAME = 'notifications-after.bin'
BOUNDARY = re.compile(r'm4rch recovery-trace-boundary: cycle=(\d+) '
                      r'before_host_phase2_records=(\d+) status=(0x[0-9a-fA-F]+|0)\b')


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JOURNAL = load('recovery_progress_journal', 'decode-receive-journal.py')
LOGS = load('recovery_progress_logs', 'analyze-recovery.py')


def analyze(journal, prior, logs):
    decoded = JOURNAL.decode(journal)
    delta, interval = LOGS.log_delta(prior, logs)
    boundaries = [dict(cycle=int(m[1]), prefix=int(m[2]), status=int(m[3], 0))
                  for m in BOUNDARY.finditer(delta)]
    records = []
    unexpected_trace_types = 0
    for entry in decoded['entries']:
        if entry['ring_id'] != 10:
            continue
        if entry['type'] != 5:
            unexpected_trace_types += 1
            continue
        raw = bytes.fromhex(entry['raw_hex'])
        timestamp = struct.unpack_from('<Q', raw, 4)[0]
        args = list(struct.unpack_from('<4Q', raw, 0xc))
        packed, function = struct.unpack_from('<2I', raw, 0x2c)
        match = packed == 0x04000046 and function == 0 and (
            args[0] == 0 and args[1] == 0x1000 and args[2] <= 0xffffffff and args[3] == 0)
        records.append(dict(sequence=entry['sequence'], ring_index=entry['ring_index'],
                            timestamp=timestamp, packed_event=hex(packed),
                            firmware_role=packed >> 24, function_type=function,
                            args=args, matches_progress_shape=match))
    reasons = []
    if interval is None:
        reasons.append('No retained unique before/after log boundary')
    if not boundaries:
        reasons.append('No recovery trace boundary in the bounded log interval')
    if decoded['header']['status_flags']:
        reasons.append('Receive journal status is nonzero')
    if unexpected_trace_types:
        reasons.append('RX14 trace ring contains a record with a type other than5')
    used = decoded['header']['used']
    if any(b['cycle'] < 1 or b['prefix'] > used or b['status'] for b in boundaries):
        reasons.append('Invalid cycle, out-of-range prefix, or nonzero boundary status')
    if any(a['prefix'] > b['prefix'] for a, b in zip(boundaries, boundaries[1:])):
        reasons.append('Recovery journal prefixes move backwards')
    attributions = []
    if not reasons:
        for i, boundary in enumerate(boundaries):
            end = boundaries[i + 1]['prefix'] if i + 1 < len(boundaries) else used
            matches = [r for r in records if r['matches_progress_shape'] and
                       boundary['prefix'] <= r['sequence'] < end]
            attributions.append(dict(boundary_index=i, cycle=boundary['cycle'],
                                     prefix=boundary['prefix'], end_exclusive=end,
                                     matching_records=matches))
    return dict(schema='m4rch-recovery-progress-observation-v1',
                journal_header=decoded['header'], log_interval_bound=interval is not None,
                log_boundary=interval, boundaries=boundaries, trace_records=records,
                unexpected_trace_types=unexpected_trace_types,
                attribution_qualified=not reasons, attribution_errors=reasons,
                attribution_scope='host-journal-prefix-selection',
                phase_token_timestamp_chronology_verified=False,
                manual_chronology_review_required=True,
                attributions=attributions,
                qualification='Qualified attribution means validated host-journal prefix '
                'selection only: sequences at or beyond a logged pre-ack prefix, stopping '
                'at the next prefix. Matching role4/event46/function0 records with '
                'arguments(0,0x1000,u32_flags,0) are candidate observations. Phase, token '
                'and firmware timestamp chronology require manual review. The prefix '
                'does not exclude previously unobserved records or racing producers; '
                'same-shape events exist elsewhere. No newly-produced phase2 marker, '
                '64c0 reach, live PC, semaphore wait, recovery completion, rendering or '
                'retirement conclusion is emitted. Missing markers locate no PC.')


def summarize(capture):
    proof = PROOF.read_bytes()
    if hashlib.sha256(proof).hexdigest() != PROOF_SHA256:
        raise ValueError('Native trace proof differs from the pinned final audit')
    names = (JOURNAL_NAME, 'dmesg-before.log', 'dmesg-after.log')
    inputs = {name: (capture / name).read_bytes() for name in names}
    report = analyze(inputs[JOURNAL_NAME], inputs[names[1]].decode(), inputs[names[2]].decode())
    report.update(capture=str(capture), journal_filename=JOURNAL_NAME,
                  trace_proof=dict(path=str(PROOF), sha256=PROOF_SHA256),
                  input_sha256={name: hashlib.sha256(data).hexdigest()
                                for name, data in inputs.items()})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.capture)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Trace records:', len(result['trace_records']),
          '; attributed markers:', sum(len(a['matching_records']) for a in result['attributions']),
          '; attribution qualified:', result['attribution_qualified'])
