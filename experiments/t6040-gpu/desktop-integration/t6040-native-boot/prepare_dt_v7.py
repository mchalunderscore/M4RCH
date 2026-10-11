#!/usr/bin/env python3
"""Stage disabled T6040 resources in the saved Linux DT, without installing it.

Firmware RAM addresses are loader-owned inputs. Five typed reservation nodes
are created without a reg property; this intentionally cannot activate a GPU.
Original SGX ADT bytes are then exported by the raw-input bridge.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import struct

import libfdt
from native_adt_bridge_v7 import bridge, node_properties, pin

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
GPU = '/soc/gpu@28a600000'
MAILBOX = '/soc/mailbox@28a608000'
REGIONS = ['ttbs', 'pagetables', 'l2', 'handoff', 'firmware']


def cells(*values):
    return b''.join(struct.pack('>I', value) for value in values)


def reg(base, size):
    return cells(base >> 32, base & 0xffffffff, size >> 32, size & 0xffffffff)


def original(adt):
    parser_path = ROOT / 'experiments/t6040-gpu/adt.py'
    spec = importlib.util.spec_from_file_location('dt_v7_adt', parser_path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser.parse(adt.read_bytes()), parser_path


def translate(tree, node, resource):
    """Original arm-io ranges bind ADT bus addresses to CPU physical addresses."""
    words = struct.unpack('<' + 'Q' * (len(node['reg']) // 8), node['reg'])
    base, size = words[resource * 2:resource * 2 + 2]
    ranges = struct.unpack('<' + 'Q' * (len(tree['/device-tree/arm-io']['ranges']) // 8),
                           tree['/device-tree/arm-io']['ranges'])
    matches = [(physical + base - child, size) for child, physical, span in
               zip(ranges[::3], ranges[1::3], ranges[2::3])
               if base >= child and base + size <= child + span]
    if len(matches) != 1:
        raise ValueError('Unique original ADT resource translation required')
    return matches[0]


def candidate(raw, tree):
    before = node_properties(raw)
    if b'apple,j614s' not in before['/']['compatible'].split(b'\0'):
        raise ValueError('Saved J614s DT required')
    if GPU in before or MAILBOX in before:
        raise ValueError('Fresh GPU-free DT input required')
    sgx = tree['/device-tree/arm-io/sgx']
    asc = tree['/device-tree/arm-io/gfx-asc']
    sgx_resource = translate(tree, sgx, 0)
    asc_resource = translate(tree, asc, 0)
    if sgx_resource != (0x288000000, 0x3758000) or asc_resource != (0x28a600000, 0x88000):
        raise ValueError('Selected captured T6040 resource geometry differs')
    # The saved kernel's existing coordinate GFX power-domain owner is reused.
    # This is a Linux power-domain transfer policy, not a reconstructed native
    # PMGR ID graph. Disabled resources do not invoke the policy.
    gfx = '/soc/power-management@288e80000/power-controller@110'
    if before[gfx].get('label') != b'gfx\0' or before[gfx]['reg'] != cells(0x110, 4):
        raise ValueError('Existing kernel GFX coordinate owner differs')
    aics = [p for p, props in before.items()
            if b'apple,t6040-aic3' in props.get('compatible', b'').split(b'\0')]
    if len(aics) != 1:
        raise ValueError('Unique AIC owner required')
    aic = int.from_bytes(before[aics[0]]['phandle'], 'big')
    phandles = [int.from_bytes(p['phandle'], 'big') for p in before.values() if 'phandle' in p]
    next_phandle = max(phandles) + 1
    if next_phandle + 7 >= 0xffffffff:
        raise ValueError('Available phandle namespace required')
    gfx_phandle = int.from_bytes(before[gfx]['phandle'], 'big') if 'phandle' in before[gfx] else next_phandle
    if 'phandle' not in before[gfx]:
        next_phandle += 1
    mailbox_phandle = next_phandle
    next_phandle += 1
    fdt = libfdt.Fdt(raw)
    fdt.resize(fdt.totalsize() + 32768)
    expected = {path: dict(props) for path, props in before.items()}
    if 'phandle' not in before[gfx]:
        fdt.setprop(fdt.path_offset(gfx), 'phandle', cells(gfx_phandle))
        expected[gfx]['phandle'] = cells(gfx_phandle)

    def add(path, props):
        parent, name = path.rsplit('/', 1)
        fdt.add_subnode(fdt.path_offset(parent or '/'), name)
        for name, value in props.items():
            fdt.setprop(fdt.path_offset(path), name, value)
        expected[path] = props

    owners = []
    for name in REGIONS:
        path = '/reserved-memory/gpu-' + name
        props = {'status': b'disabled\0', 'phandle': cells(next_phandle), 'no-map': b''}
        add(path, props)
        owners.append(next_phandle)
        next_phandle += 1
    add(GPU, {'compatible': b'apple,agx-t6040\0',
              'reg': reg(*asc_resource) + reg(*sgx_resource),
              'reg-names': b'asc\0sgx\0', 'status': b'disabled\0',
              'mboxes': cells(mailbox_phandle), 'power-domains': cells(gfx_phandle),
              'memory-region': cells(*owners),
              'memory-region-names': b'\0'.join(name.encode() for name in REGIONS) + b'\0',
              'apple,rtkit-private-vm-region': reg(0xfffffc0000000000, 0x2000000000),
              # This exact firmware-version is the existing donor loader's
              # validated boot identity. system-firmware-version is a distinct
              # property and must not replace it.
              'apple,firmware-build': tree['/device-tree/chosen']['firmware-version'].split(b'\0')[0] + b'\0',
              'apple,chip-revision': cells(int.from_bytes(
                  tree['/device-tree/arm-io']['chip-revision'], 'little'))})
    irqs = struct.unpack('<4I', asc['interrupts'])
    # Native ADT order is send-not-empty, send-empty, receive-not-empty,
    # receive-empty. Linux names order the empty IRQ first for both pairs.
    linux_irqs = [irqs[1], irqs[0], irqs[3], irqs[2]]
    add(MAILBOX, {'compatible': b'apple,t8140-asc-mailbox\0apple,asc-mailbox-v4\0',
                  'reg': reg(asc_resource[0] + 0x8000, 0x4000),
                  'interrupt-parent': cells(aic),
                  'interrupts': b''.join(cells(0, irq, 4) for irq in linux_irqs),
                  'interrupt-names': b'send-empty\0send-not-empty\0recv-empty\0recv-not-empty\0',
                  '#mbox-cells': cells(0), 'phandle': cells(mailbox_phandle),
                  'power-domains': cells(gfx_phandle), 'status': b'disabled\0'})
    fdt.pack()
    resource_only = bytes(fdt.as_bytearray())
    if node_properties(resource_only) != expected:
        raise ValueError('Resource stage changed unrelated FDT metadata')
    result, aliases = bridge(resource_only, sgx, GPU)
    # The above selected chosen/firmware-version matches the existing loader
    # contract; it is not proof of a newly loaded GPU firmware text identity.
    # Core masks and usable reservation addresses need their live owners.
    return result, {'sgx': sgx_resource, 'asc': asc_resource,
                    'mailbox_irqs': linux_irqs, 'raw_property_count': len(aliases),
                    'existing_gfx_coordinate_owner': gfx,
                    'added_nodes': [GPU, MAILBOX] + ['/reserved-memory/gpu-' + n for n in REGIONS],
                    'firmware_version_property': 'chosen/firmware-version',
                    'revision_property': 'arm-io/chip-revision (raw LE to OF cell)',
                    'missing_live_loader_inputs': ['five reserved-memory reg extents and ownership',
                        'loaded GPU firmware text identity', 'live core masks',
                        'chip-fuse maximum-power provider', 'native uptime provider']}


def stage(adt, dtb, destination):
    destination = destination.resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(parents=True, exist_ok=False)
    tree, parser = original(adt)
    data, details = candidate(dtb.read_bytes(), tree)
    output = destination / 'native-disabled-resources.dtb'
    output.write_bytes(data)
    receipt = {'schema': 'm4rch.gravity-native-t6040.dt.stage.v7',
               'inputs': [pin(p) for p in [Path(__file__), KIT / 'native_adt_bridge_v7.py', parser, adt, dtb]],
               'output': pin(output), 'details': details, 'unrelated_properties_preserved': True,
               'raw_sgx_bytes_preserved': True, 'reservations_allocated': False,
               'firmware_build_from_chosen_used': True, 'normal_startup_enabled': False,
               'system_installed': False, 'hardware_actions': []}
    (destination / 'dt-stage-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adt', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    report = stage(args.adt.resolve(), args.dtb.resolve(), args.destination)
    print(json.dumps({'output': report['output'], 'details': report['details']}))
