#!/usr/bin/env python3
"""Numeric descriptor initialization after explicit external service fixtures."""
import struct
MASK=0xfffff000003fffff
TA_ZERO=[(0xc4c,0xd0d),(0x1148,0x1218),(0x121c,0x1270),(0xff0,0x1142),(0x1288,0x13c0),(0x13c8,0x13e8),(0xd98,0xda0),(0xe68,0xff0)]
THREED_ZERO=[(0x210,0x2d1),(0x808,0x820),(0x868,0x878),(0x888,0x89c),(0x8a0,0x900),(0x904,0x950),(0x4b0,0x800),(0x970,0xaa8),(0xab0,0xad0),(0x308,0x400),(0x404,0x4a0)]
def init_3d(original,address,payload,payload_size,debug,queue_value,resource_root):
 b=bytearray(original)
 for start,end in THREED_ZERO:b[start:end]=bytes(end-start)
 for off,val,size in [(0x1b0,payload_size,8),(0x1b8,debug,8),(0x160,queue_value,8),(0x168,0,8),(0x138,resource_root+0x90,8),(0x900,0xffffffff,4),(0x144,0xffffffff,4),(0x1c1,0x101,2),(0x400,1,4),(0x408,address+0x210,8),(0x410,2,4),(0xc40,1,4),(0x2d4,0xffffffff,4)]:b[off:off+size]=(val&((1<<(8*size))-1)).to_bytes(size,'little')
 # payload is passed through the external inherited service; no visible copy here.
 struct.pack_into('<Q',b,0xc38,struct.unpack_from('<Q',original,0xc38)[0]&MASK)
 return bytes(b)
def init_ta(original,address,allocation):
 b=bytearray(original)
 for start,end in TA_ZERO:b[start:end]=bytes(end-start)
 for off,val,size in [(0x1218,0xffffffff,4),(0x1274,0xffffffff,4),(0x144,0xffffffff,4),(0xe28,0xffffffff,4),(0xe10,allocation,8),(0xf68,address+0xc4c,8),(0xf70,2,4)]:b[off:off+size]=val.to_bytes(size,'little')
 struct.pack_into('<Q',b,0x14d0,struct.unpack_from('<Q',original,0x14d0)[0]&MASK)
 return bytes(b)
