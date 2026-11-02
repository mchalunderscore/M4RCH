#!/usr/bin/env python3
"""Measure actual SMC rail power at several pinned frequencies, with restoration."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

parser=argparse.ArgumentParser()
group=parser.add_mutually_exclusive_group()
group.add_argument('--recheck', action='store_true', help='repeat representative P states with CPU usage and voltage measurements')
group.add_argument('--remaining', action='store_true', help='measure remaining non-clipped OPPs')
group.add_argument('--endpoints', action='store_true', help='capture voltage and CPU usage at earlier sampled endpoints')
group.add_argument('--tops', action='store_true', help='check whether the two highest P states can be observed under the guards')
args=parser.parse_args()
root = Path('/home/michal/Projects/m4rch')
keys = Path('/sys/kernel/debug/m4rch_smc_inventory/qos')
def qos():
    return {int(z[0]):(int(z[1]),int(z[2])) for z in (line.split() for line in keys.read_text().splitlines())}
original=qos()
if set(original) != {0,1,8} or any(lo < 0 or hi < 0 or lo > hi for lo,hi in original.values()):
    sys.exit('unexpected original user QoS requests')
gpu_zones=[p for p in Path('/sys/class/thermal').glob('thermal_zone*') if (p/'type').read_text().strip().startswith('gpu')]
if len(gpu_zones)!=7 or any((p/'policy').read_text().strip()!='power_allocator' for p in gpu_zones):
    sys.exit('unexpected GPU-zone governor; no changes made')

# Lower and upper frequency requests in ascending-safe order.
def set_limits(cpu, low, high):
    p=Path(f'/sys/devices/system/cpu/cpufreq/policy{cpu}')
    (p/'scaling_min_freq').write_text('0\n')
    (p/'scaling_max_freq').write_text(str(high)+'\n')
    (p/'scaling_min_freq').write_text(str(low)+'\n')

def interrupted(signum,frame): raise KeyboardInterrupt
for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP): signal.signal(sig,interrupted)

points=[(0,[5],[1260000,2088000,3096000,3852000,4104000]),
        (8,[9],[1260000,2088000,3096000,3852000,4104000]),
        (1,[1,2,3,4],[1020000,1788000,2352000,2592000])]
if args.recheck:
    points=[(0,[5],[2088000,3096000]),(8,[9],[2088000,3096000])]
if args.tops:
    points=[(0,[5],[4416000,4512000]),(8,[9],[4416000,4512000])]
if args.endpoints:
    points=[(0,[5],[1260000,3852000]),(8,[9],[1260000,3852000])]
if args.remaining:
    other_p=[1512000,1800000,2352000,2616000,2868000,3300000,3468000,3624000,3756000,3924000,3996000,4044000]
    points=[(0,[5],other_p),(8,[9],other_p),(1,[1,2,3,4],[1404000,2112000,2532000])]
hw=next(p for p in Path('/sys/class/hwmon').glob('hwmon*') if (p/'name').read_text().strip()=='macsmc_hwmon')
tv=[]
for f in hw.glob('*_label'):
    if f.read_text().strip() in ('SMC TVMR','SMC TVMr'): tv.append(f.with_name(f.name.replace('_label','_input')))
if len(tv)!=2: sys.exit('required additional temperature sensors are missing')
changed=[]
try:
    # The inherited GPU zones otherwise impose unrelated CPU limits even when cool.
    for z in gpu_zones:
        (z/'policy').write_text('step_wise\n'); changed.append(z)
    for policy,cpus,freqs in points:
        for freq in freqs:
            # Allow time to cool between points; never fight thermal regulation.
            for _ in range(120):
                cpu_t=int(Path('/sys/class/thermal/thermal_zone1/temp').read_text())
                if cpu_t < 82000 and max(int(p.read_text()) for p in tv) < 97000: break
                time.sleep(1)
            else: raise RuntimeError('could not cool below the pre-measurement thresholds')
            if qos() != original: raise RuntimeError('user QoS requests changed externally')
            label=f'{"recheck" if args.recheck else "remaining" if args.remaining else "final" if args.endpoints else "tops" if args.tops else "sweep"}-policy{policy}-{freq}'
            path=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')/(label+'.jsonl')
            if path.exists(): raise RuntimeError('measurement already exists: '+label)
            try:
                set_limits(policy,freq,freq)
                cmd=[sys.executable,str(root/'experiments/j614s-upstream/smc-key-inventory/guarded_load.py'), '--cpus',','.join(map(str,cpus)), '--seconds','8', '--label',label,'--limit-c','93']
                subprocess.run(cmd,check=True,timeout=35)
            finally:
                low,high=original[policy]
                set_limits(policy,low,high)
                if qos()[policy] != original[policy]: raise RuntimeError('failed to restore user QoS for policy '+str(policy))
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            print(json.dumps({'point':label, 'result':rows[-1].get('result')}),flush=True)
            if rows[-1].get('result') != 'completed': raise RuntimeError('guard stopped the sweep')
finally:
    errors=[]
    for policy,(low,high) in original.items():
        try:
            set_limits(policy,low,high)
            if qos()[policy]!=(low,high): errors.append('QoS '+str(policy))
        except Exception as exc: errors.append('QoS '+str(policy)+': '+str(exc))
    for z in changed:
        try:
            (z/'policy').write_text('power_allocator\n')
            if (z/'policy').read_text().strip()!='power_allocator': errors.append(str(z))
        except Exception as exc: errors.append(str(z)+': '+str(exc))
    if errors:
        print('RESTORATION FAILED:', *errors, file=sys.stderr,flush=True)
        sys.exit(1)
    print('All user QoS requests and GPU-zone governors restored',flush=True)
