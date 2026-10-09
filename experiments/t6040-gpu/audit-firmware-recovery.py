#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Qualify the matched firmware's recovery protocol without hardware access.

Usage: audit-firmware-recovery.py TEXT OUTPUT [--data DATA] [--graph DIRECTORY]
The optional DATA is a saved 0x60000-based firmware DATA capture, not /dev/mem.
This checks exact reviewed instructions and separately qualifies captured event
table bindings. It does not execute the firmware or certify DMA retirement.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from firmware_text_contract import qualify


SPANS = [
    ('root_copy', 0x2f26c, 0x2f304, '8b4c074b4271f104890e98dadc173ae7e7910ba31ae78d6f1fc9e36cc4b1d211'),
    ('endpoint_registration', 0x341a8, 0x341c4, 'af6bf851bc0843f82d287fa39bdbdfdb3e3ed342c85e1d466627747646f808ed'),
    ('message_dispatch', 0x3500c, 0x3510c, '2cb47c50cfc4fac5a7197d122d6f82cbdf297f093eaf5e40b8fd51bc52fccd2e'),
    ('recovery_worker', 0x3aacc, 0x3ad10, '2f7e80e56a09f275cb9f9f1b7bb8bfd880fd4a08f7ae9d4066f8ee4d2ff237a7'),
    ('recovery_entry', 0x5354, 0x5398, '6455f8275ee6e81c38c2081e67318a7aa4498c98a8bca36f086dfec9fbdd027a'),
    ('host_boolean', 0x5d7c, 0x5dd8, '5e53bb01e805beceaf71679a7bb26fbb3d9cc431dae86a876a767b5bf1d516bf'),
    ('pre_state', 0x63dc, 0x641c, 'f2043d67886009bbee14add789f799ceba3ad35991881a2fcfbe62f4efa43f47'),
    ('recovery_reinit', 0x642c, 0x6588, '75fa39cb31fdbeca10268554f357643051f1349037f97d607a262b22a26bcd45'),
    ('post_state', 0x6588, 0x65b8, '4f6b301c93fff628900d334d4589a13b976cde95258d73d1460cf7f7b32d90aa'),
    ('return_service', 0x65b8, 0x6678, 'f2c3d5bf8b2a905b419b958d4705ed1431bf0f256cd070c3b16b9612820471fb'),
    ('gpu_worker_reset', 0x39124, 0x392e4, '0a6986a6bafc4095f21a4bab4c26544527be8a0f13c9276cc060fe896e391a15'),
    ('control_notify_consumer', 0x383c8, 0x383f0, '8be8ad909d90162892cd523cdebdf0e95e1d1c157d68af9dedf3720f41509ae3'),
    ('event_dispatch', 0x37a78, 0x37b34, 'edacdb24b1847fcc84f6390794a45cb40524593fab172a0c67eb66786f5f0df1'),
    ('hardware_poll', 0x2cf78, 0x2d0d0, 'fc9bff8cece4abab67568fa2ba8306438878133d334c0817d927e8b1fb3b73b0'),
]

# Named sites make accidental changes to the interpreted boundaries diagnosable.
SITES = {
    0x2f274: 0x91132129, 0x2f2c4: 0x91138129,
    0x2f2d0: 0xa949352c, 0x2f2dc: 0xf907396d,
    0x341b8: 0x52800420, 0x341c0: 0x94004af3,
    0x3501c: 0xd370d428, 0x35030: 0x7100191f,
    0x35080: 0x9240ac28, 0x3508c: 0xf9647929,
    0x35094: 0x54000341, 0x350ac: 0xb9000509,
    0x350b8: 0x52800048, 0x3ac74: 0xb940050a,
    0x3ac80: 0xb9000119, 0x3ac8c: 0x52a01008,
    0x3aca0: 0x94002b6d, 0x3ad0c: 0x97ff2992,
    0x5384: 0xf9400d36, 0x5390: 0x540046c0,
    0x5db4: 0x1a9f07f8, 0x63e4: 0xb9091118,
    0x63ec: 0xb9090109, 0x6400: 0xf9247909,
    0x6418: 0x54ffffc1, 0x644c: 0x9400fd82,
    0x6450: 0xb90002df, 0x6594: 0xb828692a,
    0x65a4: 0x35ffffea, 0x65c4: 0xb900051f,
    0x65e0: 0x940101eb, 0x665c: 0xf829690a,
    0x6674: 0x9400fac6, 0x39234: 0xf1008a7f,
    0x39260: 0x97ff4da4, 0x3927c: 0x97ff500e,
    0x39284: 0x97ff3944, 0x392b4: 0xf829690a,
    0x392dc: 0x54ffff61, 0x35068: 0x52a00048,
    0x383e8: 0x17ff2d1d,
}

# Captured PAC-bearing function pointers are checked by low32 only for this
# exact firmware, against independently inspected code targets; no PAC claim.
TABLES = [
    (0x87448, 0x800000, 0x358c4, 0x800000),
    (0x87520, 0x20000, 0x383c8, 0),
    (0x875f8, 0x400000000, 0x39124, 0x22),
    (0x87610, 0x800000000, 0x39124, 0x23),
    (0x87628, 0x8000, 0x39024, 0x8000),
    (0x87640, 0x400, 0x39024, 0x400),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def u64(data, offset):
    return struct.unpack_from('<Q', data, offset)[0]


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def audit_graph(directory):
    receipt = json.loads((directory / 'graph-receipt.json').read_text())
    arena = (directory / 'graph-before.bin').read_bytes()
    require(len(arena) == receipt['arena_bytes'], 'Graph arena length mismatch')
    digest = hashlib.sha256(arena).hexdigest()
    require(digest == receipt['arena_sha256'], 'Graph arena hash mismatch')
    objects = {item['name']: item for item in receipt['objects']}
    for item in objects.values():
        start, size = item['arena_offset'], item['reserved_bytes']
        require(0 <= start <= len(arena) - size, 'Graph object out of arena')
    root = objects['root']['arena_offset']
    main = objects['main']['arena_offset']
    status = objects['status_b']['arena_offset']
    require(u64(arena, root + 0x18) == int(objects['main']['gpu_va'], 0),
            'root+18 does not bind the owned main object')
    require(u64(arena, root + 0xb0) == int(objects['status_b']['gpu_va'], 0),
            'root+b0 does not bind the owned status_b object')
    require(objects['status_b']['reserved_bytes'] >= 0xe440,
            'status_b does not cover the qualified native extent')
    bindings = []
    for offset, name, minimum in [
        (0x254, 'shared_0', 0x614 + 0x600),
        (0x25c, 'shared_1', 0xa40 + 0x600),
        (0x264, 'shared_2', 0x808 + 0x600),
        (0x26c, 'shared_3', 0x68),
        (0x471, 'power', 0x6564),
    ]:
        item = objects[name]
        require(u64(arena, main + offset) == int(item['gpu_va'], 0),
                f'main+{offset:x} does not bind owned {name}')
        require(item['reserved_bytes'] >= minimum,
                f'{name} does not cover reviewed accesses')
        bindings.append(dict(main_offset=offset, object=name,
                             gpu_va=item['gpu_va'], minimum_bytes=minimum,
                             reserved_bytes=item['reserved_bytes']))
    recovery = objects['shared_3']['arena_offset']
    flags = [u32(arena, status + 0x40b8 + i * 8) for i in range(256)]
    return dict(arena_sha256=digest, status_b_gpu_va=objects['status_b']['gpu_va'],
                main_gpu_va=objects['main']['gpu_va'], bindings=bindings,
                recovery_state=u32(arena, recovery),
                host_request=u32(arena, recovery + 4),
                device_recoveries=u64(arena, status + 0x48f0),
                host_phase=u32(arena, status + 0x4900),
                stopped_for_host=u32(arena, status + 0x4910),
                active_ta_recovery_records=[i for i, value in enumerate(flags)
                                            if value & 9 == 9],
                qualification='Prepared backing and pointer identity only; no live mapping or idle assertion.')


def audit_data(path):
    data = path.read_bytes()
    require(len(data) == 0x138000, 'Expected saved DATA extent 0x60000..0x198000')
    tables = []
    for address, mask, target, argument in TABLES:
        actual_mask, pointer, actual_arg = struct.unpack_from('<QQQ', data, address - 0x60000)
        require((actual_mask, pointer & 0xffffffff, actual_arg) == (mask, target, argument),
                f'Saved event table mismatch at {address:x}')
        tables.append(dict(address=hex(address), event_mask=hex(mask),
                           target=hex(target), argument=hex(argument)))
    globals_ = {hex(address): hex(u64(data, address - 0x60000)) for address in
                (0x18e4c0, 0x18ee70, 0x18f6d0, 0x18f888, 0x18f8b0, 0x18f900, 0x18f9a0)}
    return dict(sha256=hashlib.sha256(data).hexdigest(), base='0x60000',
                event_tables=tables, globals=globals_,
                platform_power_mode=u32(data, 0x18fc78 - 0x60000),
                qualification='Saved DATA has its own hash; whole DATA is mutable and is not qualified by the TEXT hash. Table PAC bits are ignored only after exact mask/argument/low32-target checks.')


def audit(text):
    identity = qualify(text)
    for offset, expected in SITES.items():
        require(u32(text, offset) == expected, f'Instruction mismatch at {offset:x}')
    spans = []
    for name, start, end, expected in SPANS:
        digest = hashlib.sha256(text[start:end]).hexdigest()
        require(digest == expected, f'Instruction span mismatch: {name}')
        spans.append(dict(name=name, start=hex(start), end_exclusive=hex(end), sha256=digest))
    return dict(
        schema='m4rch-firmware-recovery-audit-v1', text_contract=identity,
        static_contract_verified=True, hardware_verified=False,
        dma_retirement_verified=False, instruction_sites=len(SITES), spans=spans,
        protocol=dict(endpoint=33, message=0x0086000000000000,
                      token_mask=(1 << 44) - 1, root_status_offset=0xb0,
                      status_global=0x18ee70, counter_offset=0x48f0,
                      phase_offset=0x4900, stopped_offset=0x4910,
                      main_recovery_pointer_offset=0x26c,
                      recovery_object_state_offset=0,
                      recovery_object_host_request_offset=4,
                      host_pre_phase=1, host_pre_ack=2,
                      host_post_phase=3, host_post_ack=0,
                      control_notify=0x0084000000000000,
                      control_notify_event_mask=0x20000),
        findings={
            'root_binding': '2f26c..2f2b0 copies root to18e4c8; 2f2c4 takes copy+18; 2f2d0 loads pair at+90, so its second pointer is root+b0; 2f2dc stores that pointer at18ee70.',
            'message_route': '341a8..341c0 installs3500c at EP33.3501c extracts bits48..53.35080..35094 compares lower44 token with full u64 status_b+48f0; mismatch returns without a request. Equality sets recovery-object+4=1 and event2 at18e880.',
            'entry': '3ac68..3aca4 sees host-request+4, writes recovery-object+0=2, requests event800000 at18e620, waits18e438, then calls5354.5354 branches directly5c68 when object state2. This bypasses preceding ordinary active-work checks, so host must establish idle independently.',
            'pre_phase': '5dac..5db4 computes w24=(host-request!=0).63dc..6404 stores4910=w24,4900=1, increments48f0 with DSB ordering.6410..6418 waits4900==2 without a timeout.4910 is not cleared on the reviewed return path and is not an independent end-of-cycle predicate.',
            'before_pre_phase_hardware': '61d8..61ec calls2cf78(d40000,1,1). That helper maps through DATA18f900 and polls bit0==1. After6000 clock ticks it can return when recovery-object state2; a reached pre-phase therefore does not itself prove every hardware wait succeeded.',
            'between_phases': '642c..644c signals event400000000 on18e858 and waits18e408.644c..6450 then clears recovery-object state.64c4..6514 zeros three0x600-byte active arrays in *(main+254)+614,*(main+25c)+a40,*(main+264)+808.6518..6574 wakes and waits several firmware tasks before phase3.',
            'gpu_worker': 'With captured DATA event-table875f8 binding, event400000000 invokes39124(arg22).3923c..39284 calls c8f0(power,0,1,1), d2b4(power,power+38,power+38,1),7794(power), using *(main+471).392a0..392dc writes MMIO18f6d0+1e820=b and polls+1e828 bit1, with recovery-state2 escape;39328..39344 signals18e408. Transitive register-list and power routines remain only partially interpreted.',
            'post_phase': '6588..65a4 stores4900=3, DSB, waits4900==0 without timeout. After host0,65b8..65c4 clears host-request+4;65c8..6604 reinstalls EP33 callback and drains queued messages.6608..6630 zeros two internal0x90-byte blocks;6634..665c restores MMIO18f6d0+10a08 from DATA190bb0 and writes+211b0=3.6660..6674 reenables a service and wakes18e620 with event1.',
            'control_doorbell': '35058..3506c routes class84 to event20000 at18e620. With DATA87520 binding,383c8 checks (DATA18e688 &18)==0 then reads producer *(main+1b0) and branches385c, the control-ring handler. Class83 selects events1/2/4 using low2 bits; those use the work-ring consumer which also services control. Class84 is the direct control-only route.',
        },
        qualifications=[
            'This is private implementation-derived static analysis, not native recovery evidence.',
            'Keep root, graph, all shared objects, device context, page tables and firmware MMIO mappings alive for every phase and after acknowledgment.',
            'Firmware polls and task waits can hang. The host needs bounded waits and must retain allocations on every failure.',
            'A host write4900=0 is an acknowledgment, not proof firmware resumed. Verify a new control producer is consumed and verify host-request+4 clears before another cycle.',
            'Preserved graph pointers and internal restart support an in-place recovery experiment, but do not prove context reuse, work execution, DMA retirement, unload safety, or provider sleep/wake.',
            'An idle-only trial must leave work producers empty, require no active recovery records, and distinguish control consumption from GPU execution.',
            'Control-only notification and async reset worker bindings require the separate saved DATA event-table evidence.',
        ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('text', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--graph', type=Path)
    args = parser.parse_args()
    report = audit(args.text.read_bytes())
    if args.data:
        report['saved_data'] = audit_data(args.data)
    if args.graph:
        report['prepared_graph'] = audit_graph(args.graph)
    if args.data and args.graph:
        globals_ = report['saved_data']['globals']
        graph = report['prepared_graph']
        require(globals_['0x18ee70'] == graph['status_b_gpu_va'],
                'Saved firmware status_b does not match the prepared graph')
        require(globals_['0x18e4c0'] == graph['main_gpu_va'],
                'Saved firmware main does not match the prepared graph')
        report['saved_global_graph_identity_verified'] = True
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Qualified {len(SITES)} instruction sites and {len(SPANS)} spans; '
          f'recovery is statically bound, hardware remains unverified: {args.output}')


if __name__ == '__main__':
    main()
