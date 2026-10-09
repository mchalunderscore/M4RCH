#!/usr/bin/env python3
"""Prepare two idle application-recovery cycles with owned backing retained."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from owned_gpu_layout import validate


def prepare(source, audit_path, output, resident=False):
    sha = lambda data: hashlib.sha256(data).hexdigest()
    audit = json.loads(audit_path.read_text())
    prep = json.loads((source/'preparation.json').read_text())
    layout = json.loads((source/'graph-receipt.json').read_text())
    original = (source/'graph-before.bin').read_bytes()
    assert audit['schema'] == 'm4rch-firmware-recovery-audit-v1'
    assert audit['static_contract_verified'] and audit['saved_global_graph_identity_verified']
    assert audit['prepared_graph']['arena_sha256'] == sha(original)
    blob = bytearray(original)
    validate(blob, layout)
    assert prep['pages'] == 56 and layout['control_refresh']['count'] == 32
    assert sha((source/'backing.bin').read_bytes()) == prep['data_sha256']
    objects = {o['name']: o for o in layout['objects']}
    assert struct.unpack_from('<Q', blob, 0xb0)[0] == int(objects['status_b']['gpu_va'], 0)
    assert struct.unpack_from('<Q', blob, objects['main']['arena_offset']+0x26c)[0] == int(objects['shared_3']['gpu_va'], 0)
    status = objects['status_b']['arena_offset']
    assert objects['status_b']['reserved_bytes'] >= 0x4914
    assert not any(blob[status+0x40b8:status+0x4914])
    cursors = []
    deferred = []
    for i in range(12):
        cursor = objects[f'channel_{i}_cursor']['arena_offset']
        ring = objects[f'channel_{i}_ring']['arena_offset']
        cursors.append(cursor)
        if i < 2:
            assert struct.unpack_from('<QQQ', blob, cursor) == (0, 0, 1)
            deferred.append((cursor, ring, bytes(blob[ring:ring+24])))
        blob[cursor:cursor+24] = bytes(24)
        blob[ring:ring+0x4000] = bytes(0x4000)
    control = objects['channel_12_cursor']['arena_offset']
    ring = objects['channel_12_ring']['arena_offset']
    assert struct.unpack_from('<QQQ', blob, control) == (0, 0, 32)
    last = 128 if resident else 34
    for i in range(last):
        expected = struct.pack('<I', 0x16)+bytes(60)
        if i < 32:
            assert blob[ring+i*64:ring+(i+1)*64] == expected
        else:
            assert not any(blob[ring+i*64:ring+(i+1)*64])
            blob[ring+i*64:ring+(i+1)*64] = expected
    report = dict(cycles=2, work_submitted=False, allocations_retained=True,
                  status_offset=status, request_offset=objects['shared_3']['arena_offset'],
                  control_cursor_offset=control, initial_control_count=32,
                  final_control_count=34, staged_control_count=last,
                  resident_session=resident, deferred_triangle_available=resident,
                  request_endpoint=33,
                  request_class='0x86', control_notify_class='0x84',
                  audit_sha256=sha(audit_path.read_bytes()),
                  firmware_audit=audit,
                  qualification='Experimental idle recovery/reuse only. No safe DMA retirement, unload, work execution or rendering established. Failed phases retain all backing. No warm INIT.')
    prep.pop('work_publication', None)
    layout.pop('joined_work_fixture', None)
    prep['recovery_trial'] = report
    prep['qualification'] = report['qualification']
    layout['recovery_trial'] = report
    layout['channel_qualification'] = f'Work channels0..11 have zero cursors/rings. Control12 has32 visible plus{last-32} staged refresh0x16 records; each successful recovery cycle or resident control operation publishes one fresh record.'
    for obj in layout['objects']:
        offset = obj['arena_offset']
        obj['input_sha256'] = sha(blob[offset:offset+obj['input_bytes']])
    layout['arena_sha256'] = sha(blob)
    validate(blob, layout)
    contract = f'#define RECOVERY_STATUS {status}U\n#define RECOVERY_REQUEST {report["request_offset"]}U\n#define RECOVERY_CONTROL {control}U\n#define RECOVERY_CONTROL_INITIAL 32U\n#define RECOVERY_CONTROL_LAST {last}U\n'
    contract += f'#define RECOVERY_POWER {objects["power"]["arena_offset"]}U\n'
    contract += 'static const unsigned int recovery_work_cursors[] = {'+','.join(str(x)+'U' for x in cursors)+'};\n'
    contract += 'static const unsigned int recovery_work_rings[] = {'+','.join(str(x[1])+'U' for x in deferred)+'};\n'
    contract += 'static const u8 recovery_work_records[2][24] = {'+','.join('{'+','.join(str(b) for b in x[2])+'}' for x in deferred)+'};\n'
    graph = (source/'graph-contract.h').read_text().split('static const u8 graph_bytes[')[0]
    graph += f'static const u8 graph_bytes[{len(blob)}]={{\n'+''.join(f'[{i:#x}]={v:#x},\n' for i,v in enumerate(blob) if v)+'};\n'
    shutil.copytree(source, output)
    (output/'graph-before.bin').write_bytes(blob)
    (output/'graph-contract.h').write_text(graph)
    (output/'recovery-contract.h').write_text(contract)
    for name, value in [('preparation.json', prep), ('graph-receipt.json', layout)]:
        (output/name).write_text(json.dumps(value, indent=2)+'\n')
    print(f'Prepared idle recovery fixture: {sum(a != b for a,b in zip(original,blob))} changed graph bytes; no hardware actions.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'audit', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--resident', action='store_true')
    args = parser.parse_args()
    prepare(args.source, args.audit, args.output, args.resident)
