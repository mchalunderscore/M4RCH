#!/usr/bin/env python3
"""Collect thermal telemetry while running a time- and temperature-bounded CPU load."""
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument('--cpus', default='', help='comma-separated CPU numbers')
ap.add_argument('--gpu', action='store_true', help='run the existing bounded offscreen GPU compute workload')
ap.add_argument('--seconds', type=int, default=20)
ap.add_argument('--limit-c', type=float, default=95.0)
ap.add_argument('--label', required=True)
args = ap.parse_args()
cpus = [int(x) for x in args.cpus.split(',') if x]
if (not cpus and not args.gpu) or len(cpus) != len(set(cpus)) or args.seconds < 1 or args.seconds > 900 or not 65 <= args.limit_c <= 93:
    ap.error('invalid CPU set, duration, or temperature limit (maximum 93 C)')
if not set(cpus) <= set(os.sched_getaffinity(0)):
    ap.error('requested CPUs are not available')
outdir = Path('/var/lib/m4rch/j614s-smc-thermal-20261102')
outdir.mkdir(mode=0o700, parents=True, exist_ok=True)
path = outdir / (args.label + '.jsonl')
if path.exists():
    ap.error('refusing to overwrite an existing measurement')
hwmons = Path('/sys/class/hwmon')
hw = next(p for p in hwmons.glob('hwmon*') if (p/'name').read_text().strip() == 'macsmc_hwmon')
labels = {}
for f in hw.glob('*_label'):
    name = f.read_text().strip()
    if (f.parent / f.name.replace('_label', '_input')).exists():
        labels[name] = str(f.parent / f.name.replace('_label', '_input'))
keep = ['CPU Die Max', 'Fan 1', 'Fan 2', 'SMC PR0b', 'SMC PP0b', 'SMC PP2b', 'SMC PTHS', 'Total System Power', 'Heatpipe Power']
keep += ['SMC TVMR', 'SMC TVMr', 'SMC PR1b', 'SMC PS1b', 'SMC PS2b', 'SMC PS0b', 'SMC P3F2', 'SMC P5SR', 'SMC PMVC', 'SMC PPSC', 'SMC PPMC', 'SMC VR1b', 'SMC VS1b', 'SMC VS2b', 'SMC VR0b', 'SMC VP0b']
keep += [name for name in labels if name.startswith(('E-cluster Tex', 'P-cluster Tpx', 'GPU Tg0', 'GPU Tg1'))]
sensors = {k: Path(labels[k]) for k in keep if k in labels}
if not all(k in sensors for k in ('CPU Die Max', 'Fan 1', 'Fan 2', 'SMC PR0b', 'SMC PP0b', 'SMC PP2b', 'SMC TVMR', 'SMC TVMr')):
    ap.error('required thermal or power sensors missing')
thermal = [(p.name, p/'temp', (p/'type').read_text().strip()) for p in Path('/sys/class/thermal').glob('thermal_zone*') if (p/'type').read_text().strip().startswith(('cpu-', 'gpu'))]
if len(thermal) < 24:
    ap.error('expected thermal zones are not available')

children = []
last_extra = -100.0
stopping = False

def stop(signum=None, frame=None):
    global stopping
    stopping = True
    for child in children:
        if child.poll() is None:
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass

for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, stop)
try:
    os.setpriority(os.PRIO_PROCESS, 0, -10)
except PermissionError:
    ap.error('run as root to prioritize the thermal monitor')
os.sched_setaffinity(0, {1})

child_code = '''import ctypes, os, signal, sys, time
libc=ctypes.CDLL(None)
libc.prctl(1, signal.SIGKILL)
if os.getppid()==1: sys.exit(1)
os.sched_setaffinity(0, {int(sys.argv[1])})
end=time.monotonic()+int(sys.argv[2])+5
while time.monotonic()<end: pass
'''

def snapshot(start, phase):
    global last_extra
    now = time.monotonic()
    values = {}
    for label, file in sensors.items():
        values[label] = int(file.read_text())
    zone_values = {}
    for name, file, kind in thermal:
        t = int(file.read_text())
        if not -20000 < t < 150000: raise ValueError('implausible thermal reading: ' + kind)
        zone_values[kind] = t
    values['zones'] = zone_values
    values['cpu_ticks'] = {v[0][3:]:list(map(int,v[1:])) for v in (line.split() for line in Path('/proc/stat').read_text().splitlines()) if v and v[0].startswith('cpu') and v[0][3:].isdigit()}
    values['fan_targets'] = {str(i):int((hw/f'fan{i}_target').read_text()) for i in (1,2)}
    values['cpu_freq_khz'] = {str(i):int(Path(f'/sys/devices/system/cpu/cpufreq/policy{i}/scaling_cur_freq').read_text()) for i in (0,1,8)}
    values['cpuinfo_freq_khz'] = {str(i):int(Path(f'/sys/devices/system/cpu/cpufreq/policy{i}/cpuinfo_cur_freq').read_text()) for i in (0,1,8)}
    values['cooling_states'] = {p.name:int((p/'cur_state').read_text()) for p in Path('/sys/class/thermal').glob('cooling_device*')}
    pressure = hw/'thermal_pressure_level'
    if pressure.exists(): values['thermal_pressure_level'] = int(pressure.read_text())
    if now - last_extra >= 3:
        extra = {}
        for line in Path('/sys/kernel/debug/m4rch_smc_inventory/samples').read_text().splitlines():
            parts=line.split()
            if len(parts)==2:
                x=struct.unpack('<f', struct.pack('<I', int(parts[1],16)))[0]
                if math.isfinite(x): extra[parts[0]]=x
            else: raise ValueError('SMC sample error: '+line)
        values['extra_keys'] = extra
        pmp_path = Path('/sys/kernel/debug/apple-pmp-report/5003c0000.pmp-report')
        if pmp_path.exists():
            values['pmp'] = {k.strip():int(v) for k,v in (line.split(':',1) for line in pmp_path.read_text().splitlines())}
        mode_path = Path('/sys/kernel/debug/m4rch_smc_inventory/fan_modes')
        if mode_path.exists():
            values['fan_modes'] = {k:int(v) for k,v in (line.split() for line in mode_path.read_text().splitlines())}
        last_extra = now
    values['phase'] = phase
    values['elapsed'] = round(now-start, 3)
    return values

# Refuse to start if temperatures are already near the guard.
with path.open('x') as f:
    os.chmod(path,0o600)
    start = time.monotonic()
    initial = snapshot(start, 'baseline')
    if max(initial['zones'].values()) >= (args.limit_c - 5)*1000 or initial['CPU Die Max'] >= (args.limit_c - 5)*1000 or max(initial['SMC TVMR'],initial['SMC TVMr']) >= 100000:
        raise SystemExit('initial temperature too close to limit; no workload started')
    f.write(json.dumps({'metadata':{'cpus':cpus,'gpu':args.gpu,'seconds':args.seconds,'limit_c':args.limit_c,'tv_limit_c':105}})+'\n')
    f.write(json.dumps(initial)+'\n'); f.flush()
    # A warmup baseline provides an immediate before/after comparison.
    for _ in range(10):
        time.sleep(.25)
        row=snapshot(start,'baseline'); f.write(json.dumps(row)+'\n'); f.flush()
        if max(row['zones'].values()) >= args.limit_c*1000 or row['CPU Die Max'] >= args.limit_c*1000 or max(row['SMC TVMR'],row['SMC TVMr']) >= 105000:
            raise SystemExit('temperature guard during baseline')
    try:
        for cpu in cpus:
            children.append(subprocess.Popen([sys.executable,'-c',child_code,str(cpu),str(args.seconds)],start_new_session=True))
        if args.gpu:
            gpu = '/home/michal/Projects/m4rch/cache/j614s-gpu-trial/validation/6c6016fd-a269-49a6-bc89-ee1037fa01f4/native-gl46'
            if not Path(gpu).is_file(): raise FileNotFoundError('validated GPU workload missing')
            env = {k:v for k,v in os.environ.items() if k not in ('LD_LIBRARY_PATH','LD_PRELOAD','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE','MESA_GL_VERSION_OVERRIDE','MESA_GLSL_VERSION_OVERRIDE','DRI_PRIME')}
            env.update(M4_TEST_ROUNDS='1', M4_TEST_STRESS_SECONDS=str(min(args.seconds,300)))
            log = (outdir/(args.label+'-gpu.log')).open('x')
            def parent_death_signal():
                ctypes.CDLL(None).prctl(1, signal.SIGKILL)
                if os.getppid()==1: os._exit(1)
            children.append(subprocess.Popen([gpu,'/dev/dri/renderD128'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=parent_death_signal))
        deadline=time.monotonic()+args.seconds
        reason='completed'
        while time.monotonic()<deadline and not stopping:
            row=snapshot(start,'load'); f.write(json.dumps(row)+'\n'); f.flush()
            if max(row['zones'].values()) >= args.limit_c*1000 or row['CPU Die Max'] >= args.limit_c*1000 or max(row['SMC TVMR'],row['SMC TVMr']) >= 105000:
                reason='temperature-limit'; break
            if any(child.poll() is not None for child in children):
                reason='workload-ended-early'; break
            time.sleep(.25)
        if stopping: reason='interrupted'
    finally:
        stop()
        for child in children: child.wait(timeout=5)
    for _ in range(12):
        time.sleep(.25)
        row=snapshot(start,'cooldown'); f.write(json.dumps(row)+'\n'); f.flush()
    f.write(json.dumps({'result':reason})+'\n'); f.flush()
print(json.dumps({'file':str(path), 'result':reason, 'cpus':cpus}))
