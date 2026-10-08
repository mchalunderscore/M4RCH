#!/usr/bin/env python3
"""Offline record-model comparison against matched AGX instructions.

Private-derived, not clean-room. Executes only selected instruction slices in
emulated RAM; never executes the driver natively or touches GPU hardware.
"""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X8, UC_ARM64_REG_X9, UC_ARM64_REG_X11

SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'

def patch_submit(original, channel_pointer, kind, index, channel_id, submitted):
    """Patch only fields written by the native encoder; preserve its prefix."""
    if len(original) != 24:
        raise ValueError('Expected one 24-byte record')
    record = bytearray(original)
    struct.pack_into('<QI HBB', record, 8, channel_pointer & ((1 << 64) - 1),
                     kind & 0xffffffff, index & 0xffff, channel_id & 0xff,
                     1 & ~submitted)
    return bytes(record)

def consume_event(entry, read, capacity, allowed_mask):
    """Model reviewed successful fetch path, with explicit input validation."""
    if len(entry) != 72 or not 0 <= read < capacity:
        raise ValueError('Invalid record size or cursor')
    kind = struct.unpack_from('<I', entry)[0]
    # Native variable shift masks the shift amount to six bits.
    if not ((allowed_mask >> (kind & 63)) & 1):
        raise ValueError('Type rejected by native mask')
    return entry, (read + 1) % capacity, kind

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('macho', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    raw = a.macho.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA, 'Wrong binary'
    segments, pos = [], 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        command, size = struct.unpack_from('<II', raw, pos)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', raw, pos + 24))
        pos += size
    def read(address, size):
        for vm, _, off, length in segments:
            if vm <= address and address + size <= vm + length:
                start = off + address - vm
                return raw[start:start + size]
        raise ValueError('Not file backed')
    # Stop before RET/PAC epilogues. No external calls occur in these slices.
    encoder = read(0xfffffe00089c9350, 0x28)
    consumer = read(0xfffffe00089b73ac, 0xc4)
    constants = struct.unpack('<QQ', read(0xfffffe000712dd60, 16))
    assert constants == (0x2000ffd3, 256)
    assert read(0xfffffe00089b745c, 4) == bytes.fromhex('bf3b03d5')
    rng = random.Random(6040)
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(0x100000, 0x1000)
    uc.mem_map(0x200000, 0x6000)
    def run(code, registers):
        uc.mem_write(0x100000, code)
        # Flush translated code before replacing the instruction slice.
        uc.ctl_remove_cache(0x100000, 0x101000)
        for reg, value in registers.items(): uc.reg_write(reg, value)
        uc.emu_start(0x100000, 0x100000 + len(code), count=100)
    nsubmit = 0
    for submitted in range(256):
        for kind in [0, 1, 2, 0xffffffff]:
            original = rng.randbytes(24)
            pointer, index, identifier = rng.getrandbits(64), rng.getrandbits(32), rng.getrandbits(32)
            channel = bytearray(0x88)
            struct.pack_into('<Q', channel, 0x80, pointer)
            struct.pack_into('<I', channel, 0x18, identifier)
            channel[0x3c] = submitted
            uc.mem_write(0x200000, original)
            uc.mem_write(0x201000, bytes(channel))
            run(encoder, {UC_ARM64_REG_X1: 0x200000, UC_ARM64_REG_X2: kind,
                          UC_ARM64_REG_X3: 0x201000, UC_ARM64_REG_X4: index})
            actual = bytes(uc.mem_read(0x200000, 24))
            assert actual == patch_submit(original, pointer, kind, index, identifier, submitted)
            assert actual[:8] == original[:8]
            nsubmit += 1
    nevent = 0
    for capacity in [1, 2, 256, 512]:
        for cursor in sorted({0, capacity // 2, capacity - 1}):
            for kind in [0, 1, 4, 6, 15, 29, 64, 127]:
                entry = bytearray(rng.randbytes(72))
                struct.pack_into('<I', entry, 0, kind)
                mask = 1 << (kind & 63)
                state = bytearray(48)
                struct.pack_into('<Q', state, 8, 0x203000)
                struct.pack_into('<I', state, 24, cursor)
                struct.pack_into('<Q', state, 32, mask)
                uc.mem_write(0x202000, bytes(state))
                uc.mem_write(0x204000, bytes(entry))
                uc.mem_write(0x205000, b'\xa5' * 80)
                run(consumer, {UC_ARM64_REG_X0: 0x202000, UC_ARM64_REG_X1: 0x205000,
                               UC_ARM64_REG_X9: capacity, UC_ARM64_REG_X11: 0x204000})
                expected, next_read, expected_type = consume_event(bytes(entry), cursor, capacity, mask)
                assert bytes(uc.mem_read(0x205000, 72)) == expected
                assert bytes(uc.mem_read(0x205048, 8)) == b'\xa5' * 8
                assert bytes(uc.mem_read(0x204000, 72)) == bytes(entry)
                assert struct.unpack('<I', uc.mem_read(0x203000, 4))[0] == next_read
                assert uc.reg_read(UC_ARM64_REG_X0) == expected_type
                nevent += 1
    report = dict(binary_sha256=SHA, submit_model_cases=nsubmit, event_model_cases=nevent,
                  submit_slice_sha256=hashlib.sha256(encoder).hexdigest(),
                  consumer_slice_sha256=hashlib.sha256(consumer).hexdigest(),
                  native_event_allowed_mask=hex(constants[0]), native_event_capacity=constants[1],
                  event_size=72, submit_size=24,
                  limits=['Emulated RAM only; no hardware validation',
                          'Event model covers accepted copy/update slice only, not dispatch or error paths',
                          'Pointer role and submit prefix remain unresolved',
                          'DMB opcode checked; emulator does not establish DMA/cache coherency'])
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
