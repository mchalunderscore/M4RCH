#!/usr/bin/env python3
"""Numeric concrete PM scene setup, with allocations/mappings explicit."""
import struct
U64=(1<<64)-1
U32=(1<<32)-1
def scene_setup(pm,gpu,config,scenes,results,block_ids,resource_map,memory_fallback):
 p=bytearray(pm);cfg=bytearray(config);out=bytearray(scenes)
 q=lambda off:struct.unpack_from('<Q',pm,off)[0]
 w=lambda off:struct.unpack_from('<I',pm,off)[0]
 gq=lambda off:struct.unpack_from('<Q',gpu,off)[0]
 gw=lambda off:struct.unpack_from('<I',gpu,off)[0]
 memory=gq(0x11188) or memory_fallback
 units=(((memory+0x7fff)&U64)>>15)
 units=((q(0x1e8)+units-1)&U64)//q(0x1e8)
 groups=gw(0x4e4)
 if groups>=2 and w(0x68):units=(units+((groups+(groups<<(w(0x64)&31)))&U32))&U64
 stride=(((q(0x1f0)+q(0x1f8)*units+q(0x200)-1)&U64)&(-q(0x200)&U64))
 total=(stride*w(0x60))&U64;extra=bool(gpu[0xed48]&1)
 for off,val,n in [(0x250,0,4),(0x248,results['block_alloc'],8),(0x138,(q(0x138)+len(block_ids)*0x20000)&U64,8),(0x58,results['resource'],8),(0x220,results['scene_alloc'],8),(0x240,results['discard_resource'],8)]:p[off:off+n]=val.to_bytes(n,'little')
 cfg[:12]=bytes(12)
 for j in range(gw(0xf528) or gw(0x718)):
  off=j*0x80
  for dst,value,n in [(0x10,0,16),(0x20,0,8),(0x28,(resource_map+stride*(j%w(0x60)))&U64,8),(0x40,q(0xa0),8)]:out[off+dst:off+dst+n]=value.to_bytes(n,'little')
  if extra:struct.pack_into('<Q',out,off+0x30,(resource_map+total)&U64)
 return bytes(p),bytes(cfg),bytes(out),stride,(total+(stride if extra else 0))&U64
