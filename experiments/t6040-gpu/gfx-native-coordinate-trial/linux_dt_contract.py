# SPDX-License-Identifier: GPL-2.0-only
"""Metadata-only OF resource layout guard; never accesses device registers."""
import json
from pathlib import Path

KEYS = ('#address-cells', '#size-cells', 'reg', 'ranges', 'dma-ranges',
        'assigned-addresses', 'compatible', 'device_type', 'status')


def layout(base):
    base = Path(base)
    nodes = {}
    for directory in [base] + sorted(path for path in base.rglob('*') if path.is_dir()):
        name = '/' + str(directory.relative_to(base))
        if name == '/.':
            name = '/'
        values = {key: (directory / key).read_bytes() for key in KEYS
                  if (directory / key).is_file()}
        if values:
            nodes[name] = values

    def parent(name):
        return name.rsplit('/', 1)[0] or '/'

    def cells(name, key, default):
        while True:
            value = nodes.get(name, {}).get(key)
            if value is not None:
                if len(value) != 4:
                    raise ValueError('Malformed cell count: ' + name + '/' + key)
                count = int.from_bytes(value, 'big')
                if not 0 <= count <= 4:
                    raise ValueError('Unsupported cell count: ' + name + '/' + key)
                return count
            if name == '/':
                return default
            name = parent(name)

    for name, values in nodes.items():
        for key in ('#address-cells', '#size-cells'):
            if key in values:
                cells(name, key, 0)
        for key in ('reg', 'assigned-addresses'):
            if key in values:
                stride = cells(parent(name), '#address-cells', 2) + cells(parent(name), '#size-cells', 1)
                if not stride or not values[key] or len(values[key]) % (stride * 4):
                    raise ValueError('Malformed resource tuples: ' + name + '/' + key)
        for key in ('ranges', 'dma-ranges'):
            if key in values and values[key]:
                stride = (cells(name, '#address-cells', 2) +
                          cells(parent(name), '#address-cells', 2) +
                          cells(name, '#size-cells', 1))
                if not stride or len(values[key]) % (stride * 4):
                    raise ValueError('Malformed translation tuples: ' + name + '/' + key)
    return [{'node': name, 'properties': {key: value.hex() for key, value in sorted(values.items())}}
            for name, values in sorted(nodes.items())]


def encoded_layout(base):
    return (json.dumps(layout(base), indent=2) + '\n').encode()
