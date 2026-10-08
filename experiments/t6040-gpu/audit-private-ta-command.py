#!/usr/bin/env python3
"""Compare native TA SKSM header/resource/metadata/tail slices in offline RAM."""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
from private_ta_command import header, translated_resources, metadata, tail

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('macho', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
raw = a.macho.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
assert sha == '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments = []
pos = 32
for _ in range(struct.unpack_from('<I', raw, 16)[0]):
    cmd, size = struct.unpack_from('<II', raw, pos)
    if cmd == 25:
        segments.append(struct.unpack_from('<QQQQ', raw, pos+24))
    pos += size

def read(addr, size):
    for vm, _, off, length in segments:
        if vm <= addr and addr+size <= vm+length:
            return raw[off+addr-vm:off+addr-vm+size]
    raise ValueError('Not file backed')

BASE = 0xfffffe0000000000
RANGES = [(BASE+0x8a1f394, BASE+0x8a1f3f0),
          (BASE+0x8a1f3f0, BASE+0x8a1f4d8),
          (BASE+0x8a1f514, BASE+0x8a1f5d4),
          (BASE+0x8a1f6f4, BASE+0x8a1f76c)]
D, C, CTX, CH, ACC, FW, VT, OWNER, STACK = (
    0x200000, 0x204000, 0x208000, 0x20a000, 0x20b000,
    0x20c000, 0x20d000, 0x20e000, 0x220000)
m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
m.reg_write(c.UC_ARM64_REG_CPACR_EL1, 3 << 20)
m.mem_map(BASE+0x8a1f000, 0x1000)
m.mem_map(0x200000, 0x30000)
for start, end in RANGES:
    m.mem_write(start, read(start, end-start))
regs = [getattr(c, 'UC_ARM64_REG_X'+str(i)) for i in range(31)]
calls = []
seen = set()
descriptor = b''
translations = []

def hook(m, addr, size, user):
    seen.add(addr)
    word = struct.unpack('<I', m.mem_read(addr, 4))[0]
    if addr == BASE+0x8a1f3ac:
        imm = word & 0x3ffffff
        if imm & (1 << 25): imm -= 1 << 26
        assert addr+imm*4 == BASE+0xbeaf410
        assert m.reg_read(regs[0]) == struct.unpack_from('<Q', descriptor, 0x60)[0]
        assert m.reg_read(regs[1]) == BASE+0xc6e6298
        calls.append('serial-owner')
        m.reg_write(regs[0], OWNER)
        m.reg_write(c.UC_ARM64_REG_PC, addr+4)
    elif addr in (BASE+0x8a1f408, BASE+0x8a1f410,
                  BASE+0x8a1f454, BASE+0x8a1f45c,
                  BASE+0x8a1f4a0, BASE+0x8a1f4a8):
        # Authentication is outside these numeric RAM checks.
        m.reg_write(c.UC_ARM64_REG_PC, addr+4)
    elif addr in (BASE+0x8a1f434, BASE+0x8a1f480, BASE+0x8a1f4cc):
        j = len(calls)
        assert m.reg_read(regs[0]) == FW
        assert m.reg_read(regs[1]) == struct.unpack_from('<Q', descriptor, (0x1220,0x1228,0x1250)[j])[0]
        assert m.reg_read(regs[2]) == 0
        assert m.reg_read(regs[9]) == 0xabcdef00
        assert m.reg_read(regs[8]) == VT+0x2d8
        calls.append(j)
        m.reg_write(regs[0], translations[j])
        m.reg_write(c.UC_ARM64_REG_LR, addr+4)
        m.reg_write(c.UC_ARM64_REG_PC, addr+4)

m.hook_add(u.UC_HOOK_CODE, hook)

def run(which, initial):
    calls.clear()
    for reg in regs: m.reg_write(reg, 0)
    for index, value in initial.items(): m.reg_write(regs[index], value)
    m.reg_write(c.UC_ARM64_REG_SP, STACK)
    start, end = RANGES[which]
    m.emu_start(start, end, count=1000)
    assert m.reg_read(c.UC_ARM64_REG_PC) == end

rng = random.Random(604018)
counts = {}
for i in range(1024):
    command = rng.randbytes(0x9c0)
    desc = bytearray(rng.randbytes(0x1800))
    struct.pack_into('<Q', desc, 0xf98, C)
    descriptor = bytes(desc)
    context, stack = rng.randbytes(0x600), rng.randbytes(0x100)
    m.mem_write(D, descriptor); m.mem_write(CTX, context); m.mem_write(STACK, stack)
    serial = [0, 1, (1 << 64)-1, rng.getrandbits(64)][i % 4]
    owner = bytearray(rng.randbytes(0x700)); struct.pack_into('<Q', owner, 0x5e8, serial)
    m.mem_write(OWNER, bytes(owner)); m.mem_write(C, command)
    run(0, {20:D, 28:CTX})
    assert bytes(m.mem_read(C,len(command))) == header(command, descriptor, context, serial), (i,'header')
    struct.pack_into('<Q', owner, 0x5e8, (serial+1) & ((1 << 64)-1))
    assert bytes(m.mem_read(OWNER,len(owner))) == bytes(owner)
    assert calls == ['serial-owner']
    translations = [rng.getrandbits(64) for _ in range(3)]
    m.mem_write(CH+0x10, struct.pack('<Q', ACC))
    m.mem_write(ACC+0x5b0, struct.pack('<Q', FW))
    m.mem_write(FW, struct.pack('<Q', VT))
    m.mem_write(VT+0x2d8, struct.pack('<Q', 0xabcdef00))
    m.mem_write(C, command)
    run(1, {19:CH, 20:D, 24:C})
    assert calls == [0,1,2]
    assert bytes(m.mem_read(C,len(command))) == translated_resources(command, translations), (i,'translations')
    m.mem_write(C, command)
    run(2, {20:D, 24:C, 25:C+0x79c, 28:CTX})
    assert bytes(m.mem_read(C,len(command))) == metadata(command,descriptor,context), (i,'metadata')
    x26, w21, w22, branch = rng.getrandbits(64), rng.getrandbits(32), rng.getrandbits(32), rng.getrandbits(32)
    m.mem_write(C, command)
    run(3, {8:branch, 19:CH, 20:D, 21:w21, 22:w22, 24:C, 25:C+0x79c, 26:x26})
    assert bytes(m.mem_read(C,len(command))) == tail(command,descriptor,stack,x26,w21,w22,branch), (i,'tail')
    assert bytes(m.mem_read(D,len(descriptor))) == descriptor
    assert bytes(m.mem_read(CTX,len(context))) == context
    assert bytes(m.mem_read(STACK,len(stack))) == stack
    for name in ('header','translations','metadata','tail'): counts[name] = i+1
report = dict(binary_sha256=sha, counts=counts, visited_instruction_count=len(seen),
    ranges=[dict(start=hex(start), end=hex(end), sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in RANGES],
    qualification='Actual TA SKSM construction slices compared over entire 9c0 command backing, descriptor/context/stack sources unchanged. Serial wrap and whole owner checked; owner lookup and three firmware translations are explicit external service fixtures. Pointer authentication skipped. Descriptor virtual1a8, completion-resource mapping/notification, preceding tail conditional, full submit and valid drawing inputs remain unqualified. No live GPU submission or retirement proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(counts)
