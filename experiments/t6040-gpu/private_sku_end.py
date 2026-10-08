"""Numeric models of checked 3D opcode8 records; not completion semantics."""
import struct
M64=(1<<64)-1

def end_record(record,stack,values,base,offset,cursor,vector,flags):
    out=bytearray(record)
    struct.pack_into('<I',out,0,8)
    qfields={4:values['index'],0xc:values['stamp'],0x1c:values['p1'],0x24:values['p2'],
      0x30:values['p3'],0x38:values['p4'],0x40:values['p5'],0x48:values['p6'],
      0x50:values['state'],0x58:values['command'],0x64:values['p7'],0x70:values['mode'],
      0x98:values['payload'],0xa5:values['control']}
    for off,value in qfields.items():struct.pack_into('<Q',out,off,value&M64)
    for off,value in [(0x14,values['wait']), (0x18,0),(0x2c,1),(0x60,values['context']),
       (0x6c,values['switch']), (0xa0,(offset+(base&0xffffffff)-(cursor&0xffffffff))&0xffffffff),
       (0xad,values['tail']), (0xb2,values['serial']), (0xb6,0)]:
        struct.pack_into('<I',out,off,value&0xffffffff)
    out[0x78:0x98]=vector
    out[0xa4]=flags&255;out[0xb1]=values['byte']&255
    struct.pack_into('<H',out,0xba,0)
    return bytes(out)

def primary(record,stack,command,descriptor,command_gpu,payload_gpu,mode,config,base,offset,cursor):
    q=lambda source,off:struct.unpack_from('<Q',source,off)[0]
    w=lambda source,off:struct.unpack_from('<I',source,off)[0]
    has_vector=bool(w(descriptor,0xa70) or any(struct.unpack_from('<4Q',descriptor,0xa78)))
    vector=descriptor[0xa78:0xa98] if has_vector else bytes(32)
    flags=int(has_vector)|((config&3)<<2)
    values=dict(index=q(stack,0x70),stamp=q(command,0x2148),wait=w(command,0x2150),
      p1=q(stack,0x38),p2=q(stack,0x60),p3=q(stack,0x58),p4=q(stack,0x30),
      p5=q(stack,0x48),p6=q(stack,0x50),state=q(stack,0x68),command=command_gpu,
      context=w(command,0xc),p7=q(stack,0x40),switch=descriptor[0x895]&1,mode=mode&0xffffffff,
      payload=payload_gpu+0x1ac,control=command_gpu+0x21e8,tail=w(descriptor,0xc40),
      byte=descriptor[0xc44],serial=w(command,0x2154))
    return end_record(record,stack,values,base,offset,cursor,vector,flags)

def secondary(record,stack,regs,vector,base,offset,cursor):
    q=lambda off:struct.unpack_from('<Q',stack,off)[0]
    w=lambda off:struct.unpack_from('<I',stack,off)[0]
    values=dict(index=q(0x70),stamp=regs[25],wait=regs[28],p1=regs[26],p2=q(0x60),
      p3=q(0x58),p4=regs[21],p5=q(0x48),p6=q(0x50),state=regs[23],command=regs[24],
      context=w(4),p7=q(0x40),switch=w(0x18),mode=0x100000000,payload=q(0x20),
      control=q(8),tail=w(0x14),byte=w(0x1c),serial=w(0x2c))
    return end_record(record,stack,values,base,offset,cursor,vector,regs[27])
