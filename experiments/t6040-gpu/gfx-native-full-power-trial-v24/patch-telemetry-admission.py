#!/usr/bin/env python3
"""Stage exact native read-only telemetry admission; no hardware access."""
import argparse,json,hashlib,shutil
from pathlib import Path
def pin(p):p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(source,destination):
 shutil.copytree(source,destination,ignore=shutil.ignore_patterns('*.o','*.ko','*.mod','*.mod.c','*.cmd','Module.symvers','modules.order'))
 p=destination/'graph-map.h';s=p.read_text();marker='  bool afr=pa>=0x28b000000ULL'
 assert s.count(marker)==1
 s=s.replace(marker,'''  bool telemetry_ro=(pa==0x5003c0000ULL && va==0xfffffc2001b00000ULL) ||
    (pa>=0x500658000ULL && pa<0x500668000ULL &&
     !(pa&0x3fffULL) && va==0xfffffc2001b20000ULL+(pa-0x500658000ULL));
'''+marker)
 marker='(!sgx && !platform && !afr) || (platform && !mmio_leaves[i].writable) ||';assert s.count(marker)==1
 s=s.replace(marker,'(!sgx && !platform && !afr && !telemetry_ro) || (platform && !mmio_leaves[i].writable) || (telemetry_ro && mmio_leaves[i].writable) ||')
 p.write_text(s);shutil.copyfile(source/'native-power-rust.o',destination/'native-power-rust.o')
 changed=[f.name for f in source.iterdir() if f.is_file() and (destination/f.name).exists() and f.read_bytes()!=(destination/f.name).read_bytes()];assert changed==['graph-map.h']
 r=dict(schema='m4rch.telemetry-admission-stage.v24',source=str(source.resolve()),stage=str(destination.resolve()),script=pin(__file__),before=pin(source/'graph-map.h'),after=pin(p),changed_files=changed,hardware_actions=[],scope='Only five exact physical/virtual read-only leaves admitted; existing range/write/collision/system-RAM guards preserved.')
 (destination/'telemetry-admission-patch.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();stage(a.source,a.destination)
