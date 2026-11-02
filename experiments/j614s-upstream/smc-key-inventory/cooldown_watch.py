#!/usr/bin/env python3
"""Observe fan and sensor cooldown after a guarded workload without writes."""
import json,os,sys,time
from pathlib import Path
pid=int(sys.argv[1]);out=Path('/var/lib/m4rch/j614s-smc-thermal-20261102/cooldown-1512.jsonl')
if out.exists():raise SystemExit('refusing to overwrite')
os.sched_setaffinity(0,{1});os.nice(10)
hw=next(p for p in Path('/sys/class/hwmon').glob('hwmon*') if (p/'name').read_text().strip()=='macsmc_hwmon')
inputs={}
for f in hw.glob('*_label'):
 name=f.read_text().strip()
 if name in ('CPU Die Max','SMC TVMR','SMC TVMr','Fan 1','Fan 2'):
  inputs[name]=f.with_name(f.name.replace('_label','_input'))
if len(inputs)!=5:raise SystemExit('required channels missing')
start=time.monotonic();ended=None
with out.open('x') as f:
 out.chmod(0o600)
 while True:
  try: os.kill(pid,0);running=True
  except ProcessLookupError: running=False
  if not running and ended is None: ended=time.monotonic()
  row={'monotonic':time.monotonic(),'workload_running':running,'sensors':{k:int(p.read_text()) for k,p in inputs.items()}}
  mode=Path('/sys/kernel/debug/m4rch_smc_inventory/fan_modes')
  if mode.exists():row['fan_modes']={k:int(v) for k,v in (line.split() for line in mode.read_text().splitlines())}
  f.write(json.dumps(row)+'\n');f.flush()
  if ended is not None and (time.monotonic()-ended>=300 or (time.monotonic()-ended>=20 and row['sensors']['Fan 1']<100 and row['sensors']['Fan 2']<100)):break
  time.sleep(2)
