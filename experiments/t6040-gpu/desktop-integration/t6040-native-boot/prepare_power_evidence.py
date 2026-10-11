#!/usr/bin/env python3
"""Bind a native power component to saved source and ADT; RAM execution only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as reg

HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
ADT_SHA = '01fb4c838a75aac89a3ddaa90996a65c394c07933a5b6927ec7ec13f6867cf39'
BASE = 0xfffffe0000000000
# Matched source span hashes and decoded numeric data only. No private
# instruction bytes are embedded in this kit or emitted by its report.
SPANS = [
    ('configure_owner', 0x8967340, 0x8967350, '7bde60ef536275ff349bf286d15919a8bd521de44d8d3d0d0b5ab7c3d7fc2d1b'),
    ('initial_period_pair', 0x89678d8, 0x89678e8, '1dbc7d791b2a513bdc18068ed6779a30e6980a0a8630a6ed9c26b8255a9f0747'),
    ('period_property_priority', 0x8967a60, 0x8967b60, '3c57a8b783f3389c475b245c99982ee357a8a6c71788c4ec0e2108268c33a4bd'),
    ('G16_configure_inherits', 0x89d9b9c, 0x89d9bd0, 'b976159365a2f3298102313f363f15e199283a602934c38b3ef9cdd349f158d4'),
    ('T6040_configure_inherits', 0x89ea464, 0x89ea4b0, 'd35e7ffb3c328cf5c058af0b6e8211fff3274344ebf488756d8e5ae88a18b8ac'),
    ('generic_power_prefix', 0x89a8648, 0x89a870c, '13af9bc6220e919a03c8b134de4da7da5b764b7f2bf7b5119ebfbe84388a8113'),
    ('ARM_inherits_generic_power', 0x89cadc0, 0x89cadcc, 'f007d3ced193025798125b53bfcb28f1e7c1286e4dfd4ebe2285cbf881d6f49a'),
    ('ARM_array_initialization_loop', 0x89cadcc, 0x89caf20, '71b4e4aa264c8088d3a91798565fc68467795f1de21610fbd9004e2f0b17a483'),
    ('ARM_hardware_ms_writer', 0x89cd1bc, 0x89cd1fc, '1b4746df0668e5de94a8841a3e8acdf1d6a3697e607718e231c0c350b928ac8b'),
    ('aic_period_leaf', 0x89e8b18, 0x89e8b2c, '021aa804439a74ec42875d5d511cf5bfcb8e93c40a77b76122b521bc3da4fdae'),
    ('ms_period_leaf', 0x89e8b2c, 0x89e8b40, '13531b4f8e0e1bf1474e916b075028dc708591692a8fb1533a022c9c3043ce51'),
]
U32_FIELDS = [
    (0xc, 0), (0x10, 4), (0x14, 0x3f800000), (0x18, 0),
    (0x2c, 1), (0x30, 1), (0x34, 0), (0x50, 100),
    (0x5c, 0), (0x60, 4), (0x64, 0x3f800000), (0x68, 0),
    (0x6c, 1), (0x70, 1), (0x74, 0), (0x90, 100),
]
ARRAY_FIELDS = [(0xbef, 0x1000, 1, 0), (0x1bef, 0x400, 2, 0x7fff),
                (0x1fef, 0x200, 1, 0)]


def pin(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def prepare(macho, symbols, adt, adt_parser, bundle_report, module, output):
    data = macho.read_bytes()
    if hashlib.sha256(data).hexdigest() != HOST_SHA:
        raise ValueError('Matched 25G83 host source required')
    if pin(adt)['sha256'] != ADT_SHA:
        raise ValueError('Selected saved ADT required')
    segments, position = [], 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', data, position + 24))
        position += size

    def read(address, length):
        offsets = [off + BASE + address - va for va, _, off, size in segments
                   if va <= BASE + address and BASE + address + length <= va + size]
        if len(offsets) != 1:
            raise ValueError('Source span is not uniquely backed')
        return data[offsets[0]:offsets[0] + length]

    spans = []
    for name, start, end, expected in SPANS:
        actual = hashlib.sha256(read(start, end - start)).hexdigest()
        if actual != expected:
            raise ValueError('Matched native source differs: ' + name)
        spans.append({'name': name, 'start': hex(start), 'end': hex(end),
                      'bytes': end - start, 'sha256': actual})
    constants = []
    for address, expected in [(0x712d7b8, (16, 400000)),
                              (0x712d7d0, (0, 4)),
                              (0x712dd00, (0, 1, 1, 0))]:
        native = read(address, len(expected) * 4)
        if struct.unpack('<' + 'I' * len(expected), native) != expected:
            raise ValueError('Native literal data differs')
        constants.append({'address': hex(address), 'bytes': len(native),
                          'u32_values': list(expected),
                          'sha256': hashlib.sha256(native).hexdigest()})
    names = json.loads(symbols.read_text())
    getters = []
    for slot, target, name, expected in [
            (0xf60, 0x89e8b2c, '__ZN14AGXAccelerator15getSamplePeriodEv.8104',
             '7a3a015faf3b66f736c06fe1de358f26d0b144277e8df1fec39ddb3faa3b4c02'),
            (0xf68, 0x89e8b18, '__ZN14AGXAccelerator24getSamplePeriodAICClocksEv.8103',
             '739632f82e3146c82367e35764b94e551251c180129e3d898efd09fb0c10673e')]:
        entry = 0x7eae398 + slot
        value = read(entry, 8)
        if hashlib.sha256(value).hexdigest() != expected:
            raise ValueError('Selected G16X getter entry differs')
        address = BASE + 0x7004000 + (struct.unpack('<Q', value)[0] & 0xffffffff)
        if address != BASE + target or not any(
                row['name'] == name and int(row['address'], 16) == address for row in names):
            raise ValueError('Selected getter implementation is not bound')
        getters.append({'slot': hex(slot), 'entry': hex(entry),
                        'entry_sha256': expected, 'target': hex(target), 'symbol': name,
                        'cpu_field': hex(0xedac if slot == 0xf60 else 0xedb0)})
    for address, name in [(0x7133419, 'gpu-pwr-sample-period-aic-clks'),
                          (0x7133438, 'gpu-power-sample-period')]:
        if read(address, len(name) + 1) != name.encode() + b'\0':
            raise ValueError('Native property key differs')

    source = importlib.util.spec_from_file_location('native_power_saved_adt', adt_parser)
    parser = importlib.util.module_from_spec(source)
    source.loader.exec_module(parser)
    node = parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx']
    clocks = int.from_bytes(node['gpu-pwr-sample-period-aic-clks'], 'little')
    ms_property = int.from_bytes(node['gpu-power-sample-period'], 'little')
    if (len(node['gpu-pwr-sample-period-aic-clks']),
            len(node['gpu-power-sample-period']), clocks, ms_property) != (4, 4, 200000, 8):
        raise ValueError('Saved native period inputs differ')
    selected_ms = clocks // 24000
    bundle = json.loads(bundle_report.read_text())
    if (bundle['children'][4]['bytes'], int(bundle['children'][4]['offset'], 16)) != (0x6578, 0x5240):
        raise ValueError('Native power child geometry differs')

    ram = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for va, vsize, off, size in segments:
        if size:
            start, end = va & ~0xfff, (va + vsize + 0xfff) & ~0xfff
            ram.mem_map(start, end - start)
            ram.mem_write(va, data[off:off + size])
    obj, power, raw_property = 0x10000000, 0x10010000, 0x10018000
    ram.mem_map(obj, 0x20000)
    ram.mem_write(obj + 0x2d8, struct.pack('<Q', power))
    ram.reg_write(reg.UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def execute(begin, end, limit):
        ram.emu_start(BASE + begin, BASE + end, count=limit)
        if ram.reg_read(reg.UC_ARM64_REG_PC) != BASE + end:
            raise ValueError('Bounded native producer did not reach its stop')

    # Source owner pointer and initial pair, before property priority is applied.
    ram.reg_write(reg.UC_ARM64_REG_X0, obj)
    execute(0x8967340, 0x8967350, 8)
    if ram.reg_read(reg.UC_ARM64_REG_X27) != obj + 0xec88:
        raise ValueError('Native period owner differs')
    execute(0x89678d8, 0x89678e8, 8)
    if bytes(ram.mem_read(obj + 0xedac, 8)) != struct.pack('<II', 16, 400000):
        raise ValueError('Initial native period pair differs')
    native_period_cases = []
    clock_cases = [0, 1, 23999, 24000, 24001, 384000, 400000, 200000, 0xffffffff]
    clock_cases += [(i * 0x9e3779b9) & 0xffffffff for i in range(1, 33)]
    for value in clock_cases:
        ram.mem_write(raw_property, struct.pack('<I', value))
        ram.reg_write(reg.UC_ARM64_REG_X0, raw_property)
        ram.reg_write(reg.UC_ARM64_REG_X27, obj + 0xec88)
        execute(0x8967ac4, 0x8967b60, 16)
        ms, actual = struct.unpack('<II', bytes(ram.mem_read(obj + 0xedac, 8)))
        if (ms, actual) != (value // 24000, value):
            raise ValueError('Native AIC conversion differs')
        native_period_cases.append({'selection': 'aic-priority', 'input': value,
                                    'period_ms': ms, 'period_aic_clocks': actual})
    for value in [0, 1, 8, 16, 178956, 178957, 0xffffffff]:
        ram.mem_write(raw_property, struct.pack('<I', value))
        ram.reg_write(reg.UC_ARM64_REG_X0, raw_property)
        ram.reg_write(reg.UC_ARM64_REG_X23, obj + 0xedac)
        ram.reg_write(reg.UC_ARM64_REG_X27, obj + 0xec88)
        execute(0x8967b48, 0x8967b60, 10)
        ms, actual = struct.unpack('<II', bytes(ram.mem_read(obj + 0xedac, 8)))
        if (ms, actual) != (value, (value * 24000) & 0xffffffff):
            raise ValueError('Native millisecond conversion differs')
        native_period_cases.append({'selection': 'ms-fallback', 'input': value,
                                    'period_ms': ms, 'period_aic_clocks': actual})
    ram.mem_write(obj + 0xedac, struct.pack('<II', 16, 400000))
    execute(0x8967b50, 0x8967b60, 8)
    if bytes(ram.mem_read(obj + 0xedac, 8)) != struct.pack('<II', 16, 384000):
        raise ValueError('Absent property finalization differs')

    ram.mem_write(obj + 0xedac, struct.pack('<II', selected_ms, clocks))
    for begin, end, expected in [(0x89e8b18, 0x89e8b28, clocks),
                                  (0x89e8b2c, 0x89e8b3c, selected_ms)]:
        ram.reg_write(reg.UC_ARM64_REG_X0, obj)
        execute(begin, end, 8)
        if ram.reg_read(reg.UC_ARM64_REG_X0) != expected:
            raise ValueError('Selected native period getter differs')

    # Execute the actual selected stores into sentinel RAM. The copied image
    # and uptime provider are deliberately excluded; their inputs are unknown.
    ram.mem_write(power, b'\xa5' * 0x6578)
    writes = []

    def capture_write(_ram, _access, address, width, _value, _user):
        if not power <= address < address + width <= power + 0x6578:
            raise ValueError('Selected producer wrote outside owned RAM')
        writes.append((address - power, width))

    ram.hook_add(UC_HOOK_MEM_WRITE, capture_write)
    ram.reg_write(reg.UC_ARM64_REG_X19, obj)
    ram.reg_write(reg.UC_ARM64_REG_X0, clocks)
    execute(0x89a86a8, 0x89a86b0, 8)
    ram.reg_write(reg.UC_ARM64_REG_X21, power)
    execute(0x89a86cc, 0x89a870c, 24)
    ram.reg_write(reg.UC_ARM64_REG_X8, 0)
    ram.reg_write(reg.UC_ARM64_REG_X9, 0)
    execute(0x89cadf0, 0x89caf20, 2500)
    expected_image = bytearray(b'\xa5' * 0x6578)
    struct.pack_into('<II', expected_image, 4, clocks, clocks)
    for offset, value in U32_FIELDS:
        struct.pack_into('<I', expected_image, offset, value)
    for offset, size, width, value in ARRAY_FIELDS:
        expected_image[offset:offset + size] = value.to_bytes(width, 'little') * (size // width)
    actual_image = bytes(ram.mem_read(power, 0x6578))
    expected_written = set(range(4, 12))
    for offset, _ in U32_FIELDS:
        expected_written.update(range(offset, offset + 4))
    for offset, size, _, _ in ARRAY_FIELDS:
        expected_written.update(range(offset, offset + size))
    actual_written = {offset + i for offset, width in writes for i in range(width)}
    if actual_image != expected_image or actual_written != expected_written:
        raise ValueError('Native power component or unknown-field preservation differs')

    report = {
        'schema': 'native-t6040-power-component-v6',
        'logical_bytes': 0x6578, 'bundle_offset': 0x5240,
        'power_complete': False, 'normal_startup_qualified': False,
        'macho': pin(macho), 'source_spans': spans,
        'source_pins': [pin(path) for path in [symbols, adt, adt_parser, bundle_report]],
        'component_source': pin(module), 'native_literal_constants': constants,
        'period_getter_bindings': getters,
        'period_configuration': {
            'owner_base': '0xec88', 'ms_cpu_field': '0xedac', 'aic_cpu_field': '0xedb0',
            'aic_property': 'gpu-pwr-sample-period-aic-clks',
            'aic_property_address': '0x7133419',
            'ms_property': 'gpu-power-sample-period', 'ms_property_address': '0x7133438',
            'selected_branch': 'AIC property wins and skips the millisecond property',
            'aic_to_ms_divisor': 24000, 'initial_literal_ms': 16,
            'initial_literal_clocks': 400000, 'absent_final_ms': 16,
            'absent_final_clocks': 384000,
            'selected_property_width': 4, 'selected_property_byte_order': 'little',
            'production_validation': 'selected malformed input, zero period or ms multiplication overflow rejects',
            'native_unchecked_overflow': 'source wraps u32 multiplication; production deliberately rejects overflow',
            'original_adt_bridge_installed': False,
        },
        'saved_native_period': {'period_aic_clocks': clocks, 'period_ms': selected_ms,
                               'ms_property': ms_property, 'ms_property_consumed': False},
        'initial_u32_fields': [{'offset': hex(offset), 'value': value} for offset, value in U32_FIELDS],
        'array_fields': [{'offset': hex(offset), 'bytes': size, 'element_bytes': width,
                          'value': value} for offset, size, width, value in ARRAY_FIELDS],
        'dynamic_period_fields': [{'offset': '0x4', 'value': clocks}, {'offset': '0x8', 'value': clocks}],
        'hardware_period_field': {'offset': '0xed8', 'value': selected_ms,
                                  'logical_bytes': 0x2718, 'store': '0x89cd1f8'},
        'captured_performance_inputs': {
            'gpu_num_perf_states': int.from_bytes(node['gpu-num-perf-states'], 'little'),
            'properties': [{'name': name, 'bytes': len(node[name]),
                            'sha256': hashlib.sha256(node[name]).hexdigest()}
                           for name in ['perf-states', 'perf-states-sram', 'perf-states1',
                                        'perf-states-sram1', 'gpu-pwr-perf-scale0', 'gpu-pwr-perf-scale1']],
            'power_count_assignment_qualified': False,
            'limitation': 'nominal 15 states must not be replaced by the 11 grouped native hardware rows',
        },
        'source_execution': {'kind': 'bounded ARM64 Unicorn RAM only',
                             'native_period_cases': native_period_cases,
                             'native_period_case_count': len(native_period_cases),
                             'native_component_write_events': len(writes),
                             'native_component_written_bytes': len(actual_written),
                             'sentinel_image_sha256': hashlib.sha256(actual_image).hexdigest(),
                             'all_unqualified_bytes_preserved': True,
                             'provider_injection': 'saved ADT clocks passed to already bound getter result; no uptime or tuning injection'},
        'remaining_power_inputs': [
            {'range': '0xa0..0x200', 'source': '0x89a865c..0x89a8668',
             'missing': 'native firmware CPU controller image+980, size160'},
            {'offset': '0x63d4', 'source': '0x89a86b0..0x89a86c8',
             'missing': 'native uptime provider result at calltargetb928a20'},
            {'range': '0x9bc onward', 'source': '0x89a870c onward',
             'missing': 'native accelerator tuning provider values, performance state/count policy and full controller producer'},
            {'range': '0x2888..0x28b8 and 0x6530', 'source': '0x89cad7c..0x89cadec',
             'missing': 'ARM preserves preexisting owner values around generic bzero; lifecycle owner not resolved'},
            {'missing': 'Linux mapping-policy translation and original ADT bridge remain unqualified'},
        ],
        'qualification': 'Actual native stores and arithmetic qualify this bounded initial component only; full power and bundle gates remain closed.',
        'hardware_access': False, 'hardware_actions': [],
        'private_binary_or_instruction_bytes_exported': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Distinct report output already exists')
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': pin(output), 'component': pin(module),
                      'native_period_case_count': len(native_period_cases),
                      'native_component_written_bytes': len(actual_written)}, indent=2))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    names = ['macho', 'symbols', 'adt', 'adt_parser', 'bundle_report', 'module', 'output']
    for name in names:
        cli.add_argument(name, type=Path)
    prepare(**vars(cli.parse_args()))
