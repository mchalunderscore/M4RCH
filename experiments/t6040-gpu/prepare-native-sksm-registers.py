#!/usr/bin/env python3
"""Build paired native SKSM register-list candidates from explicit saved inputs.

Runs hash-pinned private producer instructions in offline Unicorn RAM. Exports
numeric command data only, never instruction bytes. This is not a live submitter.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from private_rce_entry import encode_entry, rce_metadata
from native_scheduler_candidate import prepare as prepare_scheduler
import private_ta_command as ta_command
import private_3d_command as command_3d

def integer(value, bits, name):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(name+' requires an integer')
    value = int(value, 0) if isinstance(value, str) else value
    if not 0 <= value < 1 << bits: raise ValueError(name+' out of range')
    return value

def blob(root, name, length):
    path = root/name
    data = path.read_bytes()
    if len(data) != length: raise ValueError(str(path)+' must have '+str(length)+' bytes')
    return data

def harness(macho, output, kind):
    root = Path(__file__).parent
    if kind == '3d':
        source = root/'audit-private-3d-input-generator.py'
        marker = 'rng=random.Random(604010);fixtures=[]'
        argv = [str(source), str(macho), str(output)]
    else:
        source = root/'audit-private-ta-generator.py'
        marker = "counts={'complete_ta_producer'"
        # Donor input is not read in the setup prefix; no donor data is used.
        argv = [str(source), str(macho), str(output), str(output)]
    code = source.read_text().split(marker)[0]
    if marker not in source.read_text(): raise ValueError('Harness marker changed')
    ns = {'__file__': str(source), '__name__': 'register_candidate'}
    previous = sys.argv
    try:
        sys.argv = argv; exec(compile(code, str(source), 'exec'), ns)
    finally: sys.argv = previous
    if kind == 'ta':
        inner = ns['ns']; inner['START'] = ns['START']; inner['END'] = ns['END']; ns = inner
    table, slot, wrapper = ((0xfffffe0007eaa8e0, 0x228, 0xfffffe00089d5ce4)
        if kind == '3d' else (0xfffffe0007eae018, 0x238, 0xfffffe00089e7aec))
    encoded = struct.unpack('<Q', ns['read'](table+16+slot, 8))[0]
    if 0xfffffe0007004000+(encoded & 0xffffffff) != wrapper: raise ValueError('SKSM vtable target changed')
    code = ns['read'](wrapper, 12)
    hint, load, branch = struct.unpack('<3I', code)
    if hint != 0xd503245f or load != 0xf9400800 or branch & 0xfc000000 != 0x14000000:
        raise ValueError('SKSM wrapper changed')
    imm = branch & 0x3ffffff
    if imm & (1 << 25): imm -= 1 << 26
    if wrapper+8+imm*4 != ns['START']: raise ValueError('SKSM wrapper producer changed')
    if kind == '3d': ns['m'].mem_map(wrapper & ~4095, 4096)
    ns['m'].mem_write(wrapper, code)
    ns['wrapper'] = wrapper
    ns['route_evidence'] = dict(table=hex(table), slot=hex(slot), wrapper=hex(wrapper),
        producer=hex(ns['START']), wrapper_sha256=hashlib.sha256(code).hexdigest())
    return ns

def produce(ns, kind, descriptor, command_gpu, parameter_gpu, context, scene, gpu_bit47):
    m, c = ns['m'], ns['c']; A, C, D = (ns[name] for name in ('A', 'C', 'D'))
    qwrite = lambda address, value: m.mem_write(address, struct.pack('<Q', value))
    desc = bytearray(descriptor)
    # These are CPU-only service/lookup identities inside the emulator. They are
    # not published GPU pointers and are recorded as descriptor relocations.
    relocations = {0x190: ns['O'], 0xb90: ns['R1']}
    if kind == '3d': relocations.update({0x918: 0x238000, 0x440: command_gpu})
    else: relocations.update({0x1230: 0x238000, 0x1428: ns['R1'], 0xfa0: command_gpu})
    for off, value in relocations.items(): struct.pack_into('<Q', desc, off, value)
    m.mem_write(ns['O'], context); m.mem_write(0x238000, scene)
    m.mem_write(C, bytes(0x3000)); m.mem_write(D, bytes(desc))
    qwrite(0x239000+0x10, A)
    qwrite(A+0x6d0, int(gpu_bit47) << 47)
    ns['mapped'] = parameter_gpu; ns['entries'].clear(); ns['calls'].clear()
    ns['pending'] = None; ns['map_calls'] = 0
    for reg in ns['regs']: m.reg_write(reg, 0)
    for reg, value in ((c.UC_ARM64_REG_X0, 0x239000), (c.UC_ARM64_REG_X1, C),
            (c.UC_ARM64_REG_X2, D), (c.UC_ARM64_REG_SP, ns['STACK']),
            (c.UC_ARM64_REG_LR, ns['STOP'])):
        m.reg_write(reg, value)
    m.emu_start(ns['wrapper'], ns['STOP'], count=200000)
    if m.reg_read(c.UC_ARM64_REG_PC) != ns['STOP'] or m.reg_read(c.UC_ARM64_REG_SP) != ns['STACK']:
        raise ValueError('Native producer did not return with restored stack')
    command = bytes(m.mem_read(C, 0x3000)); final = bytes(m.mem_read(D, 0x1800))
    if bytes(m.mem_read(ns['O'],len(context))) != context or bytes(m.mem_read(0x238000,len(scene))) != scene:
        raise ValueError('Producer unexpectedly changed supplied lookup backing')
    if kind == '3d' and final != rce_metadata(desc, command, 0x400000000):
        raise ValueError('3D descriptor metadata differs from independent model')
    for off, register, flag, value in ns['entries']:
        if command[off:off+12] != encode_entry(bytes(12), register, flag, value):
            raise ValueError('Native register encoder disagrees with independent codec')
    lists = []
    for phase in range(4 if kind == '3d' else 1):
        offset = 0xa0+phase*0x720 if kind == '3d' else 0x60
        meta = 0x7a0+phase*0x720 if kind == '3d' else 0x760
        descriptor_meta = 0x828+phase*16 if kind == '3d' else 0x1568
        pointer, backing_count, size = struct.unpack_from('<QHH', command, meta)
        exported_pointer, exported_count = struct.unpack_from('<QH', final, descriptor_meta)
        if pointer != command_gpu+offset or exported_pointer != pointer:
            raise ValueError('Register-list pointer does not match supplied command binding')
        if size != backing_count*12 or not 0 <= exported_count <= backing_count:
            raise ValueError('Register-list counts disagree')
        if offset+size > (meta if kind == 'ta' else offset+0x70c):
            raise ValueError('Register-list backing exceeds native list storage')
        records = []
        for j in range(backing_count):
            header, value = struct.unpack_from('<IQ', command, offset+j*12)
            records.append(dict(register=hex(header & 0x3fff8), flag=header & 1, value=hex(value)))
        lists.append(dict(phase=phase, offset=hex(offset), address=hex(pointer),
            backing_count=backing_count, exported_count=exported_count,
            backing_bytes=size, records=records))
    extent = 0x2240 if kind == '3d' else 0x9c0
    # Only producer output; zero-filled untouched storage is NOT initialization
    # evidence for the rest of this command. Do not enqueue these command files.
    return command[:extent], final, dict(lists=lists, encoded_records=len(ns['entries']),
        map_service_calls=ns['map_calls'], cpu_descriptor_relocations={hex(k):hex(v) for k,v in relocations.items()},
        entry_address=hex(ns['START']),
        producer_range=[hex(ns['START']),hex(ns['END'])],
        producer_range_sha256=hashlib.sha256(ns['read'](ns['START'],ns['END']-ns['START'])).hexdigest(),
        route_evidence=ns['route_evidence'],
        qualification='Native register producer and independent per-entry codec/metadata checks; full manually written recipe semantics not independently proved. CPU lookup/map services use explicit saved inputs and supplied map address. Untouched command fields remain zero and are uninitialized for submission.')

def prepare(macho, manifest, output):
    binding = json.loads(manifest.read_text()); root = manifest.parent
    if binding.get('schema') != 'native-sksm-register-input-v1': raise ValueError('Unknown schema')
    desc = blob(root, binding['descriptor'], 0x1800)
    context = blob(root, binding['context'], 0x100); scene = blob(root, binding['scene'], 0x100)
    flags = binding['gpu_bit47']
    if not isinstance(flags, bool): raise ValueError('gpu_bit47 requires explicit boolean')
    values = {name: integer(binding[name], 64, name) for name in
        ('ta_command_gpu', '3d_command_gpu', 'parameter_gpu')}
    for name in ('ta_command_gpu', '3d_command_gpu'):
        if not values[name] or values[name] & 63: raise ValueError(name+' must be nonzero and64-byte aligned')
    if not values['parameter_gpu']: raise ValueError('Explicit nonzero parameter GPU mapping required')
    extents = [(values['ta_command_gpu'], 0x9c0), (values['3d_command_gpu'], 0x2240)]
    if any(start+size > 1 << 64 for start,size in extents): raise ValueError('Command extent wraps address space')
    if max(start for start,_ in extents) < min(start+size for start,size in extents):
        raise ValueError('TA and3D command GPU extents overlap')
    pool_reservation=None
    if 'ordinary3d_pool' in binding:
        from native_3d_pool import reserve,STRIDE
        pool=binding['ordinary3d_pool']
        capacity=integer(pool['capacity'],32,'3D pool capacity')
        if not 1<=capacity<=256:raise ValueError('Qualified3D pool capacities1..256')
        occupancy=blob(root,pool['occupancy'],capacity)
        bases=[integer(pool[k],64,k) for k in ('cpu_base','device_base','firmware_base')]
        if any(not base or base+capacity*STRIDE>1<<64 for base in bases):
            raise ValueError('3D pool mapping extent is zero or wraps')
        pool_reservation=reserve(occupancy,integer(pool['cursor'],32,'3D pool cursor'),*bases)
        if pool_reservation is None:raise ValueError('3D pool has no free slot')
        if pool_reservation['device']!=values['3d_command_gpu']:
            raise ValueError('3D register mapping disagrees with reserved pool slot')
        if pool_reservation['device']&63 or pool_reservation['firmware']&63:
            raise ValueError('3D pool aliases must be64-byte aligned')
        desc=bytearray(desc)
        struct.pack_into('<3Q',desc,0x438,pool_reservation['cpu'],pool_reservation['device'],pool_reservation['firmware'])
        desc=bytes(desc)
    construction = None
    if 'ta_construction' in binding:
        spec = binding['ta_construction']
        # This context is the submit caller's X28 backing, not the producer's
        # descriptor190 lookup object. Keep their identities explicit.
        submit_context = blob(root, spec['submit_context'], 0x600)
        submit_stack = blob(root, spec['submit_stack'], 0x100)
        translated = spec['firmware_translations']
        if not isinstance(translated, list) or len(translated) != 3:
            raise ValueError('Three explicit firmware translation results required')
        translated = [integer(v,64,'firmware translation') for v in translated]
        if 'branch_result' in spec:
            raise ValueError('TA control must derive from accelerator mode and caller context')
        construction = dict(context=submit_context, stack=submit_stack,
            serial=integer(spec['serial'],64,'serial'), addresses=translated,
            x26=integer(spec['x26'],64,'x26'),
            w21=integer(spec['w21'],32,'w21'), w22=integer(spec['w22'],32,'w22'),
            mapping_address=integer(spec['completion_mapping_address'],64,'completion mapping'),
            accelerator_mode=integer(spec['accelerator_mode'],32,'accelerator mode'),
            aperture_flags=integer(spec['aperture_flags'],8,'aperture flags'))
        construction['branch_result'] = ta_command.conditional_control(desc,submit_context,
            construction['accelerator_mode'])
    construction_3d = None
    if '3d_construction' in binding:
        spec = binding['3d_construction']
        if 'callback' in spec or 'payload' in spec:
            raise ValueError('3D payload must derive from channel counter')
        translated = spec['firmware_translations']
        if not isinstance(translated,list) or len(translated) != 3:
            raise ValueError('Three explicit 3D firmware translation results required')
        construction_3d = dict(source=blob(root,spec['body_source'],0x400),
            frame=blob(root,spec['frame_data'],24),stack=blob(root,spec['submit_stack'],0x100),
            serial=integer(spec['serial'],64,'3D serial'),
            counter=integer(spec['channel_counter'],32,'3D channel counter'),
            w21=integer(spec['w21'],32,'3D w21'),w22=integer(spec['w22'],32,'3D w22'),
            mapping_address=integer(spec['completion_mapping_address'],64,'3D completion mapping'),
            addresses=[integer(v,64,'3D firmware translation') for v in translated])
        if 'event_control' in spec:
            event = spec['event_control']
            epochs=event['epochs']
            if not isinstance(epochs,list) or len(epochs)!=2:
                raise ValueError('Two explicit event-machine epochs required')
            capacity=integer(event['capacity'],32,'3D event queue capacity')
            if not 1 <= capacity <= 256:
                raise ValueError('Qualified event queue capacities1..256')
            construction_3d['event_control']=dict(
                context=blob(root,event['submit_context'],0x600),
                epochs=[integer(v,64,'3D event epoch') for v in epochs],
                capacity=capacity,initial=integer(event['initial'],64,'3D event queue initial'),
                aperture_flags=integer(event['aperture_flags'],8,'3D aperture flags'))
    # Produce both before exporting anything; a failed second producer leaves no
    # apparently complete pair behind. Inputs may be graph captures or fixtures.
    results = {}
    for kind in ('ta', '3d'):
        ns = harness(macho, output, kind)
        command, descriptor_out, report = produce(ns, kind, desc,
            values[kind+'_command_gpu'], values['parameter_gpu'], context, scene, flags)
        results[kind] = (command, descriptor_out, report)
    ta_candidate = None
    if construction is not None:
        command, descriptor_out, _ = results['ta']
        ta_candidate = ta_command.header(command, descriptor_out,
            construction['context'], construction['serial'])
        ta_candidate = ta_command.translated_resources(ta_candidate, construction['addresses'])
        ta_candidate = ta_command.metadata(ta_candidate, descriptor_out, construction['context'])
        ta_candidate = ta_command.completion_binding(ta_candidate,descriptor_out,
            construction['context'],construction['mapping_address'])
        ta_candidate = ta_command.tail(ta_candidate, descriptor_out, construction['stack'],
            construction['x26'], construction['w21'], construction['w22'], construction['branch_result'])
        ta_candidate, ta_candidate_descriptor = ta_command.postproducer(ta_candidate,
            descriptor_out,construction['context'],construction['aperture_flags'])
        for item in results['ta'][2]['lists']:
            offset = int(item['offset'],0)
            end = offset+item['backing_bytes']
            if end > 0x660:
                raise ValueError('TA register backing overlaps aperture storage')
            if ta_candidate[offset:end] != command[offset:end]:
                raise ValueError('TA construction changed native register backing')
        if ta_candidate[0x760:0x76c] != command[0x760:0x76c]:
            raise ValueError('TA construction changed native register metadata')
    candidate_3d = None
    if construction_3d is not None:
        command, descriptor_out, detail = results['3d']
        candidate_3d = command_3d.header(command,descriptor_out,construction_3d['serial'],construction_3d['frame'])
        candidate_3d = command_3d.bindings(candidate_3d,descriptor_out,
            construction_3d['addresses'],construction_3d['mapping_address'])
        candidate_3d = command_3d.body(candidate_3d,descriptor_out,construction_3d['source'])
        candidate_3d = command_3d.tail(candidate_3d,descriptor_out,construction_3d['stack'],
            construction_3d['w21'],construction_3d['w22'],(construction_3d['counter']+1)&255)
        candidate_3d_descriptor=descriptor_out
        if 'event_control' in construction_3d:
            event=construction_3d['event_control']
            candidate_3d,candidate_3d_descriptor=command_3d.event_control(
                candidate_3d,descriptor_out,event['context'],event['epochs'],
                event['capacity'],event['initial'],(construction_3d['counter']+1)&255,
                event['aperture_flags'])
        candidate_3d,candidate_3d_descriptor=command_3d.aperture_records(candidate_3d,candidate_3d_descriptor)
        for item in detail['lists']:
            offset=int(item['offset'],0);end=offset+item['backing_bytes']
            if item['phase']==0 and end>0x6a0:
                raise ValueError('3D register backing overlaps aperture storage')
            if candidate_3d[offset:end] != command[offset:end]:
                raise ValueError('3D construction changed native register backing')
            meta=0x7a0+item['phase']*0x720
            if candidate_3d[meta:meta+12] != command[meta:meta+12]:
                raise ValueError('3D construction changed native register metadata')
    from native_3d_scheduler import derive as derive_3d_scheduler
    schedulers = {}
    if 'scheduler' in binding:
        for kind in ('ta', '3d'):
            template = dict(binding['scheduler'][kind])
            if 'register_lists' in template: raise ValueError('Scheduler register lists must derive from producer metadata')
            if 'native_3d' in template:
                if kind!='3d' or candidate_3d is None:
                    raise ValueError('Native3D scheduler requires constructed3D descriptor')
                template=derive_3d_scheduler(candidate_3d_descriptor,template)
            if kind=='3d' and candidate_3d is not None:
                address,index,count=struct.unpack_from('<Q2I',candidate_3d_descriptor,0xa98)
                derived=dict(address=hex(address),index=index if count else 0,count=count)
                if 'aperture' in template:
                    supplied=template['aperture']
                    if any(integer(supplied[k],64,k)!=integer(derived[k],64,k) for k in derived):
                        raise ValueError('3D scheduler aperture conflicts with native descriptor')
                template['aperture']=derived
            lists = results[kind][2]['lists']
            template['register_lists'] = [dict(address=l['address'], count=l['exported_count']) for l in lists]
            template['register_lists'] += [dict(address=0, count=0)]*(4-len(lists))
            work, accounting, detail = prepare_scheduler(template)
            for j, item in enumerate(template['register_lists']):
                word = struct.unpack_from('<Q', work, 0x150+j*8)[0]
                if ((word >> 43) & 127) != item['count']:
                    raise ValueError('Scheduler count does not match exported producer count')
                if (word & ((1 << 38)-1)) != ((integer(item['address'],64,'list address') >> 5) & ((1 << 38)-1)):
                    raise ValueError('Scheduler pointer encoding disagrees')
            schedulers[kind] = (work, accounting, template, detail)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='native-sksm-register-output-v1', submission_ready=False,
        private_binary_sha256=ns['sha'],
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        inputs={name:hashlib.sha256(data).hexdigest() for name,data in
            (('descriptor',desc),('context',context),('scene',scene))},
        bindings={k:hex(v) for k,v in values.items()}, gpu_bit47=flags,
        remaining=['complete SKSM channel command construction, events/stamps/completion identity',
            'full descriptor/resource/context preparation and caller ordering',
            'Linux-owned mapping/cache/queue publication and coherent completion/readback'],
        route='G16_SKSM register-list candidates; SKU host microsequence data not used', producers={})
    for kind, (command, descriptor_out, detail) in results.items():
        for name, data in ((kind+'-register-command.bin',command), (kind+'-producer-descriptor.bin',descriptor_out)):
            (output/name).write_bytes(data)
        detail['command_sha256'] = hashlib.sha256(command).hexdigest()
        detail['descriptor_sha256'] = hashlib.sha256(descriptor_out).hexdigest()
        report['producers'][kind] = detail
    if pool_reservation is not None:
        (output/'3d-pool-occupancy-after.bin').write_bytes(pool_reservation['occupancy'])
        report['ordinary3d_pool']=dict(
            index=pool_reservation['index'],offset=hex(pool_reservation['offset']),
            cpu=hex(pool_reservation['cpu']),device=hex(pool_reservation['device']),
            firmware=hex(pool_reservation['firmware']),cursor_after=pool_reservation['cursor'],
            submission_ready=False,
            qualification='Common resource backing with three explicit fixture mapping bases and shared native slot displacement. No Linux allocation, mapping attributes, cache visibility, locking or retirement proven.')
    if ta_candidate is not None:
        (output/'ta-construction-candidate.bin').write_bytes(ta_candidate)
        (output/'ta-construction-descriptor.bin').write_bytes(ta_candidate_descriptor)
        report['ta_construction'] = dict(submission_ready=False,
            command_sha256=hashlib.sha256(ta_candidate).hexdigest(),
            context_sha256=hashlib.sha256(construction['context']).hexdigest(),
            stack_sha256=hashlib.sha256(construction['stack']).hexdigest(),
            serial=hex(construction['serial']),
            firmware_translations=[hex(v) for v in construction['addresses']],
            x26=hex(construction['x26']), w21=hex(construction['w21']), w22=hex(construction['w22']),
            branch_result=hex(construction['branch_result']),
            accelerator_mode=hex(construction['accelerator_mode']),
            completion_mapping_address=hex(construction['mapping_address']),
            aperture_flags=hex(construction['aperture_flags']),
            aperture_count=struct.unpack_from('<I',ta_candidate_descriptor,0x13bc)[0],
            aperture_pointer=hex(struct.unpack_from('<Q',ta_candidate_descriptor,0x13b0)[0]),
            descriptor_sha256=hashlib.sha256(ta_candidate_descriptor).hexdigest(),
            register_backing_preserved=True,
            qualification='Checked TA preproducer models, native register output and postproducer flag/mcache models. Aperture records use reserved660..75f; native register backing/metadata preserved. Caller X28 context distinct from producer lookup context. Translation/mapping returns are explicit fixtures; notification real output/lifetime semantics excluded. Actual submitted-kick callback checked separately. Descriptor output retains emulator CPU identities and excludes notification output/counter objects. Remaining bytes zero/unqualified; not a complete live job.')
    if candidate_3d is not None:
        (output/'3d-construction-candidate.bin').write_bytes(candidate_3d)
        (output/'3d-construction-descriptor.bin').write_bytes(candidate_3d_descriptor)
        report['3d_construction'] = dict(submission_ready=False,
            command_sha256=hashlib.sha256(candidate_3d).hexdigest(),
            descriptor_sha256=hashlib.sha256(candidate_3d_descriptor).hexdigest(),
            aperture_pointer=hex(struct.unpack_from('<Q',candidate_3d_descriptor,0xa98)[0]),
            aperture_count=struct.unpack_from('<I',candidate_3d_descriptor,0xaa4)[0],
            event_control_checked='event_control' in construction_3d,
            event_timestamp=hex(struct.unpack_from('<Q',candidate_3d_descriptor,0x178)[0]) if 'event_control' in construction_3d else None,
            source_sha256=hashlib.sha256(construction_3d['source']).hexdigest(),
            frame_sha256=hashlib.sha256(construction_3d['frame']).hexdigest(),
            stack_sha256=hashlib.sha256(construction_3d['stack']).hexdigest(),
            serial=hex(construction_3d['serial']),
            channel_counter_before=construction_3d['counter'],
            channel_counter_after=(construction_3d['counter']+1)&0xffffffff,
            scratch_payload=(construction_3d['counter']+1)&255,
            firmware_translations=[hex(v) for v in construction_3d['addresses']],
            completion_mapping_address=hex(construction_3d['mapping_address']),
            completion_mapping_present=bool(struct.unpack_from('<Q',results['3d'][1],0xb70)[0]),
            register_backing_preserved=True,
            qualification='Checked continuous ordinary3D construction models over actual four-list native producer output. Scratch payload derived from incremented u32 channel counter. Translations/conditional completion mapping, source/frame/stack are explicit fixtures. Real submitted-kick/PM counters checked in native audit but not live objects in this export. Optional event/control model uses explicit queue epochs/capacity/initial and caller context; descriptor timestamp exported. Native postproducer aperture records and descriptor pointer/count derived; scheduler aperture linked to updated descriptor. Other scheduling identities and real mapping/cache/publication/completion remain unqualified; no valid drawing job.')
    if schedulers:
        report['scheduler_candidates'] = {}
        for kind, (work, accounting, template, detail) in schedulers.items():
            (output/(kind+'-scheduler-common.bin')).write_bytes(work)
            (output/(kind+'-queue-accounting-fixture.bin')).write_bytes(accounting)
            (output/(kind+'-scheduler-bindings.json')).write_text(json.dumps(template,indent=2)+'\n')
            detail['work_sha256'] = hashlib.sha256(work).hexdigest()
            detail['qualification'] = 'Common scheduler candidate consumes actual exported producer list pointers/counts. Remaining bindings are explicit input fixtures. Host queue accounting is not an initialized live queue; high pointer prefix normalization, submission route acceptance and retirement unproved.'
            report['scheduler_candidates'][kind] = detail
    (output/'receipt.json').write_text(json.dumps(report, indent=2)+'\n')
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('macho', type=Path); p.add_argument('manifest', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); result = prepare(a.macho, a.manifest, a.output)
    print({kind:[(l['backing_count'],l['exported_count']) for l in r['lists']] for kind,r in result['producers'].items()})
