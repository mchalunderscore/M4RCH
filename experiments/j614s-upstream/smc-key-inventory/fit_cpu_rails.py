#!/usr/bin/env python3
"""Fit real pinned-core rail readings, retaining sampling and validity limits."""
from pathlib import Path
import json,math,statistics

base=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')
for policy,cpu,rail,volt,siblings in [('0','5','SMC PR0b','SMC VR0b',['0','6','7']),('8','9','SMC PP0b','SMC VP0b',['8','10','11'])]:
 points=[]
 files=list(base.glob(f'remaining-policy{policy}-*.jsonl'))+list(base.glob(f'recheck-policy{policy}-*.jsonl'))+list(base.glob(f'final-policy{policy}-*.jsonl'))
 for p in sorted(files):
  try: rows=[json.loads(x) for x in p.read_text().splitlines()]
  except json.JSONDecodeError: continue
  if not rows or rows[-1].get('result')!='completed':continue
  r=[x for x in rows if x.get('phase')=='load']; r=r[len(r)//2:]
  if len(r)<4 or any(k not in r[0] for k in (rail,volt,'cpu_ticks','cpuinfo_freq_khz')):continue
  req=int(p.stem.split('-')[-1]);frequencies=[x['cpuinfo_freq_khz'][policy] for x in r]
  if min(frequencies) < req*.99 or max(frequencies)>req*1.01: continue
  begin,end=r[0]['cpu_ticks'],r[-1]['cpu_ticks']
  def busy(k):
   d=[b-a for a,b in zip(begin[k],end[k])];total=sum(d[:8]); return (1-(d[3]+d[4])/total)*100 if total else 0
  if busy(cpu)<90 or any(busy(k)>15 for k in siblings): continue
  f=statistics.mean(frequencies)/1e6
  v=statistics.mean(x[volt] for x in r)/1000
  power=statistics.mean(x[rail] for x in r)/1e6
  points.append((req/1000,f*v*v,power,v,p.name))
 if len(points)<3:
  print('policy',policy,'insufficient eligible samples:',len(points));continue
 xs=[x[1] for x in points];ys=[x[2] for x in points];mx=statistics.mean(xs);my=statistics.mean(ys);den=sum((x-mx)**2 for x in xs)
 k=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den;c=my-k*mx
 rms=math.sqrt(statistics.mean((y-(k*x+c))**2 for x,y in zip(xs,ys)))
 print(f'P{0 if policy=="0" else 1}: n={len(points)} k={k:.4f} W/(V² GHz) c={c:.4f} W rms={rms:.4f} W')
 for mhz,x,y,v,name in sorted(points): print(f'  {mhz:.0f} MHz {v:.3f} V observed {y:.3f} W fitted {k*x+c:.3f} W ({name})')
