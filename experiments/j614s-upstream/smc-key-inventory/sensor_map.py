#!/usr/bin/env python3
"""Build a private mapping of live DT sensor keys to exposed hwmon labels."""
from collections import Counter
import json
from pathlib import Path

base=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')
meta={}
for line in (base/'smc-key-metadata.txt').read_text().splitlines():
    i,key,typ,size,flags=line.split()
    meta[bytes.fromhex(key).decode('ascii')]={'type':bytes.fromhex(typ).decode('ascii'),'size':int(size),'flags':int(flags,16)}
hw=next(p for p in Path('/sys/class/hwmon').glob('hwmon*') if (p/'name').read_text().strip()=='macsmc_hwmon')
labels={}
for f in hw.glob('*_label'):
    lab=f.read_text().strip(); v=f.with_name(f.name.replace('_label','_input'))
    if v.exists(): labels.setdefault(lab,[]).append(v.name)
root=Path('/proc/device-tree/smc@50c600000/hwmon')
result=[]
for node in sorted(root.iterdir()):
    if not node.is_dir() or not (node/'apple,key-id').is_file(): continue
    key=(node/'apple,key-id').read_bytes().rstrip(b'\0').decode('ascii')
    label=(node/'label').read_bytes().rstrip(b'\0').decode('ascii') if (node/'label').exists() else None
    result.append({'node':node.name,'key':key,'label':label,'metadata':meta.get(key),'inputs':labels.get(label,[])})
out=base/'smc-sensor-map.json'
if out.exists(): raise SystemExit('refusing to overwrite')
with out.open('x') as f:
    out.chmod(0o600)
    json.dump(result,f,indent=2)
print('device-tree sensor nodes',len(result),'missing metadata',sum(x['metadata'] is None for x in result),'with exposed input',sum(bool(x['inputs']) for x in result),'duplicate labels',sum(n>1 for n in Counter(x['label'] for x in result if x['label']).values()))
