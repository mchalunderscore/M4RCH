#!/usr/bin/env python3
"""Check candidate launcher fields, STOP/padding and rejected serialization."""
from pathlib import Path
import argparse,subprocess,json,hashlib
p=argparse.ArgumentParser(description=__doc__);p.add_argument('tool',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('receipt',type=Path);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True);report={}
fixtures=[('vertex',0,0x800010100,0x800010000,0x3c0,7,0,0,0),('fragment',1,0x800020100,0x800020000,0x480,0,4,1,0),('compute',2,0x800030100,0x800030000,0x540,0,0,0,1)]
for name,stage,launch,resource,entry,pubs,tile,samples,resources in fixtures:
 args=[stage,str(a.output/(name+'-launch.bin')),0x800000000,launch,resource,entry,pubs,0,tile,samples,resources,0]
 subprocess.run([str(a.tool),*[str(v) for v in args]],check=True)
 data=(a.output/(name+'-launch.bin')).read_bytes();offset=66 if stage<2 else 38
 assert len(data)==(256 if stage<2 else 1024)
 assert data[offset:offset+2]==b'\x77\x01' and int.from_bytes(data[offset+2:offset+5],'little')==2*entry+0x2a
 assert data[offset+7:offset+9]==b'\x02\x80'
 stop=offset+10+10+(48 if stage<2 else 16)
 assert data[stop:stop+4]==b'\x0e\0\0\0' and not any(data[stop+4:])
 report[name]={'parameters':args[:1]+args[2:],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'target_header_offset':offset,'target_field_offset':offset+2,'stop_offset':stop}
rejected=a.output/'rejected-launch.bin';assert not rejected.exists()
for args in [[3,str(rejected),0,0,0,0,0,0,0,0,0,0],[0,str(rejected),0,0,0,1,0,0,0,0,0,0],[2,str(rejected),0,0,0,0,0,0,0,0,0,0],[1,str(rejected),0,0,0,0,0,0,4,3,0,0]]:
 run=subprocess.run([str(a.tool),*[str(v) for v in args]],capture_output=True);assert run.returncode!=0 and not rejected.exists()
receipt={'source_commit':'87ac51d411f0e58a9433567ec2666f457be89e1d','source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'tool_sha256':hashlib.sha256(a.tool.read_bytes()).hexdigest(),'fixtures':report,'rejected_cases':4,'qualification':'Offline launch serialization with fixed fixture addresses; target fields, STOP and zero padding checked. Uses Gravity Apple9 launcher, not independently qualified T6040 launch implementation. No shader body entry, live allocation, root contents, VDM/CDM, PPP/PBE state, firmware job or hardware execution proved.'}
a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
print('3 candidate launch records checked; 4 invalid parameter cases rejected without output')
