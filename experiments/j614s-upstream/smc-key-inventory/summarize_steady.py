#!/usr/bin/env python3
"""Report real 60-second windows of a guarded thermal observation."""
from pathlib import Path
import json,statistics,sys
p=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')/(sys.argv[1]+'.jsonl')
a=[json.loads(x) for x in p.read_text().splitlines()]
r=[x for x in a if x.get('phase')=='load']
if not r: raise SystemExit('no load samples')
start=r[0]['elapsed']
print('| Seconds | Samples | CPU °C mean/max | TVMR °C mean/max | TVMr °C mean/max | CPU rails W | Fans RPM | PMP max |')
print('|---:|---:|---:|---:|---:|---:|---|---|')
for offset in range(0,int(r[-1]['elapsed']-start)+1,60):
 w=[x for x in r if start+offset<=x['elapsed']<start+offset+60]
 if not w:continue
 def temp(k):
  v=[x[k]/1000 for x in w]
  return f'{statistics.mean(v):.1f}/{max(v):.1f}'
 rails=statistics.mean(x['SMC PR0b']+x['SMC PP0b']+x['SMC PP2b'] for x in w)/1e6
 fans=f"{statistics.mean(x['Fan 1'] for x in w):.0f}/{statistics.mean(x['Fan 2'] for x in w):.0f}"
 samples=[x['pmp'] for x in w if 'pmp' in x]
 pmp='/'.join(str(max(x.get('lane'+str(i),0) for x in samples)) for i in range(3)) if samples else 'not sampled'
 print(f"| {offset}–{min(offset+60,round(r[-1]['elapsed']-start))} | {len(w)} | {temp('CPU Die Max')} | {temp('SMC TVMR')} | {temp('SMC TVMr')} | {rails:.2f} | {fans} | {pmp} |")
print('\nOutcome:',a[-1].get('result','running'))
