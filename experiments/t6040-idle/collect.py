#!/usr/bin/env python3
"""Collect first idle-trial evidence; no policy/register writes or PMU module."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import time


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


def arithmetic():
    # Dyadic inputs and exact operations avoid cross-libm rounding differences.
    data = b''.join(struct.pack('<d', (i / 128.0) ** 2 + 0.5)
                    for i in range(256))
    return hashlib.sha256(data).hexdigest()


def wake_task(cpu, expected):
    os.sched_setaffinity(0, {cpu})  # This worker only; not CPU hotplug.
    for _ in range(40):
        if arithmetic() != expected or os.sched_getaffinity(0) != {cpu}:
            raise ValueError(f'Task-integrity or affinity failure on CPU {cpu}')
        time.sleep(0.05)
    return {'cpu': cpu, 'arithmetic_passed': True, 'sleep_wake_cycles': 40}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    kit = Path(__file__).resolve().parent
    receipt = json.loads((kit / 'build.json').read_text())
    if platform.machine() != 'aarch64' or kernel_build_id() != receipt['build_id']:
        raise ValueError('Not the exact idle-trial kernel')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if not {b'apple,t6040', b'apple,j614s'} <= set(compatible):
        raise ValueError('Not the intended J614s/T6040 board')
    if Path('/sys/module/m4rch_pmu_fixed').exists():
        raise ValueError('Unload the fixed-counter probe before any idle observation')
    parameter = read('/sys/module/cpuidle_apple/parameters/experimental_t6040_idle')
    if parameter not in ('Y', '1'):
        raise ValueError(f'Idle opt-in is not active: {parameter}')
    driver = read('/sys/devices/system/cpu/cpuidle/current_driver')
    if driver != 'apple_idle':
        raise ValueError(f'Expected apple_idle, got {driver}')
    args.output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        with (args.output / name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    save('identity.json', {'build_id': kernel_build_id(), 'cmdline': read('/proc/cmdline'),
                          'driver': driver, 'parameter': parameter,
                          'online': read('/sys/devices/system/cpu/online')})
    save('states-before.json', states())
    # Low duty-cycle, pinned user tasks exercise ordinary timer wakeups on each
    # currently allowed CPU. This is a smoke test, not exhaustive SIMD/debug proof.
    cpus = sorted(os.sched_getaffinity(0))
    expected = arithmetic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(cpus)) as workers:
        results = list(workers.map(lambda cpu: wake_task(cpu, expected), cpus))
    save('wake-tasks.json', results)
    time.sleep(10)
    save('states-after.json', states())
    result = subprocess.run(['journalctl', '-b', '-k', '--no-pager'],
                            capture_output=True, text=True, timeout=20)
    (args.output / 'kernel-journal.txt').write_text(result.stdout + result.stderr)
    save('complete.json', {'complete': True, 'journal_exit': result.returncode,
                          'limitation': 'Short user arithmetic and timer wake smoke; not full FP/SIMD, debug, retention or boost qualification.'})
    print(args.output)


if __name__ == '__main__':
    main()
