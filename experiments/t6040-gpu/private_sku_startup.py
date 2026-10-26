"""Checked startup payload numeric construction; provider returns explicit inputs."""
import struct
M64=(1<<64)-1

def build(stack,descriptor,command,gpu_command,pm_gpu,state,resource_type,resource_map,context,config,feature):
    out=bytearray(stack);out[0x80:0x268]=bytes(0x1e8)
    q=lambda data,off:struct.unpack_from('<Q',data,off)[0]
    w=lambda data,off:struct.unpack_from('<I',data,off)[0]
    def put(off,value,width=8):struct.pack_into('<'+{1:'B',2:'H',4:'I',8:'Q'}[width],out,off,value&((1<<(width*8))-1))
    put(0x2c,0,4)
    fw_state=q(stack,0x78)+8
    for dest,value in [(0x90,gpu_command+0xa0),(0x98,pm_gpu),(0xa0,fw_state),
      (0xa8,gpu_command+0x20f0),(0xb0,pm_gpu+0x54),(0xb8,gpu_command+0x2130),
      (0xc0,gpu_command+0x2134),(0xc8,state),(0xd0,gpu_command),
      (0xf8,gpu_command+0x1fd8),(0x100,gpu_command+0x2178),(0x11c,q(stack,0x70)),
      (0x22c,q(descriptor,0xb70)),(0x234,q(descriptor,0xb80)),
      (0x244,resource_map+w(descriptor,0xb98)),(0x254,q(command,4))]:put(dest,value)
    secondary=(descriptor[0xc48]&1) if config&1 else 0
    for dest,value in [(0xd8,w(command,0xc)),(0xdc,resource_type),(0xe0,context),
      (0xe4,w(descriptor,0x900)),(0xe8,descriptor[0x897]&1),(0xec,w(descriptor,0x140)),
      (0xf0,w(command,0x2158)),(0xf4,descriptor[0xb48]&1),(0x108,descriptor[0x895]&1),
      (0x10c,descriptor[0x894]&1),(0x110,secondary),(0x118,int(descriptor[0x960]==2)),
      (0x23c,w(descriptor,0xb88)),(0x25c,w(command,0x2154))]:put(dest,value,4)
    put(0x24c,feature&1,1);put(0x24d,0,1);put(0x260,descriptor[0xc44],1)
    # Auxiliary saves outside payload, used by later end-record construction.
    for dest,value in [(0x30,gpu_command+0x2130),(0x38,pm_gpu),(0x40,gpu_command+0x1fd8),
      (0x48,gpu_command+0x2134),(0x50,gpu_command+0x20f0),(0x58,fw_state),(0x68,state)]:put(dest,value)
    count=w(descriptor,0xa70)
    if not 0<=count<=24:raise ValueError('fixture supported range; not a proved protocol maximum')
    if count:put(0x224,count,4)
    for i in range(count):
        src=0x970+i*16;dst=0x124+i*16
        out[dst:dst+8]=descriptor[src:src+8];out[dst+8:dst+12]=descriptor[src+8:src+12]
        out[dst+12]=descriptor[src+12]
        out[dst+14:dst+16]=descriptor[src+14:src+16]
    return bytes(out),secondary
