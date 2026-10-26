#!/usr/bin/env python3
"""Qualify new native power production wiring with actual Rust methods offline."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

from stage_v4 import pin

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def qualify(staging, output):
    output.mkdir(exist_ok=False, parents=True)
    source = staging / 'source/linux/drivers/gpu/drm/asahi'
    stage_path = staging / 'stage-receipt.json'
    stage = json.loads(stage_path.read_text())
    if stage['schema'] != 'm4rch.gravity-native-t6040-components.stage.v6':
        raise ValueError('Distinct v6 source stage required')
    for row in stage['inputs'] + stage['source_files']:
        if pin(Path(row['path'])) != row:
            raise ValueError('Staged input changed: ' + row['path'])
    power_path = ROOT / 'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json'
    power = json.loads(power_path.read_text())
    if power['power_complete'] or power['hardware_actions']:
        raise ValueError('Offline bounded native power evidence required')
    if power['source_execution']['native_component_written_bytes'] != 5704:
        raise ValueError('Native selected producer differs')
    contract_path = ROOT / 'docs/evidence/2026-10-06-gpu-contract.json'
    contract = json.loads(contract_path.read_text())
    if pin(contract_path)['sha256'] != 'e021761e50959b9922635ec693d07ac90d659d5eb59bc049060e616edfb87437':
        raise ValueError('Captured performance/topology contract differs')
    adt_row = next(row for row in power['source_pins'] if row['path'].endswith('/boot.adt'))
    parser_row = next(row for row in power['source_pins'] if row['path'].endswith('/adt.py'))
    spec = importlib.util.spec_from_file_location('native_v6_adt', parser_row['path'])
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    node = parser.parse(Path(adt_row['path']).read_bytes())['/device-tree/arm-io/sgx']
    core, sram = node['perf-states'], node['perf-states-sram']
    captured_core = b''.join(struct.pack('<II', row['frequency_hz'], row['voltage_raw'])
                            for table in contract['core_tables'] for row in table)
    captured_sram = b''.join(struct.pack('<II', row['frequency_hz'], row['voltage_raw'])
                            for table in contract['sram_tables'] for row in table)
    if (core, sram) != (captured_core, captured_sram):
        raise ValueError('Actual saved ADT differs from captured native ladders')
    masks = contract['macos_gpu_configuration']['core_mask_list']
    if masks != [0x3db, 0x3db] or contract['enabled_cores_from_masks'] != 16:
        raise ValueError('Selected observed native topology differs')
    if int.from_bytes(node['gpu-num-perf-states'], 'little') != 15:
        raise ValueError('Nominal captured state input differs')

    # Reuse the frozen v5 independently generated expected whole bundle, not
    # its producer or broad tests. The new change must preserve all old bytes
    # except the precisely selected native power/HW timing fields.
    previous_tests = ROOT / 'out/gpu-gravity-normal-boot-v5/qualification-v1/native-tests.rs'
    frozen_v5 = json.loads((ROOT / 'out/gpu-gravity-normal-boot-v5/qualification-v1/qualification.json').read_text())
    previous_pin = next(row for row in frozen_v5['inputs'] if row['path'] == str(previous_tests))
    if pin(previous_tests) != previous_pin:
        raise ValueError('Frozen independent v5 test fixture changed')
    found = re.search(r'let produced=platform\.native_bundle_component\(\)\.unwrap\(\);\s*'
                      r'assert_eq!\(produced\.as_slice\(\),&\[([0-9,]+)\]\);', previous_tests.read_text())
    if not found:
        raise ValueError('Frozen v5 whole-bundle expected fixture is not unique')
    expected_bundle = bytearray(int(value) for value in found[1].split(','))
    if len(expected_bundle) != 0x24000:
        raise ValueError('Frozen v5 expected bundle extent differs')
    expected_power = bytearray([0xa5] * power['logical_bytes'])
    zero_power = bytearray(power['logical_bytes'])
    for field in power['initial_u32_fields'] + power['dynamic_period_fields']:
        offset, value = int(field['offset'], 16), field['value']
        struct.pack_into('<I', expected_power, offset, value)
        struct.pack_into('<I', zero_power, offset, value)
    for field in power['array_fields']:
        offset, size, width = int(field['offset'], 16), field['bytes'], field['element_bytes']
        values = field['value'].to_bytes(width, 'little') * (size // width)
        expected_power[offset:offset + size] = values
        zero_power[offset:offset + size] = values
    if pin(source / 'g16_t6040_power.rs')['sha256'] != power['component_source']['sha256']:
        raise ValueError('Qualified power component differs from source evidence')
    hardware_field = power['hardware_period_field']
    expected_hardware = bytearray([0xa5] * hardware_field['logical_bytes'])
    struct.pack_into('<I', expected_hardware, int(hardware_field['offset'], 16), hardware_field['value'])
    offset = power['bundle_offset']
    expected_bundle[offset:offset + len(zero_power)] = zero_power
    struct.pack_into('<I', expected_bundle, int(hardware_field['offset'], 16), hardware_field['value'])
    fixtures = {
        'core.bin': core, 'sram.bin': sram,
        'expected-power-sentinel.bin': expected_power,
        'expected-hardware-sentinel.bin': expected_hardware,
        'expected-bundle.bin': expected_bundle,
    }
    for name, value in fixtures.items():
        (output / name).write_bytes(value)

    platform = (source / 'g16_platform.rs').read_text()
    structs = platform[platform.index('pub(crate) struct Register {'):platform.index('impl Platform {')]
    constructor = platform[platform.index('    fn new_t6040('):platform.index('    /// Original ADT raw period')]
    inputs = platform[platform.index('    /// Original ADT raw period'):platform.index('    fn build_registers(')]
    power_text = (source / 'g16_power.rs').read_text()
    methods = power_text[power_text.index('    /// Native zeroed shared allocation'):
                         power_text.index('    pub(crate) fn power_data')]
    fw_text = (source / 'g16_fw.rs').read_text()
    constants = '\n'.join(re.findall(r'pub\(crate\) const [A-Z_]+:.*?;', fw_text))
    fw_context = 'mod g16_fw {\n' + constants + '\n' + fw_text[fw_text.index('fn put64(out:'):] + '\n}\n'
    expected_steps = '[' + ','.join('[' + ','.join(
        'g16_t6040::Step {low_mhz:%d,high_mhz:%d,low_index:%d,high_index:%d,core_voltage:%d,sram_voltage:%d}' %
        (row['frequency_low_mhz'], row['frequency_high_mhz'], row['index_low'], row['index_high'],
         row['core_voltage_raw'], row['sram_voltage_raw']) for row in table) + ']'
        for table in contract['cluster_ladders']) + ']'
    cases = power['source_execution']['native_period_cases']
    aic_cases = '[' + ','.join('(%du32,%du32)' % (row['input'], row['period_ms'])
                             for row in cases if row['selection'] == 'aic-priority') + ']'
    ms_cases = '[' + ','.join('(%du32,%du32)' % (row['input'], row['period_aic_clocks'])
                            for row in cases if row['selection'] == 'ms-fallback') + ']'
    template = KIT / 'power_v6_tests.rs.in'
    tests = template.read_text()
    replacements = {
        'HARDWARE_MODULE': json.dumps(str(source / 'g16_t6040.rs')),
        'PROFILE_MODULE': json.dumps(str(source / 'g16_profile.rs')),
        'REGION_MODULE': json.dumps(str(source / 'g16_t6040_region_c.rs')),
        'BUNDLE_MODULE': json.dumps(str(source / 'g16_t6040_bundle.rs')),
        'POWER_MODULE': json.dumps(str(source / 'g16_t6040_power.rs')),
        'FW_CONTEXT': fw_context, 'PLATFORM_STRUCTS': structs,
        'NATIVE_CONSTRUCTOR': constructor, 'NATIVE_PERIOD_INPUTS': inputs,
        'BUNDLE_METHODS': methods, 'REG_WORDS': '0,0,0,0,2,0x88000000,0,0x3758000',
        'CORE_MASKS': ','.join(str(value) for value in masks),
        'CORE_BYTES': json.dumps(str(output / 'core.bin')),
        'SRAM_BYTES': json.dumps(str(output / 'sram.bin')),
        'MCC_MASK': str(int.from_bytes(node['active-mcc-bit-vector'], 'little')),
        'EXPECTED_POWER': json.dumps(str(output / 'expected-power-sentinel.bin')),
        'EXPECTED_HARDWARE': json.dumps(str(output / 'expected-hardware-sentinel.bin')),
        'EXPECTED_BUNDLE': json.dumps(str(output / 'expected-bundle.bin')),
        'EXPECTED_STEPS': expected_steps, 'NATIVE_AIC_CASES': aic_cases, 'NATIVE_MS_CASES': ms_cases,
    }
    for key, value in replacements.items():
        if '@' + key + '@' not in tests:
            raise ValueError('Test substitution no longer present: ' + key)
        tests = tests.replace('@' + key + '@', value)
    if re.search('@[A-Z_]+@', tests):
        raise ValueError('Unresolved test source substitution')
    rust = output / 'native-power-tests.rs'
    rust.write_text(tests)
    commands = []
    for command in [['rustc', '--edition=2021', str(rust), '-o', str(output / 'native-power-tests')],
                    [str(output / 'native-power-tests')]]:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        commands.append({'command': command, 'returncode': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('Native power qualification failed; terminal command evidence preserved')
    for row in stage['source_files']:
        if pin(Path(row['path'])) != row:
            raise ValueError('Source changed during qualification')
    if 'period_ms: power.period_ms, period_clocks: power.period_aic_clocks' not in constructor:
        raise ValueError('Actual constructor does not select native sample timing')
    if 'let child = crate::g16_t6040_bundle::CHILDREN[4]' not in methods:
        raise ValueError('Actual bundle did not select native power child')
    if 'if !crate::g16_t6040_power::POWER_COMPLETE' not in methods:
        raise ValueError('Full power rejection gate is not selected')
    if 'normal_startup_implemented: false' not in (source / 'g16_profile.rs').read_text():
        raise ValueError('Full native startup gate opened')
    inputs = [pin(path) for path in [Path(__file__), KIT / 'stage_v6.py', template,
        power_path, contract_path, previous_tests, stage_path, rust,
        ROOT / 'out/gpu-gravity-normal-boot-v5/qualification-v1/qualification.json']]
    inputs += [pin(output / name) for name in fixtures]
    inputs += stage['source_files']
    report = {
        'schema': 'm4rch.gravity-native-t6040-components.qualification.v6',
        'complete': True, 'commands': commands, 'inputs': inputs,
        'native_power_logical_bytes_compared': len(expected_power),
        'native_power_source_selected_written_bytes': 5704,
        'native_hardware_timing_bytes_compared': len(expected_hardware),
        'native_bundle_backing_bytes_compared': len(expected_bundle),
        'actual_platform_constructor_exercised': True,
        'actual_platform_native_bundle_methods_exercised': True,
        'native_period_arithmetic_cases': len(cases),
        'aic_priority_and_ignored_secondary_input_errors_exercised': True,
        'native_ms_fallback_and_absent_defaults_exercised': True,
        'malformed_zero_overflow_error_short_buffer_refusals_exercised': True,
        'unknown_power_fields_and_all_bundle_bytes_preserved': True,
        'captured_nominal_performance_states': 15, 'native_power_state_count_assigned': False,
        'captured_core_masks': masks, 'enabled_cores': 16, 'clusters': 2,
        'captured_independent_cluster_steps': 22,
        'test_adapter_scope': 'Unmodified actual Platform struct, native constructor, period-input helper and bundle methods compile against standalone property/allocation adapters. Max-power/revision and unused first reg words are fixtures; they do not gain producer qualification. Existing frozen v5 expected whole-bundle bytes are reused and changed only at independently source-backed native power/timing stores. No previous broad audits are rerun.',
        'power_complete': False, 'bundle_complete': False, 'region_c_complete': False,
        'normal_startup_enabled': False, 'of_input_bridge_installed': False,
        'full_module_compiled': False, 'hardware_actions': [],
        'limitations': power['remaining_power_inputs'],
    }
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = qualify(args.staging.resolve(), args.output.resolve())
    print(json.dumps({'complete': report['complete'],
                      'native_power_written_bytes': report['native_power_source_selected_written_bytes']}))
