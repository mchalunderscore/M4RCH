# SPDX-License-Identifier: GPL-2.0-only
"""Numeric completion-ring observations from matching firmware, never MMIO access."""
import struct

STATUS_BASE=0x21168
ACK_BASE=STATUS_BASE+0x20

def describe(descriptor,status):
 if len(descriptor)!=32 or type(status) is not int or not 0<=status<1<<64:
  raise ValueError('Require32-byte descriptor and u64 status')
 device,firmware,capacity,stride,index,cursor=struct.unpack('<QQIIII',descriptor)
 if not device:return dict(present=False)
 # Firmware loads the u64 register into a W register before splitting it.
 head=status&0xffff;count=(status>>16)&0xffff
 if not 1<=capacity<=0xffff or stride!=64 or index>=4 or max(head,cursor)>=capacity or count>capacity:
  raise ValueError('Completion geometry/status outside monitored contract')
 return dict(present=True,device_address=device,firmware_address=firmware,
             capacity=capacity,stride=stride,index=index,cursor=cursor,
             hardware_head=head,available=count,next_cursor=(cursor+count)%capacity,
             status_register_offset=STATUS_BASE+8*index,
             acknowledgement_register_offset=ACK_BASE+8*index,
             cursor_agrees_with_head=cursor==head,
             entry_offsets=[((cursor+i)%capacity)*stride for i in range(count)],
             invalidate_ranges=([(0,capacity*stride),(cursor*stride,0),(0,0)] if count==capacity else
                                [(cursor*stride,min(count,capacity-cursor)*stride),
                                 (0,max(0,count-(capacity-cursor))*stride)] if count else []))

def decode_entry(entry):
 """Observed fields consumed by12788; names deliberately remain neutral."""
 if len(entry)!=64:raise ValueError('Require64-byte completion entry')
 q=struct.unpack('<8Q',entry);word=q[0]
 return dict(raw_words=[hex(v) for v in q],low_kind=word&7,
             phase=(word>>4)&3,mode=(word>>6)&3,queue_id=(word>>9)&127,
             epoch=((word>>16)&0xffffffff)<<8|((word>>48)&255),
             metadata_offset=(word>>39)&0x1fe00,
             masked_word20=q[4]&0x3fffffffffffff,
             masked_word28=q[5]&0x3fffffffffffff,
             pointer30=q[6]&~1,flag30=q[6]&1,pointer38=q[7],
             qualification='Observed firmware field extraction only; not a completed-job identity or valid retirement proof')
