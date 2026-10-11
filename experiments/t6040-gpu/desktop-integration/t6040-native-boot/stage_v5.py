#!/usr/bin/env python3
"""Integrate native shared-bundle geometry and bounded MainConfig in a fresh stage."""
import argparse
import json
from pathlib import Path
import shutil

import stage_v4 as previous

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
pin = previous.pin
edit = previous.edit


def stage(destination):
    frozen_path = ROOT / 'docs/evidence/2026-10-11-gravity-native-t6040-components-v4.json'
    frozen = json.loads(frozen_path.read_text())
    for item in frozen['pins']:
        if pin(Path(item['path'])) != item:
            raise ValueError('Frozen v4 input changed: ' + item['path'])
    report_path = ROOT / 'out/gpu-gravity-normal-boot-v5-source-evidence/native-bundle.json'
    if pin(report_path)['sha256'] != '14f6f91b6a9827819a61303e6fcb163942477e95bc48d323f7f212805ef9a7fe':
        raise ValueError('Frozen native bundle evidence changed')
    native = json.loads(report_path.read_text())
    if pin(KIT / 'g16_t6040_bundle_v5.rs') != native['component_source']:
        raise ValueError('Native component differs from the source-backed report')
    for item in native['source_pins']:
        if pin(Path(item['path'])) != item:
            raise ValueError('Native bundle evidence input changed: ' + item['path'])
    if native['logical_bytes'] != 0x225c0 or native['backing_bytes'] != 0x24000:
        raise ValueError('Native bundle extent differs')
    if native['hardware_actions'] or native['bundle_complete']:
        raise ValueError('Bounded offline native bundle evidence required')
    destination = Path(destination).resolve()
    previous.stage(destination)
    (destination / 'stage-receipt.json').rename(destination / 'component-v4-stage-receipt.json')
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    shutil.copyfile(KIT / 'g16_t6040_bundle_v5.rs', source / 'g16_t6040_bundle.rs')
    edit(source / 'asahi_m4.rs', 'mod g16_t6040_region_c;\n',
         'mod g16_t6040_region_c;\nmod g16_t6040_bundle;\n')
    edit(source / 'g16_power.rs',
         '''    /// Entire source-built bundle, including the firmware's power controllers.
    pub(crate) fn bundle(&self, entropy: u32) -> Result<KVec<u8>> {
        if self.native_hardware.is_some() { return Err(ENOTSUPP); }''',
         '''    /// Native zeroed shared allocation with the bounded hardware and Main
    /// producers in their selected native child extents. Unknown power/channel
    /// writers and mapping policy still prevent publication of a full bundle.
    pub(crate) fn native_bundle_component(&self) -> Result<KVec<u8>> {
        let native = self.native_hardware.as_ref().ok_or(EINVAL)?;
        let layout = crate::g16_t6040_bundle::BundleLayout::new(
            crate::g16_fw::BUNDLE_ADDRESS).ok_or(EINVAL)?;
        let mut out = zeroed(crate::g16_t6040_bundle::BACKING_BYTES)?;
        let hardware = crate::g16_t6040_bundle::CHILDREN[0];
        native.write(&mut out[hardware.offset..hardware.offset + hardware.bytes])
            .ok_or(EINVAL)?;
        layout.write_component(&mut out).ok_or(EINVAL)?;
        Ok(out)
    }

    /// Entire source-built bundle, including the firmware's power controllers.
    pub(crate) fn bundle(&self, entropy: u32) -> Result<KVec<u8>> {
        if self.native_hardware.is_some() {
            let out = self.native_bundle_component()?;
            if !crate::g16_t6040_bundle::BUNDLE_COMPLETE { return Err(ENOTSUPP); }
            return Ok(out);
        }''')
    edit(source / 'g16_fw.rs', 'pub(crate) struct RootPointers {',
         '''/// Actual allocation extent selected by Bootstrap. Native mapping flags
/// have a source binding; their Linux protection translation is unqualified.
pub(crate) fn bundle_backing_bytes(native_t6040: bool) -> usize {
    if native_t6040 { crate::g16_t6040_bundle::BACKING_BYTES }
    else { BUNDLE_SIZE + 0x4000 }
}

pub(crate) struct RootPointers {''')
    edit(source / 'g16_fw.rs',
         '    pub(crate) fn encode(&self, native_t6040: bool) -> [u8; ROOT_SIZE] {',
         '''    /// MainConfig belongs to the selected native child allocation. Other
    /// root addresses retain existing owners and are not newly qualified here.
    pub(crate) fn bootstrap_for_platform(native_t6040: bool) -> Option<Self> {
        let mut pointers = Self::bootstrap();
        if native_t6040 {
            pointers.main_config = crate::g16_t6040_bundle::BundleLayout::new(
                BUNDLE_ADDRESS)?.main_gpu_address();
        }
        Some(pointers)
    }

    pub(crate) fn encode(&self, native_t6040: bool) -> [u8; ROOT_SIZE] {''')
    edit(source / 'g16.rs',
         '        let platform = crate::g16_platform::Platform::new(pdev.as_ref(), profile)?;',
         '''        let platform = crate::g16_platform::Platform::new(pdev.as_ref(), profile)?;
        let native_t6040 = platform.native_hardware.is_some();
        let pointers = crate::g16_fw::RootPointers::bootstrap_for_platform(native_t6040)
            .ok_or(EINVAL)?;''')
    edit(source / 'g16.rs',
         '''        bundle[0x28..0x30].copy_from_slice(&crate::g16_fw::TIMESTAMP_BASE.to_le_bytes());''',
         '''        // This inline header is specific to the donor allocation. Native
        // child 0 is hardware, so +28 must not receive this donor header store.
        // Native timestamp/header ownership remains a required missing producer.
        if !native_t6040 {
            bundle[0x28..0x30].copy_from_slice(&crate::g16_fw::TIMESTAMP_BASE.to_le_bytes());
        }''')
    edit(source / 'g16.rs',
         '&crate::g16_fw::RootPointers::bootstrap().encode(platform.native_hardware.is_some()),',
         '&pointers.encode(native_t6040),')
    edit(source / 'g16.rs',
         '            crate::g16_fw::BUNDLE_SIZE + PAGE_SIZE as usize,',
         '            crate::g16_fw::bundle_backing_bytes(native_t6040),')
    edit(source / 'g16.rs',
         '        let pointers = crate::g16_fw::RootPointers::bootstrap();\n', '')
    shutil.rmtree(destination / 'build-owner')
    shutil.copytree(source, destination / 'build-owner')
    report = {'schema': 'm4rch.gravity-native-t6040-components.stage.v5',
        'base_stage_receipt': pin(destination / 'component-v4-stage-receipt.json'),
        'inputs': [pin(p) for p in [Path(__file__), KIT / 'g16_t6040_bundle_v5.rs',
            KIT / 'prepare_bundle_evidence.py', frozen_path, report_path]],
        'source_files': [pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
        'native_bundle_logical_bytes': native['logical_bytes'],
        'native_bundle_backing_bytes': native['backing_bytes'],
        'native_main_offset': 0x1e100, 'native_main_bytes': 0x4c0,
        'native_child_count': 23, 'native_zero_brn_child': 7,
        'native_bundle_component_selected_in_platform_producer': True,
        'native_main_selected_in_actual_root_publication': True,
        'native_backing_selected_in_actual_firmware_allocation': True,
        'donor_inline_header_timestamp_store_selected_for_native': False,
        'native_timestamp_header_producer_complete': False,
        'region_c_complete': False, 'normal_startup_enabled': False,
        'bundle_complete': False, 'complete_boot_bundle': False,
        'mapping_policy_qualified': False, 'hardware_actions': [],
        'qualification': 'Actual native bundle producer uses the selected 23-child shared allocation and bounded native hardware/Main writers. Main root publication and allocation extent select native geometry. Full bundle, Region C, power/channel writers and normal startup remain rejected; native Linux mapping policy and timestamp header production remain unqualified.'}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    args = parser.parse_args()
    result = stage(args.destination)
    print(json.dumps({'source_files': len(result['source_files']),
                      'bundle_complete': result['bundle_complete']}))
