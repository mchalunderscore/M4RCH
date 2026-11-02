#!/usr/bin/env python3
"""Sample the existing read-only PMP report until a measured process exits."""
from pathlib import Path
import json,os,sys,time
pid=int(sys.argv[1]); out=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')/(sys.argv[2]+'.jsonl')
if out.exists(): raise SystemExit('refusing to overwrite')
os.sched_setaffinity(0,{1}); os.nice(10)
report=Path('/sys/kernel/debug/apple-pmp-report/5003c0000.pmp-report')
with out.open('x') as f:
 out.chmod(0o600)
 while True:
  try: os.kill(pid,0)
  except ProcessLookupError: break
  now=time.monotonic(); parts={}
  for line in report.read_text().splitlines():
   k,v=line.split(':',1);parts[k]=int(v.strip())
  parts['monotonic']=now
  parts['cpu_temp_mc']=int(Path('/sys/class/thermal/thermal_zone1/temp').read_text())
  parts['fan_rpm']=[int(Path(f'/sys/class/hwmon/hwmon4/fan{i}_input').read_text()) for i in (1,2)]
  f.write(json.dumps(parts)+'\n');f.flush();time.sleep(1)
