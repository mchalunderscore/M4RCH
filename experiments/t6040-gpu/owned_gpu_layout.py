# SPDX-License-Identifier: GPL-2.0-only
"""Validate logical backing versus explicit GPU page addresses; no hardware."""
PAGE=0x4000

def validate(arena, receipt):
 base=int(receipt['base'],16)
 if len(arena)%PAGE or receipt['arena_bytes']!=len(arena):raise ValueError('Invalid arena extent')
 pages=receipt.get('owned_page_vas',[base+i*PAGE for i in range(len(arena)//PAGE)])
 if len(pages)!=len(arena)//PAGE or pages[0]!=base:raise ValueError('Wrong owned GPU page count/root')
 if any(type(va) is not int or va%PAGE or va>>25!=base>>25 for va in pages):raise ValueError('Owned address outside root L2')
 if len(set(pages))!=len(pages):raise ValueError('Duplicate owned GPU page')
 devices={leaf['gpu_va'] for leaf in receipt.get('mmio_leaves',[])}
 if set(pages)&devices:raise ValueError('Owned/device GPU page collision')
 covered=set()
 objects={o['name']:o for o in receipt['objects']}
 for obj in objects.values():
  offset=obj['arena_offset'];size=obj['reserved_bytes'];va=int(obj['gpu_va'],16)
  if offset%PAGE or size%PAGE or not 0<obj['input_bytes']<=size or offset+size>len(arena):raise ValueError('Invalid owned object span')
  indices=range(offset//PAGE,(offset+size)//PAGE)
  if covered.intersection(indices):raise ValueError('Overlapping logical owned objects')
  covered.update(indices)
  if [pages[i] for i in indices]!=[va+i*PAGE for i in range(size//PAGE)]:raise ValueError('Object GPU span not contiguous')
 if covered!=set(range(len(pages))):raise ValueError('Unaccounted owned backing')
 for edge in receipt['pointers']:
  parent=objects[edge['parent']];target=objects[edge['target']];off=edge['byte_offset'];target_off=edge.get('target_byte_offset',0)
  if edge['width']!=8 or not 0<=off<=parent['input_bytes']-8 or not 0<=target_off<target['input_bytes']:raise ValueError('Pointer outside qualified object extent')
  import struct
  encoded=struct.unpack_from('<Q',arena,parent['arena_offset']+off)[0]
  if encoded!=int(edge['encoded_gpu_va'],16) or encoded!=int(target['gpu_va'],16)+target_off:raise ValueError('Owned pointer disagrees with mapping')
 return pages

def map_emulator(machine, arena, receipt):
 for i,va in enumerate(validate(arena,receipt)):
  machine.mem_map(va,PAGE)
  machine.mem_write(va,bytes(arena[i*PAGE:(i+1)*PAGE]))
