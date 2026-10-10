#!/usr/bin/env python3
"""Stage the expanded native T6040 component in a fresh full Gravity source set."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import stage as previous

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
FOLLOWUP_SHA = 'ec6e967d66f57d225c66f64924664888ffdaced39e1501ddec8f8aea90646275'


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def edit(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError('Source insertion no longer unique: ' + str(path))
    path.write_text(text.replace(before, after))


def stage(destination):
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / 'out')
    followup = ROOT / 'out/gpu-gravity-normal-boot-v1/native-resource-followup.json'
    if pin(followup)['sha256'] != FOLLOWUP_SHA:
        raise ValueError('The native constructor followup changed')
    frozen = ROOT / 'out/gpu-gravity-normal-boot-v1/freeze-v1.json'
    for item in json.loads(frozen.read_text())['pins']:
        if pin(item['path']) != item:
            raise ValueError('Frozen v1 input changed: ' + item['path'])
    report_v1 = previous.stage(destination)
    (destination / 'stage-receipt.json').rename(destination / 'component-v1-stage-receipt.json')
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    # A previously built donor can contain MODPOST output. This file is
    # generated build state, not an immutable source input for a new build.
    for folder in [source, destination / 'base', destination / 'build-owner']:
        (folder / 'asahi_m4.mod.c').unlink(missing_ok=True)
    shutil.copyfile(KIT / 'g16_t6040_v2.rs', source / 'g16_t6040.rs')
    edit(source / 'g16_platform.rs',
         'let native = crate::g16_t6040::Hardware::from_adt(masks, &core, &sram).ok_or(EINVAL)?;',
         '''let active_mcc_mask = adt_word(&node,
            c_str!("apple,sgx-active-mcc-bit-vector"), None)?;
        let gpc = adt_word(&node, c_str!("apple,sgx-no-gpc"), Some(0))? == 0;
        let native = crate::g16_t6040::Hardware::from_adt(
            masks, active_mcc_mask, gpc, &core, &sram).ok_or(EINVAL)?;''')
    edit(source / 'g16_platform.rs',
         'registers, mcc: KVec::new(), gpc: false, native_hardware: Some(native) })',
         'registers, mcc: KVec::new(), gpc, native_hardware: Some(native) })')
    # Select the matched root identifier in the actual firmware publication
    # producer. No other root/MainConfig fields are silently shifted or donated.
    edit(source / 'g16_fw.rs',
         '''pub(crate) fn encode(&self) -> [u8; ROOT_SIZE] {
        let mut out = [0u8; ROOT_SIZE];
        for (i, value) in [0x04b8u16, 0x8392, 0xc357, 0x0c89].iter().enumerate() {
            out[i * 2..i * 2 + 2].copy_from_slice(&value.to_le_bytes());
        }''',
         '''pub(crate) fn encode(&self, native_t6040: bool) -> [u8; ROOT_SIZE] {
        let mut out = [0u8; ROOT_SIZE];
        // The component's pure byte producer is exercised against the saved
        // matched G16S parser operand. Other fields still require their binding.
        crate::g16_t6040::write_root_interface(&mut out, native_t6040).unwrap();''')
    edit(source / 'g16.rs',
         '&crate::g16_fw::RootPointers::bootstrap().encode(),',
         '&crate::g16_fw::RootPointers::bootstrap().encode(platform.native_hardware.is_some()),')
    # Copy only this fresh source into its distinct module build directory.
    shutil.rmtree(destination / 'build-owner')
    shutil.copytree(source, destination / 'build-owner')
    files = [pin(p) for p in sorted(source.rglob('*')) if p.is_file()]
    report = {
        'schema': 'm4rch.gravity-native-t6040-components.stage.v2',
        'base_stage_receipt': pin(destination / 'component-v1-stage-receipt.json'),
        'inputs': [pin(p) for p in [Path(__file__), KIT / 'g16_t6040_v2.rs', followup, frozen,
            ROOT / 'docs/evidence/2026-10-07-gravity-gpu-firmware-interface-current.json',
            ROOT / 'experiments/t6040-gpu/prepare-native-init-recovery.py',
            ROOT / 'experiments/t6040-gpu/graph-register-batch.py']],
        'source_files': files,
        'resolved_native_geometry_slots': [3, 22, 39],
        'unresolved_slots': [27, 41],
        'unresolved_native_mapping_permission_slots': [3, 22, 39],
        'native_root_identifier_selected_in_publication_producer': True,
        'native_gpc_absent_property_policy_selected_in_hardware_producer': True,
        'normal_startup_enabled': False, 'complete_boot_bundle': False,
        'hardware_actions': [],
        'qualification': 'Expanded actual Gravity Platform::hwdata/FirmwareSpace producer: exact native MCC/CAXI/MTR geometry, independent two-cluster voltage rows, matched native root identifier and native no-gpc policy. Full bundle/power/Region C remain explicitly rejected. MCC/MTR read-only and CAXI second-page write are explicit experimental PTE selections; native permissions are not claimed complete.'}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    arguments = parser.parse_args()
    report = stage(arguments.destination)
    print(json.dumps({'source_files': len(report['source_files']),
                      'normal_startup_enabled': report['normal_startup_enabled']}))
