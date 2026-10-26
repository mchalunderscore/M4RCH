#!/usr/bin/env python3
"""Summarize an exact idle-recovery capture without touching hardware.

Register predicates are observations, not a firmware PC or a retirement proof.
Missing samples remain unknown, including old captures without MMIO diagnostics.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from firmware_text_contract import qualify
from owned_gpu_layout import validate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log_delta(prior, logs):
    if prior and logs.startswith(prior):
        return logs[len(prior):], 'prefix'
    # Kernel ring wrap drops old records. Bind a unique retained tail of the
    # before log, including timestamps, instead of attributing the whole log.
    lines = prior.splitlines(keepends=True)
    if len(lines) >= 32:
        tail = ''.join(lines[-32:])
        if logs.count(tail) == 1:
            return logs.split(tail, 1)[1], 'retained-32-line-tail'
    return '', None


def summarize(candidate, capture):
    receipt = json.loads((candidate / 'asc-root-envelope/build-receipt.json').read_text())
    layout_path = candidate / 'asc-graph-init/graph-receipt.json'
    layout = json.loads(layout_path.read_text())
    attempt = json.loads((capture / 'attempt.json').read_text())
    if receipt != attempt['validated_build_receipt']:
        raise ValueError('Capture and candidate build receipts differ')
    if digest(layout_path) != receipt['graph_receipt_sha256']:
        raise ValueError('Candidate layout receipt changed')
    if not receipt.get('graph_recovery_trial'):
        raise ValueError('Not an idle-recovery candidate')
    before = (capture / 'objects-before.bin').read_bytes()
    after = (capture / 'objects-after.bin').read_bytes()
    if hashlib.sha256(before).hexdigest() != receipt['graph_fixture_sha256']:
        raise ValueError('Capture baseline differs from prepared graph')
    validate(before, layout)
    if len(after) != len(before):
        raise ValueError('Incomplete owned-object snapshot')
    firmware = qualify((capture / 'text.bin').read_bytes())
    expected = receipt['graph_recovery_trial']['firmware_audit']['text_contract']
    if firmware['normalized_sha256'] != expected['normalized_sha256']:
        raise ValueError('Firmware differs from the bound recovery contract')
    objects = {obj['name']: obj['arena_offset'] for obj in layout['objects']}

    def word(name, offset, width='I'):
        return struct.unpack_from('<' + width, after, objects[name] + offset)[0]

    prior = (capture / 'dmesg-before.log').read_text()
    logs = (capture / 'dmesg-after.log').read_text()
    # Do not silently mix earlier operations into a new sample if dmesg rotated.
    delta, log_boundary = log_delta(prior, logs)
    bounded = log_boundary is not None
    traces, powers, results, operations = [], [], [], []
    for line in delta.splitlines():
        match = re.search(r'm4rch recovery-state: cycle=(\d+) phase=(\S+) counter=(\d+) state=(\d+) host_stop=(\d+) request_state=(\d+) request_flag=(\d+) control=(\d+)/(\d+)/(\d+)', line)
        if match:
            fields = match.groups()
            traces.append(dict(cycle=int(fields[0]), phase=fields[1], counter=int(fields[2]),
                               state=int(fields[3]), host_stop=int(fields[4]),
                               request_state=int(fields[5]), request_flag=int(fields[6]),
                               control=list(map(int, fields[7:]))))
        match = re.search(r'm4rch recovery-power: phase=(\S+) recovery_phase=(\d+) pstate=(\d+) (?:power78|target)=(\d+) down_active=(\d+) up_count=(\d+)', line)
        if match:
            phase, state, pstate, power78, active, count = match.groups()
            clock = re.search(r'^\[\s*([0-9.]+)\]', line)
            powers.append(dict(phase=phase, monotonic_seconds=float(clock[1]) if clock else None,
                               recovery_phase=int(state), pstate=int(pstate), power78=int(power78),
                               down_active=int(active), up_count=int(count), registers={}))
        match = re.search(r'm4rch recovery-poll: phase=(\S+) raw5960=(0x[0-9a-f]+|0) raw5978=(0x[0-9a-f]+|0)', line)
        if match and powers and powers[-1]['phase'] == match[1]:
            powers[-1]['registers'].update(primary5960=int(match[2], 0), primary5978=int(match[3], 0))
        match = re.search(r'm4rch recovery-prc: phase=(\S+) rawd4c004=(0x[0-9a-f]+|0)', line)
        if match and powers and powers[-1]['phase'] == match[1]:
            powers[-1]['registers']['prc_d4c004'] = int(match[2], 0)
        for label, field in (('aux-poll', 'raw5970'), ('aux-prc', 'rawd4c000'), ('engine-poll', 'rawd44070')):
            match = re.search(r'm4rch recovery-' + label + r': phase=(\S+) ' + field + r'=(0x[0-9a-f]+|0)', line)
            if match and powers and powers[-1]['phase'] == match[1]:
                powers[-1]['registers'][field] = int(match[2], 0)
        match = re.search(r'm4rch recovery-result: completed=(\d+) requested=(\d+)', line)
        if match:
            results.append(dict(completed=int(match[1]), requested=int(match[2])))
        match = re.search(r'm4rch recovery-operation: id=(\d+) result=(-?\d+) resident=(\d+) sealed=(\d+) work_submitted=(\d+)', line)
        if match:
            operations.append(dict(zip(('id', 'result', 'resident', 'sealed', 'work_submitted'), map(int, match.groups()))))

    for sample in powers:
        regs = sample['registers']
        sample['conditions'] = {
            'f38_low_three_clear': (regs['primary5960'] & 7) == 0 if 'primary5960' in regs else None,
            'down_request_bit0': bool(regs['primary5978'] & 1) if 'primary5978' in regs else None,
            'down_ack_bit1': bool(regs['primary5978'] & 2) if 'primary5978' in regs else None,
            'prc_low_five': regs['prc_d4c004'] & 31 if 'prc_d4c004' in regs else None,
            'aux_gate_low_three_clear': (regs['raw5970'] & 7) == 0 if 'raw5970' in regs else None,
            'aux_prc_low_five': regs['rawd4c000'] & 31 if 'rawd4c000' in regs else None,
            'engine_event_low_sixteen': regs['rawd44070'] & 0xffff if 'rawd44070' in regs else None,
        }
        sample['mmio_complete'] = {'primary5960', 'primary5978', 'prc_d4c004'} <= regs.keys()
        sample['startup_mmio_complete'] = {'raw5970', 'rawd4c000', 'rawd44070'} <= regs.keys()
    return dict(
        schema='m4rch-recovery-observation-v1', boot_id=attempt['boot_id'], capture=str(capture),
        candidate_module_sha256=receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],
        firmware_identity=firmware,
        input_sha256={name: digest(capture / name) for name in ('attempt.json', 'objects-before.bin', 'objects-after.bin', 'dmesg-before.log', 'dmesg-after.log')},
        log_interval_bound=bounded, log_boundary=log_boundary,
        log_interval_error=None if bounded else 'Before log has no retained unique boundary; no operation-specific log conclusions emitted',
        owned_state=dict(counter=word('status_b', 0x48f0, 'Q'), phase=word('status_b', 0x4900),
                         host_stop=word('status_b', 0x4910), request_state=word('shared_3', 0),
                         request_flag=word('shared_3', 4), control=[word('channel_12_cursor', x) for x in (0, 8, 16)],
                         pstate=word('power', 0x38), power78=word('power', 0x78),
                         down_active=word('power', 0x63c8), up_count=word('power', 0x652c),
                         work_roots=[[word('channel_%d_cursor' % i, x) for x in (0, 8, 16)] for i in range(12)]),
        phase_trace=traces, power_samples=powers, cycle_results=results, operations=operations,
        session_flags={name: attempt.get(name) for name in ('resident_session_active', 'resident_session_usable', 'diagnostic_session_active', 'submit_attempted', 'reboot_required')},
        qualification='Owned snapshots and sequential MMIO observations only. Missing registers are unknown. A satisfied predicate does not show firmware reached that poll; an unsatisfied predicate does not locate its live PC. Native down target is zero; power+78 is the old value until transition returns. No recovery reuse, DMA retirement or rendering is established by this summary.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = summarize(args.candidate, args.capture)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Owned recovery phase:', result['owned_state']['phase'],
          'MMIO samples:', sum(sample['mmio_complete'] for sample in result['power_samples']))
