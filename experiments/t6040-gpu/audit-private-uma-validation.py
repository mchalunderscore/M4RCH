#!/usr/bin/env python3
"""Execute actual TA UMA locking, full native canSubmitLocked and usage update."""
from pathlib import Path
from private_uma_emulation import NativeUMA, LOCK, LOCK_END, UPDATE, CHECK, CHECK_END, expected_validation, expected_update
base = Path(__file__).with_name('audit-private-render-inputs.py')
setup = base.read_text().split('rng=random.Random(604011);')[0].replace(
    'm.hook_add(u.UC_HOOK_CODE,hook)', 'base_handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup, str(base), 'exec')); m.hook_del(base_handle)
uma = NativeUMA(m, read)
def uma_hook(m, address, size, user):
    if uma.hook(address): return
    if struct.unpack('<I', m.mem_read(address, 4))[0] == 0xd50323ff:
        m.reg_write(c.UC_ARM64_REG_PC, address+4); return
    hook(m, address, size, user)
m.hook_add(u.UC_HOOK_CODE, uma_hook)
rng = random.Random(604049)
counts = dict(cases=0, successful_validation=0, seed_mismatch=0,
              event_rejection=0, usage_updates=0, descriptor_event_updates=0)
def execute(fn, requested):
    for reg in regs: m.reg_write(reg, 0)
    for reg, value in ((c.UC_ARM64_REG_X0, D), (c.UC_ARM64_REG_X1, requested),
            (c.UC_ARM64_REG_SP, STACK), (c.UC_ARM64_REG_LR, STOP)):
        m.reg_write(reg, value)
    m.emu_start(fn, STOP, count=10000)
    assert m.reg_read(c.UC_ARM64_REG_PC) == STOP and m.reg_read(c.UC_ARM64_REG_SP) == STACK
    return m.reg_read(c.UC_ARM64_REG_W0)
for i in range(1024):
    descriptor = rng.randbytes(0x1800); m.mem_write(D, descriptor)
    wanted = [rng.getrandbits(64), rng.getrandbits(64)]
    seeds = [wanted[j] ^ int(bool(i & (1 << j))) for j in range(2)]
    event_returns = [rng.getrandbits(32) & ~1 | int(bool(i & (4 << j))) for j in range(2)]
    counters = [((1 << 64)-1 if i % 5 == 0 else rng.getrandbits(64)) for _ in range(2)]
    flags = [rng.randrange(256), rng.randrange(256)]
    uma.seed(D, seeds, event_returns, counters, flags)
    uma.qwrite(D+0x208, wanted[1]); before_d = bytes(m.mem_read(D, 0x1800))
    before_p = [bytes(m.mem_read(p, 0x220)) for p in uma.pools]
    before_n = [bytes(m.mem_read(n, 0x200)) for n in uma.nodes]
    uma.active = True; expected, events, increments = expected_validation(seeds, wanted, event_returns)
    assert execute(LOCK, wanted[0]) == expected and uma.events == events, (i, uma.events, events)
    for j, p in enumerate(uma.pools):
        ep = bytearray(before_p[j]); struct.pack_into('<Q', ep, 0x48, (counters[j]+increments[j]) & ((1 << 64)-1))
        assert bytes(m.mem_read(p, len(ep))) == ep
    assert bytes(m.mem_read(D, len(before_d))) == before_d
    for n, before in zip(uma.nodes, before_n): assert bytes(m.mem_read(n, len(before))) == before
    counts['cases'] += 1
    if expected:
        counts['seed_mismatch' if expected == 0xe00002d5 else 'event_rejection'] += 1
    else:
        counts['successful_validation'] += 1; uma.events.clear()
        execute(UPDATE, 0)
        assert uma.events == expected_update(flags), (i, uma.events, expected_update(flags))
        for j, n in enumerate(uma.nodes):
            en = bytearray(before_n[j])
            if flags[j] & 1: en[0x1b8] = 0
            assert bytes(m.mem_read(n, len(en))) == en
        for p, before in zip(uma.pools, before_p): assert bytes(m.mem_read(p, len(before))) == before
        assert bytes(m.mem_read(D, len(before_d))) == before_d
        counts['usage_updates'] += 1
        counts['descriptor_event_updates'] += sum(bool(flag & 1) for flag in flags)
report = dict(private_binary_sha256=sha, counts=counts,
    ranges=[dict(start=hex(start), end=hex(end), sha256=hashlib.sha256(read(start,end-start)).hexdigest()) for start,end in ((UPDATE,LOCK_END),(CHECK,CHECK_END))],
    qualification='1024 actual TA UMA lock calls with full native canSubmitLocked nested for reached pools; both seed mismatches and low-bit event service success/rejection, counter wrap. Successful cases execute actual usage update; randomized byte flags and full descriptor/pool/node comparisons. Mutex, event-copy/compare services explicit argument-checked fixtures; optional host tracing disabled. Logical lock order only, no real concurrency, allocation, cache, fence semantics or GPU submission.')
args.output.write_text(json.dumps(report, indent=2)+'\n'); print(counts)
