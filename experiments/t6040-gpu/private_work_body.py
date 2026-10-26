#!/usr/bin/env python3
"""Private-derived common work body; external setup and firmware execution excluded."""
import struct
from private_nop_body import convert_timestamp
from private_nop_header import advance_timestamp
MASK64=(1<<64)-1


def patch_work_body(record, timestamp, capacity, initial, queue_id, dependencies,
                    previous, qos, rce_kind, reglists, masks, auxiliary):
    if len(record)!=0x200 or len(dependencies)>8 or len(reglists)!=4 or len(masks)!=4:
        raise ValueError('Only fixture geometry and dependency counts 0..8 qualified')
    out=bytearray(record)
    def get(off):return struct.unpack_from('<Q',out,off)[0]
    def put(off,val):struct.pack_into('<Q',out,off,val&MASK64)
    for i,(event,idx,epoch) in enumerate(dependencies):
        converted=convert_timestamp(epoch,event,capacity,initial)
        put(0x28+8*i,(get(0x28+8*i)&0xffff800000000000)|converted|((idx&127)<<40))
        put(0x20,get(0x20)|(1<<i))
    i=len(dependencies)
    put(0x28+8*i,(get(0x28+8*i)&~((1<<47)-1))|(previous&((1<<47)-1))|((queue_id&127)<<40))
    word=get(0x20)|(1<<i)
    word=(word&~(255<<32))|((qos[0]&255)<<32)
    word=(word&~(31<<40))|((qos[2]&31)<<40)
    word=(word&~(65535<<48))|((qos[1]&65535)<<48)
    put(0x20,word);out[0x148]=rce_kind&3
    for off,(address,count) in zip((0x150,0x158,0x160,0x168),reglists):
        put(off,(get(off)&0xfffc000000000000)|((address>>5)&((1<<38)-1))|((count&127)<<43))
    for off,val in zip((0x128,0x130,0x138,0x140),masks):put(off,val)
    put(0x178,auxiliary)
    return bytes(out),advance_timestamp(timestamp,capacity)
