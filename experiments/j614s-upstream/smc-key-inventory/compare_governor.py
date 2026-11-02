#!/usr/bin/env python3
"""Temporarily compare GPU-zone governor, restoring all policies on exit."""
import os
from pathlib import Path
import signal
import subprocess
import sys

zones = [p for p in Path('/sys/class/thermal').glob('thermal_zone*') if (p/'type').read_text().strip().startswith('gpu')]
if len(zones) != 7 or any((p/'policy').read_text().strip() != 'power_allocator' for p in zones):
    sys.exit('unexpected GPU zone configuration; no policies changed')
changed=[]
def interrupted(signum, frame):
    raise KeyboardInterrupt
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP): signal.signal(sig, interrupted)
try:
    for p in zones:
        (p/'policy').write_text('step_wise\n')
        changed.append(p)
    subprocess.run([sys.executable, '/home/michal/Projects/m4rch/experiments/j614s-upstream/smc-key-inventory/guarded_load.py', '--cpus', '5', '--seconds', '20', '--label', 'gpu-stepwise-p0-actual', '--limit-c', '93'], check=True, timeout=45)
finally:
    errors=[]
    for p in changed:
        try:
            (p/'policy').write_text('power_allocator\n')
            if (p/'policy').read_text().strip() != 'power_allocator': errors.append(str(p))
        except OSError as exc: errors.append(f'{p}: {exc}')
    if errors:
        print('POLICY RESTORATION FAILED:', *errors, file=sys.stderr)
        sys.exit(1)
    print('GPU zone policies restored')
