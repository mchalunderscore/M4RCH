#!/usr/bin/env python3
"""Prepare native common scheduler work bytes from explicit supplied bindings.

No allocation, queue creation, publication or GPU execution. Input integers are
JSON numbers or hexadecimal strings. A successfully serialized record is not
proof of live submission readiness.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from private_work_prefix import patch_work_prefix
from private_work_body import patch_work_body
from private_scheduler_publish import publish_nop

def integer(v):
 if isinstance(v,bool):raise ValueError('Boolean supplied for integer binding')
 if not isinstance(v,(str,int)):raise ValueError('Integer or hexadecimal string required')
 return int(v,0) if isinstance(v,str) else v
def bounded(value,bits,name):
 value=integer(value)
 if not 0<=value<1<<bits:raise ValueError(name+' out of encoded range')
 return value

def prepare(binding,initial_record=bytes(0x200)):
 q=binding['queue'];timestamp=bounded(q['timestamp'],64,'timestamp');qid=bounded(q['id'],7,'queue id');priority=bounded(q['priority'],2,'priority');capacity=integer(q['capacity']);previous=bounded(q['previous'],64,'previous');initial=bounded(q['initial'],64,'initial')
 if not 1<=capacity<=256:raise ValueError('Counter capacity outside qualified1..256')
 if integer(q['pending'])>=capacity:raise ValueError('Queue has no available pending slot')
 pending=bounded(q['pending'],32,'pending')
 ap=binding['aperture'];ap_address=bounded(ap['address'],64,'aperture address');ap_index=bounded(ap['index'],6,'aperture index');ap_count=integer(ap['count'])
 if not 0<=ap_count<=64:raise ValueError('Aperture count outside encoded range')
 if ap_count and ap_address&31:raise ValueError('Aperture address must be32-byte aligned')
 payload=[bounded(x,64,'payload') for x in binding['payload']]
 if len(payload)!=2:raise ValueError('Two payload bindings required')
 dep=[]
 for d in binding['dependencies']:
  event=bounded(d['event'],32,'event');index=bounded(d['index'],7,'event index');epoch=bounded(d['epoch'],64,'epoch')
  if index>=24:raise ValueError('Event backing index outside currently qualified0..23')
  dep.append((event,index,epoch))
 if len(dep)>8:raise ValueError('Dependency count outside currently qualified0..8')
 if not isinstance(binding['alternate_kind'],bool) or not isinstance(binding['extra_flag'],bool):raise ValueError('Explicit boolean flags required')
 qos=binding['qos']
 if len(qos)!=3:raise ValueError('Three QOS bindings required')
 qos=[bounded(qos[0],8,'qos0'),bounded(qos[1],16,'qos1'),bounded(qos[2],5,'qos2')]
 lists=[]
 for item in binding['register_lists']:
  address=bounded(item['address'],64,'register address');count=bounded(item['count'],7,'register count')
  if address&31:raise ValueError('Register-list address must be32-byte aligned')
  if bool(address)!=bool(count):raise ValueError('Address/count presence mismatch')
  lists.append((address,count))
 if len(lists)!=4:raise ValueError('Four register-list bindings required')
 masks=[bounded(x,64,'mask') for x in binding['masks']]
 if len(masks)!=4:raise ValueError('Four mask bindings required')
 kind=bounded(binding['rce_kind'],2,'RCE kind');aux=bounded(binding['auxiliary'],64,'auxiliary')
 prefixed=patch_work_prefix(initial_record,timestamp,qid,priority,ap_address,ap_index,ap_count,binding['alternate_kind'],binding['extra_flag'],payload)
 work,next_timestamp=patch_work_body(prefixed,timestamp,capacity,initial,qid,dep,previous,qos,kind,lists,masks,aux)
 queue=bytearray(0x100)
 for off,value,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x1c,priority,'I'),(0x44,pending,'I'),(0x48,next_timestamp,'Q'),(0x90,initial,'Q')]:struct.pack_into('<'+fmt,queue,off,value)
 updated,overflow=publish_nop(queue,timestamp);assert not overflow
 return work,updated,dict(timestamp=timestamp,next_timestamp=next_timestamp,queue_id=qid,register_lists=lists,dependencies=dep,serialized_bytes=len(work),submission_ready=False,remaining=['live queue/root/resource identity and mapping validation','firmware work/microsequence/lifecycle binding','publication and cache visibility','completion/event/stamp retirement and coherent readback'])

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bindings',type=Path);p.add_argument('output',type=Path);a=p.parse_args();binding=json.loads(a.bindings.read_text());work,queue,report=prepare(binding)
 a.output.mkdir(exist_ok=False,parents=True);(a.output/'work-common.bin').write_bytes(work);(a.output/'queue-accounting-fixture.bin').write_bytes(queue)
 report.update(binding_sha256=hashlib.sha256(a.bindings.read_bytes()).hexdigest(),work_sha256=hashlib.sha256(work).hexdigest(),qualification='Checked native common work prefix/body/accounting models only. Explicit input bindings with representability/geometry checks. Queue accounting output is a host fixture, not an initialized queue. No allocator, firmware publication, GPU job validity or completion. High address prefix normalization is not proved by low-field encoding; no live submission gate.')
 (a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
