#!/usr/bin/env python3
"""Decode a bounded AGXF native-submit failure capture into JSON packet metadata."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

NAMES = {0: 'render', 1: 'compute', 2: 'vertex_attachments',
         3: 'fragment_attachments', 4: 'compute_attachments'}


def decode(data):
    if len(data) < 48:
        raise ValueError('truncated capture header')
    header = struct.unpack_from('<12I', data)
    magic, version, header_size, pid, fd, queue, error, flags, size, ins, outs, reserved = header
    if (magic, version, header_size, reserved) != (0x46584741, 1, 48, 0):
        raise ValueError('unsupported capture format')
    if size > 1024 * 1024 or len(data) != 48 + size:
        raise ValueError('capture payload length mismatch')
    payload = data[48:]
    result = dict(pid=pid, fd=fd, queue=queue, errno=error, flags=flags,
                  input_syncs=ins, output_syncs=outs, command_bytes=size,
                  payload_sha256=hashlib.sha256(payload).hexdigest(), commands=[])
    offset = 0
    while offset < size:
        if len(result['commands']) == 1024:
            result['parse_error'] = 'command count exceeds decoder bound'
            break
        if size - offset < 8:
            result['parse_error'] = f'truncated command header at offset {offset}'
            break
        kind, length, vdm, cdm = struct.unpack_from('<4H', payload, offset)
        command = dict(offset=offset, type=kind, name=NAMES.get(kind, 'unknown'),
                       payload_bytes=length, vdm_barrier=vdm, cdm_barrier=cdm)
        result['commands'].append(command)
        if length > size - offset - 8:
            result['parse_error'] = f'command payload exceeds capture at offset {offset}'
            break
        offset += 8 + length
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    if args.capture.stat().st_size > 48 + 1024 * 1024:
        parser.error('capture exceeds maximum size')
    try:
        result = decode(args.capture.read_bytes())
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
