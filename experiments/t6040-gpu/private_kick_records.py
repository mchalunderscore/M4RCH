#!/usr/bin/env python3
"""Private-derived partial packed kick records, not complete job constructors."""
import struct


def patch_add_kicks(original, queue, scheduler_id, kick_timestamp, value):
    if len(original) < 21: raise ValueError('Record prefix requires 21 bytes')
    result = bytearray(original)
    struct.pack_into('<IHHBQI', result, 0, 14, queue & 0xffff, 1,
                     scheduler_id & 0xff, kick_timestamp, value & 0xffffffff)
    return bytes(result)


def patch_alternate_kick(original, queue, kick_timestamp):
    if len(original) < 18: raise ValueError('Record prefix requires 18 bytes')
    result = bytearray(original)
    struct.pack_into('<IHQI', result, 0, 16, queue & 0xffff, kick_timestamp, 0xfe)
    return bytes(result)
