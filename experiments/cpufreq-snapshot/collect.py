#!/usr/bin/env python3
"""Read driver-owned DVFS snapshots; optionally bracket two accepted PMU probes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path('/sys/kernel/debug/m4rch-cpufreq')


def uint(value, bits=64):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError('Invalid unsigned integer')
    return value


def hexint(value, bits):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-f]+', value):
        raise ValueError('Invalid raw hex value')
    return uint(int(value, 16), bits)


def cpus(text):
    result = []
    for field in text.split(','):
        if not re.fullmatch(r'[0-9]+(?:-[0-9]+)?', field):
            raise ValueError('Malformed CPU membership')
        ends = [int(x) for x in field.split('-')]
        first, last = ends[0], ends[-1]
        if not 0 <= first <= last < 256:
            raise ValueError('Out-of-range CPU membership')
        result.extend(range(first, last + 1))
    if len(result) != len(set(result)):
        raise ValueError('Duplicate CPU membership')
    return result


def analyze(raw):
    d = json.loads(raw)
    if type(d['schema']) is not int or d['schema'] != 1 or d['atomic'] is not False:
        raise ValueError('Unsupported or falsely atomic snapshot')
    uint(d['policy_cpu'], 32)
    uint(d['max_pstate'], 32)
    if type(d['has_ps2']) is not bool:
        raise ValueError('Malformed PS2 capability')
    members = cpus(d['init_cpus'])
    if d['policy_cpu'] not in members:
        raise ValueError('Policy representative outside initial membership')
    if d['compatible'] not in ('apple,t8112-cluster-cpufreq',
            'apple,t8103-cluster-cpufreq', 'apple,s5l8960x-cluster-cpufreq',
            'apple,cluster-cpufreq'):
        raise ValueError('Unknown selected driver compatible')
    opps = {}
    for p in d['opps']:
        state, freq = uint(p['state'], 32), uint(p['frequency_khz'], 32)
        uint(p['flags'], 32)
        if state in opps or not freq:
            raise ValueError('Duplicate state or zero-frequency OPP')
        opps[state] = freq
    if not opps:
        raise ValueError('Missing OPP mapping')
    c, s = d['command'], d['status']
    if (c['offset'], c['width'], s['offset'], s['width']) != (32, 64, 80, 32):
        raise ValueError('Unexpected register aperture')
    cmd, mask = hexint(c['raw'], 64), hexint(c['mask'], 64)
    uint(c['state'], 32)
    uint(c['frequency_khz'], 32)
    uint(d['get_rate_state'], 32)
    uint(d['get_rate_khz'], 32)
    shift = uint(c['shift'], 6)
    if c['state'] != (cmd & mask) >> shift:
        raise ValueError('Command decode does not match raw value')
    if c['frequency_khz'] != opps.get(c['state'], 0):
        raise ValueError('Command frequency does not match OPP level')
    if c['busy'] is not bool(cmd & (1 << 31)) or c['set'] is not bool(cmd & (1 << 25)):
        raise ValueError('Command flags do not match raw value')
    times = [uint(c['begin_ns']), uint(c['end_ns'])]
    status = hexint(s['raw'], 32)
    status_mask = hexint(s['mask'], 32)
    status_shift = uint(s['shift'], 5)
    if s['available'] is True:
        if not status_mask:
            raise ValueError('Status present without reviewed decode mask')
        get_state = (status & status_mask) >> status_shift
        times += [uint(s['begin_ns']), uint(s['end_ns'])]
    elif s['available'] is False:
        if status_mask or status or s['begin_ns'] or s['end_ns']:
            raise ValueError('Fallback claims an unread status value')
        get_state = cmd & 31
    else:
        raise ValueError('Malformed status availability')
    times += [uint(d['policy_begin_ns']), uint(d['policy_end_ns'])]
    if times != sorted(times):
        raise ValueError('Timestamp ordering invalid')
    uint(d['policy_cur_khz'], 32)
    if d['get_rate_state'] != get_state or d['get_rate_khz'] != opps.get(get_state, 0):
        raise ValueError('Get-rate decode does not match raw state/OPP map')
    return {'command_khz': c['frequency_khz'], 'get_rate_khz': d['get_rate_khz'],
            'command_state': c['state'], 'get_rate_state': get_state,
            'mapping_missing': c['state'] not in opps or get_state not in opps,
            'busy': c['busy'], 'span_ns': times[-1] - times[0]}


def read_snapshot(path):
    start = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    try:
        r = subprocess.run(['cat', str(path)], capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired as exc:
        return {'read_begin_ns': start,
                'read_end_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                'raw': (exc.stdout or b'').decode(errors='replace'),
                'error': 'debugfs read timeout; stop and preserve evidence'}
    record = {'read_begin_ns': start,
              'read_end_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME),
              'raw': r.stdout, 'stderr': r.stderr, 'returncode': r.returncode}
    if r.returncode:
        record['error'] = 'debugfs read failed'
    else:
        try:
            record['analysis'] = analyze(r.stdout)
        except (ValueError, KeyError, TypeError) as exc:
            record['error'] = str(exc)
    return record


def unload_probe(output):
    report = {'boottime_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME)}
    try:
        result = subprocess.run(['rmmod', 'm4rch_pmu_fixed'], capture_output=True,
                                text=True, timeout=10)
        report.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except subprocess.TimeoutExpired:
        report['error'] = 'Unload timeout; investigate before any further trial'
    report['module_present'] = Path('/sys/module/m4rch_pmu_fixed').exists()
    with (output/'cleanup.jsonl').open('a') as f:
        f.write(json.dumps(report)+'\n')
    if report.get('returncode') != 0 or report['module_present']:
        raise RuntimeError('PMU cleanup failed; no automatic retry, preserve evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, choices=(5, 60), default=60)
    parser.add_argument('--probe-on-boost', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo')
    kit = Path(__file__).resolve().parent
    subprocess.run(['python3', str(kit/'verify.py')], check=True)
    paths = sorted(ROOT.glob('policy*/snapshot'))
    if len(paths) != 3:
        raise SystemExit('Expected three driver-owned policy snapshots; do not force probes')
    args.output.mkdir(mode=0o700, exist_ok=False)
    (args.output/'context.json').write_text(json.dumps({
        'samples_requested': args.samples, 'probe_on_boost': args.probe_on_boost,
        'policy_paths': [str(p) for p in paths],
        'limit': 'Successive driver reads; no control writes or injected workload. '
                 'Optional fixed-counter loops have overhead and are not sustained/task clocks.'}, indent=2)+'\n')
    pmu = None
    if args.probe_on_boost:
        subprocess.run(['python3', str(kit/'pmu/verify.py')], check=True)
        if Path('/sys/module/m4rch_pmu_fixed').exists():
            raise SystemExit('PMU probe already loaded; investigate ownership')
        allowed = {'software', 'breakpoint', 'tracepoint', 'kprobe', 'uprobe'}
        if any(p.name not in allowed for p in Path('/sys/bus/event_source/devices').iterdir()):
            raise SystemExit('Unexpected PMU event source; do not override ownership guard')
        spec = importlib.util.spec_from_file_location('fixed_counter', kit/'pmu/collect.py')
        pmu = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pmu)
    cancelled = False
    def cancel(signum, frame):
        nonlocal cancelled
        cancelled = True
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, cancel)
    loaded = False
    probes = []
    started = time.monotonic()
    try:
        with (args.output/'snapshots.jsonl').open('x') as f:
            for n in range(args.samples):
                if cancelled:
                    raise RuntimeError('Capture interrupted; cleanup requested')
                if time.monotonic() - started > args.samples + 15:
                    raise RuntimeError('Capture exceeded soft duration bound')
                tick = time.monotonic()
                row = {'sample': n, 'policies': {}}
                for path in paths:
                    record = read_snapshot(path)
                    row['policies'][path.parent.name] = record
                    f.write(json.dumps({'sample': n, 'policy': path.parent.name, **record})+'\n')
                    f.flush()
                    if 'error' in record:
                        raise RuntimeError('Malformed/failed snapshot; raw evidence preserved')
                    # One probe per P cluster, only after observing a high command.
                    data = json.loads(record['raw'])
                    cpu = next((x for x in (0, 8) if x in cpus(data['init_cpus'])), None)
                    if cancelled:
                        raise RuntimeError('Capture interrupted; cleanup requested')
                    if pmu is None or cpu is None or cpu in probes:
                        continue
                    if record['analysis']['command_khz'] < 4400000 or record['analysis']['busy']:
                        continue
                    probes.append(cpu)
                    subprocess.run(['insmod', str(kit/'pmu/m4rch_pmu_fixed.ko'), f'cpu={cpu}'], check=True)
                    loaded = True
                    # Loading itself can change load; take a NEW bracket after load.
                    before = read_snapshot(path)
                    event = {'cpu': cpu, 'before': before}
                    (args.output/f'probe-cpu{cpu}.json').write_text(json.dumps(event, indent=2)+'\n')
                    if 'error' in before:
                        raise RuntimeError('Pre-probe snapshot failed')
                    if before['analysis']['command_khz'] >= 4400000 and not before['analysis']['busy']:
                        event['counter_begin_ns'] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        try:
                            result = subprocess.run(['cat', '/sys/kernel/debug/m4rch-pmu-fixed/sample'],
                                                    capture_output=True, text=True, timeout=5)
                        except subprocess.TimeoutExpired as exc:
                            event['raw'] = (exc.stdout or b'').decode(errors='replace')
                            event['error'] = 'Counter read timeout; no further trials'
                            event['counter_end_ns'] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                            (args.output/f'probe-cpu{cpu}.json').write_text(json.dumps(event, indent=2)+'\n')
                            raise RuntimeError(event['error']) from exc
                        event['counter_end_ns'] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        event['raw'] = result.stdout
                        event['stderr'] = result.stderr
                        event['returncode'] = result.returncode
                        event['after'] = read_snapshot(path)
                        (args.output/f'probe-cpu{cpu}.json').write_text(json.dumps(event, indent=2)+'\n')
                        if result.returncode or 'error' in event['after']:
                            raise RuntimeError('Probe or post-probe snapshot failed')
                        event['analysis'] = pmu.analyze(result.stdout, cpu)
                    else:
                        event['skipped'] = 'High command no longer present after module load'
                    (args.output/f'probe-cpu{cpu}.json').write_text(json.dumps(event, indent=2)+'\n')
                    loaded = False
                    unload_probe(args.output)
                time.sleep(max(0, 1 - (time.monotonic() - tick)))
    finally:
        if loaded:
            loaded = False
            unload_probe(args.output)
    (args.output/'complete.json').write_text(json.dumps({'complete': True,
        'elapsed_seconds': time.monotonic()-started, 'probe_cpus_attempted': probes})+'\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
