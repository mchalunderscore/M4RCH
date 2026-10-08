"""Stage a bounded batch of operand-free refresh controls; never GPU work."""
import hashlib
import struct

def stage(arena, receipt, count=1):
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError('Refresh count must be an integer in1..32; no wraparound')
    data = bytearray(arena)
    base = int(receipt['base'], 16)
    channel = receipt['empty_channel_fixture'][12]
    cursors = [int(x, 16)-base for x in channel['cursors']]
    ring = int(channel['ring'], 16)-base
    if any(data[cursors[0]:ring+0x4000]):
        raise ValueError('Control fixture must initially be empty')
    struct.pack_into('<I', data, cursors[2], count)
    for index in range(count):
        struct.pack_into('<I', data, ring+index*0x40, 0x16)
    for obj in receipt['objects']:
        offset = obj['arena_offset']
        obj['input_sha256'] = hashlib.sha256(data[offset:offset+obj['input_bytes']]).hexdigest()
    receipt['control_refresh'] = dict(index=12, opcode=0x16, record_bytes=0x40,
        count=count, read=0, prefetch=0, write=count, operands='zero; native handler reads none',
        qualification='Bounded initial control fixture; no wraparound. Work channels remain empty RAM surrogates. No job, FList or rendering command; no extra doorbell.')
    receipt['arena_sha256'] = hashlib.sha256(data).hexdigest()
    receive = 'Receive14 has experimental four-buffer backing; receive13/15/16 unchanged/unqualified.' if 'receive14_fixture' in receipt else 'Channels13..16 remain unchanged/unqualified.'
    receipt['channel_qualification'] = f'Work0..11 use zero RAM cursor surrogates; control12 contains{count} initial refresh records and producer{count}. {receive} No production work queue or rendering.'
    return data, receipt
