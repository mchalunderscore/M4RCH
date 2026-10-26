#!/usr/bin/env python3
"""Numeric model of matched AGX channel reset prefix; private-derived.

This is not a complete queue constructor. Caller supplies native source fields,
whose pointer roles/lifetimes must be qualified before any live use.
"""
import struct


def reset_prefix(queue_before, pointers, capacity, identifier, context):
    if len(queue_before) < 0x64 or len(pointers) != 3:
        raise ValueError('Require queue prefix and three pointer source values')
    state = bytearray(0xc0)
    queue = bytearray(queue_before)
    for offset, value in zip([0, 8, 16], pointers):
        struct.pack_into('<Q', state, offset, value)
    struct.pack_into('<I', state, 0x48, identifier & 0xffffffff)
    for offset in [0x24, 0x44]: struct.pack_into('<I', state, offset, 0xffffffff)
    struct.pack_into('<I', state, 0x28, 4)
    struct.pack_into('<Q', state, 0x9c, context)
    struct.pack_into('<I', queue, 0x60, capacity & 0xffffffff)
    for offset in [0, 0x10, 0x20, 0x30, 0x40]: struct.pack_into('<I', queue, offset, 0)
    struct.pack_into('<I', queue, 0x50, 0xffffffff)
    return bytes(state), bytes(queue)
