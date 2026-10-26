#!/usr/bin/env python3
"""Private-derived native NOP accounting and direct kick MMIO arithmetic."""
import struct


def publish_nop(queue, original_timestamp):
    if len(queue) != 0x100: raise ValueError('Expected queue object fixture')
    out = bytearray(queue)
    old = struct.unpack_from('<I', out, 0x44)[0]
    capacity = struct.unpack_from('<I', out, 0x10)[0]
    struct.pack_into('<I', out, 0x44, (old + 1) & 0xffffffff)
    overflow = old == capacity
    if not overflow:
        out[0x98] = 1
        struct.pack_into('<Q', out, 0xa0, original_timestamp)
    return bytes(out), overflow


def direct_kick(queue_id, count, offset0, offset1, stride_units):
    # Exact native OR; arbitrary-width IDs are not asserted protocol-valid.
    control = 0x0020040000021018 | ((queue_id & 0xffffffff) << 43)
    displacement = (9 * stride_units) & 0xffffffff
    return [((offset0 + displacement) & 0xffffffff, control & ((1 << 64) - 1)),
            ((offset1 + displacement) & 0xffffffff, count & 0xffffffff)]
