#!/usr/bin/env python3
"""Stage the expanded T6040 producer with native counter and absent-resource bindings."""
import argparse
import json
from pathlib import Path
import shutil

import stage_v2 as previous

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
pin = previous.pin
EVIDENCE = ROOT / 'out/gpu-gravity-normal-boot-v3-source-evidence'


def stage(destination):
    counter_path = EVIDENCE / 'native-counter.json'
    absent_path = EVIDENCE / 'native-slot27-absent.json'
    flags_path = EVIDENCE / 'native-descriptor-flags.json'
    counter = json.loads(counter_path.read_text())
    absent = json.loads(absent_path.read_text())
    flags = json.loads(flags_path.read_text())
    if flags['native_hardware_flags'] != {'3': 2, '22': 2, '39': 2, '41': 2}:
        raise ValueError('The native hardware descriptor flags differ')
    if counter['slot'] != 41 or counter['physical'] != '0x288e1f800' or counter['size'] != 0x4000:
        raise ValueError('The native counter geometry differs')
    if absent['slot'] != 27 or absent['hardware_descriptor'] != {
            'physical': 0, 'virtual': 0, 'size': 0, 'stride': 0,
            'relative': 0, 'flags': 2}:
        raise ValueError('The canonical native slot27 absence differs')
    expected_sha = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
    if any(item['macho']['sha256'] != expected_sha for item in [counter, absent, flags]):
        raise ValueError('The matched native image binding differs')
    if counter['hardware_actions'] or absent['hardware_actions'] or flags['hardware_actions']:
        raise ValueError('Offline source evidence required')
    destination = Path(destination).resolve()
    previous.stage(destination)
    (destination / 'stage-receipt.json').rename(destination / 'component-v2-stage-receipt.json')
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    # Remove inherited kbuild state from this fresh stage. The .mod file holds
    # owner-specific object paths and is regenerated along with .mod.c.
    for folder in [source, destination / 'base', destination / 'build-owner']:
        for pattern in ['*.mod', '*.mod.c', '*.o', '*.ko', '.*.cmd',
                        'Module.symvers', 'modules.order']:
            for path in folder.rglob(pattern):
                if path.is_file():
                    path.unlink()
    shutil.copyfile(KIT / 'g16_t6040_v3.rs', source / 'g16_t6040.rs')
    shutil.rmtree(destination / 'build-owner')
    shutil.copytree(source, destination / 'build-owner')
    report = {
        'schema': 'm4rch.gravity-native-t6040-components.stage.v3',
        'base_stage_receipt': pin(destination / 'component-v2-stage-receipt.json'),
        'inputs': [pin(p) for p in [Path(__file__), KIT / 'g16_t6040_v3.rs',
            KIT / 'prepare_counter_evidence.py', counter_path, absent_path, flags_path,
            KIT / 'prepare_slot27_evidence.py',
            ROOT / 'docs/evidence/2026-10-07-gpu-sparse-counter-result.json']],
        'source_files': [pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
        'resolved_native_geometry_slots': [3, 22, 39, 41],
        'native_absent_slots': [27], 'unresolved_slots': [],
        'native_descriptor_flag_slots': [3, 22, 27, 39, 41],
        'unresolved_native_descriptor_flag_slots': [0, 9, 10, 11, 17, 20, 26, 28,
            29, 31, 32, 33, 34, 35, 37, 40, 43],
        'unresolved_native_mapping_permission_slots': [3, 22, 39, 41],
        'native_root_identifier_selected_in_publication_producer': True,
        'native_gpc_absent_property_policy_selected_in_hardware_producer': True,
        'normal_startup_enabled': False, 'complete_boot_bundle': False,
        'hardware_actions': [],
        'qualification': 'Actual Gravity component producer gains the inherited native counter geometry and canonical absent slot27 flags; no donor resource is substituted. Unique counter page aliases preserve the captured first-page write permission. Full bundle/power/Region C remain rejected, and native mapping permission translation remains incomplete.'}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    args = parser.parse_args()
    report = stage(args.destination)
    print(json.dumps({'source_files': len(report['source_files']),
                      'normal_startup_enabled': report['normal_startup_enabled']}))
