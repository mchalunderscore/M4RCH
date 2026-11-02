#!/usr/bin/env python3
"""Exercise one real GPU zone at lower trips; restore trips even if killed."""
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
out = Path('/var/lib/m4rch/j614s-smc-thermal-20261102/gpu-transition-trial.jsonl')
if out.exists():
    sys.exit('refusing to overwrite evidence')
if int((zone / 'temp').read_text()) >= 49000:
    sys.exit('GPU zone too warm for the lowered-trip test')

# A separate process restores trips if this controller dies or exceeds its
# deadline. The original target is never raised above its original value.
watch = '''import os,sys,time
from pathlib import Path
parent=int(sys.argv[1]); switch=Path(sys.argv[2]); target=Path(sys.argv[3])
deadline=time.monotonic()+90
while time.monotonic()<deadline:
 try: os.kill(parent,0)
 except ProcessLookupError: break
 time.sleep(.25)
try:
 switch.write_text('100000\\n')
 target.write_text('101000\\n')
except Exception as e:
 print('WATCHDOG RESTORE FAILED:', e, file=sys.stderr)
'''
watchdog = subprocess.Popen([sys.executable, '-c', watch, str(os.getpid()), str(switch), str(target)])
load = None
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(sig, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))
try:
    with out.open('x') as log:
        out.chmod(0o600)
        target.write_text('53000\n')
        switch.write_text('52000\n')
        if (switch.read_text().strip(), target.read_text().strip()) != ('52000', '53000'):
            raise RuntimeError('trip setup failed')
        load = subprocess.Popen([sys.executable,
            '/home/michal/Projects/m4rch/experiments/j614s-upstream/smc-key-inventory/guarded_load.py',
            '--cpus', '5', '--gpu', '--seconds', '35', '--limit-c', '88',
            '--label', 'gpu-transition-lowered-trip'], start_new_session=True)
        start = time.monotonic()
        crossed = None
        released = False
        while time.monotonic() - start < 45:
            now = time.monotonic()
            temp = int((zone / 'temp').read_text())
            row = {'elapsed': round(now - start, 3), 'temp_mc': temp,
                   'switch_mc': int(switch.read_text()), 'target_mc': int(target.read_text()),
                   'p0_state': int(Path('/sys/class/thermal/cooling_device0/cur_state').read_text())}
            log.write(json.dumps(row) + '\n'); log.flush()
            if crossed is None and temp >= 52000:
                crossed = now
            if crossed is not None and not released and now - crossed >= 5:
                switch.write_text('100000\n')
                target.write_text('101000\n')
                released = True
            if released and now - crossed >= 10:
                break
            if load.poll() is not None:
                break
            time.sleep(.25)
        log.write(json.dumps({'crossed': crossed is not None, 'released': released}) + '\n')
        print(json.dumps({'crossed': crossed is not None, 'released': released,
                          'trace': str(out)}), flush=True)
finally:
    # Put the switch back first, then the target: never expose a raised target.
    restored = False
    try:
        switch.write_text('100000\n')
        target.write_text('101000\n')
        if (switch.read_text().strip(), target.read_text().strip()) != ('100000', '101000'):
            raise RuntimeError('trip restoration failed')
        restored = True
    finally:
        if load and load.poll() is None:
            os.killpg(load.pid, signal.SIGTERM)
            load.wait(timeout=10)
        if restored:
            watchdog.terminate()
            watchdog.wait(timeout=5)
