#!/usr/bin/env python3
"""Private-derived arithmetic for native G16 NOP scheduler header/counter."""
MASK64 = (1 << 64) - 1


def patch_header(original, timestamp, queue, priority):
    header = (original & ~3) | 2
    header = (header & 0xf800000000000003) | ((timestamp & ((1 << 47) - 1)) << 2) | ((queue & 127) << 42)
    return (header & 0xc7ffffffffffffff) | ((priority & 3) << 59)


def advance_timestamp(original, capacity):
    if not 1 <= capacity <= 256:
        raise ValueError('Only qualified counter capacities 1..256')
    low = ((original & 255) + 1) % capacity
    middle = (original + (256 if low == 0 else 0)) & 0xffffffff00
    return (original & 0xffffff0000000000) | middle | low
