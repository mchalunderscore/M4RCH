#!/usr/bin/env python3
"""Decode saved hardware descriptors/rings/status; no live register reads or writes."""
import argparse,hashlib,json
from pathlib import Path
from firmware_completion import describe,decode_entry

def integer(value):
 if type(value) is int:return value
 if type(value) is str:return int(value,0)
 raise ValueError('Require integer or hexadecimal string')

def decode(hardware,statuses,rings):
 if len(hardware)<0x26a0 or len(statuses)!=4 or len(rings)!=4:
  raise ValueError('Require hardware through26a0, four status words and four backing inputs')
 queues=[]
 for index in range(4):
  descriptor=hardware[0x2620+index*32:0x2640+index*32]
  plan=describe(descriptor,integer(statuses[index]));plan['slot']=index
  if plan['present']:
   backing=rings[index]
   if backing is None or len(backing)<plan['capacity']*plan['stride']:
    raise ValueError('Present queue requires full ring capture')
   plan['backing_sha256']=hashlib.sha256(backing).hexdigest()
   plan['entries']=[dict(offset=offset,**decode_entry(backing[offset:offset+64])) for offset in plan['entry_offsets']]
  queues.append(plan)
 return dict(queues=queues,hardware_sha256=hashlib.sha256(hardware).hexdigest(),retirement_verified=False,
             qualification='Captured RAM/status numeric decoding only. Capture can be non-atomic; status sampling and cache visibility must be recorded separately. No acknowledgement writes, cursor updates, job retirement or resource release. Payload fields reflect firmware extraction, not a completed draw or valid fence.')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 manifest=json.loads(a.manifest.read_text());root=a.manifest.parent
 rings=[None if name is None else (root/name).read_bytes() for name in manifest['rings']]
 report=decode((root/manifest['hardware']).read_bytes(),manifest['statuses'],rings)
 report['manifest_sha256']=hashlib.sha256(a.manifest.read_bytes()).hexdigest()
 a.output.write_text(json.dumps(report,indent=2)+'\n');print('Decoded',sum(len(q.get('entries',[])) for q in report['queues']),'observed entries; no retirement claim')
if __name__=='__main__':main()
