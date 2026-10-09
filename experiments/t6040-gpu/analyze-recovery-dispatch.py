#!/usr/bin/env python3
"""Build an offline recovery transition ledger from a saved initial capture.

Only numeric observations and conditional native-path support are reported.
This tool never accesses hardware and never authorizes recovery or retirement.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import struct
from collections import Counter
from pathlib import Path

from firmware_text_contract import qualify

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'dispatch_progress', HERE / 'analyze-recovery-progress.py')
PROGRESS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROGRESS)
WORKER_PROOF = HERE.parents[1] / 'docs/evidence/2026-10-09-recovery-worker-ack-path.json'
WORKER_SHA = '587e0276d56f664034d141be7bbf265851cb86da3eb19df7532adcd68245dd35'
BIT25 = 0x2000000
TOKEN_MASK = (1 << 44) - 1
STATE = re.compile(r'm4rch recovery-state: cycle=(\d+) phase=(\S+) counter=(\d+) '
                   r'state=(\d+) host_stop=(\d+) request_state=(\d+) '
                   r'request_flag=(\d+) control=(\d+)/(\d+)/(\d+)')
SEND = re.compile(r'm4rch recovery-send: endpoint=33 packet=(0x[0-9a-fA-F]+)')


def host_records(delta):
    states, sends, boundaries = [], [], []
    for line_number, line in enumerate(delta.splitlines()):
        match = STATE.search(line)
        if match:
            values = match.groups()
            states.append(dict(line=line_number, cycle=int(values[0]), phase=values[1],
                               counter=int(values[2]), state=int(values[3]),
                               host_stop=int(values[4]), request_state=int(values[5]),
                               request_flag=int(values[6]), control=list(map(int, values[7:]))))
        match = SEND.search(line)
        if match:
            packet = int(match[1], 16)
            if packet & 0x00ff000000000000 == 0x0086000000000000:
                sends.append(dict(line=line_number, packet=hex(packet), token=packet & TOKEN_MASK))
        match = PROGRESS.BOUNDARY.search(line)
        if match:
            boundaries.append(dict(line=line_number, cycle=int(match[1]),
                                   prefix=int(match[2]), status=int(match[3], 0)))
    return states, sends, boundaries


def kind(record):
    packed = int(record['packed_event'], 16)
    args = record['args']
    if packed == 0x04000046 and record['function_type'] == 0 and args == [0, 0x1000, 4, 0]:
        return 'recovery_marker'
    if record['firmware_role'] == 0 and record['function_type'] == 0 and args[2] <= 0xffffffff:
        if packed == 0x12f and args[3] == 0:
            return 'main_entry'
        if packed == 0x130:
            return 'main_exit'
    return None


def dispatch_pairs(records):
    """Pair only uninterrupted role0 main-dispatch entry/exit observations."""
    pending, ambiguous, pairs, errors = None, False, [], []
    for record in records:
        event = kind(record)
        if event == 'main_entry':
            if not record['args'][0] & record['args'][1]:
                errors.append(dict(reason='Entry pending mask does not contain handler mask',
                                   sequences=[record['sequence']]))
                # A malformed entry is not an exit or a new dispatch boundary.
                # Keep ambiguity until an exit instead of laundering the stream.
                ambiguous = True
                continue
            if pending is not None:
                errors.append(dict(reason='Entry before preceding handler exit',
                                   sequences=[pending['sequence'], record['sequence']]))
                ambiguous = True
            pending = record
        elif event == 'main_exit':
            if record['args'][0] & record['args'][1]:
                errors.append(dict(reason='Exit pending mask still contains handler mask',
                                   sequences=[record['sequence']]))
            elif pending is None or pending['args'][0] != record['args'][0]:
                errors.append(dict(reason='Exit has no matching uninterrupted entry',
                                   sequences=[record['sequence']]))
            elif ambiguous:
                errors.append(dict(reason='Exit belongs to an ambiguous entry sequence',
                                   sequences=[pending['sequence'], record['sequence']]))
            else:
                pairs.append(dict(handler_mask=hex(record['args'][0]), entry=pending, exit=record))
            pending, ambiguous = None, False
    if pending is not None:
        errors.append(dict(reason='Entry has no observed exit', sequences=[pending['sequence']]))
    return pairs, errors


def analyze(journal, prior, logs):
    base = PROGRESS.analyze(journal, prior, logs)
    delta, _ = PROGRESS.LOGS.log_delta(prior, logs)
    states, sends, boundaries = host_records(delta)
    traces = base['trace_records']
    monotonic = all(a['timestamp'] < b['timestamp'] for a, b in zip(traces, traces[1:]))
    errors = list(base['attribution_errors'])
    if not monotonic:
        errors.append('Trace timestamps are not strictly increasing; wrap/freshness unresolved')
    cycles, used_sends = [], set()
    for index, boundary in enumerate(boundaries):
        end = boundaries[index + 1]['prefix'] if index + 1 < len(boundaries) else base['journal_header']['used']
        end_line = boundaries[index + 1]['line'] if index + 1 < len(boundaries) else len(delta.splitlines())
        preceding = [s for s in states if s['line'] < boundary['line']]
        pre = preceding[-1] if preceding else None
        older_states = [s['line'] for s in states if pre and s['line'] < pre['line']]
        lower_line = max(older_states + ([boundaries[index - 1]['line']] if index else []) + [-1])
        sent = [s for s in sends if pre and lower_line < s['line'] < pre['line']]
        request = sent[-1] if sent else None
        reasons = list(errors)
        if not (pre and pre['phase'] == 'pre' and pre['cycle'] == boundary['cycle'] and
                pre['state'] == 1 and pre['host_stop'] == 1 and pre['request_state'] == 2 and
                pre['request_flag'] == 1 and len(set(pre['control'])) == 1 and
                32 <= pre['control'][0] < 128):
            reasons.append('No coherent matching pre-phase observation before this boundary')
        if not (request and pre and request['token'] < TOKEN_MASK and
                pre['counter'] == request['token'] + 1):
            reasons.append('Recovery request token and pre-phase counter are not bound')
        if request:
            if request['line'] in used_sends:
                reasons.append('Recovery request reused by another boundary')
            used_sends.add(request['line'])
        previous_pre = cycles[-1]['pre_phase'] if cycles else None
        if pre and previous_pre and pre['counter'] != previous_pre['counter'] + 1:
            reasons.append('Recovery counters do not advance between observed boundaries')
        selected = [r for r in traces if boundary['prefix'] <= r['sequence'] < end]
        markers = [r for r in selected if kind(r) == 'recovery_marker']
        if len(markers) != 1:
            reasons.append('Expected one exact role4 marker in this interval; source remains ambiguous')
        marker = markers[0] if len(markers) == 1 else None
        pairs, pairing_errors = dispatch_pairs(selected)
        entries = [r for r in selected if kind(r) == 'main_entry' and r['args'][0] == BIT25 and
                   r['args'][1] & BIT25 and
                   marker and r['sequence'] > marker['sequence'] and r['timestamp'] > marker['timestamp']]
        bit25_pairs = [p for p in pairs if p['handler_mask'] == hex(BIT25) and
                       marker and p['entry']['sequence'] > marker['sequence'] and
                       p['entry']['timestamp'] > marker['timestamp']]
        matching_states = [s for s in states if boundary['line'] < s['line'] < end_line and
                           pre and s['cycle'] == pre['cycle'] and s['counter'] == pre['counter']]
        posts = [s for s in matching_states if s['phase'] == 'post' and s['state'] == 3 and s['host_stop'] == 1]
        fresh = [s for s in matching_states if s['phase'] == 'fresh-control-consumed' and
                 s['state'] == 0 and s['host_stop'] == 1 and s['request_state'] == 0 and
                 s['request_flag'] == 0 and len(set(s['control'])) == 1 and
                 s['control'][0] == pre['control'][0] + 1 and
                 any(p['line'] < s['line'] for p in posts)]
        # A shape match can come from another source. No automatic source attribution.
        cycles.append(dict(boundary_index=index, cycle=boundary['cycle'], prefix=boundary['prefix'],
                           end_exclusive=end, request=request, pre_phase=pre,
                           observation_checks_passed=not reasons, observation_errors=reasons,
                           marker_candidates=markers, later_bit25_entries=entries,
                           later_bit25_pairs=bit25_pairs, dispatch_pairing_errors=pairing_errors,
                           post_phase_observations=posts, fresh_control_observations=fresh,
                           conditional_support=dict(
                               after_first_power_wait=bool(marker and not reasons),
                               sampler_wait_passed=bool(entries and not reasons),
                               scheduler_ack_handler_returned=bool(bit25_pairs and not reasons)),
                           marker_source_manually_verified=False,
                           semaphore_consumption_verified=False,
                           final_power_ack_verified=False))
    histogram = Counter((kind(r), hex(r['args'][0])) for r in traces
                        if kind(r) in ('main_entry', 'main_exit'))
    return dict(schema='m4rch-recovery-dispatch-observation-v1',
                journal_header=base['journal_header'], log_interval_bound=base['log_interval_bound'],
                log_boundary=base['log_boundary'], trace_count=len(traces),
                trace_timestamps_strictly_increasing=monotonic, observation_errors=errors,
                dispatch_histogram=[dict(event=k[0], handler_mask=k[1], records=v)
                                    for k, v in sorted(histogram.items())], cycles=cycles,
                manual_source_and_chronology_review_required=True,
                recovery_reuse_verified=False, dma_retirement_verified=False,
                rendering_verified=False,
                qualification='Saved-record ledger only. Conditional support requires manual '
                'qualification of the marker source and same-invocation chronology. Journal '
                'prefixes are not global producer quiescence. An ordered bit25 entry supports '
                'passing the sampler wait; a paired exit supports handler return after the '
                'scheduler signal. Neither establishes semaphore consumption or final power '
                'ACK. Missing events locate no live PC. Host post/fresh-control logs are retained '
                'as observations, not standalone recovery, DMA retirement or rendering proof.')


def summarize(capture, layout_path):
    proofs = ((PROGRESS.PROOF, PROGRESS.PROOF_SHA256), (WORKER_PROOF, WORKER_SHA))
    for path, expected in proofs:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned native proof changed: ' + str(path))
    names = ('notifications-after.bin', 'dmesg-before.log', 'dmesg-after.log',
             'attempt.json', 'objects-before.bin', 'text.bin')
    inputs = {name: (capture / name).read_bytes() for name in names}
    attempt = json.loads(inputs['attempt.json'])
    receipt = attempt['validated_build_receipt']
    layout_bytes = layout_path.read_bytes()
    if hashlib.sha256(layout_bytes).hexdigest() != receipt['graph_receipt_sha256']:
        raise ValueError('Layout differs from capture build receipt')
    if hashlib.sha256(inputs['objects-before.bin']).hexdigest() != receipt['graph_fixture_sha256']:
        raise ValueError('Baseline graph differs from capture build receipt')
    firmware = qualify(inputs['text.bin'])
    trial = receipt['graph_recovery_trial']
    if (trial['request_endpoint'], trial['request_class'], trial['control_notify_class'],
            trial['initial_control_count'], trial['staged_control_count']) != (33, '0x86', '0x84', 32, 128):
        raise ValueError('Unsupported captured recovery protocol or staged control contract')
    if firmware['normalized_sha256'] != trial['firmware_audit']['text_contract']['normalized_sha256']:
        raise ValueError('Firmware differs from capture recovery contract')
    layout = json.loads(layout_bytes)
    status = next(o for o in layout['objects'] if o['name'] == 'status_a')
    mask = struct.unpack_from('<I', inputs['objects-before.bin'], status['arena_offset'])[0]
    report = analyze(inputs[names[0]], inputs[names[1]].decode(), inputs[names[2]].decode())
    report.update(capture=str(capture), boot_id=attempt['boot_id'],
                  capture_metadata_bound=True, firmware_identity=firmware,
                  host_trace_mask_initial=mask, firmware_trace_mask_verified=False,
                  dispatch_trace_initially_requested=bool(mask & 2),
                  candidate_module_sha256=receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],
                  input_sha256={name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()},
                  layout=dict(path=str(layout_path), sha256=hashlib.sha256(layout_bytes).hexdigest()),
                  native_proofs=[dict(path=str(path), sha256=expected) for path, expected in proofs])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--layout', type=Path, help='Default: capture parent graph-receipt.json')
    args = parser.parse_args()
    try:
        result = summarize(args.capture, args.layout or args.capture.parent / 'graph-receipt.json')
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.error(str(error))
    print('Saved cycles:', len(result['cycles']), '; bit25 entry observations:',
          sum(len(c['later_bit25_entries']) for c in result['cycles']), '; manual review required')
