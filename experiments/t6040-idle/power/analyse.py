#!/usr/bin/env python3
"""Summarise raw ABBA captures; does not modify hardware or input files."""
import argparse
import json
from pathlib import Path
import statistics

def battery_watts(raw):
    values=[]
    for path,text in raw.items():
        if not path.endswith('/uevent') or not isinstance(text,str):continue
        d=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        if d.get('POWER_SUPPLY_TYPE')!='Battery' or d.get('POWER_SUPPLY_STATUS')!='Discharging':continue
        try:
            if 'POWER_SUPPLY_POWER_NOW' in d:
                value=abs(int(d['POWER_SUPPLY_POWER_NOW']))/1e6;method='power_now'
            else:
                value=abs(int(d['POWER_SUPPLY_CURRENT_NOW'])*int(d['POWER_SUPPLY_VOLTAGE_NOW']))/1e12;method='current_now*voltage_now'
            values.append({'path':path,'watts':value,'method':method})
        except (KeyError,ValueError):continue
    return values

def busy_fraction(first,last):
    def fields(raw):
        text=raw.get('/proc/stat')
        if not isinstance(text,str):return None
        line=next((l for l in text.splitlines() if l.startswith('cpu ')),None)
        return list(map(int,line.split()[1:9])) if line else None
    a,b=fields(first),fields(last)
    if a is None or b is None or len(a)<5 or len(b)<5:return None
    d=[y-x for x,y in zip(a,b)];total=sum(d)
    return (total-d[3]-d[4])/total if total>0 and min(d)>=0 else None

def summarise(data):
    samples=data['samples'];first,last=samples[0],samples[-1]
    batteries={}
    for s in samples:
        for v in battery_watts(s['raw']):
            k=v['path']+' '+v['method'];batteries.setdefault(k,[]).append(v['watts'])
    powers={k:{'samples':len(v),'median_watts':statistics.median(v),'min_watts':min(v),'max_watts':max(v),'constant_all_samples':len(set(v))==1} for k,v in batteries.items()}
    deltas={}
    for path,a in first['raw'].items():
        if '/cpuidle/state' in path and path.endswith(('/usage','/time','/rejected')):
            try:deltas[path]=int(last['raw'][path])-int(a)
            except (KeyError,ValueError,TypeError):pass
    return {'enabled':data['enabled'],'duration_seconds':last['monotonic']-first['monotonic'],'cpu_busy_fraction':busy_fraction(first['raw'],last['raw']),'discharging_battery_estimates':powers,'cpuidle_counter_deltas':deltas,'limitations':['Battery telemetry is whole-machine, uncalibrated; units follow Linux power_supply ABI.','Missing/charging samples are excluded. Constant values may indicate quantization or stale data.','Counter time is software accounting, not measured hardware power-state residency.']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('capture',type=Path);args=parser.parse_args()
    phases={str(i):summarise(json.loads((args.capture/f'phase-{i}.json').read_text())) for i in range(1,5)}
    print(json.dumps({'phases':phases,'interpretation':'Compare the two enabled and two disabled phases with matching battery/activity conditions; no automatic causal verdict.'},indent=2))
if __name__=='__main__':main()
