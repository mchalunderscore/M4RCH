#!/usr/bin/env python3
"""Extract native G16X child geometry for production v5; saved-source RAM only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn import arm64_const as reg

HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
BASE = 0xfffffe0000000000
SPANS = [
    ('child_descriptor_literals_before_BRN', 0x89ab668, 0x89ab770, '995ad498848f371885c56a5e3dbaeeeb3ae8db56eff3d68179f7cb98f1579423'),
    ('native_BRN_size_callback', 0x89ab770, 0x89ab7ac, 'a4ecf5df238b0559f9c70ea493833183098d4e77f2c15c672ad863fc93b5db8a'),
    ('selected_G16X_BRN_size_leaf', 0x89e8afc, 0x89e8b08, '4a420b54660fd00d957814befb0602f8eef9859e1d8f0b87d32b3cdd1f612a4b'),
    ('child_descriptor_literals_after_BRN', 0x89ab7ac, 0x89ab8f8, '6879d3c94a9e6c6113119eacb20adc6155bea4398c4a77a6c0d1eb564b90c33e'),
    ('bundle_allocation_parameters_and_call', 0x89ab8d0, 0x89ab93c, '7c7852312e0991ad301b0c267d3e94ab405b0dbbc0d316a19b001c7be8b4861a'),
    ('main_channel_pointer_views', 0x89ab93c, 0x89ab950, '9c70caa5391b0edcf51c40c49b14604785b73c40c738e8b28939d358ed3b95a2'),
    ('native_MainConfig_pointer_writers', 0x89be47c, 0x89be7c8, '473c95e34f5ae9bff87ce1dd1895d9a331596d553bc4c4eaf2921c54bc4d6b62'),
    ('native_MainConfig_zero2f8', 0x89cd2dc, 0x89cd41c, 'aca43612c307cabfdbb8254689086ba30969598a8543328b79cd67bb209354fa'),
    ('native_root_MainConfig_pointer', 0x89cd96c, 0x89cd9b0, '5e8d63711021af166e89eac338a33e00c9bade996553ba0538129f8d9c37cfdd'),
    ('allocator_page_and_flags', 0x89a7c70, 0x89a7dbc, 'b7d4b2b023265d899c0720b52911560f7dbcbf2f28d952b79154791467c46818'),
]
# Independent source operands, not parsed from the Rust component.
EXPECTED = [
    (0x2b8, 0x300, 0x2718), (0x2c0, 0x308, 0xc18),
    (0x2c8, 0x310, 0x1048), (0x2d0, 0x318, 0xe10),
    (0x2d8, 0x320, 0x6578), (0x2e0, 0x328, 0x68),
    (0x2e8, 0x330, 0x800), (0x2f0, 0x338, 0),
    (0x2f8, 0x340, 0x88), (0x440, 0x448, 0x1800),
    (0x418, 0x420, 0x1800), (0x3f0, 0x3f8, 0x1800),
    (0x3c8, 0x3d0, 0x1800), (0x4e0, 0x4e8, 0x1800),
    (0x4b8, 0x4c0, 0x1800), (0x490, 0x498, 0x1800),
    (0x468, 0x470, 0x1800), (0x580, 0x588, 0x1800),
    (0x558, 0x560, 0x1800), (0x530, 0x538, 0x1800),
    (0x508, 0x510, 0x1800), (0x858, 0x878, 0x4c0),
    (0x8b0, 0x8b8, 0x4000),
]
POINTERS = [
    ('hardware', 0, 0x300, 0x89be754),
    ('repeated', 8, 0x338, 0x89be70c),
    ('header', 0x10, 0x340, 0x89be6c4),
    ('shared0', 0x254, 0x308, 0x89be4d4),
    ('shared1', 0x25c, 0x310, 0x89be51c),
    ('shared2', 0x264, 0x318, 0x89be564),
    ('shared3', 0x26c, 0x328, 0x89be5ac),
    ('shared4', 0x274, 0x330, 0x89be5f0),
    ('power', 0x471, 0x320, 0x89be67c),
]


def pin(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def prepare(macho, symbols, region_c_report, graph_report, module, output):
    data = macho.read_bytes()
    if hashlib.sha256(data).hexdigest() != HOST_SHA:
        raise ValueError('Matched 25G83 input required')
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
    for name, begin, end, expected in SPANS:
        actual = hashlib.sha256(read(begin, end - begin)).hexdigest()
        if actual != expected:
            raise ValueError('Matched source span differs: ' + name)
        spans.append({'name': name, 'start': hex(begin), 'end': hex(end),
                      'bytes': end - begin, 'sha256': actual})
    vtable_entry = read(0x7eaf318, 8)
    if hashlib.sha256(vtable_entry).hexdigest() != '38fa36e4d68e70f83023e2e751e3aa73cfa5f30eef9107d3f0db831e1febc0be':
        raise ValueError('Selected G16X vtable entry differs')
    target = BASE + 0x7004000 + (struct.unpack('<Q', vtable_entry)[0] & 0xffffffff)
    symbol_rows = [row for row in json.loads(symbols.read_text())
                   if row['name'] == '__ZNK17AGXAcceleratorG1619getSizeOfFWBRNTableEv.8100'
                   and int(row['address'], 16) == target]
    if target != BASE + 0x89e8afc or len(symbol_rows) != 1:
        raise ValueError('Native zero BRN size method is not bound')

    ram = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for va, vsize, off, size in segments:
        if size:
            start, end = va & ~0xfff, (va + vsize + 0xfff) & ~0xfff
            ram.mem_map(start, end - start)
            ram.mem_write(va, data[off:off + size])
    obj, stack, page_shift = 0x10000000, 0x20010000, 0x30000000
    ram.mem_map(obj, 0x40000)
    ram.mem_map(0x20000000, 0x20000)
    ram.mem_map(page_shift, 0x1000)
    ram.reg_write(reg.UC_ARM64_REG_X19, obj)
    ram.reg_write(reg.UC_ARM64_REG_SP, stack)
    ram.reg_write(reg.UC_ARM64_REG_X29, stack + 0x330)
    ram.reg_write(reg.UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def execute(begin, end, limit):
        ram.emu_start(BASE + begin, BASE + end, count=limit)
        if ram.reg_read(reg.UC_ARM64_REG_PC) != BASE + end:
            raise ValueError('Bounded native producer did not reach its stop')

    execute(0x89ab668, 0x89ab770, 300)
    # Execute the actual selected leaf, bypassing its already-bound PAC dispatch.
    execute(0x89e8afc, 0x89e8b04, 10)
    if ram.reg_read(reg.UC_ARM64_REG_X0) != 0:
        raise ValueError('Native BRN size differs')
    execute(0x89ab7ac, 0x89ab8f8, 300)
    descriptor = stack + 0x330 - 0x88
    before = bytes(ram.mem_read(stack + 0x20, 23 * 24))
    actual = [(cpu - obj, mapping - obj, size)
              for cpu, mapping, size, _ in struct.iter_unpack('<QQII', before)]
    if actual != EXPECTED or any(offset for _, _, _, offset in struct.iter_unpack('<QQII', before)):
        raise ValueError('Native child descriptor operands differ')
    outer_cpu, outer_mapping, space, children, count, flags = struct.unpack(
        '<QQB7xQI4xQ', bytes(ram.mem_read(descriptor, 48)))
    if (outer_cpu - obj, outer_mapping - obj, space, children, count, flags) != (
            0x348, 0x350, 9, stack + 0x20, 23, 0):
        raise ValueError('Native outer descriptor differs')
    # The native allocator reads an imported page-shift operand. Profile 14 is
    # an explicit RAM fixture, not a recovered live kernel import value.
    ram.mem_write(BASE + 0x7ea2388, struct.pack('<Q', page_shift))
    ram.mem_write(page_shift, struct.pack('<I', 14))
    ram.reg_write(reg.UC_ARM64_REG_X1, descriptor)
    execute(0x89a7c70, 0x89a7cf4, 1000)
    after = bytes(ram.mem_read(stack + 0x20, 23 * 24))
    offset, child_rows = 0, []
    for index, (cpu, mapping, size, native_offset) in enumerate(struct.iter_unpack('<QQII', after)):
        if index:
            offset = (offset + child_rows[-1]['bytes'] + 63) & ~63
        if native_offset != offset:
            raise ValueError('Actual native child alignment differs')
        child_rows.append({'index': index, 'cpu_owner': hex(cpu - obj),
                           'mapping_owner': hex(mapping - obj), 'offset': hex(offset), 'bytes': size})
    logical = offset + child_rows[-1]['bytes']
    backing = (logical + 0x3fff) & ~0x3fff
    if logical != 0x225c0 or backing != 0x24000 or ram.reg_read(reg.UC_ARM64_REG_X21) != backing:
        raise ValueError('Native allocation extent differs')
    owners = {int(row['mapping_owner'], 16): row['index'] for row in child_rows}
    main_rows = [{'name': name, 'offset': hex(offset), 'mapping_owner': hex(owner),
                  'child_index': owners[owner], 'width': 8, 'store': hex(store),
                  'translation_callback_slot': '0x2d8', 'translation_argument2': 0}
                 for name, offset, owner, store in POINTERS]
    constants = read(0x712d808, 0x58)
    if hashlib.sha256(constants).hexdigest() != '314cdd893f4e4eff972e3d61f935f81ccc21ce1735ff55393b46d7818efc5bfc':
        raise ValueError('Native child-size constant table differs')
    report = {
        'schema': 'm4rch.native-t6040-bundle-component.v1', 'logical_bytes': logical,
        'backing_bytes': backing, 'main_offset': '0x1e100', 'main_bytes': 0x4c0,
        'bundle_complete': False, 'normal_startup_qualified': False,
        'macho': pin(macho), 'source_spans': spans,
        'source_pins': [pin(symbols), pin(region_c_report), pin(graph_report)],
        'component_source': pin(module), 'children': child_rows,
        'native_size_constants': {'address': '0x712d808', 'bytes': len(constants),
                                   'sha256': hashlib.sha256(constants).hexdigest()},
        'native_outer_descriptor': {'cpu_owner': '0x348', 'mapping_owner': '0x350',
                                    'range': 9, 'children': 23, 'additional_flags': 0,
                                    'allocation_call': '0x89ab934', 'callback_slot': '0x238',
                                    'allocate_bool2': 1, 'allocate_bool3': 0},
        'zero_brn_child': {'index': 7, 'logical_bytes': 0, 'mapping_owner': '0x338',
                           'selected_class': 'AGXAcceleratorG16X',
                           'vtable_address_point': '0x7eae398', 'slot': '0xf80',
                           'entry': '0x7eaf318', 'entry_sha256': hashlib.sha256(vtable_entry).hexdigest(),
                           'target': '0x89e8afc', 'native_leaf_return': 0,
                           'aliases_header_child': 8, 'alias_offset': '0xc040',
                           'separate_page_or_zero_fill': False},
        'native_child_alignment': {'bytes': 64, 'formula': '(previous_offset + previous_size + 63) & -64',
                                   'page_rounding': '(last_offset + last_size + page_bytes - 1) & -page_bytes',
                                   'profile_page_shift': 14, 'profile_page_bytes': 0x4000,
                                   'native_import_pointer': '0x7ea2388',
                                   'imported_native_page_shift_value_separately_recovered': False,
                                   'zero_initial_backing': 'existing pinned allocator _bzero proof'},
        'native_mapping_policy': {'range': 9, 'allocate_bool3': 0,
                                  'false_base': '0x7', 'special_range9_flags': '0x20900000000',
                                  'combined_native_flags': '0x20900000007',
                                  'linux_pte_translation_qualified': False,
                                  'production_permission_change': False},
        'main_pointer_fields': main_rows,
        'main_literal_fields': [{'offset': '0x250', 'width': 4, 'value': 0, 'store': '0x89be7a0'},
                                {'offset': '0x2f8', 'width': 8, 'value': 0, 'store': '0x89cd418'}],
        'root_main_binding': {'owner': '0x878', 'mapping_load': '0x89cd96c',
                              'translation_call': '0x89cd9a4', 'root_store': '0x89cd9ac',
                              'root_offset': '0x18', 'main_child': 21,
                              'selected_root_pointer': 'owned_bundle_base + 0x1e100'},
        'source_execution': {'hardware_access': False, 'cases': 1, 'child_records': 23,
                              'actual_native_descriptor_producer': True,
                              'actual_selected_zero_BRN_leaf': True,
                              'actual_native_alignment_and_rounding_loop': True,
                              'page_shift_operand': 'RAM fixture 14 for selected profile',
                              'PAC_dispatch_executed': False,
                              'native_allocation_or_mapping_provider_executed': False,
                              'full_shared_data_or_callbacks_executed': False,
                              'descriptor_before_sha256': hashlib.sha256(before).hexdigest(),
                              'descriptor_after_sha256': hashlib.sha256(after).hexdigest()},
        'production_transfer': {'owned_bundle_allocation_bytes': backing,
                                'native_root_main_pointer_selected': True,
                                'native_child0_hardware_bytes': 0x2718,
                                'native_power_object_bytes': 0x6578,
                                'native_main_bytes': 0x4c0,
                                'pointer_geometry_requires_no_donor_offsets': True,
                                'complete_bundle_return_requires_bundle_complete': True,
                                'all_unqualified_component_bytes_preserved': True},
        'remaining_full_bundle_inputs': [
            'full native hardware contents: current 0x2570 component vs 0x2718 logical extent',
            'full power object contents through native logical extent0x6578',
            'complete 17 channel records and fresh work/cursor/ring owners',
            'MainConfig external pointer200, extra240 and other input fields',
            'nested shared/header child contents and external callbacks',
            'complete native Root/Region A/status/Region C fields',
            'FW address translation callback and native mapping flag translation',
            'cache publication and mapping lifetime',
        ],
        'qualification': 'Native literal child-descriptor producers, selected zero BRN leaf and 23-child alignment/page-rounding loop execute only in RAM. Numeric native MainConfig/root pointer store operands bind the bounded Rust component. Provider allocation, address translation callbacks, full bundle contents, normal startup, GPU submission and render remain unqualified.',
        'hardware_access': False, 'hardware_actions': [],
        'private_binary_or_instruction_bytes_exported': False,
    }
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    names = ['macho', 'symbols', 'region_c_report', 'graph_report', 'module', 'output']
    for name in names:
        cli.add_argument(name, type=Path)
    args = cli.parse_args()
    result = prepare(*[getattr(args, name).resolve() for name in names])
    print(json.dumps({'children': len(result['children']), 'logical_bytes': result['logical_bytes'],
                      'backing_bytes': result['backing_bytes'], 'main_offset': result['main_offset'],
                      'main_bytes': result['main_bytes'], 'bundle_complete': False, 'hardware_actions': []}))
