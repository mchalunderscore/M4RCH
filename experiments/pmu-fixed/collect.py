#!/usr/bin/env python3
"""Capture one explicit fixed-counter trial; no load, affinity or boot changes."""
import argparse
import json
import re
import subprocess
from pathlib import Path

HEADER = re.compile(r'cpu=(\d+) midr=([0-9a-f]{8}) status=(-?\d+) timer_hz=(\d+) '
                    r'pmcr0=([0-9a-f]{16}) pmcr1=([0-9a-f]{16}) '
                    r'final0=([0-9a-f]{16}) final1=([0-9a-f]{16})')
ROW = re.compile(r'loops=(\d+) cycles=(\d+) instructions=(\d+) ticks=(\d+)')


def analyze(raw, expected_cpu):
    lines = raw.splitlines()
    header = HEADER.fullmatch(lines[0]) if lines else None
    if header is None:
        raise ValueError('Malformed trial header')
    cpu, midr, status, rate, control0, control1, final0, final1 = header.groups()
    if int(cpu) != expected_cpu:
        raise ValueError('Unexpected CPU')
    if int(status) != 0:
        raise ValueError('Kernel refused or failed trial: ' + status)
    if control0 != final0 or control1 != final1:
        raise ValueError('PMU control restoration failed')
    if int(rate) <= 0 or len(lines) != 4:
        raise ValueError('Incomplete trial or missing timer rate')
    samples = []
    for line, expected in zip(lines[1:], (256, 4096, 65536)):
        row = ROW.fullmatch(line)
        if row is None:
            raise ValueError('Malformed count row')
        loops, cycles, instructions, ticks = map(int, row.groups())
        if loops != expected or min(cycles, instructions, ticks) <= 0:
            raise ValueError('Missing or non-advancing fixed counters')
        if instructions < 3 * loops or instructions > 3 * loops + 512:
            raise ValueError('Retired count inconsistent with known three-instruction loop')
        if ticks * 500 > int(rate):
            raise ValueError('Tiny trial exceeded two milliseconds')
        samples.append({'loops': loops, 'cycles': cycles, 'instructions': instructions,
                        'ticks': ticks, 'elapsed_ns': ticks * 1e9 / int(rate),
                        'cycles_per_second_estimate': cycles * int(rate) / ticks})
    return {'cpu': int(cpu), 'midr': midr, 'control_restored': True,
            'samples': samples,
            'limit': 'Short CPU-wide EL1 loops, including read/barrier overhead; '
                     'not a task perf event or sustained maximum clock measurement.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', required=True, type=int, choices=(0, 1, 8))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    policies = {}
    for policy in Path('/sys/devices/system/cpu/cpufreq').glob('policy*'):
        values = {}
        for name in ('related_cpus', 'scaling_driver', 'scaling_governor',
                     'scaling_cur_freq', 'cpuinfo_cur_freq', 'scaling_min_freq',
                     'scaling_max_freq'):
            try:
                values[name] = (policy/name).read_text().strip()
            except OSError as exc:
                values[name] = {'error': str(exc)}
        policies[policy.name] = values
    (args.output/'policies-before.json').write_text(json.dumps(policies, indent=2)+'\n')
    try:
        result = subprocess.run(['cat', '/sys/kernel/debug/m4rch-pmu-fixed/sample'],
                                capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired as exc:
        (args.output/'raw.txt').write_bytes(exc.stdout or b'')
        (args.output/'error.txt').write_text('debugfs read timed out\n')
        raise SystemExit('Read timed out; preserve capture, investigate before retrying')
    (args.output/'raw.txt').write_text(result.stdout)
    (args.output/'stderr.txt').write_text(result.stderr)
    try:
        if result.returncode:
            raise ValueError('debugfs read failed: ' + str(result.returncode))
        report = analyze(result.stdout, args.cpu)
    except ValueError as exc:
        (args.output/'error.txt').write_text(str(exc)+'\n')
        raise SystemExit(str(exc)+'; raw capture preserved')
    (args.output/'analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    print(args.output)


if __name__ == '__main__':
    main()
