#!/usr/bin/env python3
"""Prepare a distinct bounded EP32 admission owner; never build or load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_RECEIPT_SHA = '29aedde66ac1a15ef0ea180d79dcb2470a1fb638fbaf3750c15afd4a52a2a2f7'
BASE_HEADER_SHA = '068abf0ba07c4c4777910d5074229bea3754b37f0c183a05ca73d967ede39f62'
CHANGED = ['Makefile', 'asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen insertion changed: ' + repr(old[:100]))
    return source.replace(old, new, 1)


def prepare(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists() or source == destination or source in destination.parents:
        raise ValueError('Destination must be new and outside the frozen source')
    old_path = source / 'powergate-owner-source-receipt.json'
    if sha(old_path) != BASE_RECEIPT_SHA or sha(source / 'gfx-native-powergate.h') != BASE_HEADER_SHA:
        raise ValueError('Frozen powergate v5 source changed')
    old = json.loads(old_path.read_text())
    before = {row['name']: row['sha256'] for row in old['output_source_pins']}
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen source pin changed: ' + name)
    before[old_path.name] = sha(old_path)
    copied = {name: pin for name, pin in before.items()
              if name not in ['gfx-native-powergate.h', old_path.name]}
    make = once((source / 'Makefile').read_text(),
                '-DGFX_NATIVE_POWERGATE_TRIAL', '-DGFX_NATIVE_POWERGATE_DRAIN_TRIAL')
    dispatcher = once((source / 'recovery-cycle.h').read_text(),
                      '#include "gfx-native-powergate.h"', '#include "gfx-native-powergate-drain.h"')
    owner = (source / 'asc-graph-init.c').read_text()
    owner = once(owner, 'm4rch gfx-native-powergate-session:', 'm4rch gfx-native-powergate-drain-session:')
    owner = once(owner, 'native PWRGATE retained no-work coordinator',
                 'native PWRGATE bounded admission drain retained no-work coordinator')
    destination.mkdir(parents=True)
    for name in copied:
        (destination / name).write_bytes((source / name).read_bytes())
    for name, data in [('Makefile', make), ('recovery-cycle.h', dispatcher), ('asc-graph-init.c', owner)]:
        (destination / name).write_text(data)
    header = 'gfx-native-powergate-drain.h'
    (destination / header).write_bytes((HERE / header).read_bytes())
    after = {name: sha(destination / name) for name in copied}
    changed = sorted(name for name in copied if after[name] != copied[name])
    if changed != ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']:
        raise ValueError('Unexpected source delta from frozen powergate')
    baseline = {row['name']: row['sha256'] for row in old['input_source_pins']}
    if sorted(name for name in baseline if after[name] != baseline[name]) != CHANGED:
        raise ValueError('Unexpected source delta from native status baseline')
    after[header] = sha(destination / header)
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen input changed during preparation: ' + name)
    profile = dict(old['profile'])
    profile.update({
        'compile_macro': 'GFX_NATIVE_POWERGATE_DRAIN_TRIAL', 'version': 6,
        'bounded_admission_drain': True, 'nominal_admission_deadline_ms': 11,
        'maximum_admission_wait_polls': 12, 'maximum_admission_messages': 64,
        'maximum_admission_rx_messages': 64, 'maximum_successful_admission_rx_messages': 63,
        'qualified_admission_endpoint32_only': True,
        'qualified_admission_message': '0x0042000000000000',
        'stale_ep0_refused': True, 'all_removed_frames_preserved': True,
        'precise_admission_operands_logged': True,
        'admission_operands': ['CTRL44', 'STATUS48', 'RX114', 'TX110'],
        'admission_deadline_is_nominal_jiffies': True,
        'admission_hard_wallclock_upper_bound_claimed': False,
        'admission_status_samples_counted_separately': True,
        'fresh_pre_request_status_recheck': True,
        'admission_drain_uses_frozen_receive_service': True,
        'no_management_request_during_admission': True,
        'admission_refusal_consumes_intent': True,
    })
    receipt = {
        'schema': 'm4rch.gfx-native-powergate-drain-owner-source.v1',
        'source': str(source), 'destination': str(destination),
        'source_path': str(source),
        'frozen_powergate_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'baseline_source_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'native_status_baseline': old['source'],
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'input_source_pins': [{'name': n, 'sha256': v} for n, v in before.items()],
        'output_source_pins': [{'name': n, 'sha256': v} for n, v in after.items()],
        'changed_files': CHANGED, 'added_files': [header],
        'changed_frozen_powergate_files': changed,
        'removed_unused_from_copy': ['gfx-native-powergate.h', old_path.name],
        'profile': profile, 'hardware_actions': [], 'build_actions': [],
        'qualification': 'Source preparation only. The prior refusal does not identify its transport operand. No request, ACK, teardown, recovery, render, DMA retirement or restart is established.',
    }
    output = destination / 'powergate-drain-owner-source-receipt.json'
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.destination)
    print(json.dumps({'receipt': str(args.destination / 'powergate-drain-owner-source-receipt.json'),
                      'changed_files': result['changed_files'], 'added_files': result['added_files'],
                      'hardware_actions': []}))


if __name__ == '__main__':
    main()
