#!/usr/bin/env python3
"""Compare a wider real-controller trip gap at lowered temperatures."""
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
switch, target, policy = (zone / n for n in ('trip_point_0_temp', 'trip_point_1_temp', 'policy'))
if (switch.read_text().strip(), target.read_text().strip(), policy.read_text().strip()) != ('100000', '101000', 'power_allocator'):
    sys.exit('unexpected GPU policy; nothing changed')
if not 48500 <= int((zone / 'temp').read_text()) <= 50000:
    sys.exit('sensor is outside the comparison range; nothing changed')
cooling = Path('/sys/class/thermal/cooling_device0')
if (cooling / 'type').read_text().strip() != 'cpufreq-cpu0':
    sys.exit('unexpected P0 cooling device')
out = Path('/var/lib/m4rch/j614s-smc-thermal-20261102/gpu-gap-five-degrees.jsonl')
if out.exists():
    sys.exit('refusing to overwrite evidence')

# Restoring the gap alone does not recalculate allocator gains, so rebind it.
watch_code = '''import os,sys,time
from pathlib import Path
parent=int(sys.argv[1]); z=Path(sys.argv[2]); deadline=time.monotonic()+90
while time.monotonic()<deadline:
 try: os.kill(parent,0)
 except ProcessLookupError: break
 time.sleep(.25)
try:
 (z/'trip_point_0_temp').write_text('100000\\n')
 (z/'trip_point_1_temp').write_text('101000\\n')
 (z/'policy').write_text('step_wise\\n')
 (z/'policy').write_text('power_allocator\\n')
except Exception as e: print('WATCHDOG RESTORE FAILED:', e, file=sys.stderr)
'''
watchdog = subprocess.Popen([sys.executable, '-c', watch_code, str(os.getpid()), str(zone)])
load = None
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(sig, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))
try:
    with out.open('x') as log:
        out.chmod(0o600)
        target.write_text('48000\n')
        switch.write_text('43000\n')
        policy.write_text('step_wise\n')
        policy.write_text('power_allocator\n')
        log.write(json.dumps({'setup': {'target_mc': int(target.read_text()),
                                      'switch_mc': int(switch.read_text()),
                                      'sustainable_mw': int((zone/'sustainable_power').read_text()),
                                      'k_po': int((zone/'k_po').read_text()),
                                      'k_pu': int((zone/'k_pu').read_text()),
                                      'k_i': int((zone/'k_i').read_text())}})+'\n'); log.flush()
        load = subprocess.Popen([sys.executable,
            '/home/michal/Projects/m4rch/experiments/j614s-upstream/smc-key-inventory/guarded_load.py',
            '--cpus', '5', '--seconds', '18', '--limit-c', '88',
            '--label', 'gpu-gap-five-degrees-p0'], start_new_session=True)
        start = time.monotonic()
        while time.monotonic()-start < 30:
            log.write(json.dumps({'elapsed':round(time.monotonic()-start,3),
                                  'temp_mc':int((zone/'temp').read_text()),
                                  'p0_state':int((cooling/'cur_state').read_text())})+'\n');log.flush()
            if load.poll() is not None:
                break
            time.sleep(.25)
        if load.poll() is None:
            raise TimeoutError('guarded workload exceeded deadline')
        print(json.dumps({'workload_exit':load.returncode,'trace':str(out)}),flush=True)
finally:
    restored = False
    try:
        switch.write_text('100000\n')
        target.write_text('101000\n')
        policy.write_text('step_wise\n')
        policy.write_text('power_allocator\n')
        if (switch.read_text().strip(), target.read_text().strip(), policy.read_text().strip()) != ('100000', '101000', 'power_allocator'):
            raise RuntimeError('trip/policy restoration failed')
        restored = True
    finally:
        if load and load.poll() is None:
            os.killpg(load.pid, signal.SIGTERM)
            load.wait(timeout=10)
        if restored:
            watchdog.terminate();watchdog.wait(timeout=5)
