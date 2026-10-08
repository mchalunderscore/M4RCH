#!/usr/bin/env python3
"""Check paired native producers and derived common-work links, offline only."""
import argparse
import hashlib
import importlib.util
import json
import random
import struct
import tempfile
from pathlib import Path

path = Path(__file__).with_name('prepare-native-sksm-registers.py')
spec = importlib.util.spec_from_file_location('paired_registers', path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('macho', type=Path); p.add_argument('output', type=Path); args = p.parse_args()
counts = dict(pairs=0, native_register_lists=0, scheduler_links=0,
              checked_ta_firmware_values=0, rejected_inputs=0, ta_construction_pairs=0, construction_3d_pairs=0)
examples = []
rng = random.Random(604019)
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
        epoch = [0, (1 << 64)-1, 0x123456789abcdef0, rng.getrandbits(64)][i % 4]
        struct.pack_into('<Q', descriptor, 0x14e8, epoch)
        offset = [0,1,0xffffffff,i*32][i % 4]
        struct.pack_into('<I',descriptor,0x1430,offset)
        struct.pack_into('<I',descriptor,0x1388,i)
        struct.pack_into('<I',descriptor,0x1274,i)
        for j in range(i):
            struct.pack_into('<QIBBH',descriptor,0x1288+j*16,
                rng.getrandbits(64),rng.getrandbits(32),rng.getrandbits(8),0,rng.getrandbits(16))
        struct.pack_into('<I',descriptor,0x144,i)
        struct.pack_into('<Q',descriptor,0xb70,fw if i&1 else 0)
        struct.pack_into('<I',descriptor,0xb98,offset)
        struct.pack_into('<Q',descriptor,0xba0,fw+0x100)
        descriptor[0xb9c]=i&1
        struct.pack_into('<I',descriptor,0xa70,i)
        for j in range(i):
            struct.pack_into('<QIBBH',descriptor,0x970+j*16,
                rng.getrandbits(64),rng.getrandbits(32),rng.getrandbits(8),0,rng.getrandbits(16))
        event_timestamp=[0,1,0x7fffffff,0x80000000,0xffffffff][i%5]
        struct.pack_into('<I',descriptor,0x210,event_timestamp)
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
        submit_context, submit_stack = bytearray(rng.randbytes(0x600)), rng.randbytes(0x100)
        submit_context[0x5c0] = [0,1,2,3][i // 4]
        (root/'submit-context.bin').write_bytes(submit_context)
        (root/'submit-stack.bin').write_bytes(submit_stack)
        translations = [fw+j*0x8000 for j in range(3)]
        serial = [(1 << 64)-1, 0, i][i % 3]
        binding['ta_construction'] = dict(submit_context='submit-context.bin',
            submit_stack='submit-stack.bin', serial=hex(serial),
            firmware_translations=[hex(v) for v in translations],
            x26=hex(fw+0x100), w21=i, w22=i+1,
            completion_mapping_address=hex((1 << 64)-1 if i % 2 else fw),
            accelerator_mode=i % 4, aperture_flags=i & 3)
        source_3d,frame_3d=rng.randbytes(0x400),rng.randbytes(24)
        (root/'3d-source.bin').write_bytes(source_3d);(root/'3d-frame.bin').write_bytes(frame_3d)
        counter_3d=[0,255,0xffffffff,i][i%4]
        binding['3d_construction']=dict(body_source='3d-source.bin',frame_data='3d-frame.bin',
            submit_stack='submit-stack.bin',serial=hex(serial),channel_counter=counter_3d,
            w21=i+2,w22=i+3,firmware_translations=[hex(v) for v in translations],
            completion_mapping_address=hex((1<<64)-1))
        binding['3d_construction']['event_control']=dict(submit_context='submit-context.bin',epochs=[3,7],capacity=16,initial=0,aperture_flags=i)
        binding['scheduler']['3d'].pop('aperture')
        manifest = root/'input.json'; manifest.write_text(json.dumps(binding))
        report = module.prepare(args.macho,manifest,root/('pair-'+str(i)))
        assert report['submission_ready'] is False
        output_dir = root/('pair-'+str(i))
        ta = (output_dir/'ta-construction-candidate.bin').read_bytes()
        register_only = (output_dir/'ta-register-command.bin').read_bytes()
        assert len(ta) == 0x9c0
        assert ta[0x60:0x660] == register_only[0x60:0x660]
        assert ta[0x760:0x780] == register_only[0x760:0x780]
        assert struct.unpack_from('<IQ',ta,0) == (0,serial)
        assert struct.unpack_from('<3Q',ta,0x20) == tuple(translations)
        assert struct.unpack_from('<Q',ta,0x7a8)[0] == epoch & ((1 << 40)-1)
        assert ta[0x7b0:0x7b2] == bytes([(epoch >> 40) & 255])*2
        assert ta[0x94d] == submit_context[0x278]
        assert ta[0x90e:0x91e] == submit_context[0x3c8:0x3d8]
        assert struct.unpack_from('<Q2I',ta,0x8ae) == (fw+0x100,i,i+1)
        assert ta[0x8a6:0x8ae] == submit_stack[0x40:0x48]
        mapping_address = int(binding['ta_construction']['completion_mapping_address'],0)
        assert struct.unpack_from('<Q',ta,0x945)[0] == (mapping_address+offset) & ((1 << 64)-1)
        expected_control = 0
        # Choose enabled caller contexts independently of mode, including mode3.
        if i % 4 and submit_context[0x5c0] in (1,2):
            if i % 4 == 1: expected_control = (submit_context[0x13f]&1)^1
            elif i % 4 == 3: expected_control = 1
        assert struct.unpack_from('<I',ta,0x89e)[0] == expected_control
        assert ta[0x93c] == submit_context[0x434]&1
        constructed_descriptor = (output_dir/'ta-construction-descriptor.bin').read_bytes()
        assert struct.unpack_from('<Q2I',constructed_descriptor,0x13b0) == (
            int(report['producers']['ta']['lists'][0]['address'],0)+0x600 if i else 0,
            0 if i else 0xffffffff,i)
        for j in range(i):
            address,length,dsid,_,size = struct.unpack_from('<QIBBH',descriptor,0x1288+j*16)
            expected_start = ((dsid<<47)|(i<<41)|(address>>7)|(1<<55)) & ((1<<64)-1)
            expected_end = ((address>>7)+length)|((1<<min(size,4))<<42)|(1<<41)
            assert struct.unpack_from('<QQ',ta,0x660+j*16) == (expected_start,expected_end)
        assert report['ta_construction']['submission_ready'] is False
        counts['ta_construction_pairs'] += 1
        candidate_3d=(output_dir/'3d-construction-candidate.bin').read_bytes()
        assert len(candidate_3d)==0x2240
        assert struct.unpack_from('<IQ',candidate_3d,0)==(1,serial)
        assert struct.unpack_from('<3Q',candidate_3d,0x28)==tuple(translations)
        assert candidate_3d[0x90]==(counter_3d+1)&255
        assert candidate_3d[0x2178:0x2190]==frame_3d
        assert candidate_3d[0x60:0x70]==source_3d[0x2f0:0x300]
        assert struct.unpack_from('<2I',candidate_3d,0x2150)==(i+2,i+3)
        assert struct.unpack_from('<Q',candidate_3d,0x21df)[0]==(((1<<64)-1+offset)&((1<<64)-1) if i&1 else 0)
        selected_epoch=3 if event_timestamp<0x80000000 else 7
        combined=(((selected_epoch<<24)|(event_timestamp>>8))-1)&((1<<64)-1)
        quotient,remainder=divmod(combined,16)
        expected_timestamp=remainder|((quotient&0xffffffff)<<8)|(((counter_3d+1)&255)<<40)
        assert struct.unpack_from('<Q',candidate_3d,0x2160)[0]==expected_timestamp
        assert struct.unpack_from('<Q',(output_dir/'3d-construction-descriptor.bin').read_bytes(),0x178)[0]==expected_timestamp
        assert struct.unpack_from('<4I',candidate_3d,0x2124)==(submit_context[0x2a5]&1,submit_context[0x2a6]&1,0,0)
        assert candidate_3d[0x222d]==1|((i&3)<<2)
        assert report['3d_construction']['event_control_checked'] is True
        ap_pointer=int(report['producers']['3d']['lists'][0]['address'],0)+0x600 if i else 0
        assert struct.unpack_from('<Q2I',(output_dir/'3d-construction-descriptor.bin').read_bytes(),0xa98)==(ap_pointer,0 if i else 0xffffffff,i)
        scheduler_ap=json.loads((output_dir/'3d-scheduler-bindings.json').read_text())['aperture']
        assert scheduler_ap==dict(address=hex(ap_pointer),index=0,count=i)
        for j in range(i):
            addr,length,dsid,_,size=struct.unpack_from('<QIBBH',descriptor,0x970+j*16)
            start=((dsid<<47)|(i<<41)|(addr>>7)|(1<<55))&((1<<64)-1)
            end=((addr>>7)+length)|((1<<min(size,4))<<42)|(1<<41)
            assert struct.unpack_from('<QQ',candidate_3d,0x6a0+j*16)==(start,end)

        raw_3d=(output_dir/'3d-register-command.bin').read_bytes()
        for item in report['producers']['3d']['lists']:
            off=int(item['offset'],0);end=off+item['backing_bytes'];meta=0x7a0+item['phase']*0x720
            assert candidate_3d[off:end]==raw_3d[off:end]
            assert candidate_3d[meta:meta+12]==raw_3d[meta:meta+12]
        assert report['3d_construction']['submission_ready'] is False
        counts['construction_3d_pairs']+=1

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
        dict(parameter_gpu=0),dict(gpu_bit47=1),
        dict(ta_construction={**binding['ta_construction'], 'firmware_translations':[0,1]}),
        dict(ta_construction={**binding['ta_construction'], 'serial':True}),
        dict(ta_construction={**binding['ta_construction'], 'branch_result':0}),
        dict(ta_construction={**binding['ta_construction'], 'completion_mapping_address':True}),
        dict(ta_construction={**binding['ta_construction'], 'accelerator_mode':True}),
        dict(ta_construction={**binding['ta_construction'], 'aperture_flags':256}),
        {'3d_construction':{**binding['3d_construction'],'channel_counter':True}},
        {'3d_construction':{**binding['3d_construction'],'firmware_translations':[0]}},
        {'3d_construction':{**binding['3d_construction'],'callback':0}},
        {'3d_construction':{**binding['3d_construction'],'event_control':{**binding['3d_construction']['event_control'],'capacity':0}}},
        {'3d_construction':{**binding['3d_construction'],'event_control':{**binding['3d_construction']['event_control'],'epochs':[1]}}},
        {'scheduler':{**binding['scheduler'],'3d':{**binding['scheduler']['3d'],'aperture':dict(address=0,index=0,count=0)}}}]
    for j, replacement in enumerate(invalid):
        bad = {**binding,**replacement}; manifest.write_text(json.dumps(bad)); destination=root/('bad-'+str(j))
        try: module.prepare(args.macho,manifest,destination)
        except ValueError: pass
        else: raise AssertionError('Invalid input accepted')
        assert not destination.exists(); counts['rejected_inputs'] += 1
report = dict(private_binary_sha256=report['private_binary_sha256'],counts=counts,examples=examples,tool_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    qualification='16 synthetic pairs through native SKSM wrappers;64 expected TA FW-register values,80 list/scheduler links. Partial TA commands check serial/translations/epoch/caller inputs, completion offset wrap, all16 mode/context combinations and counts0..15 aperture records with descriptor pointer/count. Native register backing/metadata preserved. Sixteen partial ordinary3D candidates check native list preservation, header/frame/body/resource inputs and counter-derived payload. Eighteen malformed inputs fail before export. Ordinary3D event/control and aperture records0..15 derive timestamps and scheduler aperture metadata; native whole-window audits provide separate numeric qualification. Context/scene zero fixtures; remaining command storage, recipe semantics, live mappings/cache/queues/completion and valid drawing unqualified. No hardware touched.')
args.output.write_text(json.dumps(report,indent=2)+'\n'); print(counts)
