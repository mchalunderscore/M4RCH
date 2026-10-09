#!/usr/bin/env python3
"""Prepare a distinct two-epoch retained power-cycle owner; never build/load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_RECEIPT_SHA = 'e55cf8f6bf8a5b8d979a567412cada0b1df38b5d7750183a34e448a38d9c39c1'
BASE_HEADER_SHA = 'f3f4429f6b372157cedcbcce1d29ef61ddaf8654fab2afabf035da8322152787'
ADDED = ['gfx-retained-power-cycle.h', 'gfx-retained-power-cycle-coordinate.h']
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']


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
    old_path = source / 'powergate-drain-owner-source-receipt.json'
    if sha(old_path) != BASE_RECEIPT_SHA or sha(source / 'gfx-native-powergate-drain.h') != BASE_HEADER_SHA:
        raise ValueError('Frozen successful drain v2 source changed')
    old = json.loads(old_path.read_text())
    before = {row['name']: row['sha256'] for row in old['output_source_pins']}
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen source pin changed: ' + name)
    before[old_path.name] = sha(old_path)
    make = (source / 'Makefile').read_text() + '\nccflags-y += -DGFX_RETAINED_POWER_CYCLE_TRIAL\n'
    dispatcher = once((source / 'recovery-cycle.h').read_text(),
                      '#include "gfx-native-powergate-drain.h"', '#include "gfx-retained-power-cycle.h"')
    dispatcher = once(dispatcher, 'ret=gfx_native_powergate_command(buf);',
                      'ret=gfx_retained_cycle_command(buf);')
    dispatcher = once(dispatcher, 'static void recovery_receive_worker(struct work_struct *work);',
                      'static bool gfx_retained_cycle_intent;\nstatic void recovery_receive_worker(struct work_struct *work);')
    dispatcher = once(dispatcher, 'if(recovery_resident && !recovery_session_failed) {',
                      'if(recovery_resident && !recovery_session_failed && !gfx_retained_cycle_intent) {')
    dispatcher = once(dispatcher, 'if(!recovery_session_failed) schedule_delayed_work(',
                      'if(!recovery_session_failed && !gfx_retained_cycle_intent) schedule_delayed_work(')
    owner = (source / 'asc-graph-init.c').read_text()
    owner = once(owner, '#include "gfx-coordinate-owner.h"',
                 '#include "gfx-coordinate-owner.h"\n#include "gfx-retained-power-cycle-coordinate.h"')
    owner = once(owner, 'm4rch gfx-native-powergate-drain-session:',
                 'm4rch gfx-retained-power-cycle-session:')
    owner = once(owner, 'native PWRGATE bounded admission drain retained no-work coordinator',
                 'retained native PWRGATE two-epoch transport management no-work coordinator')
    if owner.count('gfx_native_powergate_startup_retained(') != 3:
        raise ValueError('Frozen startup retention call count changed')
    owner = owner.replace('gfx_native_powergate_startup_retained(',
                          'gfx_retained_cycle_startup_retained(')
    destination.mkdir(parents=True)
    for name in before:
        (destination / name).write_bytes((source / name).read_bytes())
    for name, data in [('Makefile', make), ('recovery-cycle.h', dispatcher), ('asc-graph-init.c', owner)]:
        (destination / name).write_text(data)
    for name in ADDED:
        (destination / name).write_bytes((HERE / name).read_bytes())
    # The frozen first header remains byte-identical. The new startup wrapper
    # adds a distinct unknown marker after its unchanged retention operation.
    after = {name: sha(destination / name) for name in before}
    changed = sorted(name for name in before if after[name] != before[name])
    if changed != CHANGED:
        raise ValueError('Unexpected delta from frozen successful drain')
    for name in ADDED:
        after[name] = sha(destination / name)
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen input changed during preparation: ' + name)
    profile = dict(old['profile'])
    profile.update({
        'compile_macro': 'GFX_RETAINED_POWER_CYCLE_TRIAL', 'version': 7,
        'typed_commands': ['sample', 'gfx-snapshot', 'gfx-powergate', 'gfx-retained-cycle'],
        'maximum_retained_cycle_intents': 1, 'maximum_retained_cycle_starts': 1,
        'maximum_retained_cycle_pm_gets': 1, 'maximum_retained_cycle_pm_puts': 1,
        'maximum_retained_cycle_requests': 1, 'maximum_total_pm_puts': 2,
        'maximum_total_powergate_requests': 2, 'maximum_protocol_records': 16,
        'maximum_protocol_polls': 4001, 'nominal_protocol_timeout_ms': 4000,
        'exact_cold_reentry_status': '0x6a', 'cold_reentry_start_clear': True,
        'fresh_rx_empty_required_before_start_and_second_request': True,
        'autonomous_hello_versions': [12, 12],
        'autonomous_endpoint_map_shape': [{'base': 0, 'bitmap': 3, 'last': False},
                                          {'base': 1, 'bitmap': 3, 'last': True}],
        'retained_management_roundtrip_admitted': True, 'transport_only': False,
        'separate_second_pm_reference': True, 'separate_second_coordinator_epoch': True,
        'first_epoch_evidence_immutable': True, 'host_protocol_journal_separate': True,
        'owned_page_pointer_and_pa_identity_required': 174,
        'first_strict_physical_off_required_before_pm_get': True,
        'no_init220_request': True, 'no_application_start': True,
        'no_application_root_publication': True, 'no_context_reattach': True,
        'no_firmware_data_restore': True, 'no_queue_or_counter_reset': True,
        'application_rejoin_verified': False, 'application_rejoined': False,
        'terminal_intent_seals_all_other_commands': False,
        'second_intent_seals_all_controls': True,
        'second_powergate_admission': 'own autonomous HELLO12 and successful final map ACK, fresh RX EMPTY/TX available; explicit management-only hypothesis',
    })
    receipt = {
        'schema': 'm4rch.gfx-retained-power-cycle-owner-source.v1',
        'source': str(source), 'destination': str(destination), 'source_path': str(source),
        'baseline_source_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'frozen_drain_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'input_source_pins': [{'name': n, 'sha256': v} for n, v in before.items()],
        'output_source_pins': [{'name': n, 'sha256': v} for n, v in after.items()],
        'changed_files': ['Makefile', 'asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h'],
        'changed_frozen_drain_files': changed, 'added_files': ADDED,
        'profile': profile, 'hardware_actions': [], 'build_actions': [],
        'qualification': 'Source preparation only. First successful PWRGATE/OFF does not prove reentry. Second management handshake after autonomous HELLO/map is an explicit bounded hypothesis, never an application rejoin or DMA retirement proof.',
    }
    output = destination / 'retained-power-cycle-owner-source-receipt.json'
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
    print(json.dumps({'receipt': str(args.destination / 'retained-power-cycle-owner-source-receipt.json'),
                      'changed_files': result['changed_files'], 'added_files': result['added_files'],
                      'hardware_actions': []}))


if __name__ == '__main__':
    main()
