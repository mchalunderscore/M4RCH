#!/usr/bin/env python3
"""Compare private metadata-only SMC inventory with live hwmon device tree."""
from collections import Counter
from pathlib import Path
import json

source = Path('/var/lib/m4rch/j614s-smc-thermal-20261102/smc-key-metadata.txt')
tree = Path('/proc/device-tree/smc@50c600000/hwmon')
rows = {}
errors = []
for line in source.read_text().splitlines():
    bits = line.split()
    if len(bits) != 5:
        errors.append(line)
        continue
    index, keyhex, typehex, size, flags = bits
    key = bytes.fromhex(keyhex).decode('ascii', errors='replace')
    typ = bytes.fromhex(typehex).decode('ascii', errors='replace')
    rows[key] = {'type':typ, 'size':int(size), 'flags':int(flags, 16)}

properties = {}
for p in tree.rglob('apple,key-id'):
    key = p.read_bytes().rstrip(b'\0').decode('ascii')
    properties.setdefault(key, []).append(str(p.parent.relative_to(tree)))

eligible = {k for k,v in rows.items() if k[:1] in 'TVIP' and v['type'] == 'flt ' and v['size'] == 4 and v['flags'] & 0x80 and not v['flags'] & 0x10}
described = {k for k in properties if k[:1] in 'TVIP'}
missing = sorted(k for k in properties if k not in rows)
ineligible = {k:rows[k] for k in sorted(described - eligible) if k in rows}
extra = sorted(eligible - described)
result = {
    'total_metadata_rows':len(rows),
    'errors':len(errors),
    'dt_key_properties':sum(map(len, properties.values())),
    'dt_distinct_key_ids':len(properties),
    'dt_missing_key_ids':missing,
    'tvip_eligible_totals':dict(sorted(Counter(k[0] for k in eligible).items())),
    'tvip_dt_distinct_totals':dict(sorted(Counter(k[0] for k in described).items())),
    'tvip_dt_keys_not_readable_floats':ineligible,
    'eligible_not_described':extra,
    'eligible_not_described_counts':dict(sorted(Counter(k[0] for k in extra).items())),
    'dt_sensor_keys':sorted(described),
}
print(json.dumps(result, indent=2))
