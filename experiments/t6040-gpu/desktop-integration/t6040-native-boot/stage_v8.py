#!/usr/bin/env python3
"""Compose complete native power providers into a distinct frozen-v7 source stage.

Source-only integration. Gates stay closed; no build, load or hardware action.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
from stage_v4 import pin
from stage_v7 import change

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
BASELINE = ROOT / 'out/gpu-gravity-normal-boot-v7'


def wiring(files):
    # Constructor reads raw ADT byte aliases before any hardware operation.
    source = files['g16_t6040_power.rs']
    required = re.findall(r'"([^"]+)"', re.search(r'REQUIRED_BYTE_PROPERTIES:.*?= &\[(.*?)\];', source, re.S).group(1))
    optional = re.findall(r'"([^"]+)"', re.search(r'OPTIONAL_WORD_PROPERTIES:.*?= &\[(.*?)\];', source, re.S).group(1))
    for name in required + optional:
        if f'append!("{name}");' not in files['g16_platform.rs']:
            change(files, 'g16_platform.rs', '        let mut properties: KVec<(&str, &[u8])> = KVec::new();',
                   f'        append!("{name}");\n        let mut properties: KVec<(&str, &[u8])> = KVec::new();')
    # V7 already owns both standalone pages and all 27 support children. Bind
    # addresses to those retained allocations; no CPU pointer becomes a GPU VA.
    text = files['g16_power.rs']
    start = text.index('    /// Native zeroed shared allocation')
    stop = text.index('    /// Entire source-built bundle', start)
    method = '''    /// One fresh native session: map-derived tables and retained owned aliases.
    pub(crate) fn native_boot_components(&self,
        maps: &crate::g16_t6040_power::PerfStateMaps,
        policy: &crate::g16_t6040_power::LinuxBootPolicy,
    ) -> Result<(KVec<u8>, KVec<u8>, KVec<u8>)> {
        let native = self.native_hardware.as_ref().ok_or(EINVAL)?;
        let layout = crate::g16_t6040_bundle::BundleLayout::new(
            crate::g16_fw::BUNDLE_ADDRESS).ok_or(EINVAL)?;
        let mut out = zeroed(crate::g16_t6040_bundle::BACKING_BYTES)?;
        let shared = crate::g16_t6040_shared::NativeTopology::new(
            layout.base(), 0xffff_fc20_0003_0000, crate::g16_fw::ROOT_ADDRESS,
            0xffff_fc20_0010_8000, 0xffff_fc20_000f_8000).ok_or(EINVAL)?;
        shared.write_bundle_component(&mut out).ok_or(EINVAL)?;
        let hardware = crate::g16_t6040_bundle::CHILDREN[0];
        native.write(&mut out[hardware.offset..hardware.offset + hardware.bytes]).ok_or(EINVAL)?;
        let power = self.native_power.as_ref().ok_or(EINVAL)?
            .with_perf_state_maps(maps).ok_or(EINVAL)?;
        let child = crate::g16_t6040_bundle::CHILDREN[4];
        // Fresh backing starts zero; these preserved provider slots belong to
        // this allocation and cannot be copied from an earlier consumed boot.
        let providers = crate::g16_t6040_power::LifecycleProviders::capture(
            &out[child.offset..child.offset + child.bytes], policy,
            crate::g16_t6040_power::PowerOwnedAliases {
                support26_gpu: shared.support.base() + 0xc3180,
                qos_gpu: crate::g16_queue_owner::QOS_GPU,
                aonptd_gpu: 0xffff_fc20_0011_0000,
            }).ok_or(EINVAL)?;
        power.write_lifecycle_component(&mut out[child.offset..child.offset + child.bytes],
            &providers).ok_or(EINVAL)?;
        power.write_hardware_component(&mut out[hardware.offset..hardware.offset + hardware.bytes],
            &providers).ok_or(EINVAL)?;
        let mut region_c = zeroed(0x4000)?;
        power.write_region_c_component(&mut region_c, &providers).ok_or(EINVAL)?;
        let mut aonptd = zeroed(0x4000)?;
        power.write_aonptd_component(&mut aonptd).ok_or(EINVAL)?;
        let control = crate::g16_t6040_bundle::CHILDREN[22];
        out[control.offset..control.offset + 4].copy_from_slice(&0x16u32.to_le_bytes());
        // Native 89aa3dc..404 calls selected 89c8ff8 VA conversion, identity,
        // and stores child0+28. Existing timestamp aperture ownership applies.
        put64(&mut out, hardware.offset + 0x28, crate::g16_fw::TIMESTAMP_BASE);
        Ok((out, region_c, aonptd))
    }

'''
    files['g16_power.rs'] = text[:start] + method + text[stop:]
    change(files, 'g16_power.rs', '''            let out = self.native_bundle_component()?;
            if !crate::g16_t6040_power::POWER_COMPLETE
                || !crate::g16_t6040_bundle::BUNDLE_COMPLETE { return Err(ENOTSUPP); }
            return Ok(out);''', '''            // Native construction requires one cold configuration snapshot.
            // Bootstrap owns that snapshot and explicit Linux policy.
            return Err(ENOTSUPP);''')
    # Donor data can be prepared immediately. Native tables cannot be prepared
    # until cold-state validation and the one SGX map-register snapshot.
    text = files['g16.rs']
    start = text.index('        // All board inputs are checked before any firmware is started.')
    stop = text.index('        let dev = pdev.as_ref();', start)
    files['g16.rs'] = text[:start] + '''        // The source-only stage never accesses hardware with unfinished gates.
        if native_t6040 && (!crate::g16_t6040_power::POWER_COMPLETE
            || !crate::g16_t6040_bundle::BUNDLE_COMPLETE) { return Err(ENOTSUPP); }
        let mut bundle = if native_t6040 { KVec::new() }
            else { platform.bundle(unsafe { kernel::bindings::get_random_u32() })? };
        if !native_t6040 {
            bundle[0x28..0x30].copy_from_slice(&crate::g16_fw::TIMESTAMP_BASE.to_le_bytes());
        }
        let mut region_c = if native_t6040 { KVec::new() } else { platform.region_c()? };
        let mut native_aonptd = KVec::new();
''' + text[stop:]
    change(files, 'g16.rs', '''        for offset in [0x1000104, 0x1000108] {''', '''        if native_t6040 {
            // Exactly one future fresh-boot snapshot, before firmware or power
            // register writes. Source-derived 8 words hold 16 map nibbles each.
            let mut primary = [0u32; 8];
            let mut secondary = [0u32; 8];
            for i in 0..8 {
                primary[i] = sgx_io.try_read32(
                    crate::g16_t6040_power::PERF_STATE_MAP_REG_OFFSETS[0] + i * 4)?;
                secondary[i] = sgx_io.try_read32(
                    crate::g16_t6040_power::PERF_STATE_MAP_REG_OFFSETS[1] + i * 4)?;
            }
            let maps = crate::g16_t6040_power::PerfStateMaps::from_register_words(
                &primary, &secondary).ok_or(EINVAL)?;
            let native = platform.native_hardware.as_ref().ok_or(EINVAL)?;
            let enabled_cores = native.masks.iter().map(|mask| mask.count_ones()).sum();
            let clusters = native.masks.iter().filter(|mask| **mask != 0).count() as u32;
            // Same raw monotonic origin as persistent QoS publication.
            // SAFETY: The kernel raw monotonic service has no pointer inputs.
            let ns = u64::try_from(unsafe { kernel::bindings::ktime_get_raw() }).map_err(|_| EINVAL)?;
            let policy = crate::g16_t6040_power::LinuxBootPolicy::t6040_20w_24mhz(
                ns, enabled_cores, clusters).ok_or(EINVAL)?;
            (bundle, region_c, native_aonptd) = platform.native_boot_components(&maps, &policy)?;
        }
        for offset in [0x1000104, 0x1000108] {''')
    change(files, 'g16.rs', '''        if native_t6040 {
            let mut qos = [0u8; crate::g16_t6040_qos::RESOURCE_BYTES];''', '''        if native_t6040 {
            firmware_space.write(0xffff_fc20_0011_0000, &native_aonptd)?;
            let mut qos = [0u8; crate::g16_t6040_qos::RESOURCE_BYTES];''')
    # Retain v7 public/runtime semantics and matching raw clock conversion.


def stage(destination):
    old = json.loads((BASELINE / 'stage-receipt.json').read_text())
    base = BASELINE / 'source/linux/drivers/gpu/drm/asahi'
    for row in old['source_files']:
        if pin(row['path']) != row:
            raise ValueError('Frozen v7 source changed: ' + row['path'])
    files = {str(Path(row['path']).relative_to(base)): Path(row['path']).read_text()
             for row in old['source_files']}
    component = KIT / 'g16_t6040_power_complete_v7.rs'
    files['g16_t6040_power.rs'] = component.read_text()
    wiring(files)
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    for name, text in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    shutil.copytree(source, destination / 'build-owner')
    report = {'schema': 'm4rch.gravity-native-t6040-components.stage.v8',
              'base_stage_receipt': pin(BASELINE / 'stage-receipt.json'),
              'inputs': [pin(Path(__file__)), pin(KIT / 'stage_v4.py'),
                         pin(KIT / 'stage_v7.py'), pin(component)],
              'source_files': [pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
              'normal_startup_enabled': False, 'system_installed': False,
              'hardware_actions': [], 'compiled': False,
              'complete_power_writer_integrated': True,
              'cold_perf_maps_single_snapshot_integrated': True,
              'linux_power_policy': {'maximum_mw': 20000, 'clock_hz': 24000000},
              'native_hardware_timestamp_28_integrated': True,
              'owned_resource_aliases': {'support26': '0xfffffc20000f3180',
                  'qos': '0xfffffc200012c000', 'aonptd': '0xfffffc2000110000'},
              'startup_barriers': ['independent complete power output qualification',
                  'full bundle startup qualification and Linux loader reservations',
                  'bounded native triangle execution and qualified GPU OFF teardown']}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    result = stage(parser.parse_args().destination)
    print(json.dumps({'source_files': len(result['source_files']),
                      'normal_startup_enabled': result['normal_startup_enabled']}))
