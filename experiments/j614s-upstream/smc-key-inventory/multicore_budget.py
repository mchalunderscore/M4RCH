#!/usr/bin/env python3
"""Guarded all-core thermal observation at a fixed moderate P-cluster frequency."""
from pathlib import Path
import argparse
import signal
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--freq-khz', type=int, default=2088000, choices=(1512000,1800000,2088000,3096000))
parser.add_argument('--seconds', type=int, default=120)
parser.add_argument('--label', default='all-core-2088-120')
args=parser.parse_args()
if args.seconds < 1 or args.seconds > 720: parser.error('duration must be 1..720 seconds')

def qos():
    lines=Path('/sys/kernel/debug/m4rch_smc_inventory/qos').read_text().splitlines()
    return {int(a):(int(b),int(c)) for a,b,c,*_ in map(str.split,lines)}
def limits(cpu,low,high):
    p=Path(f'/sys/devices/system/cpu/cpufreq/policy{cpu}')
    (p/'scaling_min_freq').write_text('0\n')
    (p/'scaling_max_freq').write_text(f'{high}\n')
    (p/'scaling_min_freq').write_text(f'{low}\n')
def interrupted(signum, frame): raise KeyboardInterrupt
for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP): signal.signal(signum,interrupted)
original=qos(); zones=[p for p in Path('/sys/class/thermal').glob('thermal_zone*') if (p/'type').read_text().strip().startswith('gpu')]
if len(zones)!=7 or any((p/'policy').read_text().strip()!='power_allocator' for p in zones): sys.exit('unexpected GPU-zone governor')
changed=[]
try:
    for z in zones: (z/'policy').write_text('step_wise\n'); changed.append(z)
    for p in (0,8): limits(p,args.freq_khz,args.freq_khz)
    subprocess.run([sys.executable,'/home/michal/Projects/m4rch/experiments/j614s-upstream/smc-key-inventory/guarded_load.py','--cpus','0,5,6,7,8,9,10,11,1,2,3,4','--seconds',str(args.seconds),'--label',args.label,'--limit-c','93'],check=True,timeout=args.seconds+25)
finally:
    errors=[]
    for p in (0,8):
        try:
            limits(p,*original[p])
            if qos()[p]!=original[p]: errors.append(f'policy{p} QoS mismatch')
        except Exception as e: errors.append(f'policy{p}: {e}')
    for z in changed:
        try:
            (z/'policy').write_text('power_allocator\n')
            if (z/'policy').read_text().strip()!='power_allocator': errors.append(str(z))
        except Exception as e: errors.append(str(z)+': '+str(e))
    if errors:
        print('RESTORATION FAILED:',*errors,file=sys.stderr,flush=True)
        sys.exit(1)
    print('CPU QoS requests and GPU zone policies restored',flush=True)
