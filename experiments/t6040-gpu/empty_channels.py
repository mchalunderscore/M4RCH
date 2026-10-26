# SPDX-License-Identifier: GPL-2.0-only
"""Experimental empty RAM cursors. Not real hardware work-channel state."""
import hashlib,struct
PAGE=0x4000
COUNT=13  # Twelve work records and one control record; receive channels unqualified.
def extend(arena,receipt,leaves):
 data=bytearray(arena);base=int(receipt['base'],16)
 main=next(o for o in receipt['objects'] if o['name']=='main')['arena_offset']
 records=[]
 for i in range(COUNT):
  offset=len(data);state=base+offset;ring=state+PAGE
  data.extend(bytes(2*PAGE))
  for kind,start,size in [('cursor',offset,24),('ring',offset+PAGE,PAGE)]:
   receipt['objects'].append({'name':f'channel_{i}_{kind}','arena_offset':start,'gpu_va':hex(base+start),
      'input_bytes':size,'reserved_bytes':PAGE,'input_sha256':hashlib.sha256(data[start:start+size]).hexdigest(),
      'layout_evidence':'experimental-empty-RAM-channel','complete_extent_qualified':False})
  field=0x20+i*0x20
  values=(state,state+8,state+16,ring)
  struct.pack_into('<4Q',data,main+field,*values)
  records.append({'index':i,'main_offset':hex(field),'cursors':[hex(x) for x in values[:3]],'ring':hex(ring),'ring_bytes':PAGE})
  for j,(kind,delta) in enumerate([('cursor',0),('cursor',8),('cursor',16),('ring',0)]):
   receipt['pointers'].append({'parent':'main','byte_offset':field+j*8,'target':f'channel_{i}_{kind}',
       'target_byte_offset':delta,'width':8,'encoded_gpu_va':hex(values[j])})
 if len(data)!=47*PAGE or base+len(data)>min(v['gpu_va'] for v in leaves):raise ValueError('Empty-channel arena geometry/overlap')
 receipt.update(arena_bytes=len(data),empty_channel_fixture=records,
   channel_qualification='Zero RAM cursor fixtures for structural startup only; not hardware-backed work cursors, production ring capacity or command submission. Channels13..16 remain unchanged/unqualified.')
 return data,receipt
