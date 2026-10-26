"""Numeric native TA primary SKU slice 89e72ec..89e775c, owned providers."""
import struct
MASK=(1<<64)-1
def q(b,o):return struct.unpack_from('<Q',b,o)[0]
def w(b,o):return struct.unpack_from('<I',b,o)[0]
def put(b,o,v,n=8):b[o:o+n]=(v&((1<<(n*8))-1)).to_bytes(n,'little')
def startup(command,descriptor,b):
 out=bytearray(0x1c8)
 for o,v in [(0x10,b['command_gpu']+0x60),(0x18,q(command,0x20)),(0x20,b['translated_state']),
 (0x28,b['fw_state']+4),(0x30,b['state']), (0x60,b['command_gpu']+0x7b2),(0x68,b['command_gpu']+0x8de),
 (0x78,b['counter']), (0x38,b['command_gpu']+0x88a), (0x1b4,q(command,4)),
 (0x18c,q(descriptor,0x1408)),(0x194,q(descriptor,0x1418)),(0x1a4,b['resource_map']+w(descriptor,0x1430))]:put(out,o,v)
 for o,v in [(0x40,w(command,0xc)),(0x44,b['resource_type']),(0x48,b['context_id']),
 (0x4c,w(descriptor,0x1218)),(0x50,descriptor[0x1138]&1),(0x54,w(descriptor,0x1270)),
 (0x58,w(command,0x8be)),(0x70,descriptor[0x113b]&1),(0x74,int(descriptor[0x960]==2)),
 (0x1bc,w(command,0x8ba)),(0x19c,w(descriptor,0x1420)),(0x1c0,descriptor[0x1141]&1),
 (0x5c,descriptor[0x1558]&1),(0x80,descriptor[0x1142]&1)]:put(out,o,v,4)
 out[0x1ac]=b['feature']&1
 count=w(descriptor,0x1388)
 if count>16:raise ValueError('Qualified count <=16')
 if count:put(out,0x184,count,4)
 for i in range(count):
  src=0x1288+i*16;dst=0x84+i*16
  out[dst:dst+12]=descriptor[src:src+12];out[dst+12]=descriptor[src+12];out[dst+14:dst+16]=descriptor[src+14:src+16]
 return bytes(out)
def end(command,descriptor,b,relative):
 out=bytearray(0x94);put(out,0,6,4)
 for o,v in [(4,b['translated_state']),(0xc,q(command,0x20)),(0x14,b['fw_state']+4),
 (0x1c,b['state']),(0x24,b['command_gpu']+0x88a),(0x34,b['command_gpu']+0x7b2),
 (0x40,b['counter']),(0x48,q(command,0x8ae)),(0x78,b['stream_fw']+4+0x18c),
 (0x85,b['command_gpu']+0x94e)]:put(out,o,v)
 for o,v in [(0x2c,w(command,0xc)),(0x30,descriptor[0x1138]&1),(0x3c,descriptor[0x113b]&1),
 (0x50,w(command,0x8b6)),(0x80,-relative)]:put(out,o,v,4)
 has=w(descriptor,0x1388)!=0 or any(descriptor[0x1390:0x13b0])
 if has:out[0x58:0x78]=descriptor[0x1390:0x13b0]
 out[0x84]=int(has)|((b['channel_config']&3)<<2);out[0x8d]=descriptor[0x15c0]
 return bytes(out)
def stream(initial,command,descriptor,b):
 from private_sku_records import timestamp
 out=bytearray(initial);out[:0x1cc]=struct.pack('<I',5)+startup(command,descriptor,b);off=0x1cc
 if not descriptor[0x1138]&1:
  for begin in (True,False):out[off:off+0x4c]=timestamp(out[off:off+0x4c],command,b['timestamp_index'],b['command_gpu'],b['state'],begin);off+=0x4c
 out[off:off+0x94]=end(command,descriptor,b,off);off+=0x94
 put(out,off,0x40000002,4);off+=4
 cmd=bytearray(command);put(cmd,0x790,b['stream_fw']);put(cmd,0x798,(off+63)&~63,4)
 return bytes(out),bytes(cmd),off
