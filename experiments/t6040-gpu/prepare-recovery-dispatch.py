#!/usr/bin/env python3
"""Prepare native main-dispatch tracing from a saved recovery fixture.

Usage: prepare-recovery-dispatch.py SOURCE WORKER_PROOF OUTPUT
Offline only. The only arena change is status_a+0 from1 to3; existing mappings,
control records, retained backing and deferred draw inputs remain unchanged.
"""
import argparse
import copy
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

from firmware_text_contract import NORMALIZED_SHA256, qualify
from owned_gpu_layout import validate


DRIVER_SHA256 = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
SOURCE_ARENA_SHA256 = '5b8e184cf501747f0b985418f37d8dc999f4c936a42fbc1cc840de91fa8aba09'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def prepare(source, worker_proof_path, output):
    if output.exists() or source.resolve() in output.resolve().parents:
        raise ValueError('Output must be a new directory outside the source')
    proof_bytes = worker_proof_path.read_bytes()
    proof = json.loads(proof_bytes)
    assert proof['schema'] == 'm4rch-native-recovery-worker-ack-path-v1'
    assert proof['hardware_actions'] is False and proof['candidate_changes'] is False
    assert proof['inputs']['driver_sha256'] == DRIVER_SHA256
    driver = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X').read_bytes()
    assert sha(driver) == DRIVER_SHA256
    assert proof['inputs']['text_identity']['normalized_sha256'] == NORMALIZED_SHA256
    text = (Path(proof['inputs']['capture']) / 'text.bin').read_bytes()
    identity = qualify(text)
    assert identity == proof['inputs']['text_identity']
    for span in proof['matched_ranges']:
        start, end = int(span['start'], 16), int(span['end_exclusive'], 16)
        assert 0 <= start < end <= len(text)
        assert sha(text[start:end]) == span['sha256']

    observation = proof['next_native_observation_contract']
    assert observation['main_entry'] == dict(
        gate='0x37abc tbz(mask18eecc,#1,37adc)', call='0x37ad8',
        packed_event='0x0000012f', role=0, function_type=0,
        args=['handler_mask', 'remaining_pendingmask', 'u32(main_hold18e678)', '0'],
        actualinvoke='0x37ae4')
    assert observation['main_exit'] == dict(
        gate='0x37af8 tbz(mask18eecc,#1,37b18)', call='0x37b10',
        packed_event='0x00000130', role=0, function_type=0,
        args=['handler_mask', 'remaining_pendingmask_afterclear',
              'u32(main_hold18e678)', 'u64(held_pending18e670)'])
    # Actual matched bit1 predicates and event/call instructions, independent
    # of the proof's descriptive gate strings. Bit6 is deliberately not staged.
    checks = {0x37ab8: 0x397b32e8, 0x37abc: 0x36080108,
              0x37ac8: 0x528025e0, 0x37ad8: 0x97ff9e2b,
              0x37ae4: 0xd63f091f, 0x37af4: 0x397b32e8,
              0x37af8: 0x36080108, 0x37b04: 0x52802600,
              0x37b10: 0x97ff9e1d, 0x36074: 0x36080108,
              0x36078: 0x528020a0, 0x36090: 0x97ffa4bd}
    for address, instruction in checks.items():
        assert struct.unpack_from('<I', text, address)[0] == instruction, hex(address)

    layout_path, prep_path = source / 'graph-receipt.json', source / 'preparation.json'
    layout = json.loads(layout_path.read_text())
    prep = json.loads(prep_path.read_text())
    original = (source / 'graph-before.bin').read_bytes()
    validate(original, layout)
    assert sha(original) == layout['arena_sha256'] == SOURCE_ARENA_SHA256
    assert prep['native_init_recovery']['binary_sha256'] == DRIVER_SHA256
    assert prep['native_init_recovery']['firmware']['normalized_sha256'] == NORMALIZED_SHA256
    assert layout['recovery_trial'] == prep['recovery_trial']
    assert prep['recovery_trial']['resident_session'] is True
    assert prep['recovery_trial']['work_submitted'] is False
    assert prep['recovery_trial']['allocations_retained'] is True
    assert prep['pages'] == 56 and 'work_publication' not in prep
    service = prep['recovery_trial']['receive_service']
    assert service['record_bytes'] == 72 and service['journal_capacity'] == 65536
    assert service['rings'][10]['capacity'] == 512 and service['rings'][10]['type_mask'] == 0x20
    assert layout['control_refresh']['opcode'] == 22
    assert layout['control_refresh']['count'] == 32
    assert layout['recovery_trial']['progress_trace']['arena_sha256'] == sha(original)
    assert 'native_trace_disable' not in prep['recovery_trial']['progress_trace']

    objects = {obj['name']: obj for obj in layout['objects']}
    assert len(objects) == len(layout['objects'])
    for obj in objects.values():
        start = obj['arena_offset']
        assert sha(original[start:start + obj['input_bytes']]) == obj['input_sha256'], obj['name']
    status, root, region = objects['status_a'], objects['root'], objects['region_c']
    assert status['input_bytes'] == 0x20
    binding = [edge for edge in layout['pointers']
               if edge['parent'] == 'root' and edge['byte_offset'] == 0xa8]
    assert len(binding) == 1 and binding[0]['target'] == 'status_a'
    assert binding[0]['width'] == 8 and binding[0].get('target_byte_offset', 0) == 0
    assert struct.unpack_from('<Q', original, root['arena_offset'] + 0xa8)[0] == int(status['gpu_va'], 16)
    assert struct.unpack_from('<II', original, region['arena_offset'] + 0x9b8) == (2, 40)
    at = status['arena_offset']
    assert struct.unpack_from('<I', original, at)[0] == 1
    blob = bytearray(original)
    struct.pack_into('<I', blob, at, 3)
    changed = [dict(arena_offset=i, object='status_a', byte_offset=i - at,
                    before=old, after=new)
               for i, (old, new) in enumerate(zip(original, blob)) if old != new]
    assert changed == [dict(arena_offset=at, object='status_a', byte_offset=0, before=1, after=3)]
    old_objects = copy.deepcopy(layout['objects'])
    status['input_sha256'] = sha(blob[at:at + status['input_bytes']])
    layout['arena_sha256'] = sha(blob)
    validate(blob, layout)
    for before, after in zip(old_objects, layout['objects']):
        expected = dict(before)
        if expected['name'] == 'status_a':
            expected['input_sha256'] = status['input_sha256']
        assert after == expected

    old_contract = (source / 'recovery-contract.h').read_bytes()
    assert old_contract.endswith(b'\n')
    assert b'RECOVERY_TRACE_MASK' not in old_contract and b'RECOVERY_TRACE_INITIAL_MASK' not in old_contract
    new_contract = old_contract + (
        f'#define RECOVERY_TRACE_MASK {at}U\n'
        '#define RECOVERY_TRACE_INITIAL_MASK 3U\n').encode()
    assert new_contract.startswith(old_contract)
    old_graph_header = (source / 'graph-contract.h').read_bytes()
    graph_prefix, delimiter, old_array = old_graph_header.partition(b'static const u8 graph_bytes[')
    assert delimiter and re.match(rb'\d+\]=\{\n', old_array)
    assert int(old_array.split(b']', 1)[0]) == len(original)
    parsed_array = bytearray(len(original))
    for offset, value in re.findall(rb'\[(0x[0-9a-f]+)\]=(0x[0-9a-f]+),\n', old_array):
        parsed_array[int(offset, 16)] = int(value, 16)
    assert parsed_array == original
    graph_header = graph_prefix + f'static const u8 graph_bytes[{len(blob)}]={{\n'.encode()
    graph_header += ''.join(f'[{i:#x}]={value:#x},\n'
                            for i, value in enumerate(blob) if value).encode() + b'};\n'
    assert graph_header.startswith(graph_prefix)

    changed_files = {'graph-before.bin', 'graph-contract.h', 'recovery-contract.h',
                     'preparation.json', 'graph-receipt.json'}
    preserved = {str(path.relative_to(source)): sha(path.read_bytes())
                 for path in sorted(source.rglob('*'))
                 if path.is_file() and str(path.relative_to(source)) not in changed_files}
    assert preserved['backing.bin'] == prep['data_sha256']
    assert {'job-data.h', 'render-data.h', 'graph-map.h', 'command-pool-map.h',
            'render-backing-map.h', 'boot-contract.h', 'asc-graph-init.c', 'Makefile'} <= preserved.keys()
    disable = dict(object='status_a', byte_offset=0, value=0,
                   force_snapshot_opcode=22, minimum_completed_idle_cycles=4)
    report = dict(
        schema='m4rch-recovery-dispatch-preparation-v1', hardware_actions=False,
        source=str(source), source_graph_sha256=sha(original), arena_sha256=sha(blob),
        source_layout_sha256=sha(layout_path.read_bytes()),
        source_preparation_sha256=sha(prep_path.read_bytes()),
        worker_proof=dict(path=str(worker_proof_path), sha256=sha(proof_bytes)),
        private_driver_sha256=DRIVER_SHA256, firmware_text_identity=identity,
        firmware_instruction_checks={hex(k): hex(v) for k, v in checks.items()},
        changes=[dict(object='status_a', byte_offset=0, width=4, before=1, after=3)],
        changed_bytes=changed, changed_byte_count=len(changed),
        preserved_input_sha256=preserved,
        recovery_contract=dict(original_sha256=sha(old_contract), sha256=sha(new_contract),
                               original_prefix_preserved=True,
                               trace_mask_arena_offset=at, initial_mask=3),
        graph_header=dict(source_sha256=sha(old_graph_header), sha256=sha(graph_header),
                          original_descriptor_prefix_preserved=True),
        native_trace_disable=disable,
        generator_sha256=sha(Path(__file__).read_bytes()),
        qualification='Native status_a trace mask bit1 is added to existing bit0 for '
        'main-dispatch entry/exit observations. Special timer40000000 uses separate '
        'event105. Observations require independent phase/token/timestamp chronology; '
        'missing events identify no live PC. This is not a recovery fix, complete '
        'ACK qualification, teardown, retirement or rendering proof. Trace-off metadata '
        'requires at least4 completed idle cycles and forceconfig22; it does not '
        'authorize a private semaphore write or bypass an incomplete recovery.')
    layout['dispatch_trace_trial'] = report
    prep['dispatch_trace_trial'] = report
    for metadata in (layout, prep):
        metadata['recovery_trial']['progress_trace']['native_trace_disable'] = dict(disable)
    assert layout['recovery_trial'] == prep['recovery_trial']
    shutil.copytree(source, output)
    (output / 'graph-before.bin').write_bytes(blob)
    (output / 'graph-contract.h').write_bytes(graph_header)
    (output / 'recovery-contract.h').write_bytes(new_contract)
    for name, value in (('preparation.json', prep), ('graph-receipt.json', layout),
                        ('dispatch-preparation.json', report)):
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    assert all(sha((output / name).read_bytes()) == digest for name, digest in preserved.items())
    assert all(sha((source / name).read_bytes()) == digest for name, digest in preserved.items())
    assert (source / 'graph-before.bin').read_bytes() == original
    assert (source / 'graph-contract.h').read_bytes() == old_graph_header
    assert (source / 'recovery-contract.h').read_bytes() == old_contract
    print(json.dumps(dict(output=str(output), changed_bytes=len(changed),
                          arena_sha256=sha(blob), recovery_trace_mask=at,
                          initial_mask=3, native_trace_disable=disable), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'worker_proof', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    prepare(args.source, args.worker_proof, args.output)
