# SPDX-License-Identifier: GPL-2.0-only
"""Offline post-unload table checks for the exact structural graph experiment."""
import re,struct
BASE=0x105fff78000
ROOT=0xfffffc2000100000
MASK=((1<<42)-1)&~0x3fff

def last_allocation(log,count):
 records=[(int(i),int(pa,16)) for i,pa in re.findall(r'owned page (\d+) physical=(0x[0-9a-f]+)',log)]
 records=records[-count:]
 if [i for i,_ in records]!=list(range(count)):raise ValueError('Incomplete final owned allocation group')
 pages=[pa for _,pa in records]
 if len(set(pages))!=count or any(not pa or pa&~MASK for pa in pages):raise ValueError('Invalid owned physical page set')
 return pages

def check(table,l2,baseline,log,object_pages):
 if len(table)!=0x40000 or len(baseline)!=0x40000 or len(l2)!=0x4000:raise ValueError('Wrong reserved table extent')
 pages=last_allocation(log,object_pages+2)
 refs=[hex(word) for blob in (table,l2) for (word,) in struct.iter_unpack('<Q',blob) if word&3==3 and word&MASK in pages]
 def word(offset):return struct.unpack_from('<Q',table,offset)[0]
 path=(not ((word(0)^((BASE+0x4000)|3))&~(1<<10)) and
       not ((word(0x4000)^((BASE+0x8000)|3))&~(1<<10)) and
       word(0x8000)&3==3 and word(0x8000)&MASK==0x10000be4000 and
       word(0x8000+24*8)&3==3 and word(0x8000+24*8)&MASK==0x10001d44000 and
       word(((ROOT>>36)&63)*8) in (0,0x200105fff744cb))
 # RTKit sleep may clear the firmware's top-level GPU root entry. Accept
 # only that exact removal from a warm baseline, with TEXT/DATA unchanged.
 root_offset=((ROOT>>36)&63)*8
 adjusted=bytearray(baseline)
 if word(root_offset)==0:struct.pack_into('<Q',adjusted,root_offset,0)
 preserved=path and (table==baseline or table==adjusted or not any(baseline))
 return dict(owned_page_count=len(pages),owned_page_references=refs,reserved_l2_zero=not any(l2),
             loader_root_preserved=preserved,loader_text_data_path_qualified=path,
             gpu_root_after=hex(word(((ROOT>>36)&63)*8)),
             post_unload_verified=not refs and not any(l2) and preserved)
