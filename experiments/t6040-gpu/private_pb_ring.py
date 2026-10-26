#!/usr/bin/env python3
"""Numeric G16 16-byte parameter-buffer descriptor ring updates."""
import struct
U32=(1<<32)-1
MASK=(1<<22)-1
def load_entry(original,state,saved):
 a,b,c,d=struct.unpack('<4I',original);s0,s1,s2,s3=struct.unpack('<4I',saved)
 address=struct.unpack_from('<Q',state,0x28)[0]
 hi=(((address+(0 if address&(1<<42) else 0x7000000000))&0x7000000000)|((address>>3)&0x8000000000))
 a=(((address>>4)&U32)&~7)|(a&7);a=(a&~1)|int(s3!=0)
 b=((hi>>8)&~((1<<28)-1))|(b&((1<<28)-1));b=(b&~MASK)|(struct.unpack_from('<I',state,0x34)[0]&MASK)
 c=(c&~MASK)|(s0&MASK);d=(d&~MASK)|(s1&MASK);d=(d&0x7fffffff)|((s2&1)<<31)
 return struct.pack('<4I',a,b&U32,c,d)
def store_entry(entry):
 a,b,c,d=struct.unpack('<4I',entry)
 return struct.pack('<4I',c&MASK,d&MASK,d>>31,a&1)
