"""Stage one operand-free refresh control; never stage GPU work."""
import hashlib
import struct

def stage(arena, receipt):
    data = bytearray(arena)
    base = int(receipt['base'], 16)
    channel = receipt['empty_channel_fixture'][12]
    cursors = [int(x, 16)-base for x in channel['cursors']]
    ring = int(channel['ring'], 16)-base
    if any(data[cursors[0]:ring+0x4000]):
        raise ValueError('Control fixture must initially be empty')
    struct.pack_into('<I', data, cursors[2], 1)
    struct.pack_into('<I', data, ring, 0x16)
    for obj in receipt['objects']:
        offset = obj['arena_offset']
        obj['input_sha256'] = hashlib.sha256(data[offset:offset+obj['input_bytes']]).hexdigest()
    receipt['control_refresh'] = dict(index=12, opcode=0x16, record_bytes=0x40,
        read=0, prefetch=0, write=1, operands='zero; native handler reads none',
        qualification='Single initial control fixture. Work channels remain empty RAM surrogates. No job, FList or rendering command; no extra doorbell.')
    receipt['arena_sha256'] = hashlib.sha256(data).hexdigest()
    receipt['channel_qualification'] = 'Work0..11 use zero RAM cursor surrogates; control12 contains one initial refresh record and producer1. Channels13..16 remain unchanged/unqualified. No production work queue or rendering.'
    return data, receipt
