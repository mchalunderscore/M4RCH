#!/usr/bin/env python3
"""Private-derived G16 12-byte RCE entry patches, not a render register recipe."""
import struct


def encode_entry(original, register, flag, value):
    if len(original)!=12:raise ValueError('Expected 12-byte entry')
    old=struct.unpack_from('<I',original)[0]
    header=(old&0xfffc0006)|(register&0x3fff8)|(flag&1)
    return struct.pack('<IQ',header,value&((1<<64)-1))


def decode_entry(entry):
    header,value=struct.unpack('<IQ',entry)
    return header&0x3fff8,header&1,value


def rce_metadata(descriptor,command,constant):
    out=bytearray(descriptor)
    for off in (0x830,0x840,0x850,0x860):struct.pack_into('<H',out,off,0)
    for off in (0x838,0x848,0x858):struct.pack_into('<Q',out,off,0)
    for j in range(4):
        address=struct.unpack_from('<Q',command,0x7a0+j*0x720)[0]
        count=struct.unpack_from('<H',command,0x80 if j==0 else 0x7a8+j*0x720)[0]
        struct.pack_into('<Q',out,0x828+j*16,address);struct.pack_into('<H',out,0x830+j*16,count)
    struct.pack_into('<Q',out,0x820,constant)
    return bytes(out)
