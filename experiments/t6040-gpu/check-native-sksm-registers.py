#!/usr/bin/env python3
"""Check paired native producers and derived common-work links, offline only."""
import argparse
import hashlib
import importlib.util
import json
import struct
import tempfile
from pathlib import Path

path = Path(__file__).with_name('prepare-native-sksm-registers.py')
spec = importlib.util.spec_from_file_location('paired_registers', path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('macho', type=Path); p.add_argument('output', type=Path); args = p.parse_args()
counts = dict(pairs=0, native_register_lists=0, scheduler_links=0,
              checked_ta_firmware_values=0, rejected_inputs=0)
examples = []
with tempfile.TemporaryDirectory(prefix='native-sksm-register-test-') as directory:
    root = Path(directory)
    for i in range(16):
        descriptor = bytearray(0x1800)
        fw = 0xffffffb000100000+i*0x10000
        for off, value in ((0x8c8,1),(0x4a4,32),(0x4a8,32)):
            struct.pack_into('<I',descriptor,off,value)
        for off, value in ((0x8a0,fw),(0x8b8,0x40000000),(0x1160,fw),(0x1178,fw+0x4000)):
            struct.pack_into('<Q',descriptor,off,value)
        descriptor[0x1558] = i & 1
        (root/'descriptor.bin').write_bytes(descriptor)
        (root/'context.bin').write_bytes(bytes(0x100)); (root/'scene.bin').write_bytes(bytes(0x100))
        def scheduler(qid):
            return dict(queue=dict(timestamp=i+1,id=qid,priority=0,capacity=16,previous=0,initial=0,pending=0),
                aperture=dict(address=0,index=0,count=0),payload=[0,0],dependencies=[],qos=[0,0,0],
                rce_kind=0,masks=[0,0,0,0],auxiliary=0,alternate_kind=False,extra_flag=False)
        binding = dict(schema='native-sksm-register-input-v1',descriptor='descriptor.bin',
            context='context.bin',scene='scene.bin',ta_command_gpu=hex(0x100000000+i*0x100000),
            **{'3d_command_gpu':hex(0x100010000+i*0x100000)},parameter_gpu=hex(0x100020000+i*0x100000),
            gpu_bit47=bool(i&2),scheduler={'ta':scheduler(1),'3d':scheduler(2)})
        manifest = root/'input.json'; manifest.write_text(json.dumps(binding))
        report = module.prepare(args.macho,manifest,root/('pair-'+str(i)))
        assert report['submission_ready'] is False
        lists = report['producers']['ta']['lists'][0]['records']
        for reg, flag, value in ((0x1c038,1,fw),(0x1c9c8,0,fw),(0x1c078,1,fw+0x4000),(0x1c9d8,0,fw+0x4000)):
            assert [int(x['value'],0) for x in lists if int(x['register'],0)==reg and x['flag']==flag] == [value]
            counts['checked_ta_firmware_values'] += 1
        for kind in ('ta','3d'):
            detail = report['producers'][kind]; counts['native_register_lists'] += len(detail['lists'])
            scheduler_out = json.loads((root/('pair-'+str(i))/(kind+'-scheduler-bindings.json')).read_text())
            for j, item in enumerate(detail['lists']):
                assert scheduler_out['register_lists'][j] == dict(address=item['address'],count=item['exported_count'])
                counts['scheduler_links'] += 1
            assert report['scheduler_candidates'][kind]['submission_ready'] is False
        counts['pairs'] += 1
        if i < 4: examples.append(dict(case=i,bindings=report['bindings'],
            gpu_bit47=report['gpu_bit47'],
            routes={kind:r['route_evidence'] for kind,r in report['producers'].items()},
            lists={kind:[dict(address=l['address'],backing_count=l['backing_count'],exported_count=l['exported_count']) for l in r['lists']] for kind,r in report['producers'].items()},
            hashes={kind:r['command_sha256'] for kind,r in report['producers'].items()}))
    invalid = [dict(ta_command_gpu=True), dict(ta_command_gpu='0x100000001'),
        {'3d_command_gpu':binding['ta_command_gpu']}, dict(ta_command_gpu='0xffffffffffffffc0'),
        dict(parameter_gpu=0),dict(gpu_bit47=1)]
    for j, replacement in enumerate(invalid):
        bad = {**binding,**replacement}; manifest.write_text(json.dumps(bad)); destination=root/('bad-'+str(j))
        try: module.prepare(args.macho,manifest,destination)
        except ValueError: pass
        else: raise AssertionError('Invalid input accepted')
        assert not destination.exists(); counts['rejected_inputs'] += 1
report = dict(private_binary_sha256=report['private_binary_sha256'],counts=counts,examples=examples,tool_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    qualification='16 explicit synthetic paired register producers through verified G16_SKSM wrappers, independently encoded entries and metadata links;64 independently expected TA firmware-address register values,80 native list/common scheduler links. Both conditional initial-entry states and GPU bit47 values. Six malformed input cases fail before export. Context/scene are explicit zero fixtures; untouched command storage, complete recipe semantics, live physical mapping/cache/queue/completion and valid primitive submission are not qualified. No hardware touched.')
args.output.write_text(json.dumps(report,indent=2)+'\n'); print(counts)
