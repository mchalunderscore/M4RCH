# SPDX-License-Identifier: GPL-2.0-only
"""Experimental receive13 buffers, independently owned and device-disjoint."""
import hashlib,json,struct
from pathlib import Path
from owned_gpu_layout import PAGE,validate
SPECS=[('receive13_state_a',0x30),('receive13_aux',0x4800),
       ('receive13_state_b',0x1b0),('receive13_ring',0x28800)]
def extend(arena,receipt):
 evidence=Path(__file__).resolve().parents[2]/'docs/evidence/2026-10-08-private-receive13-layout.json'
 provenance=json.loads(evidence.read_text())
 if provenance['macho_sha256']!='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e' or provenance['receive13_extents']!=[size for _,size in SPECS] or provenance['receive13_main_offset']!='0x1c0':
  raise ValueError('Receive13 provenance changed')
 if len(arena)!=54*PAGE or 'receive14_fixture' not in receipt:raise ValueError('Require receive14 fixture first')
 pages=validate(arena,receipt);data=bytearray(arena);base=int(receipt['base'],16)
 device_pages={leaf['gpu_va'] for leaf in receipt['mmio_leaves']}
 main=next(o for o in receipt['objects'] if o['name']=='main')['arena_offset']
 if any(data[main+0x1c0:main+0x1e0]):raise ValueError('Receive13 already populated')
 addresses=[];address=pages[-1]+PAGE
 for i,(name,size) in enumerate(SPECS):
  offset=len(data);reserved=(size+PAGE-1)//PAGE*PAGE
  # Find a wholly contiguous GPU span, jumping past occupied device leaves.
  while conflicts:=device_pages.intersection(range(address,address+reserved,PAGE)):
   address=max(conflicts)+PAGE
  if address+reserved> ((base>>25)+1)<<25:raise ValueError('Receive13 exceeds root L2')
  data.extend(bytes(reserved));pages.extend(range(address,address+reserved,PAGE));addresses.append(address)
  receipt['objects'].append(dict(name=name,arena_offset=offset,gpu_va=hex(address),input_bytes=size,reserved_bytes=reserved,
   input_sha256=hashlib.sha256(bytes(size)).hexdigest(),layout_evidence='matching25G83 private receive13 allocation/mapping sites',complete_extent_qualified=False))
  struct.pack_into('<Q',data,main+0x1c0+i*8,address)
  receipt['pointers'].append(dict(parent='main',byte_offset=0x1c0+i*8,target=name,target_byte_offset=0,width=8,encoded_gpu_va=hex(address)))
  address+=reserved
 for obj in receipt['objects']:
  start=obj['arena_offset'];obj['input_sha256']=hashlib.sha256(data[start:start+obj['input_bytes']]).hexdigest()
 receipt.update(arena_bytes=len(data),owned_page_vas=pages,mapped_pages=len(pages)+len(device_pages),arena_sha256=hashlib.sha256(data).hexdigest(),
  receive13_fixture=dict(index=13,main_offset='0x1c0',addresses=[hex(x) for x in addresses],extents=[size for _,size in SPECS],
   evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),qualification='Four independent zero buffers with static private extents/positions. Internal contents, roles, event production and readiness unverified; receive15/16 unchanged. Sparse owned GPU pages avoid device VA ranges; no jobs.'))
 if len(pages)!=69:raise ValueError('Wrong receive13 page count')
 validate(data,receipt)
 return data,receipt
