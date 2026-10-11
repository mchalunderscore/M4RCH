#!/usr/bin/env python3
"""Bind the bounded native Region C producer to saved source; no hardware access."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
HOST_BASE = 0xfffffe0000000000
ADT_SHA = '01fb4c838a75aac89a3ddaa90996a65c394c07933a5b6927ec7ec13f6867cf39'
# Reviewed source spans and decoded numeric operands only. Private instruction
# bytes are never emitted into this kit or its numeric report.
SPANS = [
    ('RegionC_child_targets_and_size', 0x89abc24, 0x89abc4c, '9baf7936b808d11570755851af9c280cfb027aedeaf36fe7a54aaa854047678b'),
    ('allocation_parameters_producers', 0x89abbc4, 0x89abc04, 'dd646eb54c83209b5944c82e75200ad301561afc7ae8340b078ce5e72e1eda9b'),
    ('RegionC_allocation_parameters', 0x89abc54, 0x89abca4, '7634c34ec8ab586bf6b52556e8130ab97f47637bfd183035702b649b8abcabf5'),
    ('allocator_argument_capture', 0x89a7c44, 0x89a7c70, 'bea6ee8719fa6229515dd621e656d81340735fc25d7f1a0145946a472dd77fdb'),
    ('allocator_child_offset_and_page_rounding', 0x89a7c70, 0x89a7cf4, '48fc3de0a0c6b01a68db87ad686c777201dff134256bbbf9af52c4e06ccda001'),
    ('allocator_native_mapping_flags', 0x89a7d6c, 0x89a7d88, 'c4750f49376b5a941af00a12c1751d99706760822b860227a2f22c1cc6efe84e'),
    ('allocator_zeroing_and_child_cpu_va_exposure', 0x89a7df0, 0x89a7ea8, '27a40f27ae0c6f304150d33b5f1099bdf648bc15253a7fa40cb41a0f9183917b'),
    ('native_root_RegionC_pointer', 0x89cd9b0, 0x89cd9f4, '29902b730f6984697bf4ce28a14e5d64408aa245c705a330ae0e19c8993059e2'),
    ('generic_RegionC_initial_zero_words', 0x89aa02c, 0x89aa070, '88cb216cebfab5ea13ac12a80425d3c2ea059ea53cd1f345a50a146794dae36e'),
    ('generic_RegionC_zero10_and_e1c', 0x89aa100, 0x89aa140, 'c007289eacb9cf96f341591f705c3c0469204ba34dace20aacb13899beaccd79'),
    ('generic_RegionC_initial_120', 0x89aa160, 0x89aa168, 'ed3fe4eb76f96d5d7d13b93dab664de858f88de97b03c403187edcbeddf14497'),
    ('generic_RegionC_tail_initial_literals', 0x89aa524, 0x89aa540, '2e672a8138bd23fe2550e655b1fb35d12dbae594eb83c453412c8d60f7fb4b00'),
    ('ARM_inherits_generic_initializer', 0x89cd104, 0x89cd124, '0a1f064002e2e7324cdb8e911d7e32ff89a5651d47c94487c249def0d0e17fea'),
    ('ARM_RegionC_zero9c4', 0x89cd4d4, 0x89cd4dc, '0ce49afffe370448a7e898d018a448ac72fc0d930343f2c6114c7839501382e2'),
    ('ARM_RegionC_zero5a', 0x89cd650, 0x89cd658, '27039e13d260152ac73eec673d996793488da9cbe04e65624e6348f68fdd54d6'),
    ('ARM_RegionC_zero14', 0x89cd694, 0x89cd69c, 'e88182fbc1a21bc30aabbaa46012b169fbf43b296de85456b9a4367f46941057'),
    ('ARM_RegionC_zero4c_50_9dc', 0x89cd6cc, 0x89cd6ec, '57dceafa88dac1a670f59711f1ffee0c65172e4f8298271cd8a2777e19de68ca'),
    ('ARM_RegionC_zero40_44', 0x89cd8dc, 0x89cd8f0, 'af9877f25614183f612e46cf07ebbd3bd764b42bc4a87ea5888cb5a24f594e7e'),
    ('ARM_RegionC_zeroe29', 0x89cd824, 0x89cd83c, 'dc3d1f7187cc8754baa5ab79d96e9d21096a08ba81e2785ffe815016a163fcb2'),
    ('ARM_power_RegionC_zero9c_a0', 0x89cce64, 0x89cce70, '184e1e309ffd6e5414343ce34bcbf10a8f6c07bad4f3860da3ba8ee4338e6576'),
    ('ARM_RegionC_power_pointer_hold', 0x89cc7c8, 0x89ccb18, '681ee44594b8263e9ef778b0e56bed56b3a0c90377204f8ed2d07b98be3cca52'),
    ('ARM_power_RegionC_literal7ec', 0x89ccb18, 0x89ccb88, '7651d53e85e64d8e07e0c2af08f716f121eeba988c1172549c97dad7bb2bd72c'),
    ('GPU_idle_property_and_default', 0x89cf188, 0x89cf1f0, '9a6e0a827bf0993740c307929b5172f774338aab335bc86537ece0fb1b72f0f4'),
    ('Fender_idle_property_and_default', 0x89cf214, 0x89cf274, '2fb0cb976644844c822e4c92170471b922513af4c60ee8128cd768cad4253c01'),
    ('initial_GPU_idle_delay_selection', 0x89ccb88, 0x89ccba8, 'cc75b12dd59fc60a5092a77b333a7c95b7d9d74150a15423eb566a7614a47e7c'),
    ('initial_Fender_idle_delay_selection', 0x89ccbb4, 0x89ccbd4, '9f13c545aed0bd3b5d58a49a6318a3261e455777862448830b28bdfef87e5437'),
]
# Independent source-derived expected stores; do not parse the Rust serializer
# to create its expected image. Offset e29 is e1d+c, not e2d.
U32_FIELDS = [
    (0x4, 0, 0x89aa060), (0x8, 0, 0x89aa064),
    (0x10, 0, 0x89aa130), (0x14, 0, 0x89cd698),
    (0x18, 0, 0x89aa068), (0x1c, 0, 0x89aa06c),
    (0x3c, 120, 0x89aa164), (0x40, 0, 0x89cd8e8),
    (0x44, 0, 0x89cd8ec), (0x48, 0, 0x89aa104),
    (0x4c, 0, 0x89cd6d0), (0x50, 0, 0x89cd6cc),
    (0x5a, 0, 0x89cd654), (0x9c, 0, 0x89cce68),
    (0xa0, 0, 0x89cce6c), (0x7ec, 1, 0x89ccb78),
    (0x9c4, 0, 0x89cd4d8), (0x9dc, 0, 0x89cd6e8),
    (0xe29, 0, 0x89cd838), (0xe3d, 1, 0x89aa530),
    (0xe41, 0, 0x89aa534), (0xe45, 0, 0x89aa538),
    (0xe49, 0, 0x89aa53c),
]


def pin(path):
    path = path.resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def prepare(macho, symbols, adt, adt_parser, delay_report, graph_report, module, output):
    data = macho.read_bytes()
    if hashlib.sha256(data).hexdigest() != HOST_SHA:
        raise ValueError('Matched 25G83 AGX input required')
    segments, position = [], 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', data, position + 24))
        position += size

    def read(address, size):
        offsets = [off + HOST_BASE + address - va for va, _, off, length in segments
                   if va <= HOST_BASE + address and HOST_BASE + address + size <= va + length]
        if len(offsets) != 1:
            raise ValueError('Source span is not uniquely backed')
        return data[offsets[0]:offsets[0] + size]

    spans = []
    for name, begin, end, expected in SPANS:
        actual = hashlib.sha256(read(begin, end - begin)).hexdigest()
        if actual != expected:
            raise ValueError('Matched source span differs: ' + name)
        spans.append({'name': name, 'start': hex(begin), 'end': hex(end),
                      'bytes': end - begin, 'sha256': actual})
    extent = read(0x712d8b8, 8)
    if struct.unpack('<II', extent) != (0xe58, 0):
        raise ValueError('Native child size/offset differs')
    bzero = [s for s in json.loads(symbols.read_text())
             if s['name'] == '_bzero' and s['address'] == '0xfffffe000b744da0'
             and s['owner'] == 'com.apple.kernel']
    if len(bzero) != 1:
        raise ValueError('Matched kernel zeroing target not established')
    properties = [('gpu', 'gpu-idle-off-delay-ms', 0x7138c8f, 2, 0x9b8),
                  ('fender', 'gpu-fender-idle-off-delay-ms', 0x7138ca5, 40, 0x9bc)]
    if pin(adt)['sha256'] != ADT_SHA:
        raise ValueError('Saved native ADT differs')
    spec = importlib.util.spec_from_file_location('saved_adt', adt_parser)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    tree = parser.parse(adt.read_bytes())
    delay = json.loads(delay_report.read_text())
    expected_defaults = [(p, value, hex(offset)) for _, p, _, value, offset in properties]
    actual_defaults = [(r['property'], r['milliseconds'], r['owned_offset'])
                       for r in delay['native_identity']['defaults']]
    if actual_defaults != expected_defaults or delay['native_identity']['sha256'] != HOST_SHA:
        raise ValueError('Existing qualified delay producer/consumer evidence differs')
    property_rows = []
    for name, prop, address, default, offset in properties:
        encoded = prop.encode() + b'\0'
        if read(address, len(encoded)) != encoded:
            raise ValueError('Matched property string differs')
        present = [path for path, props in tree.items() if prop in props]
        if present:
            raise ValueError('Saved default-case ADT unexpectedly supplies ' + prop)
        property_rows.append({'name': name, 'native_property': prop,
                              'linux_raw_property': 'apple,sgx-' + prop,
                              'string_address': hex(address), 'string_bytes': len(encoded),
                              'string_sha256': hashlib.sha256(encoded).hexdigest(),
                              'native_absent_default': default, 'output_offset': hex(offset),
                              'saved_adt_present_nodes': present})
    report = {
        'schema': 'm4rch.native-t6040-region-c-component.v1',
        'logical_bytes': 0xe58, 'backing_bytes': 0x4000,
        'region_c_complete': False, 'normal_startup_qualified': False,
        'macho': pin(macho), 'source_spans': spans,
        'source_pins': [pin(symbols), pin(adt), pin(adt_parser), pin(delay_report), pin(graph_report)],
        'component_source': pin(module),
        'native_child_descriptor': {'constant_address': '0x712d8b8', 'constant_bytes': 8,
                                    'constant_sha256': hashlib.sha256(extent).hexdigest(),
                                    'size': 0xe58, 'initial_offset': 0, 'children': 1,
                                    'cpu_output_object_offset': '0x380',
                                    'mapping_output_object_offset': '0x388',
                                    'outer_cpu_output_object_offset': '0x5a0',
                                    'outer_mapping_output_object_offset': '0x5a8',
                                    'range': 8, 'allocate_bool2': 1, 'allocate_bool3': 1,
                                    'allocation_call': '0x89abc9c', 'callback_slot': '0x238'},
        'native_backing': {'rounding': '(child_offset + child_size + page_bytes - 1) & -page_bytes',
                           'page_shift_import_pointer': '0x7ea2388',
                           'profile_page_shift': 14, 'profile_page_bytes': 0x4000,
                           'imported_native_page_shift_value_separately_recovered': False,
                           'rounded_profile_bytes': 0x4000,
                           'zeroing_call': '0x89a7e20', 'zeroing_symbol': '_bzero',
                           'zeroing_target': '0xfffffe000b744da0',
                           'zeroing_bytes': 'whole rounded allocation',
                           'child_cpu_exposure': '0x89a7e80..0x89a7e8c',
                           'child_va_exposure': '0x89a7e98..0x89a7ea4'},
        'native_root_binding': {'mapping_load': '0x89cd9b0', 'mapping_object_offset': '0x388',
                                'translation_call': '0x89cd9e8', 'callback_slot': '0x2d8',
                                'translation_argument2': 0, 'root_store': '0x89cd9f0',
                                'root_offset': '0x20',
                                'firmware_consumer_binding': 'existing pinned init-graph report'},
        'native_mapping_policy': {'bool3_true_base': '0x10000000005',
                                  'bool3_false_base': '0x7',
                                  'constructor_descriptor_additional_flags': 0,
                                  'range8_high_flags': '0x800000000',
                                  'combined_range8_native_flags': '0x10800000005',
                                  'linux_pte_translation_qualified': False,
                                  'production_permission_change': False},
        'initial_u32_fields': [{'offset': hex(offset), 'value': value, 'store': hex(store)}
                               for offset, value, store in U32_FIELDS],
        'initial_u8_fields': [{'offset': '0xe1c', 'value': 0, 'store': '0x89aa13c'}],
        'idle_default_fields': {'gpu': {'offset': '0x9b8', 'value': 2},
                                'fender': {'offset': '0x9bc', 'value': 40}},
        'idle_property_policy': {'properties': property_rows,
                                 'saved_adt': pin(adt), 'saved_adt_nodes_checked': len(tree),
                                 'native_read': 'first little-endian u32 of OSData if present and type matches',
                                 'linux_component_input': 'optional exact 4-byte raw little-endian property',
                                 'present_malformed_property': 'refused; stricter than unchecked native first-word read',
                                 'values': 'all u32, including zero; no invented range restriction',
                                 'initial_override_state': 'native flags 1dd4/1de0 and values 1dd0/1ddc initialized zero',
                                 'loader_raw_property_bridge_installed': False,
                                 'runtime_override_owner_qualified': False},
        'production_transfer': {'typed_api': 'RegionC::from_adt(...).write_component(...)',
                                'logical_extent_bound': True, 'root_pointer_owner_bound': True,
                                'page_allocation_for_profile_bound': True,
                                'whole_backing_initially_zero': True,
                                'component_preserves_all_unqualified_bytes': True,
                                'full_object_return_requires_region_c_complete': True,
                                'donor_maximum_power_or_timing_defaults_used': False},
        'remaining_full_object_inputs': [
            'native power interface and nonconstant policy/timing/cluster fields',
            'complete initial producer call graph and later callback writes',
            'Region C e51 and other unqualified tail/input fields',
            'native mapping flag translation to Linux UAT permission bits',
            'live original-ADT property export bridge when a property is present',
        ],
        'qualification': 'Exact bounded initial literal stores and optional native idle-input transfer. Allocation child size, profile rounding, zeroed backing and root+20 owner chain are source bound. This is not a complete Region C image, full native bootbundle, runtime reset policy, MMIO trial, normal startup, submission or render proof.',
        'hardware_access': False, 'hardware_actions': [],
        'private_binary_or_instruction_bytes_exported': False,
    }
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    names = ['macho', 'symbols', 'adt', 'adt_parser', 'delay_report', 'graph_report', 'module', 'output']
    for name in names:
        cli.add_argument(name, type=Path)
    args = cli.parse_args()
    result = prepare(*[getattr(args, name).resolve() for name in names])
    print(json.dumps({'logical_bytes': result['logical_bytes'], 'backing_bytes': result['backing_bytes'],
                      'source_spans': len(result['source_spans']),
                      'initial_u32_fields': len(result['initial_u32_fields']),
                      'region_c_complete': result['region_c_complete'], 'hardware_actions': []}))
