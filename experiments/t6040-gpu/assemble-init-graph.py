#!/usr/bin/env python3
"""Assemble an OFFLINE candidate graph from explicit opaque object templates.

No device access, mappings, allocation, firmware publication or readiness claim.
Templates and unknown extents remain caller-supplied candidate inputs. Only the
pointer edges in plan-init-graph.py are relocated; transitive pointers are not
invented. Zero-filled templates are never supplied implicitly.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('graph_plan', Path(__file__).with_name('plan-init-graph.py'))
graph_plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_plan)


def assemble(templates, base):
    """Return bytes and a receipt after validating the entire candidate input."""
    plan = graph_plan.plan()
    names = {obj['name'] for obj in plan['objects']}
    if set(templates) != names:
        raise ValueError(f'template set differs: missing={sorted(names-set(templates))}, extra={sorted(set(templates)-names)}')
    if not isinstance(base, int) or base % graph_plan.PAGE:
        raise ValueError('base must be an integer aligned to16KiB')
    # Candidate high-half GPU VA window used by the existing root probe.
    # This range check does not establish that the window is actually free.
    if not 0xfffffc2000000000 <= base < 0xfffffc4000000000:
        raise ValueError('base outside candidate firmware allocation VA window')
    cursor = 0
    objects = []
    for obj in plan['objects']:
        data = templates[obj['name']]
        if not isinstance(data, bytes) or not data:
            raise ValueError(f'{obj["name"]}: require nonempty explicit bytes')
        minimum = obj['extent']
        if minimum is not None and len(data) < minimum:
            raise ValueError(f'{obj["name"]}: {len(data):x} bytes below provisional extent{minimum:x}')
        reservation = (len(data) + graph_plan.PAGE - 1) // graph_plan.PAGE * graph_plan.PAGE
        if base + cursor + reservation > 0xfffffc4000000000:
            raise ValueError('graph exceeds candidate allocation VA window')
        objects.append(dict(name=obj['name'], arena_offset=cursor,
                            gpu_va=hex(base + cursor), input_bytes=len(data),
                            reserved_bytes=reservation,
                            input_sha256=hashlib.sha256(data).hexdigest(),
                            layout_evidence=obj['evidence'],
                            complete_extent_qualified=False))
        cursor += reservation
    by_name = {obj['name']: obj for obj in objects}
    arena = bytearray(cursor)
    for obj in objects:
        start = obj['arena_offset']
        arena[start:start + obj['input_bytes']] = templates[obj['name']]
    edges = []
    spans = set()
    for edge in plan['pointers']:
        parent = by_name[edge['parent']]
        target = by_name[edge['target']]
        offset = edge['byte_offset']
        if offset < 0 or offset + 8 > parent['input_bytes']:
            raise ValueError('relocation lies outside supplied parent template')
        positions = {(parent['name'], i) for i in range(offset, offset + 8)}
        if spans & positions:
            raise ValueError('overlapping relocation fields')
        spans |= positions
        value = base + target['arena_offset']
        struct.pack_into('<Q', arena, parent['arena_offset'] + offset, value)
        edges.append(dict(edge, encoded_gpu_va=hex(value)))
    receipt = dict(publishable=False, device_access=False, base=hex(base),
                   arena_bytes=cursor, arena_sha256=hashlib.sha256(arena).hexdigest(),
                   objects=objects, pointers=edges, topology=plan['topology'],
                   unresolved=plan['unresolved'],
                   qualification='Offline pointer-relocated candidate only. Explicit templates are not evidence of correct object contents or full extents. No transitive-pointer validation, live VA collision check, mapping or publication performed.')
    return bytes(arena), receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path, help='JSON: base(integer or hex string), templates(object name to relative binary path)')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    base = manifest['base']
    if isinstance(base, str):
        base = int(base, 0)
    templates = {name: (args.manifest.parent / path).read_bytes()
                 for name, path in manifest['templates'].items()}
    arena, receipt = assemble(templates, base)
    # Require a fresh directory, so an invalid/new candidate cannot silently
    # overwrite a previously inspected pair of bytes and receipt.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'candidate-arena.bin').write_bytes(arena)
    (args.output_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{len(receipt["objects"])} explicit templates, {len(receipt["pointers"])} relocated edges; offline candidate only')


if __name__ == '__main__':
    main()
