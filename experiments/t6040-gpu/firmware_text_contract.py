# SPDX-License-Identifier: GPL-2.0-only
"""Exact captured-image check allowing only two observed boot metadata payloads.

The tag/length headers remain checked. No instruction bytes are excluded.
Payload interpretation is deliberately not assumed from four-character tags.
"""
import hashlib

TEXT_SIZE = 0x60000
NORMALIZED_SHA256 = '190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac'
PAYLOADS = [(0x59841, b'GKTS'), (0x59924, b'ECAP')]


def qualify(data):
    if len(data) != TEXT_SIZE:
        raise ValueError('Firmware TEXT length mismatch')
    normalized = bytearray(data)
    fields = []
    for offset, tag in PAYLOADS:
        if data[offset-8:offset] != tag+b'\x08\0\0\0':
            raise ValueError('Boot metadata tag/length mismatch')
        fields.append(dict(offset=hex(offset), tag_bytes=tag.decode(), payload_hex=data[offset:offset+8].hex()))
        normalized[offset:offset+8] = b'\0'*8
    digest = hashlib.sha256(normalized).hexdigest()
    if digest != NORMALIZED_SHA256:
        raise ValueError('Firmware image differs outside qualified boot metadata payloads')
    return dict(raw_sha256=hashlib.sha256(data).hexdigest(), normalized_sha256=digest,
                observed_variable_payloads=fields,
                qualification='Exact match outside two tagged eight-byte boot metadata payloads; tags and lengths are also checked. No instruction bytes excluded.')
