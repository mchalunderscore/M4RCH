#!/usr/bin/env python3
"""Saved completion identity checks in RAM; never authorize retirement or release.

Usage: analyze-completion-identities.py MACHO TEXT PREPARED OUTPUT
The native event provider, mapping completion and firmware scheduling are external.
"""
import argparse
import hashlib
import json
import random
import re
import struct
from pathlib import Path

import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify
from firmware_completion import decode_entry

PRIVATE_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
NORMALIZED_SHA = '190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac'
BASE = 0xfffffe0000000000
MASK32 = (1 << 32) - 1
sha = lambda b: hashlib.sha256(b).hexdigest()
regs = [getattr(c, 'UC_ARM64_REG_X' + str(i)) for i in range(31)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('macho', 'text', 'prepared', 'output'):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    native_image = a.macho.read_bytes()
    assert sha(native_image) == PRIVATE_SHA
    text_image = a.text.read_bytes()
    identity = qualify(text_image)
    assert identity['normalized_sha256'] == NORMALIZED_SHA
    segments = []
    symbol_table = None
    pos = 32
    for _ in range(struct.unpack_from('<I', native_image, 16)[0]):
        cmd, size = struct.unpack_from('<II', native_image, pos)
        if cmd == 25:
            segments.append(struct.unpack_from('<QQQQ', native_image, pos + 24))
        elif cmd == 2:
            symbol_table = struct.unpack_from('<IIII', native_image, pos + 8)
        pos += size
    assert symbol_table is not None
    symoff, nsyms, stroff, strsize = symbol_table
    strings = native_image[stroff:stroff + strsize]
    undefined = set()
    for i in range(nsyms):
        string_index, kind, section, description, value = struct.unpack_from('<IBBHQ', native_image, symoff + i * 16)
        if kind & 0xe == 0 and string_index:
            undefined.add(strings[string_index:].split(b'\0', 1)[0].decode())
    boundary_imports = [
        '__ZN17IOGPUEventMachine11signalStampEij',
        '__ZN17IOGPUEventMachine21findChannelByStampIdxEj',
        '__ZN17IOGPUEventMachine27requestStampIndexForChannelEP12IOGPUChannelP11IOGPUDevice',
        '__ZNK17IOGPUEventMachine9testStampEi',
        '__ZNK14IOGPUWorkQueue35findCommandDescriptorWithStampValueEij',
    ]
    assert set(boundary_imports) <= undefined
    for target in (BASE + 0xa7cf84c, BASE + 0xa7f9308, BASE + 0xa8032b4):
        assert not any(vm <= target < vm + length for vm, _, off, length in segments)

    def native(address, size):
        address |= BASE
        spans = [off + address - vm for vm, _, off, length in segments
                 if vm <= address and address + size <= vm + length]
        assert len(spans) == 1
        return native_image[spans[0]:spans[0] + size]

    ranges = {
        'native_write_stamp': (0x899f564, 0x899f620),
        'native_force_complete_stamp': (0x899f424, 0x899f4e8),
        'native_3d_timestamp': (0x895ba4c, 0x895bae8),
        'native_3d_complete_mapping_tail': (0x895e268, 0x895e2ac),
        'native_command_buffer_complete': (0x89877b8, 0x8987880),
        'native_retained_workqueue_lookup': (0x8979928, 0x8979a10),
        'native_iofence_complete': (0x8a2e0a8, 0x8a2e2e8),
    }
    firmware_ranges = {
        'completion_prefix': (0x12788, 0x12850),
        'command_class_dispatch': (0x12bdc, 0x12dd0),
        'three_d_timestamp_read': (0x1459c, 0x145f0),
        'class17_payload_selection': (0x12d20, 0x12d98),
        'class17_notification_gate': (0x14c94, 0x14d1c),
        'class17_stamp_mask': (0x15070, 0x150b0),
        'type1_publish_no_pending_metadata': (0x32bac, 0x32ce8),
    }
    proofs = {}
    evidence = Path(__file__).resolve().parents[2] / 'docs/evidence'
    for name in ('2026-10-08-private-3d-event.json',
                 '2026-10-08-private-event-mask.json',
                 '2026-10-08-firmware-completion-ring.json',
                 '2026-10-08-firmware-completion-fields.json'):
        b = (evidence / name).read_bytes()
        proof = json.loads(b)
        if 'binary_sha256' in proof:
            assert proof['binary_sha256'] == PRIVATE_SHA
            region = proof.get('window', proof.get('slice'))
            lo, hi = int(region['start'], 0), int(region['end'], 0)
            assert sha(native(lo, hi - lo)) == region['sha256']
        else:
            assert proof['firmware']['normalized_sha256'] == NORMALIZED_SHA
            lo, hi = map(lambda x: int(x, 0), proof['range'])
            assert sha(text_image[lo:hi]) == proof['range_sha256']
        proofs[name] = {'sha256': sha(b), 'counts': proof['counts']}

    # Complete native writeStamp fast paths and forceCompleteStamp method.
    # Calls at the provider boundary are recorded, never emulated as retirement.
    m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
    m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
    m.mem_map(BASE + 0x899f000, 4096)
    m.mem_write(BASE + 0x899f424, native(0x899f424, 0x1fc))
    RAM, SIZE, MACHINE, ACCEL, COMPLETED, MIRROR, RECORD, STACK, STOP = (
        0x200000, 0x64000, 0x200000, 0x240000, 0x250000, 0x251000,
        0x252000, 0x261000, 0x263000)
    m.mem_map(RAM, SIZE)
    observed = []

    def native_hook(mu, address, size, unused):
        if address == STOP:
            mu.emu_stop()
            return
        word = struct.unpack('<I', mu.mem_read(address, 4))[0]
        if word in (0xd503237f, 0xd50323ff):
            mu.reg_write(c.UC_ARM64_REG_PC, address + 4)
        elif word == 0xd65f0fff:
            mu.reg_write(c.UC_ARM64_REG_PC, mu.reg_read(c.UC_ARM64_REG_LR))
        elif word >> 26 == 0b100101:
            imm = word & 0x3ffffff
            if imm & (1 << 25):
                imm -= 1 << 26
            assert address + imm * 4 == BASE + 0xa7cf84c
            observed.append(('event_provider', *[mu.reg_read(regs[i]) for i in range(3)]))
            mu.reg_write(c.UC_ARM64_REG_PC, address + 4)
        elif address == BASE + 0x899f4e4:
            observed.append(('updated_provider', mu.reg_read(regs[0])))
            mu.emu_stop()

    m.hook_add(u.UC_HOOK_CODE, native_hook)
    rng = random.Random(604009127)
    values = [0, 1, 0xff, 0x100, 0x7fffff00, 0x7fffffff, 0x80000000, 0xffffffff]
    counts = {'write_stamp': 0, 'write_stamp_sign_crossings': 0,
              'force_complete_stamp': 0, 'force_complete_advances': 0}

    def run_native(start, ram, arguments):
        m.mem_write(RAM, bytes(ram))
        for reg in regs:
            m.reg_write(reg, 0)
        for index, value in enumerate(arguments):
            m.reg_write(regs[index], value)
        m.reg_write(c.UC_ARM64_REG_SP, STACK)
        m.reg_write(c.UC_ARM64_REG_LR, STOP)
        observed.clear()
        m.emu_start(BASE + start, STOP, count=300)

    for index in range(128):
        for value in values:
            ram = bytearray(rng.randbytes(SIZE))
            struct.pack_into('<I', ram, MACHINE - RAM + 0x2250, 256)
            epoch_row = MACHINE - RAM + 0x1450 + index * 24
            current = (value - 0x100) & MASK32
            struct.pack_into('<I', ram, epoch_row, current)
            target = MACHINE - RAM + 0x2254 + index * 1024 + ((value >> 8) & 255) * 4
            expected = bytearray(ram)
            struct.pack_into('<II', expected, RECORD - RAM, value, index)
            struct.pack_into('<I', expected, target, 0)
            struct.pack_into('<I', expected, epoch_row, value)
            if (current ^ value) & 0x80000000:
                counts['write_stamp_sign_crossings'] += 1
                offset = epoch_row + (8 if value < 0x80000000 else 16)
                old = struct.unpack_from('<Q', expected, offset)[0]
                struct.pack_into('<Q', expected, offset, (old + 1) & ((1 << 64) - 1))
            run_native(0x899f564, ram, [MACHINE, index, RECORD, value])
            assert m.reg_read(c.UC_ARM64_REG_PC) == STOP and not observed
            assert bytes(m.mem_read(RAM, SIZE)) == expected
            counts['write_stamp'] += 1

            ram = bytearray(rng.randbytes(SIZE))
            old = values[(index + values.index(value)) % len(values)]
            struct.pack_into('<Q', ram, MACHINE - RAM + 0x10, ACCEL)
            struct.pack_into('<QQ', ram, ACCEL - RAM + 0x580, COMPLETED, MIRROR)
            struct.pack_into('<I', ram, COMPLETED - RAM + index * 4, old)
            expected = bytearray(ram)
            delta = (value - old) & MASK32
            advances = 0 < delta < (1 << 31)
            delivered = value if advances else old
            if advances:
                struct.pack_into('<I', expected, COMPLETED - RAM + index * 4, value)
                struct.pack_into('<I', expected, MIRROR - RAM + index * 4, value)
            run_native(0x899f424, ram, [MACHINE, index, value])
            assert observed == [('event_provider', MACHINE, index, delivered),
                                ('updated_provider', ACCEL)]
            assert m.reg_read(c.UC_ARM64_REG_SP) == STACK
            # Method stack scratch is excluded, all other backing must match.
            actual = bytes(m.mem_read(RAM, SIZE))
            assert actual[:STACK - RAM - 0x20] == expected[:STACK - RAM - 0x20]
            assert actual[STACK - RAM:] == expected[STACK - RAM:]
            counts['force_complete_stamp'] += 1
            counts['force_complete_advances'] += int(advances)

    # A class17 completion payload is command+4, selected at12d34/14c94.
    # This checks its store and notification-mask call, not the intervening
    # hardware-completion eligibility, scheduler state, or provider behavior.
    fw = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
    fw.mem_map(0x15000, 4096)
    fw.mem_write(0x15070, text_image[0x15070:0x150b0])
    fw.mem_map(0x500000, 0x4000)
    notification_calls = []

    def firmware_hook(mu, address, size, unused):
        if address == 0x150b0:
            mu.emu_stop()
        elif address == 0x150ac:
            notification_calls.append((mu.reg_read(regs[0]), mu.reg_read(regs[1])))
            mu.reg_write(c.UC_ARM64_REG_PC, address + 4)

    fw.hook_add(u.UC_HOOK_CODE, firmware_hook)
    for index in range(128):
        for value in values:
            ram = bytearray(rng.randbytes(0x4000))
            struct.pack_into('<Q', ram, 0, 0x501000)
            struct.pack_into('<II', ram, 0x10, value, index)
            expected = bytearray(ram)
            struct.pack_into('<I', expected, 0x1000, value)
            mask = (1 << index).to_bytes(16, 'little')
            expected[0x3120:0x3130] = mask
            fw.mem_write(0x500000, bytes(ram))
            fw.reg_write(regs[21], 0x500000)
            fw.reg_write(regs[29], 0x5031c0)
            notification_calls.clear()
            fw.emu_start(0x15070, 0x150b0, count=40)
            assert notification_calls == [struct.unpack('<QQ', mask)]
            assert bytes(fw.mem_read(0x500000, 0x4000)) == expected
    counts['class17_store_mask'] = 128 * len(values)

    # Read the prepared command and KSM identities without rewriting any input.
    prep_bytes = (a.prepared / 'preparation.json').read_bytes()
    prep = json.loads(prep_bytes)
    backing = (a.prepared / 'backing.bin').read_bytes()
    assert len(backing) == prep['pages'] * 16384 and sha(backing) == prep['data_sha256']
    graph = (a.prepared / 'graph-before.bin').read_bytes()
    layout = json.loads((a.prepared / 'graph-receipt.json').read_bytes())
    assert sha(graph) == layout['arena_sha256']
    job_bytes = (a.prepared / 'job-data.h').read_bytes()
    header = job_bytes.decode()
    count = int(re.search(r'#define JOB_COUNT (\d+)U', header).group(1))
    extent = int(re.search(r'#define COMMAND_BYTES (0x[0-9a-f]+)U', header).group(1), 0)
    command_base = int(re.search(r'#define FW_BASE (0x[0-9a-f]+)ULL', header).group(1), 0)
    assert (count, extent) == (64, 0x2240)
    body = header.split('static const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={', 1)[1]
    records = re.findall(r'\{([^{}]*)\}', body)
    assert len(records) == count
    commands = []
    for record in records[:2]:
        command = bytearray(extent)
        seen = set()
        for offset, value in re.findall(r'\[(0x[0-9a-f]+)\]=(0x[0-9a-f]+)', record):
            offset, value = int(offset, 0), int(value, 0)
            assert offset not in seen and offset < extent and value <= 255
            seen.add(offset)
            command[offset] = value
        commands.append(bytes(command))
    assert [sha(b) for b in commands] == prep['integrated_pair']['command_sha256']
    queues = []
    for i, q in enumerate(prep['owned_scheduler']):
        record = backing[(49 + i * 2) * 16384 + 512:(49 + i * 2) * 16384 + 1024]
        word, = struct.unpack_from('<Q', record)
        queue = (word >> 42) & 127
        timestamp = (word >> 2) & ((1 << 40) - 1)
        pointer, state = struct.unpack_from('<QQ', record, 0x10)
        assert queue == q['queue_id'] and timestamp == q['work_timestamp']
        assert state == int(q['state_fw'], 0)
        assert pointer == command_base + (extent if q['stage'] == 'ta' else 0)
        command = commands[1 if q['stage'] == 'ta' else 0]
        queues.append({'stage': q['stage'], 'chosen_ksm_queue_id': queue,
                       'ksm_timestamp_low40': timestamp, 'command_fw': hex(pointer),
                       'state_fw': hex(state), 'command_kind': struct.unpack_from('<I', command)[0],
                       'command_timestamp_low40': (struct.unpack_from('<Q', command, 0x7a8 if q['stage'] == 'ta' else 0x2160)[0] & ((1 << 40) - 1)),
                       'timestamp_equality_only': True, 'event_machine_registration_verified': False})
        if q['stage'] == 'ta':
            queues[-1]['completion_mapping_field945'] = hex(struct.unpack_from('<Q', command, 0x945)[0])
        else:
            queues[-1]['completion_record2140_raw_hex'] = command[0x2140:0x2160].hex()
            queues[-1]['completion_operand2150_raw_u32'] = struct.unpack_from('<I', command, 0x2150)[0]
            queues[-1]['completion_index2154_raw_u32'] = struct.unpack_from('<I', command, 0x2154)[0]
            queues[-1]['optional_completion_mapping21df'] = hex(struct.unpack_from('<Q', command, 0x21df)[0])
    # Decoder is the existing audited implementation, not a second interpretation.
    decoder_boundary_cases = 0
    for queue in (0, 1, 63, 64, 127):
        for epoch in (0, 1, (1 << 40) - 1):
            entry = bytearray(64)
            word = (queue << 9) | (((epoch >> 8) & MASK32) << 16) | ((epoch & 255) << 48) | 0x10
            struct.pack_into('<Q', entry, 0, word)
            decoded = decode_entry(entry)
            assert (decoded['queue_id'], decoded['epoch']) == (queue, epoch)
            decoder_boundary_cases += 1
    counts['existing_decoder_boundaries'] = decoder_boundary_cases

    report = {
        'schema': 'm4rch-completion-identity-contract-v1',
        'private_binary_sha256': PRIVATE_SHA, 'firmware': identity,
        'inputs': {'prepared': str(a.prepared), 'preparation_sha256': sha(prep_bytes),
                   'graph_sha256': sha(graph), 'backing_sha256': sha(backing),
                   'job_header_sha256': sha(job_bytes)},
        'reused_proofs': proofs,
        'native_ranges': {name: {'start': hex(lo), 'end': hex(hi), 'sha256': sha(native(lo, hi - lo))}
                          for name, (lo, hi) in ranges.items()},
        'firmware_ranges': {name: {'start': hex(lo), 'end': hex(hi), 'sha256': sha(text_image[lo:hi])}
                            for name, (lo, hi) in firmware_ranges.items()},
        'ram_checks': counts, 'prepared_identities': queues,
        'locally_derived': {
            'write_stamp': {'command_record': 'u32 stamp,u32 index at+0/+4',
                            'slot': 'machine+2254+index*400+(((stamp>>8)&255)*4)',
                            'epoch_row': 'machine+1450+index*18; native init count2250=256',
                            'advance_required': 'new stamp equals prior+100 modulo32; exceptional path excluded'},
            'force_complete_stamp': {'backing': 'accelerator+580/+588 arrays, index*4',
                                     'advance': 'signed32(new-old)>0',
                                     'external_call': 'a7cf84c(machine,index,current_value)',
                                     'updated_call': 'a7f9308(accelerator)'},
            'class17_completion': {'command_class_u32': 17, 'command_class_hex': '0x11',
                                   'payload': 'command+4', 'pointer': 'payload+0 u64',
                                   'value': 'payload+10 u32', 'notification_index': 'payload+14 u32',
                                   'notification_call': '32bac(low64_mask,high64_mask)',
                                   'checked_index_range': [0, 127], 'eligible_branch_proved': False},
            'ordinary_3d': {'native_event_record': 'descriptor+210',
                            'native_queue_path': 'accelerator+f938[index*8] -> queue+68 -> owner+140 event machine',
                            'native_epochs': 'machine+1458/+1460+index*18',
                            'timestamp_publication': 'descriptor+178 and command+2160',
                            'firmware_timestamp_read': '1459c; store13c3a0+completion_queue_id*8 at145e0'},
        },
        'unresolved_links': [
            'Chosen KSM queue ID to allocated event-machine stamp index/channel/workqueue.',
            'Full hardware completion eligibility and ordinary TA/3D stamp/notification publication.',
            'External a7cf84c event-provider callbacks, command completion/error/fence dispatch.',
            'Native resource callback invocation and external mapping/cache/DMA retirement.',
            'Live coherent completion plus validated target pixels; same-instance post-work recovery.',
        ],
        'identity_domains': [
            {'domain': 'KSM queue', 'range': [0, 127], 'meaning': '7-bit hardware scheduler identity'},
            {'domain': 'hardware completion descriptor', 'range': [0, 3], 'meaning': 'Four routing rings; not four job IDs'},
            {'domain': 'type1 notification index', 'range': [0, 127], 'meaning': 'External event-machine stamp index'},
            {'domain': 'type1 selector', 'range': [0, 23], 'meaning': 'Native guard on separate u16; not notification bit'},
        ],
        'resource_boundaries': {
            'retained_workqueue_lookup': '8979928..8979a10 searches channel+18 against stamp index through candidate workqueue+218/+220; external enumeration/casts, then virtual retain20. No identity with chosen KSM queue is assumed.',
            'command_buffer_complete': '89877b8..8987880 obtains internal resources+30/+278; locks resource+40; if resource+38>=1, invokes external a8032b4 on nonnull maps+50/+58 and decrements+38. It does not itself prove provider unmap/destruction or DMA quiescence.',
            'three_d_complete': '895dca4..895e318 has an initial descriptor+1c2 bit0 guard, pool counters and internal-resource mapping completion. Tail895e268..895e2ac separately services resource+70 maps+50/+58 and decrements reference. Full callback dispatch and cleanup remain unqualified.',
            'iofence_complete': '8a2e0a8..8a2e2e8 receives an AGXIOFenceData pointer, validates/unlinks its+a0/+a8 list links and workqueue+e0, stores provider time at workqueue+f8, and for the head fence tail-dispatches workqueue virtual+1b0 with the same fence pointer. Callback trigger and virtual target/lifecycle are not qualified here.',
            'external_provider': 'a7cf84c is outside file-backed executable segments. Undefined imports include IOGPUEventMachine::signalStamp, stamp registration/channel lookup, event tests, and IOGPUWorkQueue::findCommandDescriptorWithStampValue. Their implementations and exact imported-address binding are not supplied by this audit.',
            'verified_undefined_imports': boundary_imports,
            'provider_targets_outside_file_backed_segments': True,
        },
        'implementation_obligations': [
            'Allocate and retain explicit stamp-index/channel/workqueue/command ownership; do not equate numeric IDs across domains.',
            'Keep original event stamp, selected epoch, queue capacity/initial value, packed timestamp/payload, command pointers and mapping identities in each submitted record.',
            'Decode matching hardware completion and read command-class-specific completion state coherently; retain ambiguity/errors and duplicate/stale records.',
            'Join native-compatible stamp notification to the exact pending command/fence through an independently qualified host registry and wrap/generation rules.',
            'Invoke completion/error callbacks once and balance retained resources only after a separately qualified DMA/context retirement transition.',
        ],
        'completion_verified': False, 'retirement_verified': False,
        'resource_release_authorized': False,
        'qualification': 'Offline numeric identities and bounded actual-instruction RAM checks only. PAC omitted, external event calls recorded, firmware notification publisher not executed. No scheduling, DMA/cache, fence signal, eligible full completion, rendering, recovery after work, or safe reuse/free is established.',
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ram_checks': counts, 'prepared_identities': queues,
                      'retirement_verified': False}, indent=2))


if __name__ == '__main__':
    main()
