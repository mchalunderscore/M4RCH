#!/usr/bin/env python3
"""Read-only capture after the single CPU4 idle diagnostic; no workload."""
import argparse
import json
import os
from pathlib import Path
import platform
import struct
import subprocess

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return {'unavailable': str(error)}


def kernel_build_id():
    data = Path('/sys/kernel/notes').read_bytes()
    offset = 0
    while offset + 12 <= len(data):
        namesz, descsz, kind = struct.unpack_from('<III', data, offset)
        offset += 12
        name = data[offset:offset + namesz]
        offset += (namesz + 3) & ~3
        desc = data[offset:offset + descsz]
        offset += (descsz + 3) & ~3
        if name == b'GNU\0' and kind == 3:
            return desc.hex()
    raise ValueError('Kernel build ID absent')


def states():
    return {str(p): read(p) for p in sorted(Path('/sys/devices/system/cpu').glob(
        'cpu[0-9]*/cpuidle/state*/*')) if p.name in
        ('name', 'desc', 'usage', 'time', 'disable', 'rejected')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    output = parser.parse_args().output
    receipt = json.loads((Path(__file__).resolve().parent / 'build.json').read_text())
    if platform.machine() != 'aarch64' or kernel_build_id() != receipt['build_id']:
        raise ValueError('Not the exact CPU4 trace kernel')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if not {b'apple,t6040', b'apple,j614s'} <= set(compatible):
        raise ValueError('Not the intended board')
    if Path('/sys/module/m4rch_pmu_fixed').exists():
        raise ValueError('Fixed-counter helper must remain unloaded')
    parameters = {name: read('/sys/module/cpuidle_apple/parameters/' + name)
                  for name in ('experimental_t6040_idle', 'experimental_t6040_idle_trace')}
    if any(value not in ('Y', '1') for value in parameters.values()):
        raise ValueError(f'Trace parameters absent: {parameters}')
    output.mkdir(parents=True, exist_ok=False)
    data = {'build_id': kernel_build_id(), 'cmdline': read('/proc/cmdline'),
            'parameters': parameters, 'online': read('/sys/devices/system/cpu/online'),
            'driver': read('/sys/devices/system/cpu/cpuidle/current_driver'), 'states': states()}
    (output / 'identity-and-states.json').write_text(json.dumps(data, indent=2) + '\n')
    result = subprocess.run(['journalctl', '-b', '-k', '--no-pager'],
                            capture_output=True, text=True, timeout=30)
    journal = result.stdout + result.stderr
    (output / 'kernel-journal.txt').write_text(journal)
    (output / 'trace-lines.txt').write_text('\n'.join(line for line in journal.splitlines()
        if 'M4RCH_IDLE' in line or 'M4RCH_FAULT' in line) + '\n')
    os.sync()
    if result.returncode: raise ValueError('Journal collection failed; saved partial capture')
    print(output)

if __name__ == '__main__':
    main()
