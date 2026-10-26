#!/usr/bin/env python3
"""Private-derived G16 render input copies and fast-target numeric geometry."""
import struct
U32=(1<<32)-1;U64=(1<<64)-1
RTM_COPIES=[(0x8c0,0x20,8),(0x8c8,0xb8,4),(0x8b8,0xb0,8),(0x8d0,0xbc,4),(0x8d4,0x114,4),(0x8d8,0xc0,4),(0x8dc,0xc4,4),(0x8e0,0xc8,4),(0x8e4,0xcc,4),(0x8e8,0xd0,4),(0x8ec,0xd4,4),(0x8f0,0x98,4),(0x8f4,0x18,4),(0x8f8,0x118,4)]
FAST_COPIES=[(0x8c8,0x78,4),(0x8b8,0x70,8),(0x8cc,0x98,4),(0x8d0,0x7c,4),(0x8d8,0x80,4),(0x8dc,0x84,4),(0x8e0,0x88,4),(0x8e4,0x8c,4),(0x8e8,0x90,4),(0x8ec,0x94,4)]

def copies(original,source,fields):
    out=bytearray(original)
    for dst,src,size in fields:out[dst:dst+size]=source[src:src+size]
    return out

def load_render_target(original,source,mapped):
    if len(mapped)!=3:raise ValueError('three independent map returns required')
    out=copies(original,source,RTM_COPIES)
    for dst,src,base in zip((0x8a0,0x8a8,0x8b0),(0x2a8,0x2b0,0x2b8),mapped):
        struct.pack_into('<Q',out,dst,(struct.unpack_from('<Q',source,src)[0]+base)&U64)
    return bytes(out)

def load_fast_target(original,source):return bytes(copies(original,source,FAST_COPIES))

def load_parameter_management(original,source,vector_a,vector_b,getter_values):
    index,capacity=struct.unpack_from('<I',source,0x2c)[0],struct.unpack_from('<I',source,0xb0)[0]
    pointer=struct.unpack_from('<Q',source,0xa8)[0]
    span=capacity*8 if pointer else 0
    if span>=1<<32:raise ValueError('span overflow')
    if index*8>=1<<31:raise ValueError('signed index guard')
    if index*8+8>span:raise ValueError('index outside span')
    out=bytearray(original)
    for dst,value in [(0x910,vector_a[index]),(0x918,vector_b[index]),*zip((0x920,0x928,0x930),getter_values)]:struct.pack_into('<Q',out,dst,value&U64)
    out[0x938:0x940]=source[0xb8:0xc0];out[0x948:0x94c]=source[0x1d4:0x1d8]
    return bytes(out)

def validate_render_info(info):
    x,y,samples=struct.unpack_from('<3I',info)
    return int(x<=16384 and y<=16384 and 1<=samples<=7)

def validate_fast_info(info):
    x,y,w,h=struct.unpack_from('<4I',info)
    return int(((x+w)&U32)<=16384 and ((y+h)&U32)<=16384)

def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]

def fast_geometry(original):
    out=bytearray(original);q=lambda off:struct.unpack_from('<I',original,off)[0]
    x,y,w,h=(q(off) for off in (0x10,0x14,0x18,0x1c))
    sx=int(q(0x68)==16);sy=int(q(0x6c)==16)
    tx=x>>5;ty=y>>5
    nx=(((((x+w+31)&U32)>>5)-tx)&U32)<<sx;nx&=U32
    ny=(((((y+h+31)&U32)>>5)-ty)&U32)<<sy;ny&=U32
    nx=max(nx,1);ny=max(ny,1)
    struct.pack_into('<I',out,0x98,(((tx<<sx)<<16)|(ty<<sy))&U32)
    struct.pack_into('<II',out,0x78,q(0x20),(ny&1023)|((nx&1023)<<16))
    packed=0;samples=q(0x20)
    if samples in (1,2,4,8):
        for i in range(samples*2):packed|=(q(0x24+i*4)<<(i*4))&U64
    struct.pack_into('<Q',out,0x70,packed)
    constant=struct.unpack('<f',struct.pack('<I',0x3fddb3d9))[0]
    for dst,extent in [(0x88,w),(0x8c,h)]:
        if extent:struct.pack_into('<f',out,dst,f32(constant/f32(extent)))
        else:struct.pack_into('<I',out,dst,0x38ddb3d7)
    return bytes(out)
