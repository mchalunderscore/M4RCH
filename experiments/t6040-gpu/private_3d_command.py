"""Numeric models for checked SKSM command construction slices, not valid jobs."""
import struct

def header(command, descriptor, serial, frame_data, fast=False):
    out = bytearray(command)
    struct.pack_into('<I', out, 0, 2 if fast else 1)
    struct.pack_into('<Q', out, 4, serial)
    out[0xc:0x10] = descriptor[0x144:0x148]
    out[0x997 if fast else 0x21e7] = descriptor[0x148]
    base = 0x8fc if fast else 0x2170
    out[base:base+4] = descriptor[0x140:0x144]
    struct.pack_into('<I', out, base+4, 0 if fast else int(descriptor[0x960] == 2))
    out[base+8:base+32] = frame_data
    if not fast:
        struct.pack_into('<I', out, 0x2100, descriptor[0x897] & 1)
        struct.pack_into('<I', out, 0x20f8, 0)
    return bytes(out)

# Destination, descriptor source, byte width. Explicit table independent of emulator.
BODY_COPIES = [(0x40,0x8a0,8),(0x48,0x8b8,8),(0x50,0x8c8,4),
 (0x54,0x8d0,4),(0x58,0x8c0,4),(0x70,0x8e8,8),(0x78,0x8f8,4),
 (0x1d20,0x4b0,8),(0x1d30,0x4b8,8),(0x1d40,0x4c0,8),(0x1d50,0x4e0,8)]
BODY_COPIES += [(0x1d58+j*8,0x4e8+j*8,8) for j in range(34)]
BODY_COPIES += [(0x1e68+j*8,0x5f8+j*8,8) for j in range(12)]
# The first run above ends at 0x1e60 <-0x5f0. Together runs copy 0x4e8..0x650.
BODY_COPIES += [(0x1ec8,0x668,8),(0x1ed0,0x6c8,8),(0x1ed8,0x700,8),
 (0x1f28,0x6a8,8),(0x1ee0,0x670,16),(0x1ef0,0x6f8,8),(0x1ef8,0x680,8),
 (0x1f00,0x6d8,8),(0x1f08,0x728,8),(0x1f30,0x6c0,8),(0x1f20,0x720,8),
 (0x1f48,0x750,16),(0x1f68,0x790,8),(0x1f70,0x798,4),(0x1f74,0x760,16),
 (0x1f90,0x7a4,4),(0x1f94,0x780,16),(0x1fa8,0x7a8,8),(0x1fb0,0x4a0,4),
 (0x1f38,0x740,16),(0x1fc0,0x7b0,8),(0x1fc8,0x7c0,4),(0x1fd0,0x660,8)]

def body(command, descriptor, source):
    out=bytearray(command)
    for dest,src,width in BODY_COPIES:out[dest:dest+width]=descriptor[src:src+width]
    for dest,src,width in [(0x60,0x2f0,16),(0x1f10,0xa0,16),(0x1f88,0x1b4,8)]:
        out[dest:dest+width]=source[src:src+width]
    out[0x1fdc:0x20f0]=bytes(0x114)
    for dest in (0x1fd8,0x20f0):out[dest:dest+4]=bytes(4)
    return bytes(out)

def tail(command, descriptor, stack, w21, w22, callback):
    out=bytearray(command)
    struct.pack_into('<I',out,0x20fc,descriptor[0x88c]&1)
    out[0x2208:0x220c]=descriptor[0xc40:0xc44]
    struct.pack_into('<I',out,0x2104,descriptor[0x868]&1)
    for dest,src,width in [(0x2108,0x86c,12),(0x21a8,0xab0,16),
      (0x21b8,0xac0,8),(0x21c0,0xac8,8),(0x21ce,0xb70,8),
      (0x2198,0x878,8),(0x21a0,0x880,8)]:out[dest:dest+width]=descriptor[src:src+width]
    out[0x2114:0x2124]=bytes(16)
    out[0x90]=callback&255;out[0x220c]=descriptor[0xc44]
    out[0x2140:0x2148]=stack[0x50:0x58];out[0x2148:0x2150]=stack[0x40:0x48]
    struct.pack_into('<2I',out,0x2150,w21,w22)
    out[0x2158:0x215c]=stack[0x4c:0x50];out[0x215c:0x2160]=stack[0x48:0x4c]
    return bytes(out)


def bindings(command, descriptor, translations, completion_mapping):
    """Numeric ordinary3D resource writes; actual services remain explicit."""
    if len(translations) != 3:
        raise ValueError('Three explicit firmware translation results required')
    out=bytearray(command)
    out[0x21d6]=descriptor[0xb9c]&1
    out[0x21d7:0x21df]=descriptor[0xba0:0xba8]
    if struct.unpack_from('<Q',descriptor,0xb70)[0]:
        offset=struct.unpack_from('<I',descriptor,0xb98)[0]
        struct.pack_into('<Q',out,0x21df,(completion_mapping+offset)&((1<<64)-1))
    out[0x20:0x28]=descriptor[0x188:0x190]
    struct.pack_into('<3Q',out,0x28,*translations)
    return bytes(out)


def event_control(command, descriptor, context, epochs, capacity, initial, payload, aperture_flags):
    """Ordinary3D event conversion and control writes; explicit queue fixtures."""
    from private_nop_body import convert_timestamp
    if len(epochs) != 2:
        raise ValueError('Two event-machine epochs required')
    out, desc = bytearray(command), bytearray(descriptor)
    event = struct.unpack_from('<I',desc,0x210)[0]
    # CMN wEvent,1 / CSEL GT includes the overflow flag. In particular,
    # 0x7fffffff selects the first epoch despite its wrapped negative sum.
    timestamp = convert_timestamp(epochs[event >> 31],event,capacity,initial) | ((payload & 255) << 40)
    struct.pack_into('<Q',desc,0x178,timestamp)
    struct.pack_into('<Q',out,0x2160,timestamp)
    struct.pack_into('<Q',out,0x2190,0)
    struct.pack_into('<4I',out,0x2124,context[0x2a5]&1,context[0x2a6]&1,
                     desc[0x88f]&1,desc[0x893]&1)
    struct.pack_into('<I',out,0x2138,desc[0x895]&1)
    out[0x2168:0x2170]=desc[0x100:0x108]
    flags=out[0x222d]&0xf2
    if struct.unpack_from('<I',desc,0xa70)[0] or any(context[0x490:0x4b0]):
        flags |= 1 | ((aperture_flags&3)<<2)
        out[0x220d:0x222d]=desc[0xa78:0xa98]
    out[0x222d]=flags
    out[0x222e:0x2232]=bytes(4)
    return bytes(out),bytes(desc)


def aperture_records(command, descriptor):
    """Native ordinary3D postproducer mcache helper/HAL record writes."""
    out,desc=bytearray(command),bytearray(descriptor)
    count=struct.unpack_from('<I',desc,0xa70)[0]
    if count>16:
        raise ValueError('3D aperture count exceeds reserved storage')
    struct.pack_into('<QQ',desc,0xa98,0,0xffffffff)
    qid=struct.unpack_from('<I',desc,0x144)[0]
    for j in range(count):
        address,length=struct.unpack_from('<QI',desc,0x970+j*16)
        dsid=desc[0x970+j*16+12]
        size=struct.unpack_from('<H',desc,0x970+j*16+14)[0]
        start=((dsid<<47)|(qid<<41)|(address>>7)|(1<<55))&((1<<64)-1)
        end=(((address>>7)+length)&((1<<64)-1))|((1<<min(size,4))<<42)|(1<<41)
        struct.pack_into('<QQ',out,0x6a0+j*16,start,end)
    if count:
        pointer=(struct.unpack_from('<Q',out,0x7a0)[0]+0x600)&((1<<64)-1)
        struct.pack_into('<Q2I',desc,0xa98,pointer,0,count)
    return bytes(out),bytes(desc)
