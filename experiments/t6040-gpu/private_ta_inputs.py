#!/usr/bin/env python3
"""Numeric TA descriptor loaders; resource services remain external."""
import struct
from private_render_inputs import copies,load_parameter_management,load_render_target,U64

def load_ta_parameter_management(original,source,vector_a,vector_b,getter_values):
    out=bytearray(load_parameter_management(original,source,vector_a,vector_b,getter_values))
    index=struct.unpack_from('<I',source,0x2c)[0]
    for dst,value in [(0x1228,vector_a[index]),(0x1230,vector_b[index]),*zip((0x1238,0x1240,0x1248),getter_values)]:struct.pack_into('<Q',out,dst,value&U64)
    out[0x1250:0x1258]=source[0xb8:0xc0];out[0x1258:0x125c]=source[0x1d4:0x1d8];out[0x1268:0x126c]=source[0x2c:0x30]
    return bytes(out)

def load_ta_render_target(original,source,service):
    """service(resource, slot) returns independent addresses in actual call order."""
    out=bytearray(original)
    def get(off,size=8):return int.from_bytes(source[off:off+size],'little')
    def put(off,value,size=8):out[off:off+size]=(value&((1<<(size*8))-1)).to_bytes(size,'little')
    def mapped(dst,offset,resource='primary',slot=0x160,condition=None):
        put(dst,(service(resource,slot)+get(offset))&U64 if condition is None or get(condition) else 0)
    mapped(0x1160,0x2a8);put(0x1168,get(0x18,4),4)
    mapped(0x1148,0x218,'support',condition=0x1d8)
    put(0xe18,get(0x1c0));service('retain',0x20);put(0xe20,get(0x218))
    mapped(0x1150,0x218,'support',0x158,0x1d8);put(0x1170,get(0x1d8));put(0x1158,get(0x28,4),4)
    mapped(0x1178,0x2b0);put(0x1180,get(0x98,4),4);mapped(0x1188,0x2b8)
    out=copies(out,source,[(0x11f0,0xf0,16),(0x1200,0x100,16),(0x1210,0x110,4),(0x11d8,0xd8,16),(0x11e8,0xe8,8)])
    if get(0x3c,4)>=2:
        for dst,src,condition in [(0x1190,0x220,0x1e0),(0x1198,0x228,0x1e8),(0x11a0,0x230,0x1f0),(0x11b0,0x238,0x1f8),(0x11b8,0x240,0x200),(0x11c0,0x248,0x208),(0x11d0,0x250,0x210)]:mapped(dst,src,'support',condition=condition)
        put(0x11a8,get(0x2c,4),4);put(0x11c8,get(0x38,4),4)
    bases=[service('primary',0x158) for _ in range(3)]
    return load_render_target(out,source,bases)
