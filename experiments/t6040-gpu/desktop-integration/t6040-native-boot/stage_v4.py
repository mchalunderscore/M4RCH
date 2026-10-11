#!/usr/bin/env python3
"""Stage the native Region C allocation/component producer in a fresh Gravity source set."""
import argparse
import json
from pathlib import Path
import shutil

import stage_v3 as previous

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
pin = previous.pin


def edit(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError('Source insertion no longer unique: ' + str(path))
    path.write_text(text.replace(before, after))


def stage(destination):
    frozen_path = ROOT / 'docs/evidence/2026-10-11-gravity-native-t6040-components-v3.json'
    frozen = json.loads(frozen_path.read_text())
    for item in frozen['pins']:
        if pin(Path(item['path'])) != item:
            raise ValueError('Frozen v3 input changed: ' + item['path'])
    report_path = ROOT / 'out/gpu-gravity-normal-boot-v4-source-evidence/native-region-c.json'
    native = json.loads(report_path.read_text())
    if native['logical_bytes'] != 0xe58 or native['backing_bytes'] != 0x4000:
        raise ValueError('Native Region C extent differs')
    if native['hardware_actions'] or native['region_c_complete']:
        raise ValueError('Bounded offline native Region C evidence required')
    destination = Path(destination).resolve()
    previous.stage(destination)
    (destination / 'stage-receipt.json').rename(destination / 'component-v3-stage-receipt.json')
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    shutil.copyfile(KIT / 'g16_t6040_region_c_v4.rs', source / 'g16_t6040_region_c.rs')
    edit(source / 'asahi_m4.rs', 'mod g16_t6040;\n',
         'mod g16_t6040;\nmod g16_t6040_region_c;\n')
    edit(source / 'g16_platform.rs',
         '''    pub(crate) fn region_c(&self) -> Result<KVec<u8>> {
        if self.native_hardware.is_some() { return Err(ENOTSUPP); }''',
         '''    /// Native initial component in the source-proved shared allocation.
    /// Full Region C remains rejected by region_c() until its remaining input
    /// writers and mapping policy have native bindings.
    pub(crate) fn native_region_c_component(&self) -> Result<KVec<u8>> {
        if self.native_hardware.is_none() { return Err(EINVAL); }
        let gpu: Option<KVec<u8>> = match self.node.get_property(
            c_str!("apple,sgx-gpu-idle-off-delay-ms")) {
            Ok(bytes) => Some(bytes), Err(ENOENT) => None, Err(error) => return Err(error),
        };
        let fender: Option<KVec<u8>> = match self.node.get_property(
            c_str!("apple,sgx-gpu-fender-idle-off-delay-ms")) {
            Ok(bytes) => Some(bytes), Err(ENOENT) => None, Err(error) => return Err(error),
        };
        let native = crate::g16_t6040_region_c::RegionC::from_adt(
            gpu.as_ref().map(|bytes| bytes.as_slice()),
            fender.as_ref().map(|bytes| bytes.as_slice())).ok_or(EINVAL)?;
        // Native shared allocation rounds e58 logical bytes to a zeroed 4000
        // backing with child offset zero, then publishes its VA at root+20.
        let mut out = zeroed(crate::g16_t6040_region_c::BACKING_BYTES)?;
        native.write_component(&mut out).ok_or(EINVAL)?;
        Ok(out)
    }

    pub(crate) fn region_c(&self) -> Result<KVec<u8>> {
        if self.native_hardware.is_some() {
            let out = self.native_region_c_component()?;
            if !crate::g16_t6040_region_c::REGION_C_COMPLETE { return Err(ENOTSUPP); }
            return Ok(out);
        }''')
    shutil.rmtree(destination / 'build-owner')
    shutil.copytree(source, destination / 'build-owner')
    report = {'schema': 'm4rch.gravity-native-t6040-components.stage.v4',
        'base_stage_receipt': pin(destination / 'component-v3-stage-receipt.json'),
        'inputs': [pin(p) for p in [Path(__file__), KIT / 'g16_t6040_region_c_v4.rs',
            frozen_path, report_path]],
        'source_files': [pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
        'native_region_c_logical_bytes': native['logical_bytes'],
        'native_region_c_backing_bytes': native['backing_bytes'],
        'native_region_c_component_selected_in_platform_producer': True,
        'native_region_c_root_field': '0x20',
        'region_c_complete': False, 'normal_startup_enabled': False,
        'complete_boot_bundle': False, 'hardware_actions': [],
        'optional_of_input_bridge': {
            'apple,sgx-gpu-idle-off-delay-ms': 'native ADT gpu-idle-off-delay-ms; preserve exactly four raw LE bytes',
            'apple,sgx-gpu-fender-idle-off-delay-ms': 'native ADT gpu-fender-idle-off-delay-ms; preserve exactly four raw LE bytes'},
        'of_input_bridge_installed': False,
        'mapping_policy_qualified': False,
        'qualification': 'Actual native Platform component producer uses the source-proved zeroed shared allocation, initial literal fields and native optional idle properties. Complete Region C, full bundle/power and normal startup remain rejected. Existing Region C mapping policy remains explicitly unqualified.'}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    args = parser.parse_args()
    result = stage(args.destination)
    print(json.dumps({'source_files': len(result['source_files']),
                      'region_c_complete': result['region_c_complete']}))
