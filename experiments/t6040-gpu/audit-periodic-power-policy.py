#!/usr/bin/env python3
"""RAM-only check of saved power-policy guard and power-up counter stores.

Usage: audit-periodic-power-policy.py CAPTURE GRAPH_RECEIPT OUTPUT
No GPU, sysfs, MMIO, firmware commands, or candidate changes.
"""
import argparse
import hashlib
import importlib.util
import json
import random
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
t = (a.capture / 'text.bin').read_bytes()
ds = (a.capture / 'data-diagnostic.bin').read_bytes()
dr = json.loads((a.capture / 'data-diagnostic-receipt.json').read_text())
assert len(ds) == dr['bytes'] and sha(ds) == dr['data_sha256']
base = int(dr['base'], 16)
spec = importlib.util.spec_from_file_location('contract', Path(__file__).with_name('firmware_text_contract.py'))
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
identity = contract.qualify(t)
layout = json.loads(a.graph_receipt.read_text())
power_offset = next(o['arena_offset'] for o in layout['objects'] if o['name'] == 'power')
objects = (a.capture / 'objects-after.bin').read_bytes()
objects_before = (a.capture / 'objects-before.bin').read_bytes()
owned_objects = {o['name']: o for o in layout['objects']}
region_c_offset = owned_objects['region_c']['arena_offset']
native_path = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
native_image = native_path.read_bytes()
assert sha(native_image) == '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
native_segments = []
pos = 32
assert struct.unpack_from('<I', native_image)[0] == 0xfeedfacf
for _ in range(struct.unpack_from('<I', native_image, 16)[0]):
    cmd, size = struct.unpack_from('<II', native_image, pos)
    if cmd == 0x19:
        native_segments.append(struct.unpack_from('<QQQQ', native_image, pos + 24))
    pos += size
def native(address, count):
    address |= 0xfffffe0000000000
    spans = [offset + address - start for start, _, offset, length in native_segments
             if start <= address and address + count <= start + length]
    assert len(spans) == 1
    return native_image[spans[0]:spans[0] + count]
def native_string(address):
    return native(address, 64).split(b'\0', 1)[0].decode()
def dword(addr):
    return struct.unpack_from('<I', ds, addr - base)[0]
def pword(off):
    return struct.unpack_from('<I', objects, power_offset + off)[0]
def config_word(off):
    return struct.unpack_from('<I', objects, region_c_offset + off)[0]

m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
m.mem_map(0, 0x60000)
m.mem_write(0, t)
m.mem_map(base, (len(ds) + 4095) & -4096)
m.mem_write(base, ds)
POWER = 0x210000
m.mem_map(POWER, 0x8000)
guard_outcomes = []
# Actual fallback guard instructions. Stop before any reset/MMIO helpers.
for flag in (0, 1, 0xffffffff):
    for mode in (0, 1, 2, 3, 0xffffffff):
        m.mem_write(0x146914, struct.pack('<I', flag))
        m.mem_write(0x146908, struct.pack('<I', mode))
        hits = []
        def stop_guard(mu, pc, size, unused):
            if pc in (0xe6e8, 0xe7f8):
                hits.append(pc)
                mu.emu_stop()
        h = m.hook_add(u.UC_HOOK_CODE, stop_guard)
        m.emu_start(0xe6cc, 0xe818, count=20)
        m.hook_del(h)
        expected = 0xe6e8 if flag != 0 and mode != 1 else 0xe7f8
        assert hits == [expected], (flag, mode, hits)
        guard_outcomes.append(dict(flag=flag, mode=mode, reaches_reset_pair=expected == 0xe6e8))
# Full power image comparison across both real counter increment slices.
rng = random.Random(6040652)
counter_cases = 0
for pc in (0xd808, 0xe37c):
    for initial in (0, 1, 1209, 0xffffffff):
        image = bytearray(rng.randbytes(0x8000))
        struct.pack_into('<I', image, 0x652c, initial)
        m.mem_write(POWER, bytes(image))
        m.reg_write(c.UC_ARM64_REG_X24, POWER + 0x63c8)
        m.emu_start(pc, pc + 12, count=3)
        struct.pack_into('<I', image, 0x652c, (initial + 1) & 0xffffffff)
        assert bytes(m.mem_read(POWER, len(image))) == image
        counter_cases += 1

# Actual producer gate: main-state bit 1 prevents posting power event mask 2.
event_gate_cases = []
for state in (0, 1, 2, 3, 4, 0x40, 0xffffffff):
    m.mem_write(0x18e688, struct.pack('<I', state))
    hits = []
    def stop_event_gate(mu, pc, size, unused):
        if pc in (0x33a88, 0x33d14):
            hits.append(pc)
            mu.emu_stop()
    h = m.hook_add(u.UC_HOOK_CODE, stop_event_gate)
    m.emu_start(0x33a7c, 0x33d14 + 4, count=5)
    m.hook_del(h)
    expected = 0x33d14 if state & 2 else 0x33a88
    assert hits == [expected]
    event_gate_cases.append(dict(main_state=state, producer_gate_open=not bool(state & 2)))

# Native branch-free default stores and publication selectors, relocated intact.
DRIVER, NATIVE_CODE = 0x200000, 0x400000
m.mem_map(DRIVER, 0x3000)
m.mem_map(NATIVE_CODE, 0x1000)
native_ranges = [(0x89cf1e0, 8), (0x89cf260, 8), (0x89ccb88, 32),
                 (0x89ccbb4, 32), (0x89c25b8, 48), (0x89c25e8, 60)]
native_cases = 0
for default_pc, default_off, flag_off, override_off, producer_pc, field, default in (
        (0x89cf1e0, 0x1dcc, 0x1dd4, 0x1dd0, 0x89ccb88, 0x9b8, 2),
        (0x89cf260, 0x1dd8, 0x1de0, 0x1ddc, 0x89ccbb4, 0x9bc, 40)):
    for flag in (0, 1, 0xffffffff):
        driver = bytearray(rng.randbytes(0x3000))
        m.mem_write(DRIVER, bytes(driver))
        m.mem_write(NATIVE_CODE, native(default_pc, 8))
        m.reg_write(c.UC_ARM64_REG_X19, DRIVER)
        m.emu_start(NATIVE_CODE, NATIVE_CODE + 8, count=2)
        struct.pack_into('<I', driver, default_off, default)
        assert bytes(m.mem_read(DRIVER, len(driver))) == driver
        override = 0x715
        struct.pack_into('<I', driver, flag_off, flag)
        struct.pack_into('<I', driver, override_off, override)
        m.mem_write(DRIVER, bytes(driver))
        image = bytearray(rng.randbytes(0x8000))
        m.mem_write(POWER, bytes(image))
        m.mem_write(NATIVE_CODE, native(producer_pc, 32))
        m.reg_write(c.UC_ARM64_REG_X19, DRIVER)
        m.reg_write(c.UC_ARM64_REG_X8, POWER)
        m.emu_start(NATIVE_CODE, NATIVE_CODE + 32, count=8)
        struct.pack_into('<I', image, field, override if flag else default)
        assert bytes(m.mem_read(POWER, len(image))) == image
        assert bytes(m.mem_read(DRIVER, len(driver))) == driver
        native_cases += 1

# Actual firmware mirror stores at 31c4..31d0, excluding the outer enable gate.
mirror_before = bytes(m.mem_read(base, len(ds)))
m.mem_write(POWER + 0x9b8, struct.pack('<II', 2, 40))
m.reg_write(c.UC_ARM64_REG_X10, POWER)
m.reg_write(c.UC_ARM64_REG_X8, 0x18eecc)
m.emu_start(0x31c4, 0x31d4, count=4)
mirror_expected = bytearray(mirror_before)
struct.pack_into('<II', mirror_expected, 0x18ef78 - base, 2, 40)
assert bytes(m.mem_read(base, len(ds))) == mirror_expected

# Opcode 22 really enters 4b1c; the operand-free handler forces the mirror,
# which clears the one-shot enable at 3388. Use actual captured pointer bindings.
dispatch_entry = struct.unpack_from('<i', t, 0x5284 + (0x16 - 4) * 4)[0] + 0x3a3c
assert dispatch_entry == 0x4b1c and t[0x58850 + 0x16] == 0
for global_address, name in ((0x18e3f0, 'status_a'), (0x18ee70, 'status_b'),
                             (0x195748, 'region_c')):
    obj = owned_objects[name]
    address = int(obj['gpu_va'], 16)
    assert struct.unpack_from('<Q', ds, global_address - base)[0] == address
    m.mem_map(address, obj['reserved_bytes'])
    m.mem_write(address, objects_before[obj['arena_offset']:obj['arena_offset'] + obj['reserved_bytes']])
config_address = int(owned_objects['region_c']['gpu_va'], 16)
config_before = objects_before[region_c_offset:region_c_offset + owned_objects['region_c']['reserved_bytes']]
force_outputs = []
force_cases = []
for gpu_delay, fender_delay in ((0, 0), (2, 40)):
    m.mem_write(base, ds)
    config = bytearray(config_before)
    struct.pack_into('<II', config, 0x9b8, gpu_delay, fender_delay)
    m.mem_write(config_address, bytes(config))
    m.reg_write(c.UC_ARM64_REG_X14, int(owned_objects['channel_12_ring']['gpu_va'], 16))
    m.reg_write(c.UC_ARM64_REG_CPACR_EL1, 3 << 20)
    steps = []
    def stop_force(mu, pc, size, unused):
        steps.append(pc)
        if pc == 0x4b48:
            mu.emu_stop()
            return
        assert 0x4b1c <= pc < 0x4b48 or 0x30a8 <= pc <= 0x338c, hex(pc)
    h = m.hook_add(u.UC_HOOK_CODE, stop_force)
    m.emu_start(0x4b1c, 0x4b4c, count=2000)
    m.hook_del(h)
    assert steps[-1] == 0x4b48
    assert all(pc in steps for pc in (0x4b1c, 0x4b44, 0x30a8, 0x31c8, 0x31d0, 0x3388))
    after = bytes(m.mem_read(base, len(ds)))
    assert struct.unpack_from('<II', after, 0x18ef78 - base) == (gpu_delay, fender_delay)
    assert struct.unpack_from('<I', after, 0x18eec8 - base)[0] == 0
    assert bytes(m.mem_read(config_address, len(config))) == config
    force_outputs.append(after)
    force_cases.append(dict(gpu_delay_ms=gpu_delay, fender_delay_ms=fender_delay,
        instructions=len(steps), expected_stores_reached=True, one_shot_enable_after=0))
force_expected = bytearray(force_outputs[0])
struct.pack_into('<II', force_expected, 0x18ef78 - base, 2, 40)
assert force_outputs[1] == force_expected

def arena_offset_for(address):
    matches = [o['arena_offset'] + address - int(o['gpu_va'], 16) for o in layout['objects']
               if int(o['gpu_va'], 16) <= address < int(o['gpu_va'], 16) + o['reserved_bytes']]
    assert len(matches) == 1
    return matches[0]
control_channel = layout['empty_channel_fixture'][12]
control_cursors_before = [struct.unpack_from('<I', objects_before, arena_offset_for(int(x, 16)))[0]
                          for x in control_channel['cursors']]
control_cursors_after = [struct.unpack_from('<I', objects, arena_offset_for(int(x, 16)))[0]
                         for x in control_channel['cursors']]
control_ring_offset = arena_offset_for(int(control_channel['ring'], 16))
control_count = layout['control_refresh']['count']
assert control_count == 32 and layout['control_refresh']['opcode'] == 0x16
control_records = objects_before[control_ring_offset:control_ring_offset + control_count * 0x40]
assert all(struct.unpack_from('<I', control_records, i * 0x40)[0] == 0x16 and
           control_records[i * 0x40 + 4:(i + 1) * 0x40] == bytes(60) for i in range(control_count))
assert control_cursors_before == [0, 0, 32] and control_cursors_after == [32, 32, 32]

later_path = a.capture / 'data-diagnostic-later.bin'
later = None
if later_path.exists():
    later_bytes = later_path.read_bytes()
    later_receipt = json.loads((a.capture / 'data-diagnostic-later-receipt.json').read_text())
    assert len(later_bytes) == later_receipt['bytes']
    assert sha(later_bytes) == later_receipt['data_sha256']
    later = dict(receipt=later_receipt, words={hex(x): struct.unpack_from('<I', later_bytes, x - base)[0]
        for x in (0x146908, 0x146914, 0x18e620, 0x18e688, 0x18e858, 0x18eec8, 0x18eef8, 0x18ef78, 0x18ef80)})

event_rows = []
for address, mask, callback, arg in ((0x87490, 0x10000000, 0x35b34, 0x10000000),
        (0x874c0, 0x40000000, 0x36010, 0), (0x87670, 2, 0x39360, 1)):
    raw = ds[address - base:address - base + 24]
    observed_mask, pointer, observed_arg = struct.unpack('<QQQ', raw)
    assert (observed_mask, pointer & 0xffffffff, observed_arg) == (mask, callback, arg)
    event_rows.append(dict(address=hex(address), mask=hex(mask), callback=hex(callback),
        argument=hex(arg), raw_callback=hex(pointer), sha256=sha(raw)))

ranges = [(0x30a8, 0x3390), (0x3a0c, 0x3a48), (0x4b1c, 0x4b4c),
          (0x5284 + (0x16 - 4) * 4, 0x5284 + (0x16 - 4) * 4 + 4),
          (0x4710, 0x4728), (0x31c4, 0x31d4), (0xd460, 0xd468), (0xd494, 0xd49c), (0xd808, 0xd814),
          (0xe37c, 0xe388), (0xe6cc, 0xe71c), (0x3a494, 0x3a4a8),
          (0x39d10, 0x39d48), (0x33a7c, 0x33ad0)]
report = dict(
    schema='m4rch-periodic-power-policy-audit-v1',
    hardware_access=False,
    capture=str(a.capture),
    diagnostic_snapshot=dict(receipt=dr, words={hex(x): dword(x) for x in
        (0x146908, 0x146914, 0x18eef8, 0x18eefc, 0x18ef78, 0x18ef80, 0x18fc78, 0x18e620, 0x18e688, 0x18e858, 0x18eec8)}),
    later_diagnostic_snapshot=later,
    owned_snapshot=dict(sha256=sha(objects), power_offset=hex(power_offset),
        words={hex(x): pword(x) for x in (4, 8, 0x10, 0x38, 0x50, 0x78, 0x9b8, 0x9bc, 0x652c)}),
    configuration_snapshot=dict(object='region_c', arena_offset=hex(region_c_offset),
        gpu_va=hex(config_address), runtime_binding='DATA 195748',
        words={hex(x): config_word(x) for x in (0x30, 0x9b8, 0x9bc)}),
    force_snapshot_control=dict(opcode='0x16', dispatch=hex(dispatch_entry),
        records=control_count, records_sha256=sha(control_records),
        cursor_before=control_cursors_before, cursor_after=control_cursors_after,
        objects_before_sha256=sha(objects_before), graph_receipt_sha256=sha(a.graph_receipt.read_bytes()),
        one_shot_enable_set='4b24: DATA 18eec8=1', mirror_call='4b44 -> 30a8',
        one_shot_enable_clear='3388: DATA 18eec8=0',
        qualification='Captured 32 operand-free opcode22 records and cursor advancement establish prior control-handler reach. RAM executes the entire actual handler and mirror with captured source bindings. A later zero one-shot enable does not exclude that prior mirror.'),
    firmware_text_identity=identity,
    firmware_ranges=[dict(start=hex(x), end=hex(y), sha256=sha(t[x:y])) for x, y in ranges],
    native_identity=dict(path=str(native_path), sha256=sha(native_image),
        defaults=[dict(property=native_string(0x7138c8f), milliseconds=2, owned_object='region_c', owned_offset='0x9b8'),
                  dict(property=native_string(0x7138ca5), milliseconds=40, owned_object='region_c', owned_offset='0x9bc')],
        ranges=[dict(start=hex(x), bytes=n, sha256=sha(native(x, n))) for x, n in native_ranges]),
    event_mask_routes=dict(main_event_18e620={'0x10000000': '0x35b34', '0x40000000': '0x36010'},
        power_event_18e858={'0x2': '0x39360(event=1), then 0x3a4a4 if power+0x38=0'},
        producer='0x33ac4 posts mask 2 after 0x33a80..0x33a84 excludes main-state bit 1',
        captured_data_table_rows=event_rows),
    emulation=dict(guard_cases=guard_outcomes, counter_whole_image_cases=counter_cases,
        event_producer_gate_cases=event_gate_cases, native_default_and_publication_cases=native_cases,
        firmware_delay_mirror_whole_data_cases=1, full_control22_mirror_cases=force_cases,
        full_control22_differential_data_comparison=True),
    conclusions=[
        'power+652c increments on the GPC-enabled path at e37c..e384 as well as the GPC-disabled path d808..d810. It counts d2b4 initialization completions, not completed application recoveries.',
        'When 18eef8=0, e598 takes the fallback guard: down/up pair c8f0+d2b4 is reached iff 146914!=0 and 146908!=1. Both late DATA snapshots have 146914=1, 146908=1; those captured values take the no-op exit in RAM. Freshness of firmware cache state is not established.',
        'Periodic event 6 directly calls other policy helpers and temperature accounting, not d2b4. Its helpers have not been completely emulated by this audit.',
        'Event 1 reaches 3a4a4 and d2b4(power,1,1,0) when power+38=0; it signals main-event 10000000 when already powered. Producer 33ac4 posts power mask 2, but main-state bit 1 at 18e688 blocks that producer. Both late snapshots have state 2 and power event mask 0; those captured state values block the producer in RAM.',
        'Native default GPU/Fender idle delays are 2/40 ms. Their consumed configuration source is region_c+9b8/+9bc (DATA195748), distinct from the runtime power object. Firmware 31c4..31d0 mirrors these to 18ef78/18ef80. Both captured configuration fields are zero, a native-default mismatch.',
        'All 32 captured initial opcode22 records were consumed. Its actual handler4b1c sets the one-shot enable18eec8, calls30a8 to copy the delay fields, and clears that enable at3388. Captured enable0 therefore does not exclude this prior reached mirror. Restoring native region_c idle defaults2/40 is justified as a contract correction; it does not establish the earlier120/s caller or solve phase2.',
        'Existing sample period 200000 clocks/native 8 ms is consistent with roughly 120/s observed power-up completions. Rate agreement alone does not prove the caller or a zero timeout cause.'
    ],
    qualification='Actual firmware guards, counter stores, event producer gate, entire control22 handler and mirror plus native default/publication stores execute in Unicorn RAM only; whole power/driver/configuration/DATA images compare. Both DATA snapshots are later than the initial120/s samples and contain historical/saved state; their guard outcomes must not be attributed to those earlier samples. The one-shot mirror enable clears on a successful mirror. Native region_c idle defaults are a reached-consumer contract correction, not proof of the120/s caller or a recovery fix. No root publication, MMIO services, complete timer/power task, recovery success, retirement or rendering verified.'
)
a.output.write_text(json.dumps(report, indent=2) + '\n')
print('15 fallback guards, 8 counters, 7 producer gates, 6 native idle cases, 1 mirror and 2 full control22 paths passed')
