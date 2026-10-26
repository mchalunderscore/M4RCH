#!/usr/bin/env python3
"""Offline matched-AGX scheduler allocation/config audit; never accesses hardware.

Executes original private Mach-O slices in Unicorn. Kernel allocation, locks,
mapping methods and inherited constructors are checked, explicit RAM services.
An independent numeric model compares complete fixture objects, including guards.
No Apple bytes are written to the report/output directory.
"""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path

import unicorn as u
from unicorn import arm64_const as c

BASE = 0xfffffe0000000000
PIN = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
REPO = Path(__file__).resolve().parents[2]
RANGES = {
    'allocate_scheduler_state': (0x89897cc, 0x8989bf8),
    'ensure_allocation_caller': (0x89896a4, 0x89896b8),
    'queue_init_reset': (0x898e510, 0x898e530),
    'pool_constructor': (0x89d2d50, 0x89d2dc4),
    'pool_init_caller': (0x89cf024, 0x89cf06c),
    'pool_init': (0x89afa80, 0x89afb44),
    'available_count': (0x89aeb74, 0x89aec44),
    'prepare_mappings': (0x89ed740, 0x89ed7c0),
    'qos_owner_init_caller': (0x898e8bc, 0x898e920),
    'qos_init': (0x8a096a0, 0x8a09718),
    'channel_pid_constructor': (0x897fab8, 0x897faec),
    'channel_pid_reset': (0x897deec, 0x897def8),
    'channel_pid_getter': (0x897de60, 0x897de70),
    'channel_subpriority_getter': (0x897de70, 0x897de80),
    'config_companions': (0x895be40, 0x895bf04),
}
EVIDENCE_RANGES = {
    'queue_inherited_init_services_not_executed': (0x898e530, 0x898e5a8),
    'channel_cpu_mapping_publication_not_executed': (0x89802b4, 0x89802f8),
    'qos_prepare_policy_not_executed': (0x8a09550, 0x8a096a0),
    'hardware_buffer_id_allocation_not_executed': (0x89ec398, 0x89ec674),
}
Q, A, F, BIT, ARR, ALLOC, RES, RVT = [0x201000 + x * 0x1000 for x in (0, 2, 4, 7, 8, 9, 13, 14)]
MF, MD, MC, MVT, CPU, TASK = 0x210000, 0x211000, 0x212000, 0x213000, 0x214000, 0x21c000
QOS, QVT, CH, CVT, STATE, DESC, CFG, PVT = [0x21d000 + x * 0x1000 for x in range(8)]
META, MCLASSVT, BASEVT, GLOBALS, STACK, STOP = 0x225000, 0x226000, 0x227000, 0x228000, 0x27e000, 0x27f000
LOCK, RLOCK, QLOCK, EVENT = 0x229000, 0x22a000, 0x22b000, 0x22c000
RETAIN, FWGET, CPUGET, METALLOC, QBASE = [0x22d000 + i * 4 for i in range(5)]
REGS = [getattr(c, 'UC_ARM64_REG_X' + str(i)) for i in range(31)]
MASK64 = (1 << 64) - 1


def put(obj, off, val, fmt='Q'):
    struct.pack_into('<' + fmt, obj, off, val)


def get(obj, off, fmt='Q'):
    return struct.unpack_from('<' + fmt, obj, off)[0]


def lowest(value):
    return (value & -value).bit_length() - 1


class Audit:
    def __init__(self, raw):
        self.raw = raw
        assert hashlib.sha256(raw).hexdigest() == PIN, 'Private driver identity mismatch'
        assert struct.unpack_from('<I', raw)[0] == 0xfeedfacf
        self.segs = []
        pos = 32
        for _ in range(struct.unpack_from('<I', raw, 16)[0]):
            cmd, size = struct.unpack_from('<II', raw, pos)
            if cmd == 25:
                self.segs.append(struct.unpack_from('<QQQQ', raw, pos + 24))
            pos += size
        self.m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
        self.m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
        self.m.reg_write(c.UC_ARM64_REG_CPACR_EL1, 3 << 20)
        pages = set()
        for start, end in RANGES.values():
            for page in range((BASE + start) & ~4095, (BASE + end + 4095) & ~4095, 4096):
                pages.add(page)
        pages.add(BASE + 0x7ea2000)
        for page in sorted(pages):
            self.m.mem_map(page, 4096)
            self.m.mem_write(page, self.read(page, 4096))
        self.m.mem_map(0x200000, 0x80000)
        self.m.mem_map(BASE + 0xc6e8000, 4096)  # gMetaClass BSS supplied explicitly.
        self.calls = []
        self.stop = STOP
        self.active = {}
        self.trap = None
        self.m.hook_add(u.UC_HOOK_CODE, self.hook)
        self.pin_slots()

    def read(self, address, size):
        for vm, _, off, length in self.segs:
            if vm <= address and address + size <= vm + length:
                return self.raw[off + address - vm:off + address - vm + size]
        raise ValueError('Not file-backed: ' + hex(address))

    def pin_slots(self):
        slots = []
        for table, slot, target, name in [
            (0x7ea7320, 0x20, 0x89afa80, 'scheduler_pool_init'),
            (0x7ea7320, 0x50, 0x89aeb74, 'scheduler_pool_available_count'),
            (0x7eb49f8, 0x150, 0x8a096a0, 'qos_queue_init'),
        ] + [(table, slot, target, name)
             for table in (0x7eaa560, 0x7eaa8e0, 0x7eadc98, 0x7eae018)
             for slot, target, name in ((0x1f0, 0x897de70, 'subpriority'), (0x1f8, 0x897de60, 'pid'))]:
            encoded = struct.unpack('<Q', self.read(BASE + table + 16 + slot, 8))[0]
            decoded = BASE + 0x7004000 + (encoded & 0xffffffff)
            assert decoded == BASE + target, (hex(table), hex(slot), hex(decoded))
            slots.append(dict(table=hex(BASE + table), address_point_delta=16,
                              slot=hex(slot), encoded=hex(encoded), target=hex(decoded), method=name))
        self.slots = slots

    def write(self, address, value):
        self.m.mem_write(address, struct.pack('<Q', value))

    def hook(self, m, pc, size, user):
        if pc == self.stop:
            m.emu_stop()
            return
        # Native bound-check trap sites: stop before constructing panic arguments.
        if pc in (BASE + 0x8989bd4, BASE + 0x8989be0, BASE + 0x8989bec):
            self.trap = hex(pc)
            m.emu_stop()
            return
        word = struct.unpack('<I', m.mem_read(pc, 4))[0]
        if word in (0xd503237f, 0xd50323ff) or word & 0xfffffc00 in (0xdac11800, 0xdac10800) or word & 0xffffffe0 == 0xdac147e0:
            # Authentication is outside the RAM qualification. Fixture pointers
            # are already plain; XPACD therefore has no additional effect.
            m.reg_write(c.UC_ARM64_REG_PC, pc + 4)
            return
        if word == 0xd65f0fff:
            m.reg_write(c.UC_ARM64_REG_PC, m.reg_read(c.UC_ARM64_REG_X30))
            return
        if word & 0xfffffc00 == 0xd73f0800:
            target = m.reg_read(REGS[(word >> 5) & 31])
            if target in (BASE + 0x89aeb74, BASE + 0x89afa80, BASE + 0x8a096a0,
                          BASE + 0x897de60, BASE + 0x897de70):
                self.calls.append(('native_virtual', hex(target)))
                m.reg_write(c.UC_ARM64_REG_X30, pc + 4)
                m.reg_write(c.UC_ARM64_REG_PC, target)
                return
            self.service(target, pc)
            return
        if word >> 26 == 0b100101:
            imm = word & 0x3ffffff
            if imm & (1 << 25):
                imm -= 1 << 26
            target = pc + imm * 4
            if target in (BASE + 0x89897cc, BASE + 0x89ed740):
                self.calls.append(('native_direct', hex(target)))
                return
            self.service(target, pc)

    def service(self, target, pc):
        m, a = self.m, self.active
        x0 = m.reg_read(REGS[0])
        if target in (BASE + 0xb7b13c4, BASE + 0xb7b27c0):
            assert x0 in (LOCK, RLOCK), ('lock object', hex(x0))
            self.calls.append(('lock' if target == BASE + 0xb7b13c4 else 'unlock', hex(x0)))
        elif target == BASE + 0x89aec4c:
            assert x0 == F + 0x1158
            self.calls.append(('synthetic_grow', a['grow']))
            if a['grow']:
                self.write(F + 0x11e0, 1 << a['block'])
            m.reg_write(REGS[0], int(a['grow']))
        elif target == RETAIN:
            assert x0 == RES
            self.calls.append(('retain_resource', hex(x0)))
        elif target == FWGET:
            assert x0 == MF
            self.calls.append(('firmware_mapping_158', hex(x0)))
            m.reg_write(REGS[0], a['fw_base'])
        elif target == CPUGET:
            assert x0 == MC
            self.calls.append(('cpu_mapping_138', hex(x0)))
            m.reg_write(REGS[0], CPU)
        elif target == BASE + 0xa8032a8:
            assert x0 in (MF, MD)
            result = a['prepare_fw' if x0 == MF else 'prepare_device']
            self.calls.append(('external_mapping_prepare', hex(x0), result))
            m.reg_write(REGS[0], result)
        elif target == BASE + 0xa8032b4:
            assert x0 == MF
            self.calls.append(('external_mapping_complete', hex(x0)))
        elif target == BASE + 0xbeaf410:
            assert x0 == Q and m.reg_read(REGS[1]) == BASE + 0xc6e6298
            self.calls.append(('synthetic_owner_metacast', hex(x0)))
            m.reg_write(REGS[0], Q)
        elif target == METALLOC:
            assert x0 == BASE + 0xc6e8048
            self.calls.append(('synthetic_qos_metaclass_alloc', hex(x0)))
            m.reg_write(REGS[0], QOS)
        elif target == QBASE:
            assert x0 == QOS
            self.calls.append(('inherited_hardware_buffer_init', a.get('base_init', 1)))
            m.reg_write(REGS[0], a.get('base_init', 1))
        elif target == BASE + 0xbf260b8:
            self.calls.append(('synthetic_lock_alloc', a.get('lock_result', QLOCK)))
            m.reg_write(REGS[0], a.get('lock_result', QLOCK))
        elif target == BASE + 0xa7f9f18:
            assert x0 == A
            self.calls.append(('external_get_gpu_task', hex(x0)))
            m.reg_write(REGS[0], TASK)
        elif target == BASE + 0xbd77200:
            assert [m.reg_read(REGS[j]) for j in (0, 1)] == [F + 0x1158 + 0x64, 30]
            self.calls.append(('external_registration', 30))
            # Supplied no-op registration service. Its actual registry mutations
            # are deliberately excluded from the whole-object expectation.
        else:
            raise AssertionError(('Unreviewed service', hex(pc), hex(target), hex(x0)))
        m.reg_write(c.UC_ARM64_REG_PC, pc + 4)

    def run(self, start, end=STOP, values=None, count=6000):
        self.stop = end
        self.trap = None
        self.calls.clear()
        for reg in REGS:
            self.m.reg_write(reg, 0)
        self.m.reg_write(c.UC_ARM64_REG_SP, STACK)
        self.m.reg_write(c.UC_ARM64_REG_X30, STOP)
        for reg, value in (values or {}).items():
            self.m.reg_write(REGS[reg], value)
        self.m.emu_start(start, end, count=count)
        pc = self.m.reg_read(c.UC_ARM64_REG_PC)
        assert pc == end or self.trap, ('did not reach bound', hex(pc), hex(end))

    def check(self, objects):
        for address, expected in objects.items():
            actual = bytes(self.m.mem_read(address, len(expected)))
            if actual != bytes(expected):
                diffs = [(hex(i), expected[i], actual[i]) for i in range(len(expected)) if expected[i] != actual[i]]
                raise AssertionError(('whole-object mismatch', hex(address), diffs[:12]))


def fixtures(audit, rng, index, mode='success'):
    sizes = {Q: 0x1000, A: 0x1000, F: 0x2000, BIT: 0x1000,
             ARR: 0x1000, ALLOC: 0x4000, RES: 0x1000, RVT: 0x1000,
             MF: 0x1000, MD: 0x1000, MC: 0x1000, MVT: 0x1000,
             CPU: 0x8000, TASK: 0x1000, QOS: 0x1000, QVT: 0x1000,
             CH: 0x1000, CVT: 0x1000, STATE: 0x1000, DESC: 0x1000,
             CFG: 0x1000, PVT: 0x1000}
    objects = {address: bytearray(rng.randbytes(size)) for address, size in sizes.items()}
    block, bit = index % 4, index % 256
    slots = [64, 128, 256, 512][(index // 4) % 4]
    global_slot = block * 256 + bit
    alloc_index, remainder = divmod(global_slot, slots)
    fw_base = 0xfffffc2000000000 + (index << 16)
    params = dict(block=block, bit=bit, slots=slots, global_slot=global_slot,
                  alloc_index=alloc_index, remainder=remainder, fw_base=fw_base,
                  grow=mode == 'grow_success', prepare_fw=int(mode == 'prepare_fw_fail'),
                  prepare_device=int(mode == 'prepare_device_fail'), owner_byte=index % 256)
    put(objects[Q], 0x538, A)
    put(objects[Q], 0x490, TASK)
    put(objects[Q], 0x898, QOS)
    put(objects[A], 0x5b0, F)
    put(objects[A], 0x140, EVENT)
    put(objects[F], 0x1158, PVT)
    put(objects[F], 0x1168, 0 if mode == 'missing_event_machine' else EVENT)
    put(objects[F], 0x1184, index % 2, 'I')
    put(objects[F], 0x118c, index % 9, 'I')
    put(objects[F], 0x1190, LOCK)
    put(objects[F], 0x1198, ARR)
    put(objects[F], 0x11a0, 16 * 8)
    put(objects[F], 0x11b8, slots, 'I')
    put(objects[F], 0x11e0, 0 if mode.startswith('grow_') else 1 << block)
    put(objects[F], 0x11e8, BIT)
    put(objects[F], 0x11f8, 0x40)
    objects[BIT][:4 * 32] = bytes(4 * 32)
    put(objects[BIT], block * 32 + (bit // 64) * 8, 1 << (bit % 64))
    if index & 1 and bit < 255:
        # Second free bit keeps the top-level block available after allocation.
        p = (bit + 1) // 64 * 8 + block * 32
        put(objects[BIT], p, get(objects[BIT], p) | (1 << ((bit + 1) % 64)))
    for j in range(16):
        put(objects[ARR], j * 8, ALLOC + j * 0x20)
        put(objects[ALLOC], j * 0x20 + 8, RES)
    put(objects[RES], 0, RVT)
    put(objects[RES], 0x40, RLOCK)
    put(objects[RES], 0x50, MF)
    put(objects[RES], 0x58, MD)
    put(objects[RES], 0x60, MC)
    for address in (MF, MD, MC):
        put(objects[address], 0, MVT)
    put(objects[RVT], 0x20, RETAIN)
    put(objects[MVT], 0x158, FWGET)
    put(objects[MVT], 0x138, CPUGET)
    put(objects[PVT], 0x50, BASE + 0x89aeb74)
    put(objects[PVT], 0x20, BASE + 0x89afa80)
    objects[TASK][0x120] = params['owner_byte']
    put(objects[QVT], 0x150, BASE + 0x8a096a0)
    put(objects[QOS], 0, QVT)
    put(objects[CH], 0, CVT)
    put(objects[CH], 0x58, STATE)
    put(objects[CVT], 0x1f0, BASE + 0x897de70)
    put(objects[CVT], 0x1f8, BASE + 0x897de60)
    put(objects[DESC], 0x60, Q)
    put(objects[DESC], 0x170, CH)
    for address, obj in objects.items():
        audit.m.mem_write(address, bytes(obj))
    audit.active = params
    return objects, params


def model_allocate(objects, p, mode):
    expected = {a: bytearray(o) for a, o in objects.items()}
    q, f, bits, alloc, res, cpu = [expected[a] for a in (Q, F, BIT, ALLOC, RES, CPU)]
    if mode == 'grow_success':
        put(f, 0x11e0, 1 << p['block'])  # Explicit synthetic grow mutation.
    allocated = mode not in ('missing_event_machine', 'grow_fail')
    if allocated:
        put(q, 0x8a8, RES)
        off = p['alloc_index'] * 0x20
        put(alloc, off, (get(alloc, off, 'I') + 1) & 0xffffffff, 'I')
        put(q, 0x8b8, p['fw_base'] + p['remainder'] * 0x40)
        put(q, 0x8a0, CPU + p['remainder'] * 0x40)
        wordoff = p['block'] * 32 + p['bit'] // 64 * 8
        put(bits, wordoff, get(bits, wordoff) & ~(1 << (p['bit'] % 64)))
        if not any(bits[p['block'] * 32:p['block'] * 32 + 32]):
            put(f, 0x11e0, get(f, 0x11e0) & ~(1 << p['block']))
    put(q, 0x8b0, p['global_slot'] if allocated else 0xffffffff, 'I')
    if get(f, 0x1184, 'I') == 1:
        count = sum(get(bits, b * 32 + k * 8).bit_count()
                    for b in range(4) if get(f, 0x11e0) & (1 << b) for k in range(4))
        put(f, 0x118c, min(get(f, 0x118c, 'I'), count), 'I')
    success = allocated and not p['prepare_fw'] and not p['prepare_device']
    if success:
        put(res, 0x38, (get(res, 0x38) + 1) & MASK64)
        off = p['remainder'] * 0x40
        cpu[off:off + 0x38] = bytes(0x38)
        put(cpu, off, 0xffff, 'H')
        cpu[off + 5] = 1
        cpu[off + 0x33] = 0xff
        cpu[off + 0x26] = p['owner_byte']
    return expected, success


def run_audit(audit):
    rng = random.Random(6040909)
    counts = dict(allocator_success=0, allocator_failures=0, joined_config=0,
                  queue_reset=0, pool_constructor=0, pool_init=0, qos_init=0,
                  native_bounds_traps=0, seed_owner_values=0, native_pid_chain=0)
    for i in range(256):
        objects, p = fixtures(audit, rng, i)
        expected, success = model_allocate(objects, p, 'success')
        audit.run(BASE + 0x89897cc, values={0: Q})
        assert audit.m.reg_read(REGS[0]) == int(success)
        assert audit.m.reg_read(c.UC_ARM64_REG_SP) == STACK
        audit.check(expected)
        counts['allocator_success'] += 1
        counts['seed_owner_values'] += 1
        # Joined native config producer uses the actual allocated queue+8b8.
        # Execute the actual channel constructor PID copy, reset publication,
        # and both real, pinned getters; all surrounding channel bytes checked.
        objects = expected
        pid = get(objects[Q], 0x498, 'I')
        channel = objects[CH]
        put(channel, 0xa8, 0)
        put(channel, 0x38, 7, 'I')
        channel[0x3c] = 0
        put(channel, 0xf8, get(objects[Q], 0x8b8))
        put(channel, 0x1f0, get(objects[Q], 0x450, 'I'), 'I')
        put(channel, 0x1f8, Q)
        put(channel, 0x40, MASK64)
        put(channel, 0x48, 0xffffffff, 'I')
        put(channel, 0x4c, pid, 'I')
        audit.run(BASE + 0x897fab8, BASE + 0x897faec, {19: CH, 21: Q, 25: 7})
        audit.check(objects)
        audit.run(BASE + 0x897deec, BASE + 0x897def8, {0: CH})
        put(objects[STATE], 0x48, pid, 'I')
        counts['native_pid_chain'] += 1
        cfg = objects[CFG]
        put(cfg, 0x52, objects[DESC][0x2f6] & 1, 'I')
        put(cfg, 0x4a, get(objects[Q], 0x8b8))
        put(cfg, 0x56, get(objects[QOS], 0x10, 'I'), 'I')
        put(cfg, 0x5e, get(objects[STATE], 0x40, 'I'), 'I')
        put(cfg, 0x5a, pid, 'I')
        audit.run(BASE + 0x895be40, BASE + 0x895bf04, {20: DESC, 24: CFG})
        assert [x[0] for x in audit.calls] == ['synthetic_owner_metacast', 'synthetic_owner_metacast', 'native_virtual', 'native_virtual']
        audit.check(objects)
        counts['joined_config'] += 1
    for i, mode in enumerate(('missing_event_machine', 'grow_fail', 'grow_success',
                               'prepare_fw_fail', 'prepare_device_fail') * 8):
        objects, p = fixtures(audit, rng, i + 300, mode)
        expected, success = model_allocate(objects, p, mode)
        audit.run(BASE + 0x89897cc, values={0: Q})
        assert audit.m.reg_read(REGS[0]) == int(success)
        audit.check(expected)
        counts['allocator_success' if success else 'allocator_failures'] += 1
        if mode == 'prepare_device_fail':
            assert ('external_mapping_complete', hex(MF)) in audit.calls
        if mode == 'prepare_fw_fail':
            assert not any(x[0] == 'external_mapping_complete' for x in audit.calls)
    # Execute actual ensureReclaimableResources caller; accepted flag changes
    # only on success. Failure branch is stopped at its native epilogue entry.
    for mode in ('success', 'prepare_device_fail', 'missing_event_machine'):
        objects, p = fixtures(audit, rng, 2, mode)
        expected, success = model_allocate(objects, p, mode)
        if success:
            expected[Q][0x5f0] = 1
        audit.run(BASE + 0x89896a4, BASE + (0x89896b8 if success else 0x89896f4), {19: Q})
        audit.check(expected)
        counts['allocator_success' if success else 'allocator_failures'] += 1
    # The genuine queue reset constructor prefix preserves every other byte.
    for i in range(8):
        objects, _ = fixtures(audit, rng, i)
        q = objects[Q]
        q[0x8a0:0x8b0] = bytes(16)
        put(q, 0x8b0, 0xffffffff, 'I')
        put(q, 0x8b8, 0)
        q[0x5f0] = 0
        put(q, 0x5f8, 0)
        put(q, 0x8c0, 0xffffffff, 'I')
        audit.run(BASE + 0x898e510, BASE + 0x898e530, {0: Q})
        audit.check(objects)
        counts['queue_reset'] += 1
    # Guarded array extent/bias failures stop at the actual native trap sites.
    for extent, bias, target in ((0, 0, 0x8989be0), (128, -9, 0x8989be0),
                                 (128, 0x7fffffff, 0x8989bd4)):
        objects, p = fixtures(audit, rng, 255)
        put(objects[F], 0x11a0, ((bias & 0xffffffff) << 32) | extent)
        audit.m.mem_write(F, bytes(objects[F]))
        audit.run(BASE + 0x89897cc, values={0: Q})
        assert audit.trap == hex(BASE + target)
        audit.check(objects)
        counts['native_bounds_traps'] += 1
    # Pool constructor initializes exactly this embedded-object region.
    for i in range(8):
        objects, _ = fixtures(audit, rng, i)
        f = objects[F]
        d0, stack_vec = rng.getrandbits(64), rng.randbytes(16)
        audit.m.mem_write(STACK, stack_vec)
        audit.m.reg_write(c.UC_ARM64_REG_Q0, d0)
        audit.m.reg_write(c.UC_ARM64_REG_Q1, 0)
        put(f, 0x1158, BASE + 0x7ea7330)
        put(f, 0x1170, 0)
        put(f, 0x1188, d0)
        f[0x1160:0x1170] = bytes(16)
        put(f, 0x1190, QLOCK)
        f[0x1198:0x11b8] = bytes(32)
        put(f, 0x11b8, 0, 'I')
        put(f, 0x11f8, 0)
        put(f, 0x1200, 0, 'I')
        f[0x11e0:0x11f0] = bytes(16)
        put(f, 0x11f0, 0, 'I')
        audit.run(BASE + 0x89d2d50, BASE + 0x89d2dc4, {19: F})
        audit.check(objects)
        counts['pool_constructor'] += 1
    # Native FW init caller passes stride64, flags9, caching1, tasknull,
    # shrink0; actual pool init reads supplied kernel-global page geometry.
    audit.write(BASE + 0x7ea2000 + 0x5c0, GLOBALS)
    audit.write(GLOBALS, EVENT)
    audit.write(BASE + 0x7ea2000 + 0x388, GLOBALS + 8)
    for shift in (12, 14, 16):
        objects, _ = fixtures(audit, rng, shift)
        put(objects[F], 0x298, A)
        audit.m.mem_write(F, bytes(objects[F]))
        audit.m.mem_write(GLOBALS + 8, struct.pack('<I', shift))
        f = objects[F]
        pool = 0x1158
        put(f, pool + 8, A)
        put(f, pool + 0x10, EVENT)
        put(f, pool + 0x18, TASK)
        put(f, pool + 0x20, EVENT)
        f[pool + 0x28] = 0
        put(f, pool + 0x2c, 0, 'I')
        put(f, pool + 0xb0, 9)
        put(f, pool + 0xb8, 1, 'I')
        put(f, pool + 0xa0, 64)
        allocation_bytes = ((1 << shift) + 2 * 64 - 1) & -(1 << shift)
        put(f, pool + 0x58, allocation_bytes)
        put(f, pool + 0x60, allocation_bytes // 64, 'I')
        audit.run(BASE + 0x89cf024, BASE + 0x89cf06c, {19: F})
        audit.check(objects)
        counts['pool_init'] += 1
    # Full native QOS init and actual command-queue association caller.
    audit.write(BASE + 0xc6e8048, MCLASSVT)
    audit.write(MCLASSVT + 0xa8, METALLOC)
    audit.write(BASE + 0x7ea2000 + 0x4e0, BASEVT)
    audit.write(BASEVT + 0xb8, QBASE)
    for base_init, lock_result in ((1, QLOCK), (0, QLOCK), (1, 0)):
        objects, p = fixtures(audit, rng, 2)
        p.update(base_init=base_init, lock_result=lock_result)
        success = bool(base_init and lock_result)
        put(objects[Q], 0x898, 0xabcdef0123456780)
        audit.m.mem_write(Q, bytes(objects[Q]))
        if success:
            put(objects[Q], 0x898, QOS)
        qos = objects[QOS]
        if base_init:
            put(qos, 0x10, 0xffffffff, 'I')
            put(qos, 0x58, A)
            put(qos, 0x60, Q)
            qos[0x45] = 0xff
            put(qos, 0x40, 0, 'I')
            put(qos, 0x68, 0, 'I')
            put(qos, 0x50, lock_result)
        audit.run(BASE + 0x898e8bc, BASE + (0x898e920 if success else 0x898ea88), {19: Q})
        audit.check(objects)
        counts['qos_init'] += 1
    return counts


def candidate_comparison(candidate):
    prep = json.loads((candidate / 'preparation.json').read_text())
    backing = (candidate / 'backing.bin').read_bytes()
    backing_sha = hashlib.sha256(backing).hexdigest()
    assert len(backing) == prep['pages'] * 16384, 'Candidate backing extent differs from receipt'
    assert backing_sha == prep['data_sha256'], 'Candidate backing identity differs from receipt'
    aliases = [int(x, 0) for x in prep['firmware_aliases']]
    assert len(aliases) == prep['pages'], 'Candidate alias extent differs from receipt'
    seed = bytearray(64)
    put(seed, 0, 0xffff, 'H')
    seed[5], seed[0x26], seed[0x33] = 1, 2, 0xff
    rows = []
    for index, queue in enumerate(prep['owned_scheduler']):
        off = (48 + index * 2) * 16384
        owner = get(backing, off + 0x1000 + 0x4a)
        page = next(j for j, base in enumerate(aliases) if base and base <= owner < base + 16384)
        native_seed = backing[page * 16384 + owner - aliases[page]:page * 16384 + owner - aliases[page] + 64]
        assert native_seed == seed, 'Candidate seed changed; re-review required'
        rows.append(dict(queue_id=queue['queue_id'], owner_pointer=hex(owner),
                         state_owner_pointer=hex(get(backing, off + 0x9c)),
                         state_pid_current=get(backing, off + 0x48, 'I'),
                         state_subpriority_current=get(backing, off + 0x40, 'I'),
                         config_update=get(backing, off + 0x1000 + 0x52, 'I'),
                         config_qos_hardware_buffer_id=get(backing, off + 0x1000 + 0x56, 'I'),
                         config_pid=get(backing, off + 0x1000 + 0x5a, 'I'),
                         config_subpriority=get(backing, off + 0x1000 + 0x5e, 'I'),
                         pid_matches_native_getter=get(backing, off + 0x48, 'I') == get(backing, off + 0x1000 + 0x5a, 'I'),
                         subpriority_matches_native_getter=get(backing, off + 0x40, 'I') == get(backing, off + 0x1000 + 0x5e, 'I'),
                         matches_native_prefix_if_owner_byte_120_is_2=True,
                         tail_38_40_zero=True))
    return dict(path=str(candidate.resolve()), backing_sha256=backing_sha,
                backing_extent=len(backing), receipt_bound=True,
                preparation_sha256=hashlib.sha256((candidate / 'preparation.json').read_bytes()).hexdigest(),
                seed_sha256=hashlib.sha256(seed).hexdigest(), rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--macho', type=Path, default=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X'))
    parser.add_argument('--output-dir', type=Path, default=REPO / 'out/native-scheduler-state')
    parser.add_argument('--candidate', type=Path, default=REPO / 'out/recovery-dispatch/candidate/asc-graph-init')
    args = parser.parse_args()
    audit = Audit(args.macho.read_bytes())
    counts = run_audit(audit)
    report = dict(schema='native-scheduler-state-audit-v1', binary_sha256=PIN,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  native_ranges={name: dict(start=hex(BASE + start), end_exclusive=hex(BASE + end),
                                           sha256=hashlib.sha256(audit.read(BASE + start, end - start)).hexdigest())
                                 for name, (start, end) in RANGES.items()},
                  static_evidence_ranges={name: dict(start=hex(BASE + start), end_exclusive=hex(BASE + end),
                                                    sha256=hashlib.sha256(audit.read(BASE + start, end - start)).hexdigest())
                                          for name, (start, end) in EVIDENCE_RANGES.items()},
                  vtable_slots=audit.slots, counts=counts,
                  candidate=candidate_comparison(args.candidate),
                  qualified_fields={'scheduler_stride': 64, 'initialized_extent': 56,
                                    'state_26_source': 'command_queue+0x490 -> byte+0x120',
                                    'config_4a_source': 'command_queue+0x8b8 = firmware mapping158 + allocated subslot offset',
                                    'config_56_source': 'command_queue+0x898 AGXQOSQueue -> hardware-buffer ID u32+0x10',
                                    'config_5e_source': 'AGXChannel::getSubPriority -> mapped channel state+0x40',
                                    'config_5a_source': 'AGXChannel::getPid -> mapped channel state+0x48',
                                    'channel_pid_producer': 'queue+0x498 -> channel+0x4c -> mapped state+0x48',
                                    'qos_init_id': '0xffffffff', 'pool_gate_1168': 'accelerator+0x140 event-machine pointer'},
                  findings=[
                      'The current seed prefix equals native initialization only for supplied owner byte+0x120=2; native initialization preserves subslot bytes 0x38..0x3f.',
                      'Mapped resource subslot construction, queue+0x8b8 publication and config+0x4a copy are joined in RAM; actual mapping/VM services remain supplied.',
                      'Config+0x56 is a QoS hardware-buffer ID. Native init uses 0xffffffff; HardwareBufferIDManager::alloc later writes the owned ID at 0x89ec4c0. Zero can be an allocated ID but no ID ownership is qualified here.',
                      'Config+0x5a is PID and+0x5e subpriority. The current staged config zeros differ from native getters applied to its staged channel state+0x48=1/2 and+0x40=1.',
                      'The document Channel UUID label at channel state+0x48 conflicts with native getPid and the native queue+0x498 -> host channel+0x4c -> mapped state+0x48 producer.',
                      'A mapping-prepare failure returns false after consuming a pool slot, retaining the resource and publishing queue pointers. This function does not roll those mutations back.',
                  ],
                  services=['synthetic lowest-block grow; no actual backing allocation',
                            'resource retain service; no actual refcount implementation',
                            'firmware mapping virtual158 and CPU mapping virtual138 address returns',
                            'external mapping prepare/complete a8032a8/a8032b4; return values supplied',
                            'kernel lock/unlock/lock allocation; no synchronization',
                            'owner metacast beaf410 returned supplied AGXCommandQueue',
                            'QOS metaclass allocation supplied object; inherited hardware-buffer init result supplied',
                            'pool task lookup a7f9f18 supplied IOGPUTask; kernel registration bd77200 no-op',
                            'kernel-global geometry/symbol-service pointers supplied; PAC bypassed'],
                  remaining_gaps=['Actual task+0x120 producer and queue+0x490 association to installed GPU VM/ASID',
                                  'Actual resource allocation, page-table installation, firmware/CPU alias mapping and lifetime',
                                  'AGXQOSQueue prepare/HardwareBufferIDManager ID ownership joined to firmware configuration',
                                  'Actual process PID queue+0x498 source and whether the experimental PID is required for execution',
                                  'Firmware context acceptance, execution/completion, cache coherence and retirement'],
                  qualification='Original matched native slices run in RAM, complete fixture objects/guards compared to independent numeric model. No native whole service chain, real VM/UAT association, hardware operation or cause of idle recovery failure established.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(counts=counts, report=str((args.output_dir / 'report.json').resolve())), indent=2))


if __name__ == '__main__':
    main()
