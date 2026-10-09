#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline admission cases using the two actual saved boot layouts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
guard = runpy.run_path(str(HERE / 'flash-layout-guard.py'))
qualify = guard['qualify_flash_layout']
baseline_path = ROOT / 'experiments/t6040-gpu/gfx-native-coordinate-trial/linux-dt-contract.json'
observed_path = ROOT / 'out/gfx-native-coordinate-live/boot-493814fd-b859-42b5-b257-c0ac4960e8a1/linux-dt-current.json'
baseline = baseline_path.read_bytes()
observed = observed_path.read_bytes()
assert hashlib.sha256(baseline).hexdigest() == '71236d89511e3689fef2d7485f2e7d7557f50603c83cbc3ce6bffa77d9d9b32b'
assert hashlib.sha256(observed).hexdigest() == 'e2adc89815e82eba3b67b3d0b466d1c1d4a47ba94f7acbe18773403952de5759'
original = json.loads(baseline)
cases = []


def encode(items):
    return (json.dumps(items, indent=2) + '\n').encode()


def target(items):
    return next(item for item in items if item['node'] == '/reserved-memory/flash@100057e8000')


def relocation(base, size=0x94000):
    items = deepcopy(original)
    flash = target(items)
    flash['node'] = '/reserved-memory/flash@' + format(base, 'x')
    flash['properties']['reg'] = base.to_bytes(8, 'big').hex() + size.to_bytes(8, 'big').hex()
    return items


def accept(name, raw):
    result = qualify(baseline, raw)
    assert result['exact_other_nodes'] == 311
    assert result['normalized_sha256'] == 'cd8aa099cda21fcd8dab8278d65145546b26311f2c8d67139fb83bf921371f8c'
    cases.append({'name': name, 'admitted': True})
    return result


def refuse(name, raw, message=None, expected=baseline):
    try:
        qualify(expected, raw)
    except (ValueError, UnicodeError) as error:
        if message:
            assert message in str(error), (name, str(error))
        cases.append({'name': name, 'admitted': False})
    else:
        raise AssertionError('Incorrect admission: ' + name)


assert accept('identical-original', baseline)['flash_relocated'] is False
real = accept('actual493814fd-relocation', observed)
assert real['flash_relocated'] is True
assert real['observed_flash']['base'] == 0x10005cf8000
accept('another-aligned-in-RAM-relocation', encode(relocation(0x10008000000)))
accept('RAM-lower-boundary', encode(relocation(0x100032b8000)))
accept('RAM-upper-boundary', encode(relocation(0x105daefc000 - 0x94000)))

for label, base, _ in guard['PROTECTED_REGIONS']:
    refuse('overlap-' + label, encode(relocation(base)), 'overlaps fixed region:')
    refuse('partial-overlap-' + label, encode(relocation(base - 0x4000)), 'overlaps fixed region:')

refuse('wrong-size', encode(relocation(0x10005cf8000, 0x98000)))
refuse('unaligned-base', encode(relocation(0x10005cf8001)), 'alignment')
refuse('zero-base', encode(relocation(0)), 'resource interval')
refuse('address-overflow', encode(relocation(0xfffffffffffc0000)), 'resource interval')
refuse('outside-RAM', encode(relocation(0x10600000000)), 'captured RAM')
refuse('straddles-RAM-end', encode(relocation(0x105daefc000 - 0x90000)), 'captured RAM')
refuse('overlaps-other-phram', encode(relocation(0x105daf00000 - 0x4000)), 'another reserved-memory')

for key, value in [('compatible', '706872616d'), ('compatible', '737973636f6e00'),
                   ('status', '6f6b617900'), ('ranges', '')]:
    items = relocation(0x10005cf8000)
    flash = next(item for item in items if item['node'] == '/reserved-memory/flash@10005cf8000')
    flash['properties'][key] = value
    refuse('flash-property-' + key + '-' + value, encode(items), 'Flash properties')

for unit in ['010005cf8000', '10005CF8000', '10005cf8001']:
    items = relocation(0x10005cf8000)
    next(item for item in items if item['node'].startswith('/reserved-memory/flash@10005'))['node'] = '/reserved-memory/flash@' + unit
    refuse('noncanonical-unit-' + unit, encode(items))

items = deepcopy(original)
target(items)['node'] = '/reserved-memory/other@100057e8000'
refuse('renamed-flash-kind', encode(items))
items = deepcopy(original)
target(items)['properties']['reg'] += target(items)['properties']['reg']
refuse('multiple-flash-resource-tuples', encode(items))

for node, prop, value in [
    ('/reserved-memory', 'ranges', '000000000000000000000000'),
    ('/reserved-memory', '#size-cells', '00000001'),
    ('/', '#address-cells', '00000001'),
    ('/memory@10000000000', 'reg', '00000100032b800000000005d7c48000'),
    ('/reserved-memory/flash@105daf00000', 'reg', '00000105daf000000000000000008000'),
]:
    items = deepcopy(original)
    next(item for item in items if item['node'] == node)['properties'][prop] = value
    refuse('unrelated-property-' + node + '-' + prop, encode(items))

items = deepcopy(original)
gpu = next(item for item in items if item['node'] == '/soc/power-management@288e80000/power-controller@110')
gpu['properties']['reg'] = '0000011400000004'
refuse('GFX-domain-reg-change', encode(items), 'Non-flash')
items = deepcopy(original)
next(item for item in items if item['node'] == '/soc')['properties']['ranges'] = '000000000000000000000000000000010000000000004000'
refuse('soc-translation-change', encode(items), 'Non-flash')

items = deepcopy(original)
items[-1] = deepcopy(target(items))
items[-1]['node'] = '/reserved-memory/flash@10006000000'
items[-1]['properties']['reg'] = '00000100060000000000000000094000'
refuse('two-normalizable-flashes', encode(items), 'Expected one')
refuse('extra-node', encode(original + [deepcopy(original[-1])]))
refuse('missing-node', encode(original[:-1]))
items = deepcopy(original)
items[-1] = deepcopy(items[0])
refuse('duplicate-node', encode(items), 'Duplicate node')
items = deepcopy(original)
items[-1]['properties']['status'] = 'GG'
refuse('malformed-property-hex', encode(items), 'encoded property')
items = deepcopy(original)
items[-1]['unexpected'] = 1
refuse('unknown-layout-field', encode(items), 'layout entry')
refuse('duplicate-JSON-key', baseline.replace(b'"node":', b'"node":"/duplicate","node":', 1), 'Duplicate JSON key')
refuse('oversized-input', b' ' * (guard['MAX_LAYOUT_BYTES'] + 1))
refuse('wrong-input-type', baseline.decode())
refuse('malformed-baseline-also-rejected', observed, expected=encode(relocation(0)))
assert baseline == baseline_path.read_bytes() and observed == observed_path.read_bytes()
print(json.dumps({'schema': 'm4rch.single-phram-flash-layout-qualification.v1',
                  'hardware_access': False, 'cases_passed': len(cases),
                  'source_sha256': hashlib.sha256((HERE / 'flash-layout-guard.py').read_bytes()).hexdigest(),
                  'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'baseline_sha256': hashlib.sha256(baseline).hexdigest(),
                  'observed_sha256': hashlib.sha256(observed).hexdigest(),
                  'actual_saved_relocation': real, 'cases': cases}, indent=2))
