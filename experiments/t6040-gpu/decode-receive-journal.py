#!/usr/bin/env python3
"""Decode a saved fixed-capacity receive journal; never access live hardware.

Only the header's used prefix is authoritative. Ring records retain their raw
72 bytes and numeric type; payload semantics and completion are not inferred.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


MAGIC = 0x5852474d
VERSION = 1
CAPACITY = 65536
HEADER = struct.Struct('<8I4Q')
ENTRY = struct.Struct('<HHI72s')
STATUS_ERROR = 1 << 0
STATUS_OVERFLOW = 1 << 1
STATUS_INVALID_CURSORS = 1 << 2
STATUS_UNEXPECTED_RECORD_OR_MESSAGE = 1 << 3
KNOWN_STATUS_FLAGS = (STATUS_ERROR | STATUS_OVERFLOW | STATUS_INVALID_CURSORS |
                      STATUS_UNEXPECTED_RECORD_OR_MESSAGE)
RINGS = {
    0: ('rx13_event', 256),
    **{i: (f'rx13_type2_validator_{i-1}', 256) for i in range(1, 10)},
    10: ('rx14_trace_a', 512),
    11: ('rx14_stats_b', 256),
}


def decode(snapshot):
    """Validate and decode one complete journal snapshot without mutating it."""
    if len(snapshot) < HEADER.size:
        raise ValueError('Truncated receive journal header')
    magic, version, entry_bytes, capacity, used, flags, doorbells, reserved, *tail = HEADER.unpack_from(snapshot)
    if magic != MAGIC or version != VERSION:
        raise ValueError('Unsupported receive journal magic or version')
    if entry_bytes != ENTRY.size or capacity != CAPACITY:
        raise ValueError('Unexpected receive journal entry size or capacity')
    if used > capacity:
        raise ValueError('Receive journal used count exceeds capacity')
    if reserved or any(tail):
        raise ValueError('Nonzero reserved receive journal header fields')
    expected = HEADER.size + capacity * entry_bytes
    if len(snapshot) != expected:
        raise ValueError(f'Require full receive journal snapshot: expected {expected} bytes, got {len(snapshot)}')

    entries = []
    for append_index in range(used):
        offset = HEADER.size + append_index * entry_bytes
        ring_id, ring_index, sequence, record = ENTRY.unpack_from(snapshot, offset)
        if sequence != append_index:
            raise ValueError(f'Receive journal sequence mismatch at entry {append_index}')
        if ring_id not in RINGS:
            raise ValueError(f'Unknown receive journal ring ID at entry {append_index}: {ring_id}')
        name, ring_capacity = RINGS[ring_id]
        if ring_index >= ring_capacity:
            raise ValueError(f'Receive journal ring index out of bounds at entry {append_index}')
        entries.append(dict(sequence=sequence, ring_id=ring_id, ring_name=name,
                            ring_index=ring_index, type=struct.unpack_from('<I', record)[0],
                            raw_hex=record.hex()))

    end = HEADER.size + used * entry_bytes
    return dict(
        schema='m4rch-receive-journal-v1',
        header=dict(magic=magic, version=version, entry_bytes=entry_bytes,
                    capacity=capacity, used=used, status_flags=flags, doorbells=doorbells),
        overflow=bool(flags & STATUS_OVERFLOW), error=bool(flags & STATUS_ERROR),
        invalid_cursors=bool(flags & STATUS_INVALID_CURSORS),
        unexpected_record_or_message=bool(flags & STATUS_UNEXPECTED_RECORD_OR_MESSAGE),
        unknown_status_flags=flags & ~KNOWN_STATUS_FLAGS,
        authoritative_records_sha256=hashlib.sha256(snapshot[HEADER.size:end]).hexdigest(),
        entries=entries,
        qualification='Offline append journal only. Only header.used entries are authoritative; '
                      'unused tail bytes are ignored. Raw record types and payloads do not establish '
                      'completion, DMA retirement, resource release or rendering.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('output', type=Path, help='Destination JSON report')
    args = parser.parse_args()
    try:
        report = decode(args.snapshot.read_bytes())
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Decoded {report["header"]["used"]} saved receive records; no completion claim')


if __name__ == '__main__':
    main()
