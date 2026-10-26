"""Numeric models for checked SKU records; no shader or live execution semantics."""
import struct
MASK64=(1<<64)-1
# opcode: first/second stamp offsets, optional pair, optional2 pointer/value,
# control address and two native constant pointer offsets.
TIMESTAMP_LAYOUTS={
 0:(0x8fe,0x906,0x90e,0x91e,0x926,0x8f6,(0x95e,0x86a)),
 1:(0x2198,0x21a0,0x21a8,0x21b8,0x21c0,0x2190,(0x21f8,0x2104)),
 2:(0x948,0x950,0x958,0x968,0x970,0x93c,(0x9a8,0x91c)),
 3:(0xf7c,0xf84,0xf8c,0xf9c,0xfa4,0xf74,(0xfe4,0xf1c)),
}
def timestamp(record,command,index,gpu_base,state,begin):
 out=bytearray(record);struct.pack_into('<I',out,0,3|(0x80000000 if begin else 0))
 opcode=struct.unpack_from('<I',command)[0]
 if opcode not in TIMESTAMP_LAYOUTS:raise ValueError('unsupported command opcode')
 first,second,pair,optional,value,control,vec=TIMESTAMP_LAYOUTS[opcode]
 optional_pair=gpu_base+pair if any(struct.unpack_from('<2Q',command,pair)) else 0
 optional_pointer=gpu_base+optional if struct.unpack_from('<Q',command,value)[0] else 0
 fields=[(4,gpu_base+control),(0xc,gpu_base+first),(0x14,gpu_base+(first if begin else second)),
  (0x1c,state),(0x24,optional_pair),(0x2c,gpu_base+vec[0]),(0x34,gpu_base+vec[1]),
  (0x3c,optional_pointer),(0x44,index&0xffffffff)]
 for off,value in fields:struct.pack_into('<Q',out,off,value&MASK64)
 return bytes(out)

def startup(record,payload):
 out=bytearray(record);struct.pack_into('<I',out,0,7);out[4:0x1ec]=payload
 return bytes(out)

def wait_record(record,value,index,address,begin):
 out=bytearray(record);struct.pack_into('<3I',out,0,0x88000004 if begin else 0x08000004,value,index)
 struct.pack_into('<Q',out,0xc,address);return bytes(out)
