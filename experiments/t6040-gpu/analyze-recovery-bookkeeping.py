#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Decode retained recovery bookkeeping offline; never request GPU operations.

Usage: analyze-recovery-bookkeeping.py CAPTURE GRAPH_RECEIPT OUTPUT [--self-test]
The optional self-test executes three small pinned instruction ranges in RAM.
It does not emulate fences, resources, scheduler, cache coherence or recovery.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from firmware_text_contract import qualify

ROOT = Path(__file__).resolve().parents[2]
DRIVER = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
DRIVER_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
BASE = 0xfffffe0000000000
MASK40 = (1 << 40)-1
NATIVE_SPANS = (
    ('timestamp_writer', 0x89ca3a0, 0x89ca3ec, 'ec194c59e4841c22e8d92ce53d5f51ac827741729e7b8eab47135572ef35e8e2'),
    ('timestamp_caller', 0x89663e4, 0x8966444, '22ebf13910397aad8b2da57a25d5aeb1196759bdb2e67abadb3dd1ea9dd64ec3'),
    ('fence_preresume', 0x8966534, 0x8966650, 'cde49c822f5b50b9d996d11e61b5619980f73bba10c26e7cd463a74176d94d0f'),
    ('post_phase_ta_dispatch', 0x89666cc, 0x8966704, '75952222f711f7310667a23e765d6e471f54d464f8aef4c9a9994ede43e9045f'),
    ('ta_reader', 0x89c9d9c, 0x89c9fb4, 'a24734d1e081969cf392296fab66a8da779eb3cdcb4abeb10b65e8d4b32899cc'),
    ('client_restart', 0x8966744, 0x8966850, 'e2b72e840de0be056b69e0500a8de5c8f073f0313ed43e0dc137cf74938f3820'),
    ('client_record', 0x8966ce0, 0x8966f3c, '1b35d9c56a14e8b90fc8d668dc6c414f0f568d8d7972e4772cc891c8803e6f40'),
    ('post_resume', 0x8966bd8, 0x8966c00, '7a7b184857f3050870cf327c1c575772fc0f3aa7e9776827df94ce1916289191'),
    ('reset_stub', 0x89d1650, 0x89d1658, 'd33fdb74881bcff46b1cf4fc3e20479b1882e0e683789e80e6d650554066a1aa'),
)
FW_SPANS = (
    ('submitted_table_consumer', 0x172c8, 0x1737c, '0b21503dabb9c5688462779883bcbf3360e37a80fbe4042f24f8e1ed841419cf'),
    ('forced_record_clear', 0x61f0, 0x6234, '678fef862cb94d0556e4d82d810720084e32188672f823a6ba039036144d2ada'),
    ('resume_phase3', 0x6594, 0x6678, 'ed3618a23d55a93576e22f6d88ad76ab054a8d107e71f819bbd36ca2f306c3b7'),
    ('ta_record_producer', 0x16694, 0x167f4, '33430dbf8c1569608305bc4e221407010e9bd5d0095d5e199dcb89052096f5d2'),
    ('ta_stamp_operand_luts', 0x58890, 0x58970, 'acba9a32c38fa3650caf0c72796ac1813342d09ae65a133b1532396053078a04'),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def checked_slice(raw, offset, length):
    if offset < 0 or length < 0 or offset+length > len(raw):
        raise ValueError('Snapshot range is not fully backed')
    return raw[offset:offset+length]


def native_reader(raw):
    if sha(raw) != DRIVER_SHA:
        raise ValueError('Driver differs from pinned AGX353.14/25G83')
    segments, position = [], 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        command, length = struct.unpack_from('<II', raw, position)
        if length < 8 or position+length > len(raw):
            raise ValueError('Malformed Mach-O command')
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', raw, position+24))
        position += length

    def read(offset, length):
        address = BASE+offset
        hits = [fo+address-va for va, _, fo, size in segments
                if va <= address and address+length <= va+size]
        if len(hits) != 1:
            raise ValueError('Native range is not uniquely file backed')
        return checked_slice(raw, hits[0], length)
    return read


def pin_spans(reader, spans):
    results = []
    for name, start, end, expected in spans:
        if sha(reader(start, end-start)) != expected:
            raise ValueError('Instruction range differs: '+name)
        results.append(dict(name=name, start=hex(start), end_exclusive=hex(end), sha256=expected))
    return results


def decode_timestamps(raw):
    if len(raw) != 128*16:
        raise ValueError('Need exactly 128 timestamp entries')
    return [dict(index=i, submitted_flag=flags, uninterpreted_word4=padding,
                 submitted_timestamp=value, canonical_native_bool=flags in (0, 1))
            for i, (flags, padding, value) in enumerate(struct.iter_unpack('<IIQ', raw))]


def decode_ta(raw):
    if len(raw) != 256*8:
        raise ValueError('Need exactly 256 TA recovery records')
    return [dict(record_index=i, flags=flags, active=(flags & 9) == 9,
                 stamp_index=(flags >> 4) & 127, stamp_operand=operand)
            for i, (flags, operand) in enumerate(struct.iter_unpack('<II', raw))]


def timestamp_patch(raw, index, flag, timestamp):
    # The native leaf lacks this check; its enclosing caller supplies 0..127.
    if not 0 <= index < 128 or flag not in (0, 1) or not 0 <= timestamp < 1 << 64:
        raise ValueError('Timestamp input outside native caller contract')
    decode_timestamps(raw)
    result = bytearray(raw)
    struct.pack_into('<I', result, index*16, flag)
    struct.pack_into('<Q', result, index*16+8, timestamp)
    return bytes(result)


def reconciliation_count(submitted, retained):
    return ((submitted-retained) & MASK40)+1


def decode_snapshot(raw, receipt):
    if len(raw) != receipt['arena_bytes']:
        raise ValueError('Captured arena length differs from receipt')
    objects = {}
    for obj in receipt['objects']:
        name = obj['name']
        if name in objects:
            raise ValueError('Duplicate object name')
        objects[name] = obj
    def area(name, relative, length):
        obj = objects[name]
        if relative < 0 or relative+length > obj['input_bytes']:
            raise ValueError('Read exceeds explicitly described object input')
        return checked_slice(raw, obj['arena_offset']+relative, length)
    owned_spans = []
    for name in ('root', 'main', 'status_b', 'shared_4'):
        obj = objects[name]
        checked_slice(raw, obj['arena_offset'], obj['input_bytes'])
        if number(obj['gpu_va']) != number(receipt['base'])+obj['arena_offset']:
            raise ValueError('Owned bookkeeping object address differs from arena offset')
        owned_spans.append((obj['arena_offset'], obj['arena_offset']+obj['input_bytes']))
    owned_spans.sort()
    if any(previous[1] > current[0] for previous, current in zip(owned_spans, owned_spans[1:])):
        raise ValueError('Owned bookkeeping input ranges overlap')
    bindings = (('root', 0x18, 'main'), ('root', 0xb0, 'status_b'),
                ('main', 0x274, 'shared_4'))
    checked = []
    for owner, offset, target in bindings:
        pointer, = struct.unpack('<Q', area(owner, offset, 8))
        if pointer != number(objects[target]['gpu_va']):
            raise ValueError('Snapshot pointer does not bind owned '+target)
        checked.append(dict(owner=owner, offset=hex(offset), target=target, pointer=hex(pointer)))
    timestamps = area('shared_4', 0, 0x800)
    records = area('status_b', 0x40b8, 0x800)
    ts, ta = decode_timestamps(timestamps), decode_ta(records)
    return dict(bindings=checked, submitted_entries=ts,
                submitted_nonzero_entries=[entry for entry in ts if entry['submitted_flag'] or entry['submitted_timestamp']],
                noncanonical_bool_indices=[entry['index'] for entry in ts if not entry['canonical_native_bool']],
                active_ta_records=[record for record in ta if record['active']],
                nonzero_ta_records=[record for record in ta if record['flags'] or record['stamp_operand']],
                ta_record_count=256, ta_all_zero=not any(records),
                timestamps_all_zero=not any(timestamps),
                table_sha256=sha(timestamps), ta_records_sha256=sha(records),
                status=dict(token=struct.unpack('<Q', area('status_b', 0x48f0, 8))[0],
                            phase=struct.unpack('<I', area('status_b', 0x4900, 4))[0]))


def self_test(native, text):
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    import unicorn.arm64_const as c
    counts = dict(native_timestamp_writer=0, native_ta_extraction=0, firmware_40bit_arithmetic=0,
                  rejected_ranges=0, decoder_boundary_cases=0)
    initial = bytes((i*17+93) & 255 for i in range(0x800))
    for index in (0, 127):
        for flag in (0, 1):
            for value in (0, MASK40, (1 << 64)-1):
                m = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
                m.mem_map(0x89ca000, 0x1000); m.mem_map(0x200000, 0x3000)
                m.mem_write(0x89ca3a0, native(0x89ca3a0, 0x4c))
                m.mem_write(0x2002e8, struct.pack('<Q', 0x201000)); m.mem_write(0x201000, initial)
                for reg, val in ((c.UC_ARM64_REG_X0, 0x200000), (c.UC_ARM64_REG_X1, index),
                                 (c.UC_ARM64_REG_X2, flag), (c.UC_ARM64_REG_X3, value)):
                    m.reg_write(reg, val)
                m.emu_start(0x89ca3a0, 0x89ca3e8, count=32)
                assert m.reg_read(c.UC_ARM64_REG_PC) == 0x89ca3e8
                assert bytes(m.mem_read(0x201000, 0x800)) == timestamp_patch(initial, index, flag, value)
                counts['native_timestamp_writer'] += 1
    for flags in (0, 1, 8, 9, 9 | (127 << 4), 0xffffffff):
        for index in (0, 255):
            raw = bytearray(0x800); struct.pack_into('<II', raw, index*8, flags, 0xffffffff)
            expected = decode_ta(raw)[index]
            m = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
            m.mem_map(0x89c9000, 0x1000); m.mem_map(0x200000, 0x1000)
            m.mem_write(0x89c9e10, native(0x89c9e10, 0x28)); m.mem_write(0x200000, bytes(raw))
            for reg, val in ((c.UC_ARM64_REG_X19, 0x200000), (c.UC_ARM64_REG_X27, index), (c.UC_ARM64_REG_X20, 9)):
                m.reg_write(reg, val)
            m.hook_add(UC_HOOK_CODE, lambda uc, addr, size, _: uc.emu_stop() if addr == 0x89c9e10 else None)
            m.emu_start(0x89c9e1c, 0x89c9e34, count=16)
            assert (m.reg_read(c.UC_ARM64_REG_PC) == 0x89c9e34) == expected['active']
            if expected['active']:
                assert m.reg_read(c.UC_ARM64_REG_X23) == expected['stamp_index']
                assert m.reg_read(c.UC_ARM64_REG_X24) == expected['stamp_operand']
            counts['native_ta_extraction'] += 1
    for submitted, retained in ((0, 0), (0, MASK40), (MASK40, 0), ((1 << 64)-1, MASK40), (7, 9)):
        m = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        m.mem_map(0x17000, 0x1000); m.mem_map(0x200000, 0x1000)
        m.mem_write(0x1733c, text[0x1733c:0x1734c])
        for reg, val in ((c.UC_ARM64_REG_X8, 0x200000), (c.UC_ARM64_REG_X9, submitted), (c.UC_ARM64_REG_X22, retained)):
            m.reg_write(reg, val)
        m.emu_start(0x1733c, 0x1734c, count=8)
        assert struct.unpack('<Q', m.mem_read(0x200048, 8))[0] == reconciliation_count(submitted, retained)
        counts['firmware_40bit_arithmetic'] += 1
    def rejects(fn):
        try:
            fn()
        except ValueError:
            counts['rejected_ranges'] += 1
            return
        raise AssertionError('Malformed/boundary input accepted')
    for index in (-1, 128): rejects(lambda: timestamp_patch(initial, index, 1, 0))
    for flags in (2, -1): rejects(lambda: timestamp_patch(initial, 0, flags, 0))
    for value in (-1, 1 << 64): rejects(lambda: timestamp_patch(initial, 0, 1, value))
    rejects(lambda: decode_timestamps(initial[:-1])); rejects(lambda: decode_ta(bytes(0x7ff)))
    rejects(lambda: checked_slice(bytes(16), 15, 2))
    for index in (0, 255):
        records = bytearray(0x800); struct.pack_into('<II', records, index*8, 9 | (127 << 4), 42)
        assert decode_ta(records)[index]['active'] and decode_ta(records)[index]['stamp_index'] == 127
        counts['decoder_boundary_cases'] += 1
    duplicate = bytearray(0x800)
    for i in (0, 255): struct.pack_into('<II', duplicate, i*8, 9 | (4 << 4), i)
    assert len([record for record in decode_ta(duplicate) if record['active']]) == 2
    counts['decoder_boundary_cases'] += 1
    fixture = bytearray(0x20000)
    fixture_objects = [dict(name=n, arena_offset=o, input_bytes=size, gpu_va=hex(0x100000+o))
                       for n, o, size in (('root', 0, 200), ('main', 0x4000, 0x500),
                                          ('shared_4', 0x8000, 0x800), ('status_b', 0xc000, 0xf008))]
    receipt = dict(base='0x100000', arena_bytes=len(fixture), objects=fixture_objects)
    for off, value in ((0x18, 0x104000), (0xb0, 0x10c000), (0x4274, 0x108000)):
        struct.pack_into('<Q', fixture, off, value)
    assert decode_snapshot(fixture, receipt)['ta_all_zero']
    counts['decoder_boundary_cases'] += 1
    for off in (0x18, 0xb0, 0x4274):
        broken = bytearray(fixture); struct.pack_into('<Q', broken, off, 0)
        rejects(lambda: decode_snapshot(broken, receipt))
    rejects(lambda: decode_snapshot(fixture[:-1], receipt))
    broken_receipt = json.loads(json.dumps(receipt))
    broken_receipt['objects'][2]['input_bytes'] = 0x7ff
    rejects(lambda: decode_snapshot(fixture, broken_receipt))
    return dict(passed=True, cases=counts, total=sum(counts.values()),
                qualification='Actual pinned leaf/extraction/arithmetic instructions only. No external service, PAC call, scheduling, cache, MMIO or recovery-success emulation.')


def analyze(capture, receipt_path, run_tests=False):
    receipt_raw = receipt_path.read_bytes(); receipt = json.loads(receipt_raw)
    attempt_raw = (capture/'attempt.json').read_bytes(); attempt = json.loads(attempt_raw)
    build = attempt['validated_build_receipt']
    if sha(receipt_raw) != build['graph_receipt_sha256']:
        raise ValueError('Graph receipt differs from captured validated build')
    native = native_reader(DRIVER.read_bytes()); text = (capture/'text.bin').read_bytes()
    fw_identity = qualify(text)
    if fw_identity['normalized_sha256'] != build['graph_recovery_trial']['firmware_audit']['text_contract']['normalized_sha256']:
        raise ValueError('Firmware differs from captured recovery contract')
    report = dict(schema='m4rch-recovery-bookkeeping-observation-v1', hardware_access=False,
                  capture=str(capture.resolve()), graph_receipt_sha256=sha(receipt_raw),
                  boot_id=attempt['boot_id'], attempt_sha256=sha(attempt_raw), capture_metadata_bound=True,
                  driver_sha256=DRIVER_SHA, firmware_text_identity=fw_identity,
                  native_spans=pin_spans(native, NATIVE_SPANS),
                  firmware_spans=pin_spans(lambda a, n: text[a:a+n], FW_SPANS), snapshots={})
    for name in ('objects-before.bin', 'objects-after.bin'):
        raw = (capture/name).read_bytes()
        if name == 'objects-before.bin' and sha(raw) != build['graph_fixture_sha256']:
            raise ValueError('Baseline graph differs from captured validated build')
        if name == 'objects-after.bin' and sha(raw) != attempt['objects_after_sha256']:
            raise ValueError('Final snapshot differs from capture metadata')
        report['snapshots'][name] = dict(sha256=sha(raw), **decode_snapshot(raw, receipt))
    report['stamp_operand_lut'] = [dict(command_type=i,
        stamp_index_offset=hex(struct.unpack_from('<Q', text, 0x58890+i*8)[0]),
        stamp_operand_offset=hex(struct.unpack_from('<Q', text, 0x58900+i*8)[0]))
        for i in range(14) if (0x228f >> i) & 1]
    report['qualification'] = ('Saved owned shared-memory observations. Empty forced-host TA records do not qualify active recovery. '
        'Timestamp index, TA record index, TA stamp index and host recovery generation are not automatically interchangeable. '
        'No completion, live PC, resource retirement, fence reset or safe reuse conclusion.')
    if run_tests: report['self_test'] = self_test(native, text)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path); parser.add_argument('graph_receipt', type=Path)
    parser.add_argument('output', type=Path); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    try:
        result = analyze(args.capture, args.graph_receipt, args.self_test)
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.error(str(error))
    print('Bookkeeping snapshots:', len(result['snapshots']), '; tests:', result.get('self_test', {}).get('total', 'not requested'))
