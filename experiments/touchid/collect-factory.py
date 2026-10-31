#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Construct J614s private sensor inputs, following Aurora SignedSensorInputs.

Run as root against this Mac's read-only Hardware volume factory-data directory.
Never publish the resulting files. Structural validation is not signature verification.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

LIMIT = 16 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def element(data, offset=0, limit=None):
    if limit is None:
        limit = len(data)
    require(0 <= offset < limit <= len(data) and offset + 2 <= limit, 'truncated DER')
    start = offset
    tag, size = data[offset], data[offset + 1]
    offset += 2
    if size & 0x80:
        count = size & 0x7f
        require(0 < count <= 4 and offset + count <= limit and data[offset] != 0, 'invalid DER length')
        size = int.from_bytes(data[offset:offset + count], 'big')
        require(size >= 128, 'noncanonical DER length')
        offset += count
    require(size <= limit - offset, 'DER exceeds envelope')
    return tag, start, offset, offset + size


def children(data, node):
    _, _, pos, end = node
    out = []
    while pos < end:
        item = element(data, pos, end)
        out.append(item)
        require(len(out) <= 1024, 'too many DER fields')
        pos = item[3]
    return out


def text(data, node, value):
    return node[0] == 0x16 and data[node[2]:node[3]] == value


def der(tag, value):
    length = len(value)
    if length < 128:
        encoded = bytes([length])
    else:
        raw = length.to_bytes((length.bit_length() + 7) // 8, 'big')
        encoded = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + encoded + value


def read_at(dirfd, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= LIMIT, 'invalid input file')
        data = bytearray()
        while len(data) < info.st_size:
            chunk = os.read(fd, min(65536, info.st_size - len(data)))
            require(chunk, 'short input file')
            data.extend(chunk)
        require(os.fstat(fd).st_size == info.st_size, 'input changed')
        return bytes(data)
    finally:
        os.close(fd)


def payload(record, kind):
    outer = element(record)
    require(outer[0] == 0x30 and outer[3] == len(record), 'invalid IMG4 envelope')
    parts = children(record, outer)
    require(len(parts) == 3 and text(record, parts[0], b'IMG4') and parts[1][0] == 0x30,
            'invalid IMG4 fields')
    fields = children(record, parts[1])
    require(len(fields) == 4 and text(record, fields[0], b'IM4P') and text(record, fields[1], kind)
            and fields[2][0] == 0x16 and fields[2][3] > fields[2][2]
            and fields[3][0] == 4 and fields[3][3] > fields[3][2], 'unexpected sensor payload')
    if kind == b'FSC2':
        require(b'CALB' in record[fields[3][2]:min(fields[3][2] + 256, fields[3][3])],
                'calibration marker missing')
    require(parts[2][0] == 0xa0 and b'IM4M' in record[parts[2][2]:parts[2][3]],
            'factory manifest missing')
    return record[parts[1][1]:parts[1][3]]


def combine(im4p, seal, trust):
    image = der(0x30, der(0x16, b'IMG4') + im4p + der(0xa0, seal))
    return der(0x30, der(0x16, b'comb') + der(0x30, der(0x16, b'fdrd') + der(4, image))
               + der(0x30, der(0x16, b'secb') + der(4, trust)))


def main():
    require(os.geteuid() == 0 and len(sys.argv) == 3, 'usage: sudo collect-factory.py FACTORY_DIR PRIVATE_OUTPUT_DIR')
    source, dest = Path(sys.argv[1]), Path(sys.argv[2])
    sourcefd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        names = os.listdir(sourcefd)
        require(len(names) <= 4096, 'too many records')
        def unique(prefix):
            matches = [x for x in names if x.startswith(prefix)]
            require(len(matches) == 1, 'missing or ambiguous ' + prefix + ' records')
            return matches[0]
        root_name, cal_name, seal_name = unique('MSRk-'), unique('FSC2-'), unique('seal-')
        require(root_name[5:] == cal_name[5:] and root_name[5:], 'sensor records do not pair')
        require(not any(n.startswith('FSCl-') for n in names), 'ambiguous calibration types')
        root, cal, seal = (read_at(sourcefd, n) for n in (root_name, cal_name, seal_name))
        trust = read_at(sourcefd, 'trustobject-current')
        digest = hashlib.sha256(trust).hexdigest()
        matches = [n for n in names if n.startswith('trustobject-') and n[12:].lower() == digest]
        require(len(matches) == 1 and read_at(sourcefd, matches[0]) == trust, 'trust bundle mismatch')
        manifest = element(seal)
        require(manifest[0] == 0x30 and manifest[3] == len(seal), 'invalid seal envelope')
        parts = children(seal, manifest)
        require(len(parts) >= 2 and text(seal, parts[0], b'IM4M'), 'invalid sealing manifest')
        outputs = {'msrk-j614s.bin': combine(payload(root, b'MSRk'), seal, trust),
                   'mesacal-j614s.bin': combine(payload(cal, b'FSC2'), seal, trust)}
        os.mkdir(dest, 0o700)
        for name, data in outputs.items():
            fd = os.open(dest / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        print('Paired sensor inputs prepared privately; DER structure checked, signatures not verified.')
    finally:
        os.close(sourcefd)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print('factory input collection failed:', exc, file=sys.stderr)
        sys.exit(1)
