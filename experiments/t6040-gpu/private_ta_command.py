"""Numeric TA SKSM construction slices; not a complete or valid drawing job."""
import struct


def header(command, descriptor, context, serial):
    out = bytearray(command)
    struct.pack_into('<IQ', out, 0, 0, serial)
    for dst, src, size in [(0xc, 0x1274, 4), (0x8d6, 0x1270, 4),
                           (0x48, 0x127c, 4), (0x18, 0x1218, 4), (0x1c, 0x1258, 4)]:
        out[dst:dst+size] = descriptor[src:src+size]
    out[0x94d] = context[0x278]
    return bytes(out)


def translated_resources(command, addresses):
    if len(addresses) != 3:
        raise ValueError('Three explicit firmware translation results required')
    out = bytearray(command)
    struct.pack_into('<3Q', out, 0x20, *addresses)
    return bytes(out)


def metadata(command, descriptor, context):
    out = bytearray(command)
    for dst, src, size in [(0x10, 0x188, 8), (0x780, 0x1150, 8),
                          (0x788, 0x1170, 8), (0x79c, 0x14d8, 8),
                          (0x7b6, 0x1000, 8), (0x7be, 0x1008, 8),
                          (0x7d6, 0x1090, 8), (0x86e, 0x86c, 12),
                          (0x91e, 0x13d8, 8), (0x926, 0x13e0, 8)]:
        out[dst:dst+size] = descriptor[src:src+size]
    struct.pack_into('<I', out, 0x7a4, context[0x4e0] & 1)
    epoch = struct.unpack_from('<Q', descriptor, 0x14e8)[0]
    struct.pack_into('<Q', out, 0x7a8, epoch & ((1 << 40)-1))
    out[0x7b0] = out[0x7b1] = (epoch >> 40) & 255
    out[0x7de:0x7f6] = bytes(24)
    out[0x7b2:0x7b6] = bytes(4)
    struct.pack_into('<I', out, 0x86a, descriptor[0x868] & 1)
    out[0x87a:0x88a] = bytes(16)
    out[0x90e:0x91e] = context[0x3c8:0x3d8]
    return bytes(out)


def completion_binding(command, descriptor, context, mapping_address):
    """Numeric command writes after explicit notification and mapping services."""
    out = bytearray(command)
    offset = struct.unpack_from('<I', descriptor, 0x1430)[0]
    struct.pack_into('<Q', out, 0x945, (mapping_address+offset) & ((1 << 64)-1))
    for dst, src in [(0x934,0x1408),(0x93d,0x1438),(0x8fe,0x878)]:
        out[dst:dst+8] = descriptor[src:src+8]
    out[0x93c] = context[0x434] & 1
    struct.pack_into('<I', out, 0x892, context[0x13c] & 1)
    struct.pack_into('<I', out, 0x89a, context[0x13f] & 1)
    return bytes(out)


def conditional_control(descriptor, context, accelerator_mode):
    """Native normal path, including mode3's two-instruction value1 trampoline."""
    kind = struct.unpack_from('<I', descriptor, 0x1130)[0]
    if accelerator_mode and context[0x5c0] in (1,2) and kind != 3:
        if accelerator_mode == 3:
            return 1
        if accelerator_mode == 1:
            return (context[0x13f] & 1) ^ 1
    return 0


def postproducer(command, descriptor, context, aperture_flags):
    """TA postproducer flags plus native G16 mcache aperture records."""
    out, desc = bytearray(command), bytearray(descriptor)
    count = struct.unpack_from('<I',desc,0x1388)[0]
    if count > 16:
        raise ValueError('Aperture count exceeds descriptor/command reserved storage')
    flags = out[0x98e] & 0xf2
    if count or any(context[0x390:0x3b0]):
        flags |= 1 | ((aperture_flags & 3) << 2)
        out[0x96e:0x98e] = desc[0x1390:0x13b0]
    out[0x98e] = flags
    struct.pack_into('<QQ',desc,0x13b0,0,0xffffffff)
    if count:
        qid = struct.unpack_from('<I',desc,0x1274)[0]
        for j in range(count):
            address, length = struct.unpack_from('<QI',desc,0x1288+j*16)
            dsid = desc[0x1288+j*16+12]
            size = struct.unpack_from('<H',desc,0x1288+j*16+14)[0]
            start = ((dsid << 47) | (qid << 41) | (address >> 7) | (1 << 55)) & ((1 << 64)-1)
            end = (((address >> 7)+length) & ((1 << 64)-1)) | ((1 << min(size,4)) << 42) | (1 << 41)
            struct.pack_into('<QQ',out,0x660+j*16,start,end)
        pointer = (struct.unpack_from('<Q',out,0x760)[0]+0x600) & ((1 << 64)-1)
        struct.pack_into('<Q2I',desc,0x13b0,pointer,0,count)
    return bytes(out),bytes(desc)


def tail(command, descriptor, stack, x26, w21, w22, branch_result):
    """Branch result is explicit: the preceding conditional path is excluded."""
    out = bytearray(command)
    struct.pack_into('<I', out, 0x89e, branch_result)
    out[0x8a2:0x8a6] = bytes(4)
    out[0x8f6:0x8fe] = bytes(8)
    out[0x8a6:0x8ae] = stack[0x40:0x48]
    struct.pack_into('<Q2I', out, 0x8ae, x26, w21, w22)
    out[0x8be:0x8c2] = stack[0x5c:0x60]
    out[0x8c2:0x8c6] = stack[0x50:0x54]
    for dst, src, size in [(0x8c6, 0xe30, 8), (0x8ce, 0xe10, 8), (0x866, 0x1130, 4)]:
        out[dst:dst+size] = descriptor[src:src+size]
    return bytes(out)
