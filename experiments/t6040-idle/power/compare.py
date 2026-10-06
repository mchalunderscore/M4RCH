#!/usr/bin/env python3
"""Same-boot ABBA saved-WFI comparison; no clock/fan/voltage changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PARAM = Path('/sys/module/cpuidle_apple/parameters')
SWITCH = PARAM / 'experimental_t6040_idle_continuous'

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return {'unavailable': str(error)}

def snapshot():
    patterns = ('/sys/class/power_supply/*/uevent',
                '/sys/class/hwmon/hwmon*/temp*_input',
                '/sys/class/hwmon/hwmon*/temp*_label',
                '/sys/class/hwmon/hwmon*/fan*_input',
                '/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq',
                '/sys/devices/system/cpu/cpufreq/policy*/scaling_governor',
                '/sys/devices/system/cpu/cpuidle/current_governor_ro',
                '/sys/devices/system/cpu/cpu*/cpuidle/state*/usage',
                '/sys/devices/system/cpu/cpu*/cpuidle/state*/time',
                '/sys/devices/system/cpu/cpu*/cpuidle/state*/rejected')
    data = {str(p): read(p) for pattern in patterns
            for p in sorted(Path('/').glob(pattern.lstrip('/')))}
    for p in ('/proc/stat', '/proc/loadavg',
              str(PARAM / 'experimental_t6040_idle_continuous_progress'), str(SWITCH)):
        data[p] = read(p)
    return {'monotonic': time.monotonic(), 'utc_epoch': time.time(), 'raw': data}

def journal():
    return subprocess.check_output(['journalctl', '-b', '-k', '-o',
                                    'short-monotonic', '--no-pager'], text=True, timeout=30)

def write_switch(enabled):
    SWITCH.write_text('1\n' if enabled else '0\n')
    if SWITCH.read_text().strip() not in (('Y', '1') if enabled else ('N', '0')):
        raise ValueError('Continuous switch readback failed')

def faults(before, after):
    delta = after[len(before):] if after.startswith(before) else '\n'.join(
        line for line in after.splitlines() if line not in set(before.splitlines()))
    return delta, bool(re.search(r'M4RCH_FAULT|BUG:|Oops:|Internal error:|CPU_PM_ENTER rejected', delta))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--settle', type=int, default=60)
    parser.add_argument('--seconds', type=int, default=180)
    args = parser.parse_args()
    if args.settle < 30 or args.seconds < 60:
        raise ValueError('Use at least 30 seconds settling and 60 seconds measuring')
    kit = Path(__file__).resolve().parent
    for line in (kit / 'SHA256SUMS').read_text().splitlines():
        h, name = line.split('  ', 1)
        if Path(name).name != name:
            raise ValueError('Unexpected kit path')
        p = kit / name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != h:
            raise ValueError('Kit hash mismatch: ' + name)
    sys.path.insert(0, str(kit))
    from collect_continuous import kernel_build_id
    BUILD = json.loads((kit / 'build.json').read_text())['build_id']
    if os.geteuid() != 0 or kernel_build_id() != BUILD:
        raise ValueError('Root on the exact continuous kernel required')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if not {b'apple,t6040', b'apple,j614s'} <= set(compatible):
        raise ValueError('Wrong board')
    if Path('/sys/module/m4rch_pmu_fixed').exists():
        raise ValueError('Keep PMU helper unloaded')
    for name in ('experimental_t6040_idle','experimental_t6040_idle_trace','experimental_t6040_idle_wfi_only'):
        if read(PARAM / name) not in ('Y', '1'):
            raise ValueError('Saved-WFI opt-in absent')
    if read(PARAM / 'experimental_t6040_idle_wfi_budget') != '0':
        raise ValueError('Bounded budget must stay zero')
    original = read(SWITCH)
    if original not in ('Y', '1'):
        raise ValueError('Start from the working enabled baseline')
    args.output.mkdir(parents=True, exist_ok=False)
    def save(name, data):
        p = args.output / name
        with p.open('x') as f:
            json.dump(data, f, indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    save('protocol.json', {'build_id': BUILD, 'order': ['enabled','disabled','disabled','enabled'],
                          'settle_seconds': args.settle, 'measurement_seconds': args.seconds,
                          'units': 'raw sysfs uevent values; power/current/voltage normally micro-units; validate provenance before conversion',
                          'scope': 'battery telemetry is whole-machine power, not CPU-only; no calibrated watt estimate inferred'})
    successful = False
    try:
        baseline = journal()
        (args.output / 'journal-start.txt').write_text(baseline)
        for phase, enabled in enumerate((True,False,False,True),1):
            write_switch(enabled)
            time.sleep(args.settle)
            samples=[]
            end=time.monotonic()+args.seconds
            while True:
                samples.append(snapshot())
                remaining=end-time.monotonic()
                if remaining<=0:break
                time.sleep(min(10,remaining))
            save(f'phase-{phase}.json', {'enabled': enabled, 'samples': samples})
            after=journal();delta,bad=faults(baseline,after)
            (args.output / f'phase-{phase}-journal-delta.txt').write_text(delta)
            baseline=after
            if bad:raise ValueError('New kernel fault/rejection: stopped and disabling continuous WFI')
        successful=True
        save('result.json', {'completed': True, 'restores_enabled_baseline': True})
    except BaseException as error:
        save('error.json', {'error': str(error)})
        raise
    finally:
        write_switch(successful)  # Failed/cancelled run stays disabled.
        (args.output / 'journal-final.txt').write_text(journal())
        os.sync()
    print(args.output)

if __name__ == '__main__':
    main()
