#!/usr/bin/env python3
"""Private-derived G16 NOP cached-dependency patch; not a job constructor."""
import struct
from private_nop_header import patch_header, advance_timestamp
MASK64 = (1 << 64) - 1


def patch_cached_body(record, timestamp, queue_id, priority, previous, masks, payload, capacity):
    if len(record) != 0x200 or len(masks) != 4 or len(payload) != 2:
        raise ValueError('Expected 0x200-byte record, four mask words and two payload words')
    result = bytearray(record)
    def get(offset): return struct.unpack_from('<Q', result, offset)[0]
    def put(offset, value): struct.pack_into('<Q', result, offset, value & MASK64)
    put(0, patch_header(get(0), timestamp, queue_id, priority))
    put(0x20, get(0x20) | 1)
    put(0x28, (get(0x28) & ~((1 << 47) - 1)) | (previous & ((1 << 47) - 1)) | ((queue_id & 127) << 40))
    for offset, value in zip((0x128, 0x130, 0x138, 0x140), masks): put(offset, value)
    put(0x148, get(0x148) & ~255)
    for offset in (0x150, 0x158, 0x160, 0x168): put(offset, get(offset) & 0xfffc000000000000)
    put(0x10, payload[0]); put(0x18, payload[1]); put(0x178, 0)
    return bytes(result), advance_timestamp(timestamp, capacity)


def convert_timestamp(epoch, event_timestamp, capacity, initial):
    """Native timestamp conversion arithmetic with caller-supplied selected epoch."""
    if not 1 <= capacity <= 256: raise ValueError('Qualified capacities 1..256')
    combined = (((epoch << 24) | ((event_timestamp & 0xffffffff) >> 8)) - 1) & MASK64
    quotient, remainder = divmod(combined, capacity)
    carry, slot = divmod((initial & 255) + (remainder & 255), capacity)
    high = ((initial >> 8) + quotient + carry) & 0xffffffff
    return (high << 8) | (slot & 255)
