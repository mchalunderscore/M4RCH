#!/usr/bin/env python3
"""Preserve original SGX ADT inputs in an offline native GPU FDT candidate.

Only the apple,sgx- namespace is changed. Resource addresses, compatibility,
interrupts, power domains, reservations and board metadata retain their owners.
The result is an actual DTB for the selected driver's raw OF property readers;
the source ADT is a saved input, never a register or reserved-memory sampler.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import libfdt

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
SGX_ADT_PATH = '/device-tree/arm-io/sgx'
RAW_PREFIX = 'apple,sgx-'


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def properties(fdt, offset):
    result = {}
    current = fdt.first_property_offset(offset, quiet=(libfdt.NOTFOUND,))
    while current >= 0:
        prop = fdt.get_property_by_offset(current)
        if prop.name in result:
            raise ValueError('Duplicate FDT property: ' + prop.name)
        result[prop.name] = bytes(prop)
        current = fdt.next_property_offset(current, quiet=(libfdt.NOTFOUND,))
    return result


def node_properties(raw):
    """Semantic FDT contents, including every unchanged node and property."""
    fdt = libfdt.Fdt(raw)
    result = {}
    offset, depth = -1, 0
    while True:
        offset, depth = fdt.next_node(offset, depth)
        if offset < 0:
            break
        path = fdt.get_path(offset)
        result[path] = properties(fdt, offset)
    return result


def raw_inputs(sgx):
    """Byte-preserving namespace; even zero-length ADT presence is retained.

    Native producer code owns the type/extent and optional-property semantics.
    Exporting bytes does not reinterpret address-bearing ADT properties as OF
    resources or convert little-endian words into OF big-endian cells.
    """
    result = {}
    for name, value in sgx.items():
        if not re.fullmatch(r'[A-Za-z0-9,._+?#-]{1,128}', name):
            raise ValueError('Invalid SGX ADT property name')
        if not isinstance(value, bytes) or len(value) > 65536:
            raise ValueError('Invalid SGX ADT property bytes: ' + name)
        result[RAW_PREFIX + name] = value
    if not result:
        raise ValueError('Original SGX ADT properties are absent')
    return result


def bridge(raw_fdt, sgx, gpu_path):
    before = node_properties(raw_fdt)
    compatible = before.get('/', {}).get('compatible', b'').split(b'\0')
    if b'apple,j614s' not in compatible or b'apple,t6040' not in compatible:
        raise ValueError('Saved J614s/T6040 FDT required')
    gpu = before.get(gpu_path)
    if gpu is None or b'apple,agx-t6040' not in gpu.get('compatible', b'').split(b'\0'):
        raise ValueError('Selected native T6040 GPU FDT node required')
    selected = raw_inputs(sgx)
    fdt = libfdt.Fdt(raw_fdt)
    fdt.resize(fdt.totalsize() + sum(len(k) + len(v) + 32 for k, v in selected.items()) + 4096)
    # Delete old raw aliases first: an absent native optional property must
    # remain absent, not inherit a stale loader value or modeled default.
    for name in gpu:
        if name.startswith(RAW_PREFIX):
            fdt.delprop(fdt.path_offset(gpu_path), name)
    for name, value in selected.items():
        fdt.setprop(fdt.path_offset(gpu_path), name, value)
    fdt.pack()
    out = bytes(fdt.as_bytearray())
    after = node_properties(out)
    expected = {path: dict(props) for path, props in before.items()}
    expected[gpu_path] = {name: value for name, value in gpu.items()
                          if not name.startswith(RAW_PREFIX)} | selected
    if after != expected:
        raise ValueError('Raw input bridge changed another FDT field')
    return out, selected


def stage(adt, dtb, gpu_path, destination):
    destination = destination.resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(parents=True, exist_ok=False)
    parser_path = ROOT / 'experiments/t6040-gpu/adt.py'
    spec = importlib.util.spec_from_file_location('native_v7_original_adt', parser_path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    source = parser.parse(adt.read_bytes())
    if SGX_ADT_PATH not in source:
        raise ValueError('Saved ADT SGX node absent')
    result, fields = bridge(dtb.read_bytes(), source[SGX_ADT_PATH], gpu_path)
    output = destination / 'native-inputs.dtb'
    output.write_bytes(result)
    report = {
        'schema': 'm4rch.gravity-native-t6040.original-adt-bridge.v7',
        'inputs': [pin(path) for path in [Path(__file__), parser_path, adt, dtb]],
        'output': pin(output), 'gpu_path': gpu_path,
        'adt_source_path': SGX_ADT_PATH,
        'raw_property_pins': [{'adt_name': name[len(RAW_PREFIX):], 'of_name': name,
                               'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                              for name, value in sorted(fields.items())],
        'property_count': len(fields), 'raw_bytes_preserved': True,
        'absent_optional_properties_preserved': True,
        'other_FDT_fields_unchanged': True, 'system_installed': False,
        'bootloader_runtime_bridge_installed': False, 'hardware_actions': [],
        'qualification': 'Actual offline DTB raw properties are the original saved SGX ADT bytes. The selected Rust native constructor consumes these aliases. This does not supply missing core masks, revision or mapping/lifetime ownership, and does not claim the live bootloader will export new raw inputs until the resulting candidate is installed or the runtime loader hook is implemented.'}
    (destination / 'bridge-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adt', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--gpu-path', required=True)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    report = stage(args.adt.resolve(), args.dtb.resolve(), args.gpu_path, args.destination)
    print(json.dumps({'output': report['output'], 'raw_properties': report['property_count']}))
