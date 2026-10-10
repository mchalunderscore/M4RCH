#!/usr/bin/env python3
"""Small offline boundary, collision, ordering and overflow tests."""
import argparse
import importlib.util
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOL = HERE / 'annotate-gfx-trace.py'
spec = importlib.util.spec_from_file_location('trace_semantics', TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
CAPTURE = ROOT / 'out/gfx-native-dispatch-contract/candidate/asc-graph-init/boot-d83451f8-42c7-4466-9983-f1b3fbea5963'


def record(event, args, timestamp, role=0, function=0, kind=5):
    raw = bytearray(72)
    struct.pack_into('<IQ4Q2I', raw, 0, kind, timestamp, *args, (role << 24) | event, function)
    return bytes(raw)


RECORDS = [
    record(0x12f, [2, 3, 0, 0], 100),
    record(0x130, [2, 1, 0, 0], 101),
    record(0x13e, [22, 0xfffffc2000100000, 0, 0], 102),
    record(0x112, [4, 0x200021, 0, 0], 103),
    record(0x12f, [2, 3, 0, 0], 104, role=7),
    record(0x12f, [0x2000000, 0x2000000, 0, 0], 105),
]


def snapshot(records=RECORDS, flags=0):
    decoder = tool.JOURNAL
    data = bytearray(decoder.HEADER.size + decoder.CAPACITY * decoder.ENTRY.size)
    decoder.HEADER.pack_into(data, 0, decoder.MAGIC, 1, decoder.ENTRY.size,
                            decoder.CAPACITY, len(records), flags, 1, 0, 0, 0, 0, 0)
    for index, raw in enumerate(records):
        decoder.ENTRY.pack_into(data, decoder.HEADER.size + index * decoder.ENTRY.size,
                                10, index % 512, index, raw)
    return bytes(data)


def fixture_log(prefixes=(0, 1, 2, 3, 4, 5)):
    lines = []
    for phase, prefix in zip(tool.PHASES, prefixes):
        lines += [f'm4rch gfx-cold-render-state: phase={phase} journal_used={prefix} journal_status=0x0',
                  f'm4rch gfx-cold-render-control: phase={phase} current=33/33/33 ready=1',
                  f'm4rch gfx-cold-render-draw: phase={phase} notify_sent=1']
    return '\n'.join(lines) + '\n'


def save_exact(path, data):
    if path.exists():
        assert path.read_bytes() == data, path
    else:
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Require a distinct absent output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    contract = tool.verify_sources(CAPTURE / 'text.bin', tool.DEFAULT_DIS, tool.DEFAULT_NATIVE)
    journal, log = snapshot(), fixture_log()

    def check(name, function):
        function()
        results.append(dict(name=name, passed=True))

    def analyze(data=journal, text=log):
        return tool.analyze(data, text, contract)

    def baseline():
        value = analyze()
        assert value['boundary_attribution']['valid']
        assert [r['interval'] for r in value['trace_records']] == list(tool.INTERVAL_NAMES)
        assert [r['sequence'] for r in value['trace_records']] == list(range(6))
        assert value['trace_records'][0]['args'] == [2, 3, 0, 0]
        assert value['trace_records'][0]['raw_hex'] == RECORDS[0].hex()
        assert value['trace_records'][2]['annotation']['opcode22_force_snapshot']
        assert value['dispatch_pairs'] == [dict(handler_mask='0x2', entry_sequence=0, exit_sequence=1)]
        assert value['last_main_dispatch_entry']['sequence'] == 5
        assert value['dispatch_pair_errors'][-1]['sequences'] == [5]
    check('half-open-boundaries-raw-order-and-unmatched-entry', baseline)

    def collisions():
        values = RECORDS + [record(0x46, [0, 0x1000, 4, 0], 106, role=4),
                            record(0x12f, [2, 3, 0, 0], 107, function=1),
                            record(0x12f, [2, 3, 0, 0], 108, kind=17),
                            record(0x12f, [2, 3, 1 << 32, 0], 109)]
        value = analyze(snapshot(values))
        assert value['trace_records'][3]['annotation'] is None
        assert value['trace_records'][3]['unknown']['control_entry_shape_compatible']
        assert value['trace_records'][4]['annotation'] is None
        assert all(r['annotation'] is None for r in value['trace_records'][6:])
        assert not value['trace_records'][6]['unknown']['recovery_invocation_verified']
        assert value['trace_records'][6]['native_event_id'] == '0x85900118'
    check('shared-event-role-function-type-width-remain-unknown', collisions)

    def prefix_order():
        value = analyze(text=fixture_log((0, 2, 1, 3, 4, 5)))
        assert not value['boundary_attribution']['valid']
        assert all(r['interval'] == 'unattributed' for r in value['trace_records'])
        assert value['trace_records'][0]['annotation'] is not None
    check('decreasing-prefix-invalidates-only-interval-attribution', prefix_order)

    def row_order():
        lines = log.splitlines()
        lines[6], lines[7] = lines[7], lines[6]
        assert not analyze(text='\n'.join(lines))['boundary_attribution']['valid']
    check('reordered-state-control-row-invalidates-boundary', row_order)

    def missing_or_duplicate():
        assert not analyze(text=log.replace('m4rch gfx-cold-render-control: phase=control-ready current=33/33/33 ready=1\n', ''))['boundary_attribution']['valid']
        assert not analyze(text=log + log.splitlines()[6] + '\n')['boundary_attribution']['valid']
        assert not analyze(text=log.replace('journal_used=2', 'journal_used=2 journal_used=2'))['boundary_attribution']['valid']
        assert not analyze(text=fixture_log((0, 1, 2, 3, 4, 7)))['boundary_attribution']['valid']
    check('missing-duplicate-malformed-and-outside-prefix-rejected', missing_or_duplicate)

    def timestamp_order():
        records = RECORDS[:]
        records[-1] = record(0x12f, [0x2000000, 0x2000000, 0, 0], 102)
        value = analyze(snapshot(records))
        assert value['timestamp_order_errors']
        assert [r['sequence'] for r in value['trace_records']] == list(range(6))
        assert value['trace_records'][-1]['timestamp'] == 102
        assert value['postdraw_trace_append_observed'] and value['postdraw_trace_append_count'] == 3
        assert 'postdraw_trace_production_observed' not in value
        assert value['interval_attribution_kind'] == 'host_journal_append_prefix'
    check('queued-older-timestamps-preserve-append-order-without-production-after-draw-claim', timestamp_order)

    def overflow():
        value = analyze(snapshot(flags=tool.JOURNAL.STATUS_ERROR | tool.JOURNAL.STATUS_OVERFLOW))
        assert value['journal_status']['overflow'] and value['boundary_attribution']['valid']
        assert value['trace_count'] == 6 and value['last_main_dispatch_entry']['sequence'] == 5
        assert value['dispatch_pair_errors'][-1]['sequences'] == [5]
        assert value['warnings'] and not value['gpu_execution_verified'] and not value['retirement_verified']
    check('overflow-preserves-authoritative-prefix-and-unmatched-route', overflow)

    def unused_tail():
        changed = bytearray(journal)
        changed[-72:] = RECORDS[-1]
        assert analyze(bytes(changed))['authoritative_records_sha256'] == analyze()['authoritative_records_sha256']
        assert analyze(bytes(changed))['trace_count'] == 6
    check('unused-tail-does-not-add-events', unused_tail)

    def bad_sequence():
        changed = bytearray(journal)
        struct.pack_into('<I', changed, tool.JOURNAL.HEADER.size + 4, 1)
        try:
            analyze(bytes(changed))
        except ValueError as error:
            assert 'sequence mismatch' in str(error)
        else:
            raise AssertionError('invalid sequence accepted')
    check('existing-decoder-rejects-corrupt-sequence', bad_sequence)

    def association():
        prior = 'old1\nold2\n'
        assert tool.boundaries(prior+log, 6, prior)['log_association']['method'] == 'strict-prefix'
        assert tool.boundaries('old2\n'+log, 6, prior)['log_association']['method'] == 'unique-exact-suffix'
        try:
            tool.boundaries('unknown\n'+log, 6, prior)
        except ValueError:
            pass
        else:
            raise AssertionError('unbound rotation accepted')
    check('exact-prior-log-or-unique-suffix-no-timestamp-fallback', association)

    def wrong_firmware():
        changed = bytearray((CAPTURE / 'text.bin').read_bytes())
        changed[0x37ad8] ^= 1
        try:
            tool.TEXT.qualify(bytes(changed))
        except ValueError:
            pass
        else:
            raise AssertionError('unmatched firmware accepted')
    check('changed-instruction-image-rejects-source-annotations', wrong_firmware)

    attempt = json.loads((CAPTURE / 'attempt.json').read_text())
    capture_pins = []
    for item in attempt['capture_pins']:
        observed = tool.pin(CAPTURE / item['name'])
        assert observed['sha256'] == item['sha256'] and observed['bytes'] == item['bytes']
        capture_pins.append(observed)

    def actual_capture():
        value = tool.analyze((CAPTURE / 'notifications-after.bin').read_bytes(),
                             (CAPTURE / 'dmesg-after.log').read_text(), contract,
                             (CAPTURE / 'dmesg-before.log').read_text())
        assert value['boundary_attribution']['valid'] and value['trace_count'] == 1097
        assert value['annotated_count'] == 1075 and value['postdraw_trace_append_count'] == 0
        assert not value['postdraw_trace_append_observed']
        assert value['interval_attribution_kind'] == 'host_journal_append_prefix'
        assert len(value['dispatch_pairs']) == 521
        assert value['last_main_dispatch_entry']['sequence'] == 1102
        assert value['dispatch_pair_errors'][-1]['sequences'] == [1102]
        assert value['last_events'][-1]['sequence'] == 1103
        assert value['last_events'][-1]['event_type'] == 0x112
        assert value['last_events'][-1]['unknown']['control_entry_shape_compatible']
    check('actual-frozen-d834-selector-count-boundaries-last-route', actual_capture)

    fixture_paths = [args.output.parent / 'synthetic-v1.bin', args.output.parent / 'synthetic-v1.log',
                     args.output.parent / 'synthetic-v1-spec.json']
    save_exact(fixture_paths[0], journal)
    save_exact(fixture_paths[1], log.encode())
    save_exact(fixture_paths[2], (json.dumps(dict(schema='m4rch.gfx-trace-synthetic.v1',
                prefixes=list(range(6)), records_raw72_hex=[r.hex() for r in RECORDS],
                qualification='Synthetic parser discriminators only; no actual firmware/hardware execution.'), indent=2)+'\n').encode())
    report = dict(schema='m4rch.gfx-trace-semantics.tests.v1', passed=True, cases=results,
                  hardware_access=False, frozen_v16_changes=False, analysis_only=True,
                  input_pins=[tool.pin(TOOL), tool.pin(__file__), tool.pin(CAPTURE/'attempt.json')]+capture_pins,
                  fixture_pins=[tool.pin(p) for p in fixture_paths], source_contract=contract,
                  qualification='Minimal parser/source-identity discriminators and one actual saved journal. '
                                'No render candidate qualification, live GPU operation, retirement or execution claim.')
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(output=str(args.output.resolve()), sha256=tool.digest(args.output.read_bytes()), cases=len(results))))


if __name__ == '__main__':
    main()
