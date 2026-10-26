#!/usr/bin/env python3
"""Private-derived model of matched AGX pointer publication, no hardware writes."""
import struct


def publish_pointer(queue_before, ring_before, pointer):
    if len(queue_before) < 0x64:
        raise ValueError('Queue extent too short')
    capacity = struct.unpack_from('<I', queue_before, 0x60)[0]
    read = struct.unpack_from('<I', queue_before, 0)[0]
    write = struct.unpack_from('<I', queue_before, 0x40)[0]
    if capacity < 2 or len(ring_before) != capacity*8 or max(read, write) >= capacity:
        raise ValueError('Invalid queue geometry/cursors')
    next_write = (write + 1) % capacity
    if next_write == read:
        raise BlockingIOError('Queue is full; do not publish')
    queue, ring = bytearray(queue_before), bytearray(ring_before)
    struct.pack_into('<Q', ring, write*8, pointer)
    # Native DMB ISH lies between these writes; RAM model only.
    struct.pack_into('<I', queue, 0x40, next_write)
    return bytes(queue), bytes(ring)
