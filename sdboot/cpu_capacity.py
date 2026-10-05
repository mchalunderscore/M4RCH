#!/usr/bin/env python3
"""Provisional capacity-overlay validation and read-only native acceptance."""
from pathlib import Path
import argparse
import json
import struct

E_PATHS = tuple('/cpus/cpu@' + str(n) for n in range(4))
P_PATHS = tuple('/cpus/cpu@' + format(n, 'x') for n in
                (*range(0x10100, 0x10104), *range(0x10200, 0x10204)))
DT_VALUES = {'E': 864, 'P': 1024}
MAX_KHZ = {'E': 2592000, 'P': 4512000}
NORMALIZED = {'E': (864 * 2592000 * 1024) // (1024 * 4512000), 'P': 1024}


def check_nodes(nodes):
    """Check all twelve CPU paths established on this specific J614s."""
    values = {}
    for cls, paths, compatible in (('E', E_PATHS, b'apple,sawtooth'),
                                    ('P', P_PATHS, b'apple,everest')):
        for path in paths:
            node = nodes.get(path, {})
            if compatible not in node.get('compatible', b'').split(b'\0'):
                raise ValueError('Capacity target has missing/wrong CPU class: ' + path)
            if node.get('capacity-dmips-mhz') != struct.pack('>I', DT_VALUES[cls]):
                raise ValueError('Missing/wrong provisional capacity: ' + path)
            values[path] = DT_VALUES[cls]
    return {'provisional': True, 'dt_values': values, 'expected_normalized': NORMALIZED}


def verify(sysfs=Path('/sys')):
    rows, errors = [], []
    root = Path(sysfs) / 'devices/system/cpu'
    cpus = sorted((p for p in root.glob('cpu[0-9]*') if p.name[3:].isdigit()),
                  key=lambda p: int(p.name[3:]))
    for cpu in cpus:
        try:
            midr = int((cpu / 'regs/identification/midr_el1').read_text().strip(), 0)
            cls = {0x54: 'E', 0x55: 'P'}[(midr >> 4) & 0xfff]
            raw = (cpu / 'of_node/capacity-dmips-mhz').read_bytes()
            if len(raw) != 4:
                raise ValueError('Malformed capacity cell')
            dt = int.from_bytes(raw, 'big')
            capacity = int((cpu / 'cpu_capacity').read_text())
            maximum = int((cpu / 'cpufreq/cpuinfo_max_freq').read_text())
            if dt != DT_VALUES[cls] or capacity != NORMALIZED[cls] or maximum != MAX_KHZ[cls]:
                errors.append(cpu.name + ': DT/runtime/frequency acceptance mismatch')
            rows.append({'cpu': int(cpu.name[3:]), 'class': cls, 'dt': dt,
                         'capacity': capacity, 'maximum_khz': maximum})
        except (OSError, ValueError, KeyError) as exc:
            errors.append(cpu.name + ': missing/unrecognized evidence: ' + str(exc))
    if len(rows) != 12 or sum(r['class'] == 'P' for r in rows) != 8 or sum(r['class'] == 'E' for r in rows) != 4:
        errors.append('Expected all twelve CPUs: eight P and four E')
    return {'pass': not errors, 'provisional': True, 'cpus': rows, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sys-root', type=Path, default=Path('/sys'))
    args = parser.parse_args()
    report = verify(args.sys_root)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['pass'] else 1)


if __name__ == '__main__':
    main()
