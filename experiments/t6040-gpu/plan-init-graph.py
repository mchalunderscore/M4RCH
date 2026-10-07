#!/usr/bin/env python3
"""Produce an offline G16S object packing plan, never firmware bytes or mappings.

Offsets are relative to a future allocation arena, not GPU virtual addresses.
Each object receives independent 16 KiB pages to avoid inherited donor aliases.
A minimum extent is not a qualified complete allocation size.
"""
import argparse
import json
from pathlib import Path

PAGE = 0x4000
# size, evidence status. Source: standalone ABI plus hash-pinned firmware audit.
SPECS = [
    ('root', 0xc8, 'firmware-copy'),
    ('main', 0x500, 'candidate-envelope'),
    ('hardware', 0x3db4, 'donor-envelope-only'),
    ('region_c', 0xe55, 'firmware-access-minimum'),
    ('extra_root', 0x6a8, 'document'),
    ('main_header', 0x88, 'document'),
    ('shared_0', 0xc18, 'document'),
    ('shared_1', 0x1048, 'document'),
    ('shared_2', 0xe10, 'document'),
    ('shared_3', 0x68, 'document'),
    ('shared_4', 0x800, 'document'),
    ('hardware_counters', 0xe40, 'document-extent-firmware-pointer'),
    ('power', 0x6564, 'firmware-access-minimum'),
    ('region_a', 0x14, 'firmware-access-minimum'),
    ('status_a', 0x20, 'firmware-access-minimum'),
    ('status_b', 0x48f8, 'firmware-access-minimum'),
    ('extra_root_1', None, 'firmware-root-pointer-target-extent-unknown'),
]
EDGES = [('root', 0x08, 'region_a'), ('root', 0xa8, 'status_a'),
         ('root', 0xb0, 'status_b'), ('root', 0xc0, 'extra_root_1'),
         ('root', 0x18, 'main'), ('root', 0x20, 'region_c'),
         ('root', 0xb8, 'extra_root'), ('main', 0, 'hardware'),
         ('main', 0x10, 'main_header'), ('main', 0x471, 'power'),
         ('hardware', 0x26b8, 'hardware_counters')]
EDGES += [('main', 0x254 + i * 8, 'shared_' + str(i)) for i in range(5)]


def plan():
    objects = []
    cursor = 0
    for name, extent, evidence in SPECS:
        reservation = (extent + PAGE - 1) // PAGE * PAGE if extent is not None else 0
        objects.append(dict(name=name, arena_offset=cursor if extent is not None else None, extent=extent,
                            reserved_bytes=reservation, evidence=evidence))
        cursor += reservation
    by_name = {o['name']: o for o in objects}
    for parent, offset, target in EDGES:
        assert offset + 8 <= by_name[parent]['extent']
        assert target in by_name
    allocated = [o for o in objects if o['arena_offset'] is not None]
    for left, right in zip(allocated, allocated[1:]):
        assert left['arena_offset'] + left['reserved_bytes'] <= right['arena_offset']
    return dict(page_bytes=PAGE, arena_bytes=cursor, objects=objects,
                pointers=[dict(parent=p, byte_offset=o, target=t, width=8)
                          for p, o, t in EDGES],
                topology=dict(chip='T6040', board='J614s', gpu_cores=16,
                              cluster_masks=['0x3db', '0x3db']),
                publishable=False,
                unresolved=[
                    'Complete main layout, including extra field+240 and 17 channel records',
                    'Full hardware layout and T6040 register descriptors/two-cluster voltage inputs',
                    'Region C complete extent, initialization values and host/firmware ownership',
                    'Power object complete extent and initialization values',
                    'Complete region A/status extents and contents; root+c0 target extent unknown',
                    'Nested shared-object contents and transitive pointers',
                    'Actual arena GPU VA bounds/collisions, physical backing, PTE permissions',
                    'Cache publication, RTKit failure paths and mapping lifetime/teardown'],
                native_preflight_coverage=dict(object_pages=18, expanded_plan_tested=False,
                    note='Latest native preflight covers18 marker pages; new power minimum increases candidate with unknown-target marker to19 pages. No firmware object reads established.'),
                qualification='Independent-page sizing plan only; unknown-size objects receive no reservation. No memory allocation, GPU addresses, firmware serialization or publication. Padding is not evidence of complete object extents.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = plan()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"{len(result['objects'])} objects, {len(result['pointers'])} pointer edges, {result['arena_bytes']} bytes provisional backing; publication blocked")
