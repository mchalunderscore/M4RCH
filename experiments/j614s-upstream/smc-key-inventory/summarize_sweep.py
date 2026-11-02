#!/usr/bin/env python3
"""Summarize measured rail powers against the booted J616s-derived OPP model."""
import argparse
import json
from pathlib import Path
import re
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('dtsi', type=Path, help='t6040.dtsi from the kernel source used for the comparison')
source = parser.parse_args().dtsi.read_text()
opp={}
for name,policy in [('opp_e','1'),('opp_p0','0'),('opp_p1','8')]:
    sec=source.split(name+':',1)[1].split('\n\t};',1)[0]
    opp[policy]={int(hz)//1000:int(w)/1e6 for hz,w in re.findall(r'opp-hz = /bits/ 64 <(\d+)>;.*?opp-microwatt = <(\d+)>;',sec,re.S)}
dir=Path('/var/lib/m4rch/j614s-smc-thermal-20261102')
print('| Cluster | Requested MHz | Observed MHz | Rail W | Idle W | Estimated per core W | J616s model W | Status |')
print('|---|---:|---:|---:|---:|---:|---:|---|')
files=list(dir.glob('sweep-policy*.jsonl'))+list(dir.glob('remaining-policy*.jsonl'))
for p in sorted(files, key=lambda p: (int(p.stem.split('-')[1].removeprefix('policy')),int(p.stem.split('-')[2]))):
    try:
        records=[json.loads(x) for x in p.read_text().splitlines()]
    except json.JSONDecodeError:
        continue
    if not records or 'result' not in records[-1]: continue
    pol=p.stem.split('-')[1].removeprefix('policy'); req=int(p.stem.split('-')[2]);
    base=[x for x in records if x.get('phase')=='baseline'];load=[x for x in records if x.get('phase')=='load'];
    if not load: continue
    tail=load[len(load)//2:]; rail={'0':'SMC PR0b','1':'SMC PP2b','8':'SMC PP0b'}[pol]
    avg=lambda rows,key:statistics.mean(x[key] for x in rows)
    raw=avg(tail,rail)/1e6; idle=avg(base,rail)/1e6
    # Match Aurora #605's E-cluster method. P results are total rail readings.
    percore=idle+(raw-idle)/4 if pol=='1' else raw
    actual=statistics.mean(x['cpuinfo_freq_khz'][pol] for x in tail)
    status='held' if abs(actual-req)<req*.01 else 'clipped/mixed; exclude'
    print(f"| {'E' if pol=='1' else 'P0' if pol=='0' else 'P1'} | {req//1000} | {actual/1000:.0f} | {raw:.3f} | {idle:.3f} | {percore:.3f} | {opp[pol].get(req,float('nan')):.3f} | {status} |")
