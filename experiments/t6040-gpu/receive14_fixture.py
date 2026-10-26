# SPDX-License-Identifier: GPL-2.0-only
"""Experimental receive14 backing from matching private AGX allocation sites.

Descriptor pointer positions and extents are static observations; zero contents
and notification behavior remain hypotheses. Never assume three RAM cursors.
"""
import hashlib,json,struct
from pathlib import Path
PAGE=0x4000
SPECS=[('receive14_state_a',0x30),('receive14_aux',0x9000),
       ('receive14_state_b',0x30),('receive14_ring',0x4800)]
def extend(arena,receipt):
 evidence=Path(__file__).resolve().parents[2]/'docs/evidence/2026-10-08-private-receive-layout.json'
 provenance=json.loads(evidence.read_text())
 if provenance['macho_sha256']!='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e' or provenance['receive14_extents']!=[size for _,size in SPECS]:
  raise ValueError('Receive14 provenance changed')
 if len(arena)!=47*PAGE:raise ValueError('Require original47-page graph')
 data=bytearray(arena);base=int(receipt['base'],16)
 main=next(o for o in receipt['objects'] if o['name']=='main')['arena_offset']
 if any(data[main+0x1e0:main+0x200]):raise ValueError('Receive14 already populated')
 addresses=[]
 for i,(name,size) in enumerate(SPECS):
  offset=len(data);reserved=(size+PAGE-1)//PAGE*PAGE;data.extend(bytes(reserved));address=base+offset;addresses.append(address)
  receipt['objects'].append(dict(name=name,arena_offset=offset,gpu_va=hex(address),input_bytes=size,reserved_bytes=reserved,
   input_sha256=hashlib.sha256(bytes(size)).hexdigest(),layout_evidence='matching25G83 private receive14 allocation/mapping sites',complete_extent_qualified=False))
  struct.pack_into('<Q',data,main+0x1e0+i*8,address)
  receipt['pointers'].append(dict(parent='main',byte_offset=0x1e0+i*8,target=name,target_byte_offset=0,width=8,encoded_gpu_va=hex(address)))
 if len(data)!=54*PAGE or base+len(data)>min(v['gpu_va'] for v in receipt['mmio_leaves']):
  raise ValueError('Receive14 extent overlaps device mappings')
 for o in receipt['objects']:
  start=o['arena_offset'];o['input_sha256']=hashlib.sha256(data[start:start+o['input_bytes']]).hexdigest()
 receipt.update(arena_bytes=len(data),mapped_pages=len(data)//PAGE+len(receipt['mmio_leaves']),
  receive14_fixture=dict(index=14,main_offset='0x1e0',addresses=[hex(x) for x in addresses],extents=[size for _,size in SPECS],
   evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),qualification='Four independently owned zero buffers, private static extents/positions. Internal content, pointer roles, event production and complete initialization unverified. Receive13/15/16 unchanged; no jobs staged.'),
  arena_sha256=hashlib.sha256(data).hexdigest())
 return data,receipt
