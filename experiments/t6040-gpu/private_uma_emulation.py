"""Private offline UMA validation/usage harness; all event services are fixtures."""
import struct
import unicorn as u
import unicorn.arm64_const as c

UPDATE = 0xfffffe0008a20b48
LOCK = 0xfffffe0008a20c0c
LOCK_END = 0xfffffe0008a20c9c
CHECK = 0xfffffe0008a29f88
CHECK_END = 0xfffffe0008a2a080
SEED_ERROR = 0xe00002d5
EVENT_ERROR = 0xe00002be

class NativeUMA:
    def __init__(self, machine, read):
        self.m = machine
        machine.mem_map(UPDATE & ~4095, 4096)
        machine.mem_write(UPDATE, read(UPDATE, LOCK_END-UPDATE))
        machine.mem_map(CHECK & ~4095, 8192)
        machine.mem_write(CHECK, read(CHECK, CHECK_END-CHECK))
        machine.mem_map(0x300000, 0x40000)
        self.pools = [0x300000, 0x301000]
        self.nodes = [0x302000, 0x303000]
        self.contexts = [0x304000, 0x305000]
        self.locks = [0x306000, 0x307000]
        self.gpu = 0x308000
        self.regs = [getattr(c, 'UC_ARM64_REG_X'+str(j)) for j in range(31)]
        self.events = []
        self.active = False

    def qwrite(self, address, value):
        self.m.mem_write(address, struct.pack('<Q', value))

    def seed(self, descriptor, seeds, event_returns, counters, flags):
        self.descriptor = descriptor
        self.event_returns = event_returns
        self.events.clear()
        for j in range(2):
            p, n, context, lock = (seq[j] for seq in
                (self.pools, self.nodes, self.contexts, self.locks))
            self.m.mem_write(p, bytes(0x220)); self.m.mem_write(n, bytes(0x200))
            for off, value in ((0x1d8, n), (0x1e0, seeds[j]),
                    (0x208, lock), (0x210, self.gpu), (0x48, counters[j])):
                self.qwrite(p+off, value)
            self.qwrite(n+0x28, context); self.qwrite(context+0x140, context+0x300)
            self.m.mem_write(n+0x1b8, bytes([flags[j]]))
        self.m.mem_write(self.gpu+0x1aed4, b'\x00') # Optional host tracing off.
        self.qwrite(descriptor+0x13e8, self.pools[0])
        self.qwrite(descriptor+0xb50, self.pools[1])

    def hook(self, address):
        if not self.active: return False
        word = struct.unpack('<I', self.m.mem_read(address, 4))[0]
        is_bl = word & 0xfc000000 == 0x94000000
        is_b = word & 0xfc000000 == 0x14000000
        if not (is_bl or is_b): return False
        imm = word & 0x3ffffff
        if imm & (1 << 25): imm -= 1 << 26
        target = address+imm*4
        x = [self.m.reg_read(reg) for reg in self.regs[:3]]
        if target in (0xfffffe000bf2635c, 0xfffffe000bf2645c):
            assert x[0] in self.locks
            self.events.append(('lock' if target == 0xfffffe000bf2635c else 'unlock', self.locks.index(x[0])))
            value = 0
        elif target in (0xfffffe000a7d0d18, 0xfffffe000a7d0d30):
            assert x[0] in [context+0x300 for context in self.contexts]
            j = [context+0x300 for context in self.contexts].index(x[0])
            n = self.nodes[j]
            if target == 0xfffffe000a7d0d30:
                assert x[1:] == [self.descriptor+(0xdc8 if j == 0 else 0x80), n+0x178]
                self.events.append(('check_event', j)); value = self.event_returns[j]
            else:
                pair = x[1:]
                if pair == [n+0x138, n+0x178]: kind = 'validate_usage'
                elif pair == [n+0x178, n+0x138]: kind = 'update_usage'
                elif pair == [self.descriptor+(0xdc8 if j == 0 else 0x80), n+0xf8]: kind = 'update_descriptor_event'
                else: raise AssertionError((hex(address), pair))
                self.events.append((kind, j)); value = 0
        else: return False
        self.m.reg_write(c.UC_ARM64_REG_X0, value)
        self.m.reg_write(c.UC_ARM64_REG_PC, address+4 if is_bl else self.m.reg_read(c.UC_ARM64_REG_LR))
        return True

def expected_validation(seeds, requested, event_returns):
    """Numerical contract independent of instruction traversal."""
    events = []
    increments = [0, 0]
    for j in range(2):
        events.append(('lock', j))
        if seeds[j] != requested[j]: result = SEED_ERROR
        else:
            events.extend([('validate_usage', j), ('check_event', j)])
            result = 0 if event_returns[j] & 1 else EVENT_ERROR
            increments[j] = int(bool(result))
        if result:
            events.extend(('unlock', k) for k in range(j, -1, -1))
            return result, events, increments
    return 0, events, increments

def expected_update(flags):
    events = []
    for j in range(2):
        events.append(('update_usage', j))
        if flags[j] & 1: events.append(('update_descriptor_event', j))
    events.extend([('unlock', 1), ('unlock', 0)])
    return events
