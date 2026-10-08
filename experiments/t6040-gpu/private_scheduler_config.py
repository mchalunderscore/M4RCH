#!/usr/bin/env python3
"""Partial native scheduler-config patch; callback values supplied, no hardware."""
import struct


def patch_config(original, header_constant, vector_constant, queue_pair, queue_id,
                 priority, descriptor_id, descriptor_flags, callback_values):
    if len(original) < 0x86 or len(vector_constant) != 16:
        raise ValueError('Invalid prefix/constant extent')
    out = bytearray(original)
    struct.pack_into('<Q', out, 0, header_constant)
    struct.pack_into('<QQ', out, 8, *queue_pair)
    struct.pack_into('<H', out, 0x18, queue_id & 0xffff)
    struct.pack_into('<I', out, 0x1a, descriptor_flags[1] & 1)
    struct.pack_into('<I', out, 0x1e, priority & 0xffffffff)
    for offset, value in [(0x22,callback_values[0]),(0x26,0),(0x32,descriptor_id),(0x46,0xffffffff),(0x62,descriptor_flags[0]&1),(0x66,callback_values[1]),(0x6a,0)]:
        struct.pack_into('<I',out,offset,value&0xffffffff)
    for offset in [0x2a,0x4a,0x52,0x5a]:struct.pack_into('<Q',out,offset,0)
    out[0x36:0x46]=vector_constant
    out[0x6e:0x7e]=vector_constant
    struct.pack_into('<Q',out,0x7e,0xffffffffffffffff)
    return bytes(out)
