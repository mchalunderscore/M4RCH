#!/usr/bin/env python3
"""Annotate saved AGX trace records against the exact matched firmware.

All input is saved ordinary files. Journal prefixes are observation boundaries,
not firmware time barriers. A producing call site is not a sampled live PC.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROOF = ROOT / 'docs/evidence/2026-10-09-native-recovery-progress-trace.json'
PROOF_SHA = 'd258e8c24bdbcb26051a71e334cfb8c4237361f4d6cc6da55559081f45374881'
NATIVE_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
DEFAULT_DIS = ROOT / 'out/private-apple/live-text.dis'
DEFAULT_NATIVE = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
PHASES = ('pipeline-intent', 'control-intent', 'control-ready', 'draw-intent',
          'draw-published', 'retained-final')
INTERVAL_NAMES = ('pre-control', 'control-consumption', 'pre-draw',
                  'draw-publication-window', 'post-draw', 'after-draw-terminal')
ROW = re.compile(r'm4rch gfx-cold-render-(state|control|draw):\s*(.*)$')
PAIR = re.compile(r'(\w+)=(\S+)')
# Small machine ranges are checked against TEXT and the disassembly. Raw
# private bytes/disassembly are never copied into the annotation report.
RANGES = (
    ('trace_producer', 0x1f384, 0x1f6b8),
    ('role_helper', 0x32f68, 0x3307c),
    ('cached_mask_copy', 0x30a8, 0x3390),
    ('opcode22_snapshot', 0x4b1c, 0x4b4c),
    ('main_dispatch', 0x37a78, 0x37b34),
    ('control_entry', 0x385c, 0x38d0),
    ('control_record_retire', 0x5120, 0x5190),
    ('event112_queue_candidate_a', 0x17100, 0x171c8),
    ('event112_queue_candidate_b', 0x387fc, 0x38844),
    ('event46_recovery_candidate', 0x64a0, 0x64c4),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=digest(data))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JOURNAL = load('gfx_trace_journal', HERE / 'decode-receive-journal.py')
TEXT = load('gfx_trace_text', HERE / 'firmware_text_contract.py')
DISPATCH = load('gfx_trace_dispatch', HERE / 'analyze-recovery-dispatch.py')
NATIVE = load('gfx_trace_native', HERE / 'gfx-native-dispatch-contract/prepare-dispatch-recipe.py')


def verify_sources(text_path, disassembly_path, native_path):
    text = Path(text_path).read_bytes()
    identity = TEXT.qualify(text)
    proof_bytes = PROOF.read_bytes()
    if digest(proof_bytes) != PROOF_SHA:
        raise ValueError('Pinned native trace proof changed')
    proof = json.loads(proof_bytes)
    native = Path(native_path).read_bytes()
    if digest(native) != NATIVE_SHA:
        raise ValueError('Native AGX identity differs from the matched trace proof')
    read = NATIVE.native_reader(native)
    native_ranges = []
    for name, record in (
        ('trace_decoder', proof['type5_payload']['native_decoder']),
        ('trace_mask_callback', proof['native_mask']['callback']),
        ('force_config_snapshot', proof['force_snapshot']['native_range']),
    ):
        start = int(record['start'], 0) | 0xfffffe0000000000
        end = int(record['end_exclusive'], 0) | 0xfffffe0000000000
        data = read(start, end - start)
        if digest(data) != record['sha256']:
            raise ValueError('Native machine range mismatch: ' + name)
        native_ranges.append(dict(name=name, start=hex(start),
                                  end_exclusive=hex(end), sha256=digest(data)))
    instructions = {
        int(match[1], 16): int(match[2], 16).to_bytes(4, 'little')
        for match in re.finditer(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s',
                                 Path(disassembly_path).read_text(), re.M)
    }
    ranges = []
    for name, start, end in RANGES:
        try:
            data = b''.join(instructions[a] for a in range(start, end, 4))
        except KeyError as error:
            raise ValueError('Disassembly omits selected instruction ' + hex(error.args[0])) from error
        if data != text[start:end]:
            raise ValueError('Disassembly differs from captured TEXT: ' + name)
        ranges.append(dict(name=name, start=hex(start), end_exclusive=hex(end),
                           bytes=end-start, sha256=digest(data), TEXT_disassembly_match=True))
    role_bytes = text[0x59438:0x59450]
    roles = list(struct.unpack('<6I', role_bytes))
    if roles != proof['type5_payload']['role_table_59438']:
        raise ValueError('Firmware role table differs')
    return dict(firmware_identity=identity, firmware_machine_ranges=ranges,
                role_table=dict(start='0x59438', values=roles, sha256=digest(role_bytes)),
                native_machine_ranges=native_ranges,
                input_pins=[pin(text_path), pin(disassembly_path), pin(native_path), pin(PROOF),
                            pin(HERE / 'firmware_text_contract.py'),
                            pin(HERE / 'gfx-native-dispatch-contract/prepare-dispatch-recipe.py')])


def log_delta(log, prior):
    if prior is None:
        return log, 0, dict(method='supplied-saved-log', prior_bound=False)
    if log.startswith(prior):
        return log[len(prior):], len(prior.splitlines()), dict(method='strict-prefix', prior_bound=True,
            exact_overlap_bytes=len(prior.encode()), before_discarded_bytes=0)
    # Same exact line-boundary suffix association used by the frozen v15 host;
    # rotation never falls back to cumulative-log or timestamp guesses.
    first = log.splitlines(keepends=True)[0] if log else ''
    offset, matches = 0, []
    for line in prior.splitlines(keepends=True):
        if first and line == first and log.startswith(prior[offset:]):
            matches.append(offset)
        offset += len(line)
    if len(matches) != 1:
        raise ValueError('No uniquely exact line-boundary saved-log suffix overlap')
    at = matches[0]
    overlap = prior[at:]
    return log[len(overlap):], len(overlap.splitlines()), dict(method='unique-exact-suffix', prior_bound=True,
        exact_overlap_bytes=len(overlap.encode()), before_discarded_bytes=len(prior[:at].encode()))


def boundaries(log, used, prior=None):
    delta, line_offset, association = log_delta(log, prior)
    rows = {kind: [] for kind in ('state', 'control', 'draw')}
    errors = []
    for number, line in enumerate(delta.splitlines(), line_offset + 1):
        match = ROW.search(line)
        if match:
            tokens = match[2].split()
            fields = dict(PAIR.findall(match[2]))
            if any('=' not in token for token in tokens) or len(fields) != len(tokens):
                errors.append(f'line{number}: malformed or duplicate structured fields')
            rows[match[1]].append(dict(line=number, **fields))
    selected = {}
    previous_prefix, previous_end_line = 0, 0
    for phase in PHASES:
        chosen = {}
        for kind in rows:
            candidates = [row for row in rows[kind] if row.get('phase') == phase]
            if len(candidates) != 1:
                errors.append(f'{phase}: expected one {kind} row, found {len(candidates)}')
            else:
                chosen[kind] = candidates[0]
        if len(chosen) != 3:
            continue
        state = chosen['state']
        try:
            prefix = int(state['journal_used'], 0)
            status = int(state['journal_status'], 0)
        except (ValueError, KeyError):
            errors.append(phase + ': invalid or missing journal prefix/status')
            continue
        if not previous_prefix <= prefix <= used:
            errors.append(phase + ': prefix out of order or outside authoritative journal')
        if not previous_end_line < state['line'] < chosen['control']['line'] < chosen['draw']['line']:
            errors.append(phase + ': state/control/draw rows are not in publication order')
        selected[phase] = dict(prefix=prefix, journal_status=status, rows=chosen)
        previous_prefix, previous_end_line = prefix, chosen['draw']['line']
    intervals = []
    if not errors and len(selected) == len(PHASES):
        # pipeline-intent has not published control. Earlier startup entries
        # also belong to pre-control, so use zero as the first prefix.
        endpoints = [0] + [selected[p]['prefix'] for p in PHASES[1:]] + [used]
        intervals = [dict(name=name, start=a, end_exclusive=b)
                     for name, a, b in zip(INTERVAL_NAMES, endpoints, endpoints[1:])]
    return dict(valid=not errors and bool(intervals), errors=errors, phases=selected,
                intervals=intervals, host_rows=rows, log_association=association,
                qualification='Saved journal append prefixes with ordered state/control/draw rows. '
                'Firmware may produce records before host draining; these are not atomic firmware '
                'time barriers. Draw publication window is distinct from post-publication evidence.')


def selector(record):
    role, event, function, args = (record[k] for k in ('firmware_role', 'event_type', 'function_type', 'args'))
    if role == 0 and function == 0 and args[2] <= 0xffffffff:
        if event == 0x12f and args[3] == 0:
            return dict(name='main-dispatch-entry', producing_call_pc='0x37ad8',
                        handler_call_pc='0x37ae4', machine_range='main_dispatch',
                        meaning='Main dispatcher selected a pending handler before its indirect call.',
                        arguments=['handler mask', 'pending mask before call', '[DATA18e678] u32', 'zero'])
        if event == 0x130:
            return dict(name='main-dispatch-exit', producing_call_pc='0x37b10',
                        handler_call_pc='0x37ae4', machine_range='main_dispatch',
                        meaning='Main dispatcher returned from a handler and cleared its mask from pending state.',
                        arguments=['handler mask', 'pending mask after clear', '[x20+8] u32', '[x20] u64'])
        if event == 0x13e and args[0] <= 0xffffffff and args[3] == 0:
            return dict(name='device-control-record-processed', producing_call_pc='0x5148',
                        machine_range='control_record_retire',
                        meaning='Device-control parser reached its trailing trace before the optional opcode counter '
                                'increment and control consumer cursor increment at517c.',
                        arguments=['record opcode u32', 'record address x28', 'opcode counter before increment u32', 'zero'],
                        opcode22_force_snapshot=bool(args[0] == 22),
                        qualification='Opcode22 supports the source-qualified config snapshot path; this record '
                                      'does not establish GPU command fetch or completion.')
    return None


def unknown(record):
    if record['event_type'] == 0x112 and record['function_type'] == 0:
        return dict(reason='Shared event112 has multiple direct producing sites; queue-index domain is unproved.',
                    compatible_producing_call_pcs=['0x38cc', '0x17144', '0x38840'],
                    control_entry_shape_compatible=bool(record['args'][0] == 4 and record['args'][2:] == [0, 0]),
                    candidate_meanings=['control entry: arg0=4, arg1=requested cursor | consumer cursor<<16, arg2/3=0',
                                        'queue cursor snapshots: arg0=queue index, arg1/2/3 packed cursors'],
                    firmware_PC_attributed=False)
    if record['event_type'] == 0x46:
        return dict(reason='Event46 is shared by35 direct producers; role/payload alone does not bind an invocation.',
                    recovery_site_candidate='0x64c0', recovery_invocation_verified=False,
                    firmware_PC_attributed=False)
    return dict(reason='No exact proven role/event/function/argument selector in this tool.', firmware_PC_attributed=False)


def analyze(snapshot, log, source_contract, prior=None, last=12):
    decoded = JOURNAL.decode(snapshot)
    boundary = boundaries(log, decoded['header']['used'], prior)
    traces, nontrace, warnings = [], [], []
    if decoded['header']['status_flags']:
        warnings.append('Journal status is nonzero: preserve the authoritative prefix. Missing later records '
                        'cannot identify a route or establish absence of execution.')
    if boundary['errors']:
        warnings.append('Host boundary attribution is invalid; trace records retain source annotations but no interval labels.')
    for entry in decoded['entries']:
        if entry['ring_id'] != 10:
            nontrace.append(entry)
            continue
        raw = bytes.fromhex(entry['raw_hex'])
        packed, function = struct.unpack_from('<2I', raw, 0x2c)
        record = dict(**entry, timestamp=struct.unpack_from('<Q', raw, 4)[0],
                      packed_event=hex(packed), firmware_role=packed >> 24, event_type=packed & 0xffffff,
                      function_type=function, args=list(struct.unpack_from('<4Q', raw, 0xc)))
        record['native_event_id'] = (hex((0x85000000 | (((packed << 8) + 0x900000) & 0xff0000) |
                                          ((packed & 0x3fff) << 2) | function) & 0xffffffff)
                                     if entry['type'] == 5 else None)
        record['interval'] = next((i['name'] for i in boundary['intervals']
                                   if i['start'] <= entry['sequence'] < i['end_exclusive']), 'unattributed')
        annotation = selector(record) if entry['type'] == 5 else None
        record['annotation'] = annotation
        record['unknown'] = None if annotation else (unknown(record) if entry['type'] == 5 else
                                                     dict(reason='Trace ring record type is not the proven type5.',
                                                          firmware_PC_attributed=False))
        traces.append(record)
    timestamp_errors = [dict(sequences=[a['sequence'], b['sequence']], timestamps=[a['timestamp'], b['timestamp']])
                        for a, b in zip(traces, traces[1:]) if a['timestamp'] >= b['timestamp']]
    if timestamp_errors:
        warnings.append('Trace timestamps are not strictly increasing; records remain in journal order, wrap/freshness unresolved.')
    # Reuse the established interrupted-entry/exit checker. Pairing refers only
    # to dispatcher handlers and does not imply GPU hardware execution.
    pairs, pair_errors = DISPATCH.dispatch_pairs([r for r in traces if r['type'] == 5])
    unknowns = collections.Counter((r['firmware_role'], r['event_type'], r['function_type'], r['unknown']['reason'])
                                   for r in traces if r['unknown'])
    intervals = []
    for item in boundary['intervals']:
        chosen = [r for r in traces if r['interval'] == item['name']]
        intervals.append(dict(**item, trace_count=len(chosen),
                              annotated_count=sum(r['annotation'] is not None for r in chosen),
                              last_events=chosen[-last:] if last else []))
    draw = boundary['phases'].get('draw-intent', {}).get('prefix') if boundary['valid'] else None
    postdraw = [r for r in traces if draw is not None and r['sequence'] >= draw]
    return dict(schema='m4rch.gfx-trace-semantics.v1', offline_only=True,
                journal_header=decoded['header'], journal_status=dict(overflow=decoded['overflow'], error=decoded['error'],
                    invalid_cursors=decoded['invalid_cursors'], unknown_status_flags=decoded['unknown_status_flags']),
                authoritative_records_sha256=decoded['authoritative_records_sha256'],
                boundary_attribution=boundary, source_contract=source_contract,
                trace_count=len(traces), annotated_count=sum(r['annotation'] is not None for r in traces),
                trace_records=traces, interval_summaries=intervals,
                interval_attribution_kind='host_journal_append_prefix',
                last_events=traces[-last:] if last else [],
                last_main_dispatch_entry=next((r for r in reversed(traces) if r['annotation'] and
                                               r['annotation']['name'] == 'main-dispatch-entry'), None),
                dispatch_pairs=[dict(handler_mask=p['handler_mask'], entry_sequence=p['entry']['sequence'],
                                     exit_sequence=p['exit']['sequence']) for p in pairs],
                dispatch_pair_errors=pair_errors, timestamp_order_errors=timestamp_errors,
                unknown_selectors=[dict(role=k[0], event_type=hex(k[1]), function_type=k[2], reason=k[3], records=n)
                                   for k, n in sorted(unknowns.items())],
                nontrace_ring_type_counts=[dict(ring_id=k[0], type=k[1], records=n) for k, n in sorted(
                    collections.Counter((r['ring_id'], r['type']) for r in nontrace).items())],
                postdraw_trace_append_observed=bool(postdraw), postdraw_trace_append_count=len(postdraw),
                cached_bit1_gated_trace_appended_at_or_after_draw_intent=any(r['annotation'] is not None for r in postdraw),
                gpu_fetch_verified=False, gpu_execution_verified=False, completion_verified=False,
                rendering_verified=False, retirement_verified=False, warnings=warnings,
                qualification='Matched source annotations describe producing call sites, not current PCs. '
                'Unknown selectors and shared event collisions remain unknown. A bounded/overflowed journal '
                'prefix, paired dispatcher return, absent tag, or management restart does not establish '
                'hardware execution, absence of execution, completion, rendering, retirement or a specific stalled wait.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--prior-log', type=Path)
    parser.add_argument('--text', type=Path, required=True)
    parser.add_argument('--disassembly', type=Path, default=DEFAULT_DIS)
    parser.add_argument('--native-driver', type=Path, default=DEFAULT_NATIVE)
    parser.add_argument('--last', type=int, default=12)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.last < 0 or args.output.exists():
        parser.error('Require nonnegative --last and a distinct absent output')
    try:
        source = verify_sources(args.text, args.disassembly, args.native_driver)
        report = analyze(args.journal.read_bytes(), args.log.read_text(), source,
                         args.prior_log.read_text() if args.prior_log else None, args.last)
        paths = [args.journal, args.log, Path(__file__), HERE / 'decode-receive-journal.py',
                 HERE / 'analyze-recovery-dispatch.py'] + ([args.prior_log] if args.prior_log else [])
        report['input_pins'] = [pin(path) for path in paths]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(dict(output=str(args.output.resolve()), sha256=digest(args.output.read_bytes()),
                          traces=report['trace_count'], annotated=report['annotated_count'],
                          postdraw_appends=report['postdraw_trace_append_count'], boundary_valid=report['boundary_attribution']['valid'],
                          overflow=report['journal_status']['overflow'])))


if __name__ == '__main__':
    main()
