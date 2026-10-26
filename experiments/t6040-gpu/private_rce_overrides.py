#!/usr/bin/env python3
"""Private native RCE override table behavior; not public cleanroom material."""
import struct
from private_rce_entry import encode_entry,decode_entry
MASK64=(1<<64)-1

def apply_overrides(backing,rows):
    out=bytearray(backing)
    count=struct.unpack_from('<H',out,0x708)[0]
    patches=[]
    for mask,value,register in rows:
        for index in range(count):
            offset=(index*12)&0xfffc
            if offset+12>len(out):raise ValueError('entry outside fixture backing')
            entry=bytes(out[offset:offset+12]);reg,flag,old=decode_entry(entry)
            if reg==register:
                new=((old&(~mask&MASK64))|(value&mask))&MASK64
                out[offset:offset+12]=encode_entry(entry,reg,flag,new)
                patches.append((index,register,new))
    return bytes(out),patches

def append_native(backing,register,flag,value):
    out=bytearray(backing);count,cursor=struct.unpack_from('<HH',out,0x708)
    if cursor+12>len(out):raise ValueError('append outside fixture backing')
    out[cursor:cursor+12]=encode_entry(out[cursor:cursor+12],register,flag,value)
    cursor,count=struct.unpack_from('<HH',out,0x70a)[0],struct.unpack_from('<H',out,0x708)[0]
    struct.pack_into('<H',out,0x70a,(cursor+12)&0xffff)
    struct.pack_into('<H',out,0x708,(count+1)&0xffff)
    return bytes(out)
