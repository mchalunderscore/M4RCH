#!/usr/bin/env python3
"""Read-only snapshot decoder for the matched receive13 transport buffers.

Consumes an owned-graph arena and receipt. Never publishes cursors or touches
hardware. Raw type/payload output is private-derived and not clean-room.
"""
import argparse
import json
import struct
from pathlib import Path


def decode_ring(state, ring, limit=64):
    if len(state) != 48 or len(ring) != 256 * 72 or not 0 <= limit <= 256:
        raise ValueError('Wrong ring geometry or entry limit')
    read, write = struct.unpack_from('<I', state, 0)[0], struct.unpack_from('<I', state, 32)[0]
    if read >= 256 or write >= 256:
        raise ValueError('Cursor outside ring')
    pending = (write - read) % 256
    entries = []
    for n in range(min(pending, limit)):
        index = (read + n) % 256
        record = ring[index * 72:(index + 1) * 72]
        entry = dict(index=index, type=struct.unpack_from('<I', record)[0], raw_hex=record.hex())
        if entry['type'] == 1:
            lo, hi = struct.unpack_from('<QQ', record, 4)
            mask = lo | (hi << 64)
            selector = struct.unpack_from('<H', record, 20)[0]
            entry['type1_observed_fields'] = dict(
                notification_indices=[i for i in range(128) if mask & (1 << i)],
                selector=selector, selector_within_native_bound=selector < 24,
                qualification='Callback enumeration only; job retirement not established')
        entries.append(entry)
    return dict(read=read, write=write, pending_modulo_256=pending,
                entries=entries, truncated=pending > limit,
                qualification='Snapshot only; equal cursors treated as empty, no phase/full flag established')


def decode(arena, receipt, limit=64):
    def obj(name, expected):
        matches = [o for o in receipt['objects'] if o['name'] == name]
        if len(matches) != 1: raise ValueError('Missing/duplicate object: ' + name)
        o = matches[0]
        start, size = o['arena_offset'], o['input_bytes']
        if size != expected or start < 0 or start + size > len(arena):
            raise ValueError('Invalid extent: ' + name)
        return arena[start:start + size]
    event_state = obj('receive13_state_a', 48)
    event_ring = obj('receive13_aux', 0x4800)
    other_states = obj('receive13_state_b', 9 * 48)
    other_rings = obj('receive13_ring', 9 * 0x4800)
    return dict(event=decode_ring(event_state, event_ring, limit),
                nine_type2_validators=[decode_ring(other_states[i*48:(i+1)*48],
                                       other_rings[i*0x4800:(i+1)*0x4800], limit)
                                      for i in range(9)],
                qualification='Offline copied snapshot, not atomic GPU capture; no cursor writes. '
                              'Nine validator geometry verified; message semantics not decoded.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('arena', type=Path)
    p.add_argument('receipt', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--limit', type=int, default=64)
    a = p.parse_args()
    a.output.write_text(json.dumps(decode(a.arena.read_bytes(), json.loads(a.receipt.read_text()), a.limit), indent=2) + '\n')

if __name__ == '__main__': main()
