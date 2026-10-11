#!/usr/bin/env python3
"""Qualify actual enqueue state transitions against saved native arithmetic."""
import hashlib,json,random,struct,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SRC=Path(__file__).with_name('g16_t6040_scheduler_owner_v9.rs')
sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
from private_nop_header import advance_timestamp
from private_scheduler_publish import publish_nop
rng=random.Random(604044);code='#[path='+json.dumps(str(SRC))+'] mod owner;\nfn main(){\n'
steps=0;cases=256
for i in range(cases):
 capacity=[1,2,3,16,256][i%5];slot=rng.randrange(capacity);timestamp=(rng.getrandbits(32)<<8)|slot;queue_id=i%128
 code+='let mut s=owner::State::from_values('+str(queue_id)+','+str(capacity)+','+str(timestamp)+',0,None).unwrap();\n'
 count=min(capacity,1+i%8);old=timestamp;credits=[]
 for j in range(count):
  next_value=advance_timestamp(timestamp,capacity)
  q=bytearray(0x100);struct.pack_into('<I',q,0x10,capacity);struct.pack_into('<I',q,0x44,j)
  expected,overflow=publish_nop(q,timestamp);assert not overflow
  pending=struct.unpack_from('<I',expected,0x44)[0];cached=struct.unpack_from('<Q',expected,0xa0)[0]
  name='c'+str(j);credits.append(name)
  code+='assert_eq!(owner::next_timestamp(s.timestamp,s.capacity),Some('+str(next_value)+'));let p=s.begin('+str(timestamp)+','+str(next_value)+').unwrap();assert_eq!(p.slot,'+str(timestamp&255)+');assert!(s.quarantined);assert!(s.begin('+str(timestamp)+','+str(next_value)+').is_none());let mut '+name+'=s.commit(p).unwrap();assert_eq!(s.pending,'+str(pending)+');assert_eq!(s.cached_previous,Some('+str(cached)+'));assert_eq!(s.timestamp,'+str(next_value)+');assert!(s.commit(p).is_none());\n'
  timestamp=next_value;steps+=1
 for name in credits[1:]:code+='c0.append(&mut '+name+').unwrap();assert!(s.retire(&mut '+name+').is_none());\n'
 code+='assert_eq!(c0.count(),'+str(count)+');\n'
 if count==capacity:code+='let before=s;assert!(s.begin(s.timestamp,owner::next_timestamp(s.timestamp,s.capacity).unwrap()).is_none());assert_eq!(s,before);\n'
 code+='let mut wrong=owner::State::from_values('+str((queue_id+1)%128)+','+str(capacity)+','+str(timestamp)+','+str(count)+',None).unwrap();assert!(wrong.retire(&mut c0).is_none());\n'
 code+='let mut empty=owner::State::from_values('+str(queue_id)+','+str(capacity)+','+str(timestamp)+',0,None).unwrap();assert!(empty.retire(&mut c0).is_none());assert_eq!(empty.pending,0);\n'
 code+='s.retire(&mut c0).unwrap();assert_eq!(s.pending,0);assert!(s.retire(&mut c0).is_none());assert_eq!(s.pending,0);\n'
 code+='let before=s;assert!(s.begin('+str(old)+',0).is_none());assert_eq!(s,before);\n'
 # Interrupted backing write retains quarantine, pending and counter.
 code+='let p=s.begin(s.timestamp,owner::next_timestamp(s.timestamp,s.capacity).unwrap()).unwrap();assert!(s.quarantined);assert_eq!(s.pending,0);assert!(s.begin(p.submitted,p.next).is_none());\n'
for q,capacity,timestamp,pending in [(128,16,0,0),(0,0,0,0),(0,257,0,0),(0,16,16,0),(0,16,0,17)]:
 code+='assert!(owner::State::from_values('+str(q)+','+str(capacity)+','+str(timestamp)+','+str(pending)+',None).is_none());\n'
code+='}\n'
with tempfile.TemporaryDirectory(prefix='native-scheduler-owner-')as td:
 p=Path(td);(p/'main.rs').write_text(code)
 subprocess.run(['rustc','--edition=2021','-Dwarnings',str(p/'main.rs'),'-o',str(p/'run')],check=True)
 subprocess.run([str(p/'run')],check=True)
def pin(p):p=Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
j=dict(schema='m4rch.native-scheduler-owner-qualification.v9',scenarios=cases,entry_transitions=steps,retirement_roundtrips=cases,duplicate_retirement_refusals=cases,wrong_owner_refusals=cases,underflow_refusals=cases,quarantined_write_refusals=cases,pins=[pin(SRC),pin(__file__),pin(ROOT/'experiments/t6040-gpu/private_nop_header.py'),pin(ROOT/'experiments/t6040-gpu/private_scheduler_publish.py'),pin(ROOT/'docs/evidence/2026-10-08-private-scheduler-publish.json'),pin(ROOT/'docs/evidence/2026-10-08-private-pending-release.json')],hardware_actions=[],runtime_enabled=False,scope='Compiled retained state/credit transitions with source-qualified independent timestamp/publish arithmetic, varying capacities and wrap slots. Reuses native accounting/retirement evidence; no fresh full-native caller oracle, DMA, concurrency or completion consumer proof.')
(ROOT/'docs/evidence/2026-10-11-native-scheduler-owner-v9.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
