#!/usr/bin/env python3
"""Prepare a distinct native-ordered retained cycle; never build or load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_RECEIPT_SHA = '59ca87b903980cac6dc9c5ea4fa44d4a346f1f9737a083eff7c50d1b6b0a7b44'
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']
ADDED = ['gfx-native-idle-cycle.h']
REMOVED = ['gfx-native-retained-cycle.h']


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
    old_path = source / 'native-retained-cycle-owner-source-receipt.json'
    if sha(old_path) != BASE_RECEIPT_SHA:
        raise ValueError('Frozen native retained v8 source receipt changed')
    old = json.loads(old_path.read_text())
    before = {row['name']: row['sha256'] for row in old['output_source_pins']}
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen source pin changed: ' + name)
    before[old_path.name] = sha(old_path)
    copied = {name: pin for name, pin in before.items() if name not in REMOVED}
    make = once((source / 'Makefile').read_text(), '-DGFX_NATIVE_RETAINED_CYCLE_TRIAL',
                '-DGFX_NATIVE_IDLE_CYCLE_TRIAL')
    dispatcher = once((source / 'recovery-cycle.h').read_text(),
                      '#include "gfx-native-retained-cycle.h"', '#include "gfx-native-idle-cycle.h"')
    owner = once((source / 'asc-graph-init.c').read_text(),
                 'm4rch gfx-native-retained-cycle-session:', 'm4rch gfx-native-idle-cycle-session:')
    owner = once(owner, 'native ordered retained PWRGATE transport management no-work coordinator',
                 'native idle stage retained PWRGATE transport management no-work coordinator')
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
    profile.pop('known_native_reentry_statuses', None)
    profile.update({
        'compile_macro': 'GFX_NATIVE_IDLE_CYCLE_TRIAL', 'version': 9,
        'typed_commands': ['sample', 'gfx-snapshot', 'gfx-powergate', 'gfx-native-idle-cycle'],
        'exact_cold_reentry_status': None,
        'pre_on_known_statuses': ['0x6a', '0x6c'],
        'post_on_known_statuses': ['0x6a', '0x6c', '0x6d'],
        'status6d_requires_second_on_complete_and_second_ref': True,
        'pre_on_status6d_refused': True,
        'stage_specific_start_admission': True,
        'reentry_four_operands_before_and_after_second_paired_on': True,
        'reentry_four_operands_after_start_intent_log': True,
        'immediate_start_fresh_ctrl_rmw': True,
        'reentry_status6e_or48_refused': True,
        'reentry_tx_valid_and_available_required': True,
        'native_ordered_start_is_experimental_hypothesis': True,
        'maximum_log_row_bytes': 511,
        'complete_newline_structured_state_rows': True,
        'second_log_row_prefixes': ['m4rch gfx-native-idle-cycle:',
            'm4rch gfx-native-idle-cycle-state:',
            'm4rch gfx-native-idle-cycle-transport:',
            'm4rch gfx-native-idle-cycle-management:',
            'm4rch gfx-native-idle-cycle-off:'],
    })
    receipt = {
        'schema': 'm4rch.gfx-native-idle-cycle-owner-source.v1',
        'source': str(source), 'destination': str(destination), 'source_path': str(source),
        'baseline_source_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'frozen_retained_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'input_source_pins': [{'name': n, 'sha256': v} for n, v in before.items()],
        'output_source_pins': [{'name': n, 'sha256': v} for n, v in after.items()],
        'changed_files': CHANGED, 'changed_frozen_retained_files': changed,
        'added_files': ADDED, 'removed_files': REMOVED,
        'profile': profile, 'hardware_actions': [], 'build_actions': [],
        'qualification': 'Source preparation only. Native start bodies do not require exact6a; exact6d admission only after own202/strictOFF and separately qualified second ON with an owned second PM reference is a bounded new hypothesis. No new reentry, second physicalOFF, application rejoin, rendering or DMA retirement has occurred.',
    }
    output = destination / 'native-idle-cycle-owner-source-receipt.json'
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
    print(json.dumps({'receipt': str(args.destination / 'native-idle-cycle-owner-source-receipt.json'),
                      'changed_files': result['changed_files'], 'added_files': result['added_files'],
                      'hardware_actions': []}))


if __name__ == '__main__':
    main()
