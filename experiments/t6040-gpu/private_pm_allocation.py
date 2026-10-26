#!/usr/bin/env python3
"""Numeric PM allocation prelude; actual allocation/lock/state services external."""
import struct
U32=(1<<32)-1

def allocation_prelude(original,gpu,device,queue_config,gpu_address,shared_address,results,memory):
 b=bytearray(original);w=lambda off:struct.unpack_from('<I',gpu,off)[0]
 capacity=w(0xf528) or w(0x718);state_count=w(0xf52c) or w(0x71c)
 if capacity>=1<<31:raise ValueError('negative native slot capacity')
 for off,value,size in [(0x10,gpu_address,8),(0x18,shared_address,8),(0x60,state_count,4),(0x48,U32,4),(0x228,0,8),(0x28,1,1),(0x6c,0,4),(0x2c,0,4),(0x128,0,4),(0x138,0,8),(0x140,struct.unpack_from('<I',original,0x148)[0],4),(0x170,results['lock_a'],8),(0x178,results['lock_b'],8),(0x190,0,8),(0x218,0,4),(0x130,results['main_lock'],8),(0x148,(memory>>17)&U32,4),(0x88,results['vector_b'],8),(0xa8,results['vector_a'],8),(0xb0,capacity,4),(0xd0,results['state_array'],8),(0x198,results['manager_array'],8),(0x1a0,results['manager_vector'],8)]:b[off:off+size]=value.to_bytes(size,'little')
 b[0x64:0x6c]=queue_config[0xc:0x14];b[0x118:0x120]=queue_config[0x28:0x30]
 for start,end in [(0x30,0x48),(0x50,0x60),(0x180,0x190)]:b[start:end]=bytes(end-start)
 b[0x1d8:0x208]=device[:0x30]
 return bytes(b),capacity,state_count,(memory>>17)&U32
