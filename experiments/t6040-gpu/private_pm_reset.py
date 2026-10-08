#!/usr/bin/env python3
"""Numeric PM reset updates with external mappings supplied explicitly."""
import struct
U32=(1<<32)-1

def reset_hw(manager,pm,state,counter,map_first,translated,map_second,map_config,support_count):
 m=bytearray(manager);s=bytearray(state);ct=bytearray(counter)
 q=lambda off:struct.unpack_from('<Q',pm,off)[0]
 w=lambda off:struct.unpack_from('<I',pm,off)[0]
 for off,val,size in [(0x38,w(0x148),4),(0x3c,0,8),(0x44,q(0xc0),8),(0x4c,q(0xc8),8),(0x20,translated,8),(0x28,map_second,8),(0x30,support_count&U32,4),(0x34,0,4),(0x54,U32,4),(0x58,q(0x70)&U32,4),(0x5c,0,8),(0x64,struct.unpack_from('<Q',manager,0x60)[0],8),(0,0,8),(0x6c,0,16),(0x8c,0,4),(0x14,0,8),(0x7c,(w(0x15c)<<2)&U32,4),(0x80,(w(0x154)<<2)&U32,4),(0x84,map_config,8),(0x10,w(0x1d4),4)]:s[off:off+size]=val.to_bytes(size,'little')
 m[0x34:0x44]=bytes(16);ct[:4]=bytes(4)
 # map_first feeds the external translator; it is not directly stored.
 return bytes(m),bytes(s),bytes(ct)

def reset_pm(pm,config):
 p=bytearray(pm);cfg=bytearray(config)
 cfg[0x40:0x50]=bytes(16);struct.pack_into('<I',cfg,0x60,1);p[0x28]=1;struct.pack_into('<I',p,0x140,struct.unpack_from('<I',config,8)[0])
 return bytes(p),bytes(cfg)
