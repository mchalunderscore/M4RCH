#!/usr/bin/env python3
"""Bounded fixed-key reads with hwmon/policies; no workload or control writes."""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

KEY_SIZES = dict.fromkeys(('Te05', 'Te0S', 'Tp01', 'Tp0Y', 'Tp0b', 'Tp0e',
                          'F0Ac', 'F1Ac', 'F0Tg', 'F1Tg'), 4)
KEY_SIZES.update(F0Md=1, F1Md=1)
RECORD = re.compile(r'(\d+) (\w{4}) info=(-?\d+) size=(\d+) '
                    r'type=([0-9a-f]{8}) flags=([0-9a-f]{2}) '
                    r'read=(-?\d+) raw=([0-9a-f]*)')


def validate_records(raw):
    """cat success alone does not imply that individual SMC reads succeeded."""
    seen = set()
    previous = -1
    for line in raw.splitlines():
        match = RECORD.fullmatch(line)
        if match is None:
            raise ValueError('Malformed SMC record')
        stamp, key, status, size, kind, flags, read, data = match.groups()
        if key not in KEY_SIZES or key in seen:
            raise ValueError('Unexpected or duplicate SMC key: ' + key)
        seen.add(key)
        expected = KEY_SIZES[key]
        expected_type = '75693820' if expected == 1 else '666c7420'
        if (int(status) < 0 or int(size) != expected or int(read) != expected
                or len(data) != expected * 2 or kind != expected_type):
            raise ValueError('Failed, short or unexpected-type SMC read: ' + key)
        if int(stamp) < previous:
            raise ValueError('Nonmonotonic SMC record timestamps')
        previous = int(stamp)
    if seen != set(KEY_SIZES):
        raise ValueError('Missing SMC records: ' + ','.join(sorted(set(KEY_SIZES) - seen)))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--samples', type=int, choices=(30, 720), default=30)
    return parser.parse_args(argv)


def policy_snapshot():
    policies = {}
    for device in Path('/sys/devices/system/cpu/cpufreq').glob('policy*'):
        values = {}
        for name in ('related_cpus', 'scaling_cur_freq', 'cpuinfo_cur_freq',
                     'scaling_governor', 'scaling_min_freq', 'scaling_max_freq'):
            try:
                values[name] = (device/name).read_text().strip()
            except OSError as exc:
                values[name] = {'error': str(exc)}
        policies[device.name] = values
    return policies


def main():
    args = parse_args()
    out = args.output
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    started = time.monotonic()
    with (out / 'samples.jsonl').open('x') as stream:
        for index in range(args.samples):
            if time.monotonic() - started > args.samples + 10:
                stream.write(json.dumps({'validation_error': 'Capture duration bound exceeded'})+'\n')
                stream.flush()
                raise SystemExit('Duration bound exceeded; capture preserved')
            try:
                result = subprocess.run(
                    ['cat', '/sys/kernel/debug/m4rch-smc-readonly/keys'],
                    capture_output=True, text=True, timeout=5)
                row = {'utc': datetime.now(timezone.utc).isoformat(),
                       'raw_status': result.returncode, 'raw': result.stdout,
                       'stderr': result.stderr, 'hwmon': {},
                       'monotonic': time.monotonic(), 'sample': index,
                       'policies': policy_snapshot()}
                failure = None
                try:
                    if result.returncode:
                        raise ValueError('SMC cat failed')
                    validate_records(result.stdout)
                except ValueError as exc:
                    failure = str(exc)
                    row['validation_error'] = failure
            except subprocess.TimeoutExpired as exc:
                row = {'utc': datetime.now(timezone.utc).isoformat(),
                       'raw': (exc.stdout or b'').decode(errors='replace'),
                       'validation_error': 'SMC cat timed out'}
                failure = row['validation_error']
            if failure is None:
                for device in Path('/sys/class/hwmon').glob('hwmon*'):
                    try:
                        if (device / 'name').read_text().strip() != 'macsmc_hwmon':
                            continue
                        for item in device.iterdir():
                            if item.name.endswith(('_input', '_target', '_label')):
                                try:
                                    row['hwmon'][item.name] = item.read_text().strip()
                                except OSError as exc:
                                    row['hwmon'][item.name] = {'error': str(exc)}
                    except OSError as exc:
                        row.setdefault('hwmon_errors', []).append(str(exc))
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            if failure is not None:
                raise SystemExit(failure + '; capture preserved')
            if index + 1 < args.samples:
                time.sleep(max(0, started + index + 1 - time.monotonic()))
    print(out)


if __name__ == '__main__':
    main()
