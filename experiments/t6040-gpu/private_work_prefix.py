#!/usr/bin/env python3
"""Private-derived common G16 work-kick prefix, not a full rendering command."""
import struct
MASK64=(1<<64)-1


def patch_work_prefix(record, timestamp, queue_id, priority, aperture_address, aperture_index,
                      aperture_count, alternate_kind, extra_flag, payload):
    if len(record)!=0x200 or len(payload)!=2:raise ValueError('Invalid fixture geometry')
    out=bytearray(record)
    def get(off):return struct.unpack_from('<Q',out,off)[0]
    def put(off,val):struct.pack_into('<Q',out,off,val&MASK64)
    if aperture_count & 0xffffffff:
        word=(get(8)&~63)|(aperture_index&63)
        word &= 0xfffe00000000003f
        word=(word&~(((1<<38)-1)<<6))|(((aperture_address>>5)&((1<<38)-1))<<6)
        word=(word&0xf03fffffffffffff)|(((aperture_count-1)&63)<<54)
        put(8,word)
    header=(get(0)&~3)|(2 if alternate_kind else 0)
    header=(header&0xf800000000000003)|((timestamp&((1<<47)-1))<<2)|((queue_id&127)<<42)
    if aperture_count & 0xffffffff:header|=1<<58
    header=(header&0xc401fffffffffffe)|((priority&3)<<59)|((1<<61) if extra_flag else 0)
    put(0,header);put(0x10,payload[0]);put(0x18,payload[1])
    return bytes(out)
