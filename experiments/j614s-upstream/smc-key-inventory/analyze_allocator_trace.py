#!/usr/bin/env python3
"""Summarize actual thermal governor events from a tracefs capture."""
from collections import defaultdict
from pathlib import Path
import re
import statistics
import sys

path=Path(sys.argv[1] if len(sys.argv)>1 else '/var/lib/m4rch/j614s-smc-thermal-20261102/allocator-pid-trace.txt')
zones=defaultdict(list)
for line in path.read_text().splitlines():
    if 'thermal_power_allocator:' not in line:
        continue
    data={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)}
    if {'thermal_zone_id','current_temperature','power_range','max_allocatable_power'} <= data.keys():
        zones[data['thermal_zone_id']].append(data)
for zone,rows in sorted(zones.items()):
    if zone != 1 and zone not in range(18,25):
        continue
    temp=[r['current_temperature']/1000 for r in rows]
    budget=[r['power_range']/1000 for r in rows]
    capacity=[r['max_allocatable_power']/1000 for r in rows]
    print(f'zone={zone} n={len(rows)} temp_C={min(temp):.1f}..{max(temp):.1f} '
          f'budget_W={min(budget):.2f}..{max(budget):.2f} '
          f'actors_max_W={statistics.median(capacity):.2f}')
