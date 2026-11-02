#!/usr/bin/env python3
"""Save a private snapshot of exposed SMC hwmon channel readings."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

out = Path('/var/lib/m4rch/j614s-smc-thermal-20261102') / (sys.argv[1] + '.json')
if out.exists(): raise SystemExit('refusing to overwrite')
hw = next(p for p in Path('/sys/class/hwmon').glob('hwmon*') if (p/'name').read_text().strip() == 'macsmc_hwmon')
values={}
errors={}
for f in sorted(hw.glob('*_input')):
    l=f.with_name(f.name.replace('_input','_label'))
    try: values[l.read_text().strip()]={'input':f.name,'value':int(f.read_text())}
    except (OSError, ValueError) as exc: errors[f.name]=str(exc)
with out.open('x') as f:
    out.chmod(0o600)
    json.dump({'utc':datetime.now(timezone.utc).isoformat(),'values':values,'errors':errors},f,indent=2)
print('captured',len(values),'channels;',len(errors),'errors')
