#!/usr/bin/env python3
"""Confirm a known STOP EAGAIN from later read-only evidence; no sysfs write."""
import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / 'experiments/t6040-gpu/gfx-poweroff-trial'
sys.path.insert(0, str(KIT))
resident = runpy.run_path(str(KIT / 'run-poweroff.py'))
require = resident['require']
save_json = resident['save_json']
EXPECTED_RECEIPT = '8644ae827a06da50d9793199a7c780305cff85abb9c9e826cde41b967971f471'
EXPECTED_OWNER = '4b4914b677c15b55718e6e96f4d6683a0dd295f4337659aff709a8ffef931be0'
KNOWN_ERROR = "BlockingIOError(11, 'Resource temporarily unavailable')"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_rows(directory):
    before = set((directory / 'dmesg-before.log').read_text().splitlines())
    return [line for line in (directory / 'dmesg-after.log').read_text().splitlines()
            if line not in before]


def row(rows, label, **selected):
    found = []
    for line in rows:
        if 'm4rch gfx-poweroff-' + label + ': ' not in line:
            continue
        fields = dict(re.findall(r'(\w+)=(\S+)', line))
        if all(fields.get(k) == str(v) for k, v in selected.items()):
            found.append(fields)
    require(len(found) == 1, 'Missing or ambiguous fresh ' + label + ' record')
    return found[0]


def equal(fields, **expected):
    require(all(int(fields[k], 0) == v for k, v in expected.items()),
            'Known STOP confirmation predicate failed: ' + str(expected))


def qualify(stop, diagnostic, stop_rows, diagnostic_rows):
    require(stop.get('requested_command') == 'stop' and stop.get('error') == KNOWN_ERROR and
            stop.get('complete') is False and not stop.get('capture_errors'),
            'Only the known returned STOP EAGAIN is eligible')
    require(len(stop['commands']) == 1 and
            stop['commands'][0]['command'] == 'stop' and
            stop['commands'][0]['stage'] == 'failed-or-interrupted' and
            stop['commands'][0]['result'] == KNOWN_ERROR,
            'Unknown, interrupted, open-error or short-write STOP remains sealed')
    require(diagnostic.get('requested_command') == 'gfx-snapshot' and
            diagnostic.get('complete') is True and not diagnostic.get('error') and
            len(diagnostic['commands']) == 1 and
            diagnostic['commands'][0]['stage'] == 'returned' and
            diagnostic['commands'][0]['result'] == 'success' and
            diagnostic['commands'][0]['started_monotonic'] > stop['commands'][0]['finished_monotonic'],
            'A successful later read-only snapshot is required')
    for report in (stop, diagnostic):
        require(not report.get('power_off_attempted') and not report.get('submit_attempted'),
                'A prior OFF/work intent cannot be reconciled')
    sr = row(stop_rows, 'result', command='stop')
    equal(sr, result=-11, gate_consumed=0, pm_attempted=0, held=1,
          host_stopped=1, sealed=1, allocations_retained=174)
    equal(row(stop_rows, 'stop'), clear_attempted=1, start_clear=1, native_idle=0,
          management_packets=0, allocations_retained=174)
    dr = row(diagnostic_rows, 'result', command='gfx-snapshot')
    equal(dr, result=0, gate_consumed=0, pm_attempted=0, held=1,
          host_stopped=1, sealed=1, allocations_retained=174)
    require(int(dr['operation']) == int(sr['operation']) + 1,
            'Intervening command prevents this narrow confirmation')
    asc = row(diagnostic_rows, 'asc', phase='gfx-snapshot')
    require(int(asc['control44'], 0) & 0x10 == 0 and int(asc['status48'], 0) & 3,
            'START-clear and native idle must both be observed')
    equal(row(diagnostic_rows, 'pm', phase='gfx-snapshot'), available=1,
          usage_count=1, runtime_status=0, runtime_error=0, enabled=1,
          active=1, suspended=0, held=1, pm_attempted=0)
    equal(row(diagnostic_rows, 'snapshot', phase='diagnostic'), result=0, valid=1,
          domain_on=1, operation_error=0, cleanup_error=0, word_valid=1)
    word = row(diagnostic_rows, 'word', phase='diagnostic')
    require(int(word['value'], 0) & 0x80001cff == 0xff,
            'Provider must still be active with command/busy bits clear')
    return {'known_stop_result': sr, 'later_snapshot_result': dr,
            'later_asc': asc, 'later_pmgr_word': word,
            'hardware_start_clear_writes': 1,
            'new_sysfs_or_hardware_writes': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('stop_capture', type=Path)
    parser.add_argument('later_snapshot', type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    receipt_path = candidate / 'asc-root-envelope/build-receipt.json'
    require(sha(receipt_path) == EXPECTED_RECEIPT, 'Wrong frozen power-off candidate')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    operations = candidate / 'asc-graph-init' / ('boot-' + boot) / 'resident-operations'
    stop_dir, diagnostic_dir = args.stop_capture.resolve(), args.later_snapshot.resolve()
    require(stop_dir.parent == operations and diagnostic_dir.parent == operations,
            'Both captures must belong to this boot and candidate')
    with (operations / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt, session, original = resident['validate'](candidate, boot)
        require(receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] == EXPECTED_OWNER,
                'Wrong actual pinned owner')
        state_path = operations / 'state.json'
        old = json.loads(state_path.read_text())
        require(old.get('boot_id') == boot and old.get('candidate_module_sha256') == EXPECTED_OWNER and
                old.get('resident_session_active') is True and old.get('operation_failed') is True and
                not old.get('in_flight') and not old.get('power_off_attempted') and
                not old.get('submit_attempted') and not old.get('host_stop_requested') and
                not old.get('resolved_known_stop_eagain'), 'State cannot be reconciled')
        require(old.get('interrupted_operation') ==
                {'command': 'stop', 'operation_directory': str(stop_dir)},
                'A different unknown operation must remain sealed')
        reports = [json.loads((p / 'attempt.json').read_text()) for p in (stop_dir, diagnostic_dir)]
        for report, directory in zip(reports, (stop_dir, diagnostic_dir)):
            require(report.get('boot_id') == boot and report.get('validated_build_receipt') == receipt,
                    'Captured receipt/boot identity changed')
            require(sha(directory / 'dmesg-after.log') == report['final_capture']['dmesg']['sha256'],
                    'Captured log changed')
        evidence = qualify(*reports, fresh_rows(stop_dir), fresh_rows(diagnostic_dir))
        files = [p / n for p in (stop_dir, diagnostic_dir)
                 for n in ('attempt.json', 'dmesg-before.log', 'dmesg-after.log')]
        confirmation = {'schema': 'm4rch.known-stop-eagain-confirmation.v1',
                        'boot_id': boot, 'candidate_receipt_sha256': sha(receipt_path),
                        'owner_sha256': EXPECTED_OWNER, 'original_state': copy.deepcopy(old),
                        'evidence': evidence, 'helper_sha256': sha(Path(__file__)),
                        'files': [{'path': str(p), 'sha256': sha(p)} for p in files],
                        'qualification': 'START-clear and later native idle only. No OFF, DMA/drain, restart or release proof.'}
        confirmation_path = operations / 'known-stop-eagain-confirmation.json'
        require(not confirmation_path.exists(), 'Confirmation exists; investigate, never repeat')
        save_json(confirmation_path, confirmation)
        new = copy.deepcopy(old)
        new['resolved_known_stop_eagain'] = {'prior_unknown_record': new.pop('interrupted_operation'),
                                           'confirmation_path': str(confirmation_path),
                                           'confirmation_sha256': sha(confirmation_path)}
        new['host_stop_requested'] = True
        # Recovery remains failed; this only makes the known completed STOP explicit.
        save_json(state_path, new)
        print(confirmation_path)


if __name__ == '__main__':
    main()
