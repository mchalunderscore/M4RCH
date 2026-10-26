#!/usr/bin/env python3
"""Stage the source-bound native power component in a fresh v5-derived producer."""
import argparse
import json
from pathlib import Path
import shutil

from stage_v4 import pin, edit

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def stage(destination):
    frozen_path = ROOT / 'docs/evidence/2026-10-11-gravity-native-t6040-components-v5.json'
    frozen = json.loads(frozen_path.read_text())
    for item in frozen['pins']:
        if pin(Path(item['path'])) != item:
            raise ValueError('Frozen v5 input changed: ' + item['path'])
    baseline = ROOT / 'out/gpu-gravity-normal-boot-v5'
    baseline_source = baseline / 'source/linux/drivers/gpu/drm/asahi'
    baseline_receipt = baseline / 'stage-receipt.json'
    old = json.loads(baseline_receipt.read_text())
    if old['schema'] != 'm4rch.gravity-native-t6040-components.stage.v5':
        raise ValueError('Frozen native v5 stage required')
    for row in old['source_files']:
        if pin(Path(row['path'])) != row:
            raise ValueError('Frozen v5 source changed: ' + row['path'])
    report_path = ROOT / 'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json'
    native = json.loads(report_path.read_text())
    if pin(report_path)['sha256'] != 'df3411781630ef92d84c37d50c40ca2d243d63be928993cc77994e401a13d1bd':
        raise ValueError('Bounded native power report differs')
    if pin(KIT / 'g16_t6040_power_v6.rs') != native['component_source']:
        raise ValueError('Power serializer differs from source evidence')
    for row in native['source_pins'] + [native['macho']]:
        if pin(Path(row['path'])) != row:
            raise ValueError('Native power input changed: ' + row['path'])
    if native['logical_bytes'] != 0x6578 or native['bundle_offset'] != 0x5240:
        raise ValueError('Native power geometry differs')
    if native['hardware_actions'] or native['power_complete']:
        raise ValueError('Bounded offline native component required')
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(exist_ok=False, parents=True)
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    source.mkdir(parents=True)
    for row in old['source_files']:
        path = Path(row['path'])
        relative = path.relative_to(baseline_source)
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(baseline_receipt, destination / 'component-v5-stage-receipt.json')
    shutil.copytree(source, destination / 'base')
    shutil.copyfile(KIT / 'g16_t6040_power_v6.rs', source / 'g16_t6040_power.rs')
    edit(source / 'asahi_m4.rs', 'mod g16_t6040_bundle;\n',
         'mod g16_t6040_bundle;\nmod g16_t6040_power;\n')
    edit(source / 'g16_platform.rs',
         '''        let maximum_power: u32 = node.get_property(c_str!("apple,m4-max-power-mw"))?;''',
         '''        let power = Self::native_power_inputs(&node)?;
        let maximum_power: u32 = node.get_property(c_str!("apple,m4-max-power-mw"))?;''')
    edit(source / 'g16_platform.rs',
         '''        // Zero placeholders below are unreachable by normal boot producers:
        // region_c(), bundle(), and power_data() reject this profile explicitly.''',
         '''        // Native sample timing is source-bound. The remaining zero
        // placeholders are unavailable to full power/bundle/Region C startup;
        // their complete native producers remain required rejection gates.''')
    edit(source / 'g16_platform.rs',
         '''            relative_a: [0; 11], relative_b: [0; 11], period_ms: 0, period_clocks: 0,''',
         '''            relative_a: [0; 11], relative_b: [0; 11],
            period_ms: power.period_ms, period_clocks: power.period_aic_clocks,''')
    edit(source / 'g16_platform.rs', '    fn build_registers(&mut self) -> Result {',
         '''    /// Original ADT raw period inputs, with the native AIC-first
    /// selection. The absent millisecond property selects the native 16 ms
    /// fallback only when AIC is absent. The raw OF bridge is not installed;
    /// full native startup remains closed until its input ownership is bound.
    fn native_power_inputs(node: &of::Node) -> Result<crate::g16_t6040_power::PowerData> {
        let aic: Option<KVec<u8>> = match node.get_property(
            c_str!("apple,sgx-gpu-pwr-sample-period-aic-clks")) {
            Ok(bytes) => Some(bytes), Err(ENOENT) => None, Err(error) => return Err(error),
        };
        // Native AIC success branches past the millisecond property query.
        let ms: Option<KVec<u8>> = if aic.is_some() { None } else {
            match node.get_property(c_str!("apple,sgx-gpu-power-sample-period")) {
                Ok(bytes) => Some(bytes), Err(ENOENT) => None, Err(error) => return Err(error),
            }
        };
        crate::g16_t6040_power::PowerData::from_adt(
            aic.as_ref().map(|bytes| bytes.as_slice()),
            ms.as_ref().map(|bytes| bytes.as_slice())).ok_or(EINVAL)
    }

    fn build_registers(&mut self) -> Result {''')
    edit(source / 'g16_power.rs',
         '''        native.write(&mut out[hardware.offset..hardware.offset + hardware.bytes])
            .ok_or(EINVAL)?;
        layout.write_component(&mut out).ok_or(EINVAL)?;''',
         '''        native.write(&mut out[hardware.offset..hardware.offset + hardware.bytes])
            .ok_or(EINVAL)?;
        // Periods belong to the selected native Platform constructor. Native
        // power offsets are relative to child4; donor bundle offsets do not
        // participate in this producer. Unknown native controller fields are
        // preserved, and the complete-power gate remains closed.
        let power = crate::g16_t6040_power::PowerData {
            period_aic_clocks: self.period_clocks, period_ms: self.period_ms,
        };
        let child = crate::g16_t6040_bundle::CHILDREN[4];
        power.write_component(&mut out[child.offset..child.offset + child.bytes])
            .ok_or(EINVAL)?;
        power.write_hardware_component(
            &mut out[hardware.offset..hardware.offset + hardware.bytes]).ok_or(EINVAL)?;
        layout.write_component(&mut out).ok_or(EINVAL)?;''')
    edit(source / 'g16_power.rs',
         '''            if !crate::g16_t6040_bundle::BUNDLE_COMPLETE { return Err(ENOTSUPP); }''',
         '''            if !crate::g16_t6040_power::POWER_COMPLETE
                || !crate::g16_t6040_bundle::BUNDLE_COMPLETE { return Err(ENOTSUPP); }''')
    shutil.copytree(source, destination / 'build-owner')
    report = {
        'schema': 'm4rch.gravity-native-t6040-components.stage.v6',
        'base_stage_receipt': pin(destination / 'component-v5-stage-receipt.json'),
        'inputs': [pin(path) for path in [Path(__file__), KIT / 'g16_t6040_power_v6.rs',
            KIT / 'prepare_power_evidence.py', frozen_path, report_path, baseline_receipt]],
        'source_files': [pin(path) for path in sorted(source.rglob('*')) if path.is_file()],
        'native_power_logical_bytes': native['logical_bytes'],
        'native_power_bundle_offset': native['bundle_offset'],
        'native_power_written_bytes': native['source_execution']['native_component_written_bytes'],
        'native_periods_selected_in_actual_platform_constructor': True,
        'native_power_component_selected_in_actual_bundle_producer': True,
        'hardware_period_ms_offset': '0xed8',
        'original_adt_property_bridge': {
            'apple,sgx-gpu-pwr-sample-period-aic-clks': 'optional original four-byte LE ADT AIC period; higher priority',
            'apple,sgx-gpu-power-sample-period': 'optional original four-byte LE ADT milliseconds; only read when AIC is absent'},
        'of_input_bridge_installed': False, 'mapping_policy_qualified': False,
        'power_complete': False, 'region_c_complete': False, 'bundle_complete': False,
        'normal_startup_enabled': False, 'complete_boot_bundle': False,
        'hardware_actions': [],
        'qualification': 'Actual native Platform constructor selects source-backed timing and actual bundle child4 receives the bounded power prefix/ARM array initializer. Full power, bundle, Region C, startup and native mapping-policy/ADT-bridge gates remain closed; no donor tuning or performance-count policy is substituted.'}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    result = stage(parser.parse_args().destination)
    print(json.dumps({'source_files': len(result['source_files']),
                      'power_complete': result['power_complete']}))
