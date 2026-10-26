#!/usr/bin/env python3
"""Prepare a distinct native-ordered retained cycle; never build or load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_RECEIPT_SHA = '4f8288982b3d2e926cce11ebe800744ea92f668008e77600929d691319e3ec9a'
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']
ADDED = ['gfx-native-retained-cycle.h']
REMOVED = ['gfx-retained-power-cycle.h']


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
    old_path = source / 'retained-power-cycle-owner-source-receipt.json'
    if sha(old_path) != BASE_RECEIPT_SHA:
        raise ValueError('Frozen retained v6 source receipt changed')
    old = json.loads(old_path.read_text())
    before = {row['name']: row['sha256'] for row in old['output_source_pins']}
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen source pin changed: ' + name)
    before[old_path.name] = sha(old_path)
    copied = {name: pin for name, pin in before.items() if name not in REMOVED}
    make = once((source / 'Makefile').read_text(), '-DGFX_RETAINED_POWER_CYCLE_TRIAL',
                '-DGFX_NATIVE_RETAINED_CYCLE_TRIAL')
    dispatcher = once((source / 'recovery-cycle.h').read_text(),
                      '#include "gfx-retained-power-cycle.h"', '#include "gfx-native-retained-cycle.h"')
    owner = once((source / 'asc-graph-init.c').read_text(),
                 'm4rch gfx-retained-power-cycle-session:', 'm4rch gfx-native-retained-cycle-session:')
    owner = once(owner, 'retained native PWRGATE two-epoch transport management no-work coordinator',
                 'native ordered retained PWRGATE transport management no-work coordinator')
    destination.mkdir(parents=True)
    for name in copied:
        (destination / name).write_bytes((source / name).read_bytes())
    for name, data in [('Makefile', make), ('recovery-cycle.h', dispatcher), ('asc-graph-init.c', owner)]:
        (destination / name).write_text(data)
    for name in ADDED:
        (destination / name).write_bytes((HERE / name).read_bytes())
    after = {name: sha(destination / name) for name in copied}
    changed = sorted(name for name in copied if after[name] != copied[name])
    if changed != CHANGED:
        raise ValueError('Unexpected delta from frozen retained source')
    for name in ADDED:
        after[name] = sha(destination / name)
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen input changed during preparation: ' + name)
    profile = dict(old['profile'])
    profile.update({
        'compile_macro': 'GFX_NATIVE_RETAINED_CYCLE_TRIAL', 'version': 8,
        'typed_commands': ['sample', 'gfx-snapshot', 'gfx-powergate', 'gfx-native-retained-cycle'],
        'exact_cold_reentry_status': None,
        'known_native_reentry_statuses': ['0x6a', '0x6c'],
        'reentry_four_operands_before_and_after_second_paired_on': True,
        'reentry_four_operands_after_start_intent_log': True,
        'immediate_start_fresh_ctrl_rmw': True,
        'reentry_status6e_or48_refused': True,
        'reentry_tx_valid_and_available_required': True,
        'native_ordered_start_is_experimental_hypothesis': True,
        'maximum_log_row_bytes': 511,
        'complete_newline_structured_state_rows': True,
        'second_log_row_prefixes': ['m4rch gfx-native-retained-cycle:',
            'm4rch gfx-native-retained-cycle-state:',
            'm4rch gfx-native-retained-cycle-transport:',
            'm4rch gfx-native-retained-cycle-management:',
            'm4rch gfx-native-retained-cycle-off:'],
    })
    receipt = {
        'schema': 'm4rch.gfx-native-retained-cycle-owner-source.v1',
        'source': str(source), 'destination': str(destination), 'source_path': str(source),
        'baseline_source_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'frozen_retained_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'input_source_pins': [{'name': n, 'sha256': v} for n, v in before.items()],
        'output_source_pins': [{'name': n, 'sha256': v} for n, v in after.items()],
        'changed_files': CHANGED, 'changed_frozen_retained_files': changed,
        'added_files': ADDED, 'removed_files': REMOVED,
        'profile': profile, 'hardware_actions': [], 'build_actions': [],
        'qualification': 'Source preparation only. Native start bodies do not require exact6a; fresh known6c admission after own202/strictOFF is a bounded new hypothesis. No new reentry, second physicalOFF, application rejoin, rendering or DMA retirement has occurred.',
    }
    output = destination / 'native-retained-cycle-owner-source-receipt.json'
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
    print(json.dumps({'receipt': str(args.destination / 'native-retained-cycle-owner-source-receipt.json'),
                      'changed_files': result['changed_files'], 'added_files': result['added_files'],
                      'hardware_actions': []}))


if __name__ == '__main__':
    main()
