#!/usr/bin/env python3
"""Test cooling release as a real GPU sensor falls through a lowered trip."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

if os.geteuid() != 0:
    sys.exit('run as root')
zones = [p for p in Path('/sys/class/thermal').glob('thermal_zone*')
         if (p / 'type').read_text().strip() == 'gpu0-thermal']
if len(zones) != 1:
    sys.exit('unexpected GPU zone')
zone = zones[0]
switch = zone / 'trip_point_0_temp'
target = zone / 'trip_point_1_temp'
if (switch.read_text().strip(), target.read_text().strip(),
        (zone / 'policy').read_text().strip()) != ('100000', '101000', 'power_allocator'):
    sys.exit('unexpected GPU policy; nothing changed')
out = Path('/var/lib/m4rch/j614s-smc-thermal-20261102/gpu-natural-cooldown.jsonl')
if out.exists():
    sys.exit('refusing to overwrite evidence')
guard = '/home/michal/Projects/m4rch/experiments/j614s-upstream/smc-key-inventory/guarded_load.py'

watch_code = '''import os,sys,time
from pathlib import Path
parent=int(sys.argv[1]); switch=Path(sys.argv[2]); target=Path(sys.argv[3])
deadline=time.monotonic()+120
while time.monotonic()<deadline:
 try: os.kill(parent,0)
 except ProcessLookupError: break
 time.sleep(.25)
try:
 switch.write_text('100000\\n'); target.write_text('101000\\n')
except Exception as e: print('WATCHDOG RESTORE FAILED:', e, file=sys.stderr)
'''
watchdog = subprocess.Popen([sys.executable, '-c', watch_code, str(os.getpid()), str(switch), str(target)])
load = None
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(sig, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))
try:
    warm = subprocess.run([sys.executable, guard, '--gpu', '--seconds', '20',
                           '--limit-c', '88', '--label', 'gpu-cooldown-warmup'], timeout=40, check=True)
    warm_log = Path('/var/lib/m4rch/j614s-smc-thermal-20261102/gpu-cooldown-warmup.jsonl')
    if json.loads(warm_log.read_text().splitlines()[-1]).get('result') != 'completed':
        sys.exit('warmup was stopped by a guard; no trip changes')
    current = int((zone / 'temp').read_text())
    switch_temp = (current // 1000 - 3) * 1000
    target_temp = switch_temp + 1000
    if not 40000 <= switch_temp < target_temp < current < 80000:
        sys.exit('unexpected cooldown starting temperature; no trip changes')
    with out.open('x') as log:
        out.chmod(0o600)
        target.write_text(f'{target_temp}\n')
        switch.write_text(f'{switch_temp}\n')
        load = subprocess.Popen([sys.executable, guard, '--cpus', '5', '--seconds', '30',
                                 '--limit-c', '88', '--label', 'gpu-cooldown-p0'], start_new_session=True)
        start = time.monotonic()
        crossed = None
        while time.monotonic() - start < 40:
            now = time.monotonic()
            temp = int((zone / 'temp').read_text())
            state = int(Path('/sys/class/thermal/cooling_device0/cur_state').read_text())
            log.write(json.dumps({'elapsed': round(now-start, 3), 'temp_mc': temp,
                                  'switch_mc': switch_temp, 'target_mc': target_temp,
                                  'p0_state': state}) + '\n'); log.flush()
            if temp < switch_temp and crossed is None:
                crossed = now
            if crossed is not None and now - crossed >= 4:
                break
            if load.poll() is not None:
                break
            time.sleep(.25)
        log.write(json.dumps({'crossed_downward': crossed is not None}) + '\n')
        print(json.dumps({'crossed_downward': crossed is not None, 'trace': str(out)}), flush=True)
finally:
    restored = False
    try:
        switch.write_text('100000\n'); target.write_text('101000\n')
        if (switch.read_text().strip(), target.read_text().strip()) != ('100000', '101000'):
            raise RuntimeError('trip restoration failed')
        restored = True
    finally:
        if load and load.poll() is None:
            os.killpg(load.pid, signal.SIGTERM)
            load.wait(timeout=10)
        if restored:
            watchdog.terminate(); watchdog.wait(timeout=5)
