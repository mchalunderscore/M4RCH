#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Permit one bounded phram relocation in an otherwise exact saved OF layout.

This consumes encoded metadata supplied by the caller. It does not read live
device trees, device registers or physical memory. The caller still pins the
baseline bytes, this source, native ADT selection and the hardware candidate.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

FLASH_SIZE = 0x94000
FLASH_ALIGNMENT = 0x4000
LAYOUT_NODES = 312
MAX_LAYOUT_BYTES = 128 * 1024
FLASH_NODE = re.compile(r'/reserved-memory/flash@([0-9a-f]+)\Z')
CAPTURED_KEYS = {'#address-cells', '#size-cells', 'reg', 'ranges', 'dma-ranges',
                 'assigned-addresses', 'compatible', 'device_type', 'status'}
# Conservative fixed apertures from the existing owner/harness. The RAM
# containment check independently excludes MMIO; these explicit intervals also
# prevent a future malformed RAM declaration from admitting a GPU collision.
PROTECTED_REGIONS = (
    ('SGX', 0x288000000, 0x4000000),
    ('ASC', 0x28a600000, 0x88000),
    ('AFR', 0x28b000000, 0x2000000),
    ('platform', 0x502414000, 0x4000),
    ('PMP', 0x5003c0000, 0x30000),
    ('PMC', 0x504000000, 0x1000000),
    ('firmware-TEXT', 0x10000be4000, 0x60000),
    ('firmware-DATA', 0x10001d44000, 0x138000),
    ('loader-L2', 0x105fff74000, 0x4000),
    ('shared-tables', 0x105fff78000, 0x40000),
    ('joined-context-table', 0x105fffb8000, 0x4000),
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _parse(raw):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_LAYOUT_BYTES,
             'Unsupported encoded layout size/type')
    items = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
    _require(isinstance(items, list) and len(items) == LAYOUT_NODES,
             'Layout must contain exactly312 captured nodes')
    nodes = {}
    for item in items:
        _require(isinstance(item, dict) and set(item) == {'node', 'properties'},
                 'Malformed layout entry')
        node, props = item['node'], item['properties']
        _require(isinstance(node, str) and node.startswith('/') and
                 (node == '/' or all(part not in ('', '.', '..')
                                     for part in node[1:].split('/'))),
                 'Malformed node path')
        _require(node not in nodes, 'Duplicate node: ' + node)
        _require(isinstance(props, dict) and props and
                 set(props) <= CAPTURED_KEYS, 'Malformed captured properties')
        for value in props.values():
            _require(isinstance(value, str) and len(value) % 2 == 0 and
                     re.fullmatch(r'[0-9a-f]*', value) is not None,
                     'Malformed encoded property')
        nodes[node] = props
    return nodes


def _intervals(reg):
    data = bytes.fromhex(reg)
    _require(data and len(data) % 16 == 0, 'Expected 2/2-cell resource tuples')
    result = []
    for offset in range(0, len(data), 16):
        base = int.from_bytes(data[offset:offset + 8], 'big')
        size = int.from_bytes(data[offset + 8:offset + 16], 'big')
        _require(base > 0 and size > 0 and base + size <= 1 << 64,
                 'Empty or overflowing resource interval')
        result.append((base, base + size))
    return result


def _overlap(start, end, base, limit):
    return start < limit and base < end


def _inspect(nodes):
    _require(nodes.get('/reserved-memory') == {
        '#address-cells': '00000002', '#size-cells': '00000002', 'ranges': ''},
        'Reserved-memory translation must remain exact 2/2 identity')
    _require(nodes.get('/', {}).get('#address-cells') == '00000002' and
             nodes.get('/', {}).get('#size-cells') == '00000002',
             'Root resource cells must remain 2/2')
    targets = []
    for node, props in nodes.items():
        match = FLASH_NODE.fullmatch(node)
        if not match or 'reg' not in props:
            continue
        intervals = _intervals(props['reg'])
        if len(intervals) == 1 and intervals[0][1] - intervals[0][0] == FLASH_SIZE:
            targets.append((node, props, intervals[0], match.group(1)))
    _require(len(targets) == 1, 'Expected one phram flash reservation of size0x94000')
    node, props, (start, end), unit = targets[0]
    _require(set(props) == {'compatible', 'reg'} and
             props['compatible'] == '706872616d00', 'Flash properties differ')
    _require(unit == format(start, 'x') and start % FLASH_ALIGNMENT == 0,
             'Flash unit address/alignment differs')
    for label, base, size in PROTECTED_REGIONS:
        _require(not _overlap(start, end, base, base + size),
                 'Flash overlaps fixed region: ' + label)
    ram = []
    for name, values in nodes.items():
        if name.startswith('/memory@') and values.get('device_type') == '6d656d6f727900':
            _require('reg' in values, 'Memory node missing reg')
            ram.extend(_intervals(values['reg']))
        if name.startswith('/reserved-memory/') and name != node and 'reg' in values:
            for base, limit in _intervals(values['reg']):
                _require(not _overlap(start, end, base, limit),
                         'Flash overlaps another reserved-memory interval: ' + name)
    _require(any(base <= start and end <= limit for base, limit in ram),
             'Flash must fit within one captured RAM interval')
    return {'node': node, 'base': start, 'end_exclusive': end, 'size': FLASH_SIZE}


def _encoded(nodes):
    items = [{'node': name, 'properties': dict(sorted(props.items()))}
             for name, props in sorted(nodes.items())]
    return (json.dumps(items, indent=2) + '\n').encode()


def qualify_flash_layout(expected_bytes, observed_bytes):
    """Validate both layouts; ignore only one flash path/reg-base relocation."""
    expected, observed = _parse(expected_bytes), _parse(observed_bytes)
    before, after = _inspect(expected), _inspect(observed)
    remaining_before = {key: value for key, value in expected.items()
                        if key != before['node']}
    remaining_after = {key: value for key, value in observed.items()
                       if key != after['node']}
    _require(remaining_before == remaining_after,
             'Non-flash captured nodes/properties changed')
    normalized = dict(remaining_before)
    normalized['/reserved-memory/flash@variable'] = {
        'compatible': '706872616d00',
        'reg': (0).to_bytes(8, 'big').hex() + FLASH_SIZE.to_bytes(8, 'big').hex(),
    }
    return {
        'schema': 'm4rch.single-phram-flash-layout.v1',
        'baseline_raw_sha256': hashlib.sha256(expected_bytes).hexdigest(),
        'observed_raw_sha256': hashlib.sha256(observed_bytes).hexdigest(),
        'normalized_sha256': hashlib.sha256(_encoded(normalized)).hexdigest(),
        'exact_other_nodes': LAYOUT_NODES - 1,
        'flash_alignment': FLASH_ALIGNMENT,
        'baseline_flash': before, 'observed_flash': after,
        'flash_relocated': before != after,
        'hardware_access': False,
        'native_selection_verified_by_this_guard': False,
    }


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: flash-layout-guard.py BASELINE_JSON OBSERVED_JSON')
    print(json.dumps(qualify_flash_layout(Path(sys.argv[1]).read_bytes(),
                                         Path(sys.argv[2]).read_bytes()), indent=2))
