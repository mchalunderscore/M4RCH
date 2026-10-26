#!/usr/bin/env python3
"""RAM-only check of recovery's empty main-mask7 callback path.

Usage: audit-recovery-empty-callbacks.py CAPTURE GRAPH_RECEIPT OUTPUT
No hardware, candidate changes, RTKernel scheduling, or live-PC inference.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import unicorn as u
from unicorn import arm64_const as c

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('capture', type=Path)
p.add_argument('graph_receipt', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
sha = lambda b: hashlib.sha256(b).hexdigest()
text = (a.capture / 'text.bin').read_bytes()
data = (a.capture / 'data-diagnostic.bin').read_bytes()
data_receipt = json.loads((a.capture / 'data-diagnostic-receipt.json').read_text())
assert data_receipt['base'] == '0x60000'
assert len(data) == data_receipt['bytes'] and sha(data) == data_receipt['data_sha256']
spec = importlib.util.spec_from_file_location('contract', Path(__file__).with_name('firmware_text_contract.py'))
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
identity = contract.qualify(text)
layout = json.loads(a.graph_receipt.read_text())
arena = (a.capture / 'objects-after.bin').read_bytes()
assert len(arena) == layout['arena_bytes']
base = int(layout['base'], 16)
objects = {o['name']: o for o in layout['objects']}
main = objects['main']['arena_offset']
status_a = int(objects['status_a']['gpu_va'], 16)
d64 = lambda v: struct.unpack_from('<Q', data, v - 0x60000)[0]
d32 = lambda v: struct.unpack_from('<I', data, v - 0x60000)[0]
shared32 = lambda v: struct.unpack_from('<I', arena, v - base)[0]
ptr = lambda off: struct.unpack_from('<Q', arena, main + off)[0]
assert d64(0x18e4c0) == int(objects['main']['gpu_va'], 16)
assert d32(0x18e688) == 2
assert d64(0x142c70) == d64(0x142c78) == 0
queues = []
for lane in range(4):
    for engine, off in [('TA', 0x20), ('3D', 0x40), ('CDM', 0x60)]:
        pointers = [ptr(lane * 0x60 + off + sub) for sub in (0, 8, 16)]
        values = [shared32(v) for v in pointers]
        assert values == [0, 0, 0]
        queues.append(dict(lane=lane, engine=engine, cursor_pointers=list(map(hex, pointers)),
                           consumer_prefetch_producer=values))
controls = [shared32(ptr(off)) for off in (0x1a0, 0x1a8, 0x1b0)]
assert controls == [32, 32, 32]
table = []
for addr, mask, arg in [(0x874d8, 2, 1), (0x874f0, 1, 0), (0x87508, 4, 2)]:
    observed = struct.unpack_from('<QQQ', data, addr - 0x60000)
    assert observed[0] == mask and observed[1] & 0xffffffff == 0x383f0 and observed[2] == arg
    table.append(dict(address=hex(addr), mask=hex(mask), callback='0x383f0', argument=arg))
direct_targets = set()
for pc in range(0x383f0, 0x38c24, 4):
    word = struct.unpack_from('<I', text, pc)[0]
    if word & 0xfc000000 == 0x94000000:
        off = word & 0x3ffffff
        if off & (1 << 25):
            off -= 1 << 26
        direct_targets.add(pc + off * 4)
assert not direct_targets.intersection((0x458d0, 0x45a54))

cases = []
for mask in (0, 3, 0x43):
    for arg in range(3):
        m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
        for addr, n in [(0, 0x60000), (0x60000, 0x138000),
                        (0xfffffc0000060000, 0x138000), (base, len(arena)), (0x300000, 0x10000)]:
            m.mem_map(addr, n)
        m.mem_write(0, text)
        m.mem_write(0x60000, data)
        m.mem_write(0xfffffc0000060000, data)
        m.mem_write(base, arena)
        m.mem_write(0x18eecc, struct.pack('<I', mask))
        m.reg_write(c.UC_ARM64_REG_CPACR_EL1, 3 << 20)
        m.reg_write(c.UC_ARM64_REG_SP, 0x30f000)
        m.reg_write(c.UC_ARM64_REG_X30, 0x5fff0)
        m.reg_write(c.UC_ARM64_REG_X0, arg)
        hits, calls, cache, traces = {}, [], [], []
        def hook(mu, pc, n, unused):
            hits[pc] = hits.get(pc, 0) + 1
            if pc == 0x5fff0:
                mu.emu_stop()
                return
            if pc in (0x3ca80, 0x1f384):
                if pc == 0x3ca80:
                    cache.append([mu.reg_read(c.UC_ARM64_REG_X0), mu.reg_read(c.UC_ARM64_REG_X1)])
                    assert cache[-1][1] == 0
                else:
                    regs = [c.UC_ARM64_REG_X0, c.UC_ARM64_REG_X1, c.UC_ARM64_REG_X2,
                            c.UC_ARM64_REG_X3, c.UC_ARM64_REG_X4, c.UC_ARM64_REG_X5]
                    traces.append([mu.reg_read(reg) for reg in regs])
                mu.reg_write(c.UC_ARM64_REG_PC, mu.reg_read(c.UC_ARM64_REG_X30))
                return
            word = struct.unpack_from('<I', text, pc)[0]
            if word == 0xd65f0fff:  # RETAB: preserve ordinary return, exclude PAC semantics.
                mu.reg_write(c.UC_ARM64_REG_PC, mu.reg_read(c.UC_ARM64_REG_X30))
                return
            if word & 0xfc000000 == 0x94000000:
                off = word & 0x3ffffff
                if off & (1 << 25):
                    off -= 1 << 26
                target = pc + off * 4
                calls.append([pc, target])
                assert target in (0x33a68, 0x385c, 0x3ca80, 0x1a6d4, 0x1f384), hex(target)
        m.hook_add(u.UC_HOOK_CODE, hook)
        m.emu_start(0x383f0, 0x5fff4, count=5000)
        assert hits.get(0x5fff0) == hits.get(0x33d14) == hits.get(0x1a8bc) == 1
        assert hits.get(0x388d8) == 4 and len(cache) == 24
        assert struct.unpack('<I', m.mem_read(status_a + 0xc, 4))[0] == 0
        assert bytes(m.mem_read(base, len(arena))) == arena
        expected = [[0x112, 0, 4, 0x200020, 0, 0]]
        expected += [[0x112, 0, lane, 0, 0, 0] for lane in range(4)]
        assert traces == (expected if mask & 2 else [])
        cases.append(dict(argument=arg, trace_mask=hex(mask), instructions=sum(hits.values()),
                          lanes_visited=4, zero_length_cache_helper_calls=24,
                          helper_targets=sorted({hex(v[1]) for v in calls}),
                          trace_event_function_args=traces, shared_arena_unchanged=True,
                          callback_returned=True))

# Exact atomic token slices only. Stop before scheduler/context restore helpers.
m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)  # Native semaphore slices use LSE CAS.
m.mem_map(0, 0x60000)
m.mem_write(0, text)
m.mem_map(0x300000, 0x1000)
token_cases = []
for initial in (0, 1):
    m.mem_write(0x300000, struct.pack('<Q', initial))
    m.reg_write(c.UC_ARM64_REG_X0, 0x300000)
    m.emu_start(0x458e8, 0x45958, count=12)
    assert m.reg_read(c.UC_ARM64_REG_PC) == 0x45958
    after = struct.unpack('<Q', m.mem_read(0x300000, 8))[0]
    assert after == 1
    token_cases.append(dict(operation='signal', initial=initial, final=after))
    m.reg_write(c.UC_ARM64_REG_X0, 0x300000)
    m.reg_write(c.UC_ARM64_REG_X9, 1)
    m.emu_start(0x45a78, 0x45a84, count=3)
    assert m.reg_read(c.UC_ARM64_REG_PC) == 0x45a84
    after = struct.unpack('<Q', m.mem_read(0x300000, 8))[0]
    assert after == 0
    token_cases.append(dict(operation='wait_fast_path', initial=1, final=after))

ranges = [(0x383f0, 0x38c24), (0x33a68, 0x33d24), (0x1a6d4, 0x1a8c0),
          (0x385c, 0x38e4), (0x39c0, 0x39e0), (0x458d0, 0x45958), (0x45a54, 0x45b28)]
out = dict(schema='m4rch-recovery-empty-callbacks-v1', boot_id=data_receipt['boot_id'],
           inputs=dict(capture=str(a.capture), text_identity=identity, data_sha256=sha(data),
                       objects_after_sha256=sha(arena), graph_receipt_sha256=sha(a.graph_receipt.read_bytes())),
           matched_ranges=[dict(start=hex(lo), end_exclusive=hex(hi), sha256=sha(text[lo:hi])) for lo, hi in ranges],
           callback_table=table, callback_direct_bl_targets=sorted(map(hex, direct_targets)),
           shared_queue_cursors=queues, shared_control_cursors=controls,
           sampled_private_fields={'0x18e688': 2, '0x142c70': 0, '0x142c78': 0},
           ram_cases=cases, atomic_token_cases=token_cases,
           conclusions=[
               '383f0 arguments0/1/2 all traverse four lanes; they are not distinct lane selectors.',
               'No direct458d0 signal or45a54 wait exists in383f0; recovery430 is signalled by the auxiliary worker, independently audited in recovery-worker-ack-path.json.',
               'For sampled state2 and empty pending bitmaps,33a68 returns before activation/power-event/semaphore400 work, and1a6d4 returns before job processing.',
               'Empty owned queues/control cursors reach callback return with no GPU/KSM register operand or job helper on the executed path, excluding intercepted cache and trace helper behavior.',
               'There is no native initialization omission established by empty queues or KSM pause_ack1 on this path. Do not seed firmware-private semaphore values.',
               'Signal with initial0 stores1; another signal retains1; wait consumes1 to0. Zero is a valid initial unsignalled state. A coherent blocked single-waiter slow path stores a task pointer at45acc, but off-core sampled zero cannot locate a live task.'
           ],
           next_observation=dict(mask_bit=1, entry_event='0x12f', exit_event='0x130',
                                 handler_masks=['0x2', '0x1', '0x4'],
                                 queue_event='0x112', queue_function=0,
                                 queue_args=['lane0..3', 'producer | consumer<<16 for TA',
                                             'producer | consumer<<16 for3D', 'producer | consumer<<16 forCDM'],
                                 qualification='Fresh role0 records only. Entry/exit delimit callback return; queue112 occurs after control service and prefetch. Absence cannot identify a livePC, and producer helper may block.'),
           hardware_actions=False, candidate_changes=False,
           qualification='RAM-only exact matched instruction branch/address proof. Private DATA values are sampled with unproven firmware-cache freshness. Zero-length cache helper and trace producer calls are intercepted, RETAB follows ordinary LR; scheduling, PAC, cache maintenance and trace locking are not modelled. No live callback/ACK/completion is inferred.')
a.output.write_text(json.dumps(out, indent=2) + '\n')
print(f'{len(cases)} empty callback cases, {len(token_cases)} atomic token cases passed; {a.output}')
