#!/usr/bin/env python3
"""Branch from actual initialized PM resources into full ordinary retention.

The initializer harness is restored after each independent branch so its original
manual PB-ring comparison remains intact. No hardware or live resources touched.
"""
from pathlib import Path
from private_uma_emulation import NativeUMA, LOCK, UPDATE, expected_validation, expected_update
from private_ta_inputs import load_ta_parameter_management
base = Path(__file__).with_name('audit-private-pm-metrics-job.py')
setup = base.read_text().split("exec(compile(tail,str(base),'exec'))")[0]
setup = setup.replace('m.hook_add(u.UC_HOOK_CODE,metrics_job_hook)',
                      'metrics_handle=m.hook_add(u.UC_HOOK_CODE,metrics_job_hook)')
exec(compile(setup, str(base), 'exec'))
m.hook_del(metrics_handle)
RET, RET_END = 0xfffffe00089fa7a8, 0xfffffe00089fb0d4
PAGEPREP, PAGEEND, PAGERELEASE, PAGEGEN = (0xfffffe00089fe494,
    0xfffffe00089fea3c, 0xfffffe00089fe44c, 0xfffffe00089fe440)
m.mem_map(0xfffffe00089fa000, 4096)
m.mem_write(RET, read(RET, RET_END-RET))
m.mem_write(PAGEGEN, read(PAGEGEN, PAGEEND-PAGEGEN))
USAGE = 0xfffffe00089fe138
CALLER, CALLER_END = 0xfffffe0008a22be4, 0xfffffe0008a22c4c
RET_CALLER, RET_CALLER_END = 0xfffffe0008a22504, 0xfffffe0008a22534
m.mem_write(USAGE, read(USAGE, PB-USAGE))
m.mem_map(0xfffffe0008a22000, 4096)
m.mem_write(CALLER, read(CALLER, CALLER_END-CALLER))
m.mem_write(RET_CALLER, read(RET_CALLER, RET_CALLER_END-RET_CALLER))
uma = NativeUMA(m, read)
for table, slot, target in ((0xfffffe0007eb3050, 0x1e0, RET),
        (0xfffffe0007eb7560, 0x208, LOCK), (0xfffffe0007eb7560, 0x210, UPDATE)):
    encoded = struct.unpack('<Q', read(table+16+slot, 8))[0]
    assert 0xfffffe0007004000+(encoded & 0xffffffff) == target
TA_PM, TA_PM_END = 0xfffffe0008a20cbc, 0xfffffe0008a20ea0
m.mem_write(TA_PM, read(TA_PM, TA_PM_END-TA_PM))
for slot, target in zip((0x158, 0x160, 0x168), GETTERS): qwrite(PMVT+slot, target)
m.mem_map(0x2f0000, 0x10000)
POBJ, POVT, PIVT, PMETA, PNEW, PINIT, PRETAIN, PLENGTH, PA, PBARRAY = [
    0x2f0000 + 0x1000*j for j in range(10)]
qwrite(0xfffffe000c6e7d00, PMETA); qwrite(PMETA+0xa8, PNEW)
qwrite(0xfffffe0007ea24d8, PIVT); qwrite(PIVT+0x150, PINIT)
qwrite(POVT+0x20, PRETAIN)
qwrite(PMVT+0x1f0, PAGEPREP); qwrite(PMVT+0x1f8, PAGERELEASE)
qwrite(PMVT+0x200, PAGEGEN)
qwrite(POVT+0x148, PLENGTH); qwrite(DVT+0x20, PRETAIN)
joined_events = []
joined_counts = dict(chains=0, fresh_page_mappings=0, descriptor_resources=0,
                     page_entries=0, initializer_mode_one=0, caller_bindings=0,
                     usage_event_service_calls=0, uma_validations=0,
                     uma_usage_updates=0, uma_descriptor_event_updates=0)
joined_counts['initialized_parameter_loads'] = 0
active_join = False

def joined_hook(m, address, size, user):
    if not active_join:
        metrics_job_hook(m, address, size, user); return
    if uma.hook(address): return
    x0 = m.reg_read(regs[0])
    if address in (0xfffffe00089fe17c, 0xfffffe00089fe1b0):
        event_args = (BCTX, D+0xdc8, 0x2fa500+0x40) if address == 0xfffffe00089fe17c else (BCTX, D+0x80, 0x2fa500)
        assert tuple(m.reg_read(regs[j]) for j in range(3)) == event_args
        joined_events.append(('usage_event_fixture', *event_args))
        joined_counts['usage_event_service_calls'] += 1
        if address == 0xfffffe00089fe1b0:
            m.reg_write(regs[0], 0); m.reg_write(c.UC_ARM64_REG_PC, m.reg_read(c.UC_ARM64_REG_LR))
        else: finish_service(address, 0)
        return
    if address in (0xfffffe0008a22c34, 0xfffffe0008a22c48):
        assert x0 == S
        if address == 0xfffffe0008a22c34:
            assert m.reg_read(regs[1]) == D
        else:
            assert tuple(m.reg_read(regs[j]) for j in range(4)) == (S, HWM, request, 3)
        joined_events.append(('caller', address))
    if address in prep_receivers:
        assert x0 == prep_receivers[address]
        joined_events.append(('prepare_resource_fixture', x0))
        finish_service(address, 0); return
    if address in support_receivers:
        assert x0 == support_receivers[address]
        joined_events.append(('support_fixture', x0))
        finish_service(address, 0); return
    if address in generation_receivers:
        assert x0 == generation_receivers[address]
        joined_events.append(('generation_fixture', x0))
        finish_service(address, generation_values[x0]); return
    word = struct.unpack('<I', m.mem_read(address, 4))[0]
    if word & 0xfffffc00 == 0xd73f0800:
        target = m.reg_read(regs[(word >> 5) & 31])
        if target in (LOCK, UPDATE):
            assert x0 == D
            m.reg_write(c.UC_ARM64_REG_LR, address+4)
            m.reg_write(c.UC_ARM64_REG_PC, target); return
        if target in (PAGEPREP, PAGERELEASE, PAGEGEN, PREPARE, BUILD):
            assert x0 == S
            joined_events.append(('native', target))
            m.reg_write(c.UC_ARM64_REG_LR, address+4)
            m.reg_write(c.UC_ARM64_REG_PC, target); return
        if target == RET:
            assert tuple(m.reg_read(regs[j]) for j in range(3)) == (S, D, STAGED)
            m.reg_write(c.UC_ARM64_REG_LR, address+4)
            m.reg_write(c.UC_ARM64_REG_PC, target); return
        if target in (PNEW, PINIT, PRETAIN, PLENGTH, MRET):
            if target == PNEW:
                assert x0 == 0xfffffe000c6e7d00; value = POBJ
            elif target == PINIT:
                assert x0 == POBJ and m.reg_read(regs[1]) == GPU; value = 1
            elif target == PLENGTH:
                assert x0 == BSUPPORT; value = 0x20000
            else:
                assert x0 in retained_objects; value = 0
            joined_events.append(('service', target, x0))
            finish_service(address, value); return
    if word & 0xfc000000 == 0x94000000:
        imm = word & 0x3ffffff
        if imm & (1 << 25): imm -= 1 << 26
        target = address + imm*4
        if target == 0xfffffe000bf257d4:
            assert m.reg_read(regs[1]) == 64*8
            allocs = sum(e[0] == 'page_array' for e in joined_events)
            assert allocs < 2
            joined_events.append(('page_array', allocs))
            finish_service(address, (PA, PBARRAY)[allocs]); return
        if target == 0xfffffe000a7c40b0:
            assert x0 == POBJ
            joined_events.append(('prepare_page_fixture',))
            finish_service(address, 0); return
        if target == 0xfffffe000a8032a8:
            assert x0 == DINNER
            joined_events.append(('discard_fixture',))
            finish_service(address, 0); return
    try:
        metrics_job_hook(m, address, size, user)
    except (AssertionError, u.UcError):
        print('joined failure', hex(address), hex(x0),
              hex(target) if 'target' in locals() else '', joined_events)
        raise

m.hook_add(u.UC_HOOK_CODE, joined_hook)

def initialized_retention():
    global active_join, prep_receivers, support_receivers, generation_receivers
    global generation_values, retained_objects, block_address, request
    # Keep the initializer's real PM/config/manager/state identities. Resource
    # support getters are external constructor outputs absent in the parent stub.
    original_ram = bytes(m.mem_read(0x200000, 0x140000))
    old_block_address = globals().get('block_address')
    try:
        qwrite(GARTVT+0x20, PRETAIN); qwrite(BSUPPORT, POVT)
        qwrite(RVT+0x20, PRETAIN); qwrite(SRVT+0x20, PRETAIN)
        qwrite(CPUVT+0x20, PRETAIN)
        qwrite(RVT2+0x20, PRETAIN)
        qwrite(0x2fad00+0x20, PRETAIN)
        for obj in RES+HRES: qwrite(obj, 0x2fad00)
        supports = [0x2fa000+j*0x100 for j in range(4)]
        for obj, support in zip((RES[1], HRES[1], RES[2], SRESOURCE), supports):
            qwrite(obj+(0x28 if obj == SRESOURCE else 0x48), support)
        qwrite(POBJ, POVT); qwrite(POBJ+0x98, 0)
        page_object_before = bytes(m.mem_read(POBJ, 0x100))
        page_array_before = [bytes(m.mem_read(addr, 0x1000)) for addr in (PA, PBARRAY)]
        qwrite(KRES+0xa0, 0); qwrite(KRES+0x50, GPU)
        page_before = rng.randbytes(0x1000); m.mem_write(PAGE_BUFFER, page_before)
        descriptor_before = rng.randbytes(0x1800); m.mem_write(D, descriptor_before)
        source_pm = bytes(m.mem_read(S, 0x300))
        va_pointer, vb_pointer = (struct.unpack_from('<Q', source_pm, off)[0] for off in (0xa8, 0x88))
        va_backing, vb_backing = (bytes(m.mem_read(ptr, 0x1000)) for ptr in (va_pointer, vb_pointer))
        va_values, vb_values = struct.unpack('<512Q', va_backing), struct.unpack('<512Q', vb_backing)
        loaded_descriptor = load_ta_parameter_management(descriptor_before, source_pm, va_values, vb_values, [0, 0, 0])
        for reg in regs: m.reg_write(reg, 0)
        for reg, value in ((c.UC_ARM64_REG_X0, D), (c.UC_ARM64_REG_X1, S),
                (c.UC_ARM64_REG_SP, STACK), (c.UC_ARM64_REG_LR, STOP)):
            m.reg_write(reg, value)
        m.emu_start(TA_PM, STOP, count=3000)
        assert m.reg_read(c.UC_ARM64_REG_PC) == STOP and m.reg_read(c.UC_ARM64_REG_SP) == STACK
        assert bytes(m.mem_read(D, 0x1800)) == loaded_descriptor
        assert bytes(m.mem_read(S, 0x300)) == source_pm
        assert bytes(m.mem_read(va_pointer, 0x1000)) == va_backing
        assert bytes(m.mem_read(vb_pointer, 0x1000)) == vb_backing
        descriptor_before = loaded_descriptor
        joined_counts['initialized_parameter_loads'] += 1
        staged_before = rng.randbytes(0x40); m.mem_write(STAGED, staged_before)
        block_address = rng.getrandbits(64)
        prep_receivers = dict(zip((0xfffffe00089fa7ec, 0xfffffe00089fa810,
            0xfffffe00089fa8d8, 0xfffffe00089fa930, 0xfffffe00089fa990,
            0xfffffe00089faa40), (RES[0], HRES[0], RES[1], HRES[1],
                                   RES[2], METRICS_RESOURCE)))
        support_receivers = {0xfffffe00089fa834: SECOND,
            0xfffffe00089fa89c: FIRST, 0xfffffe00089fa9e8: SINNER}
        generation_receivers = dict(zip((0xfffffe00089fa84c,
            0xfffffe00089fa8e8, 0xfffffe00089fa944, 0xfffffe00089fa9a0,
            0xfffffe00089fa9f8), (SUPPORT, *supports)))
        generation_values = {obj: rng.getrandbits(64) for obj in (SUPPORT, *supports)}
        retained_objects = {SECOND, FIRST, RES[1], HRES[1], RES[2], SINNER,
                            METRICS_RESOURCE, POBJ, GART, DINNER}
        pm = bytearray(m.mem_read(S, 0x300)); hm = bytearray(m.mem_read(HWM, 0x100))
        state = bytearray(m.mem_read(STATE, 0x100))
        block = bytearray(m.mem_read(BLOCK, 0x100))
        frames = bytearray(m.mem_read(CPU60[2], 0x1000))
        cfg = bytes(m.mem_read(CPU60[1], 0x1000))
        assert pm[0x28] == 1 and struct.unpack_from('<Q', pm, 0x258)[0] == 0
        assert struct.unpack_from('<3I', cfg, 0) == (1, 0, 0)
        assert struct.unpack_from('<I', hm, 0x30)[0] == 0
        assert struct.unpack_from('<Q', pm, 0x50)[0] == METRICS_RESOURCE
        joined_events.clear(); job_events.clear(); active_join = True
        qwrite(PMVT+0x1e0, RET)
        for reg in regs: m.reg_write(reg, 0)
        for reg, value in ((c.UC_ARM64_REG_X0, S), (c.UC_ARM64_REG_X1, D),
                (c.UC_ARM64_REG_X2, STAGED), (c.UC_ARM64_REG_SP, STACK),
                (c.UC_ARM64_REG_X19, D), (c.UC_ARM64_REG_X20, S),
                (c.UC_ARM64_REG_X29, STAGED+0x44),
                (c.UC_ARM64_REG_LR, STOP)): m.reg_write(reg, value)
        m.emu_start(RET_CALLER, RET_CALLER_END, count=20000)
        assert m.reg_read(c.UC_ARM64_REG_PC) == RET_CALLER_END
        assert m.reg_read(c.UC_ARM64_REG_SP) == STACK and m.reg_read(c.UC_ARM64_REG_W0) == 0
        ep, eh, ed, es = bytearray(pm), bytearray(hm), bytearray(descriptor_before), bytearray(state)
        if struct.unpack_from('<I', pm, 0x1d0)[0] == 0: struct.pack_into('<I', ep, 0x1d0, 1)
        struct.pack_into('<I', eh, 0x80, 1)
        for off, obj in ((0x70, SUPPORT), (0x78, supports[1])):
            struct.pack_into('<Q', eh, off, generation_values[obj])
        for off, obj in ((0x1b0, supports[0]), (0x1c8, supports[2]), (0x1b8, supports[3])):
            struct.pack_into('<Q', ep, off, generation_values[obj])
        for off, obj in ((0xd88, SECOND), (0xd90, FIRST), (0xda8, RES[1]),
                (0xda0, HRES[1]), (0xdc0, RES[2]), (0xdb0, SINNER),
                (0xdb8, METRICS_RESOURCE), (0xd78, POBJ), (0xd98, DINNER)):
            struct.pack_into('<Q', ed, off, obj)
        ep[0x28] = 3
        if pm[0x1a8] & 1: ep[0x1a8] = 0
        struct.pack_into('<Q', ep, 0x258, POBJ); struct.pack_into('<Q', ep, 0x1c0, 1)
        for off, value in ((0x128, 0), (0x140, 0), (0x144, 1), (0x6c, 1)):
            struct.pack_into('<I', ep, off, value)
        eh[0x34:0x44] = bytes(16)
        frame = (block_address >> 15) & 0x1ffffff
        block[0x10] = 1; struct.pack_into('<I', frames, 0, frame)
        for off, value in ((0x34, 4), (0x54, 3), (0x3c, 1), (0x40, 0)):
            struct.pack_into('<I', es, off, value)
        staged = bytearray(staged_before); struct.pack_into('<I', staged, 0, 1)
        pages = struct.pack('<4I', frame, frame+1, frame+2, frame+3)+page_before[16:]
        for addr, expected in ((S, ep), (HWM, eh), (D, ed), (STATE, es),
                (BLOCK, block), (CPU60[2], frames), (CPU60[1], cfg),
                (STAGED, staged), (PAGE_BUFFER, pages)):
            actual = bytes(m.mem_read(addr, len(expected)))
            assert actual == bytes(expected), (i, hex(addr), [hex(j) for j in range(len(expected)) if actual[j] != expected[j]][:20])
        assert [e[1] for e in joined_events if e[0] == 'native'] == [PAGEPREP, PAGERELEASE, PAGEGEN, PREPARE, BUILD]
        assert bytes(m.mem_read(PA, 8)) == struct.pack('<Q', GART)
        assert bytes(m.mem_read(PBARRAY, 8)) == struct.pack('<Q', BSUPPORT)
        assert struct.unpack('<II', m.mem_read(POBJ+0x90, 8)) == (64, 1)
        assert struct.unpack('<Q', m.mem_read(POBJ+0x98, 8))[0] == 0x20000
        page_object = bytearray(page_object_before)
        struct.pack_into('<QQIIQ', page_object, 0x80, PA, PBARRAY, 64, 1, 0x20000)
        assert bytes(m.mem_read(POBJ, len(page_object))) == page_object
        for addr, before, first in zip((PA, PBARRAY), page_array_before, (GART, BSUPPORT)):
            assert bytes(m.mem_read(addr, len(before))) == struct.pack('<Q', first)+before[8:]
        # Actual TA caller instructions now include native UMA validation/usage.
        # Earlier preparation remains omitted. All event operations are fixtures.
        qwrite(KRES+0x18, 0x2fa500)
        qwrite(D+0x10, GPU); qwrite(D+0xd68, S); qwrite(D+0xd70, HWM)
        wanted = [rng.getrandbits(64), rng.getrandbits(64)]
        flags = [rng.randrange(256), rng.randrange(256)]
        uma.seed(D, wanted, [1, 1], [0, 0], flags)
        uma.qwrite(D+0x208, wanted[1])
        qwrite(D, 0x2fa800); qwrite(0x2fa800+0x208, LOCK); qwrite(0x2fa800+0x210, UPDATE)
        qwrite(STACK+0x18, wanted[0])
        uma_before_p = [bytes(m.mem_read(p, 0x220)) for p in uma.pools]
        uma_before_n = [bytes(m.mem_read(n, 0x200)) for n in uma.nodes]
        request = i % 32; m.mem_write(D+0x1218, struct.pack('<I', request))
        m.mem_write(D+0xc44, b'\x03')
        descriptor_for_caller = bytes(m.mem_read(D, 0x1800))
        ring_before = rng.randbytes(0x1000); m.mem_write(RING, ring_before)
        scene_before = bytes(m.mem_read(CPU60[0], 0x1000)); job_events.clear()
        for reg in regs: m.reg_write(reg, 0)
        m.reg_write(c.UC_ARM64_REG_X19, D); m.reg_write(c.UC_ARM64_REG_SP, STACK)
        m.reg_write(c.UC_ARM64_REG_X20, D)
        m.reg_write(c.UC_ARM64_REG_LR, STOP)
        uma.active = True
        m.emu_start(CALLER, CALLER_END, count=3000)
        uma.active = False
        assert m.reg_read(c.UC_ARM64_REG_PC) == CALLER_END and m.reg_read(c.UC_ARM64_REG_SP) == STACK
        if not ep[0x230] & 1:
            ep[0x230] = 1; struct.pack_into('<Q', ep, 0x238, 1)
        struct.pack_into('<I', eh, 0x30, 2); struct.pack_into('<I', es, 0xc, request)
        ring = bytearray(ring_before)
        ring[request*16:request*16+16] = load_entry(ring_before[request*16:request*16+16], es, eh[0x34:0x44])
        scene = bytearray(scene_before); struct.pack_into('<I', scene, 0x48, 0)
        for addr, expected in ((S, ep), (HWM, eh), (STATE, es), (RING, ring),
                (CPU60[0], scene), (D, descriptor_for_caller), (PAGE_BUFFER, pages)):
            assert bytes(m.mem_read(addr, len(expected))) == bytes(expected), (i, 'caller', hex(addr))
        assert job_events == [('native_hal',), ('ring_cpu_map',)]
        assert [e[1] for e in joined_events if e[0] == 'caller'] == [0xfffffe0008a22c34, 0xfffffe0008a22c48]
        result, validate_events, increments = expected_validation(wanted, wanted, [1, 1])
        assert result == 0 and increments == [0, 0]
        assert uma.events == validate_events+expected_update(flags)
        for p, before in zip(uma.pools, uma_before_p): assert bytes(m.mem_read(p, len(before))) == before
        for j, n in enumerate(uma.nodes):
            en = bytearray(uma_before_n[j])
            if flags[j] & 1: en[0x1b8] = 0
            assert bytes(m.mem_read(n, len(en))) == en
        joined_counts['uma_validations'] += 1; joined_counts['uma_usage_updates'] += 1
        joined_counts['uma_descriptor_event_updates'] += sum(bool(flag & 1) for flag in flags)
        joined_counts['caller_bindings'] += 1
        joined_counts['chains'] += 1; joined_counts['fresh_page_mappings'] += 1
        joined_counts['descriptor_resources'] += 9; joined_counts['page_entries'] += 4
        joined_counts['initializer_mode_one'] += 1
    finally:
        active_join = False
        uma.active = False
        m.mem_write(0x200000, original_ram)
        block_address = old_block_address

needle = 'job_pm=bytes(m.mem_read(S,0x300));'
assert tail.count(needle) == 1
tail = tail.replace(needle, 'initialized_retention();'+needle)
# Explicit inherited-constructor outputs; the PM-specific initializer does not
# initialize these fields. Preserve them through both independent parent models.
needle = "struct.pack_into('<Q',original,0xa8,0);"
assert tail.count(needle) == 1
tail = tail.replace(needle, needle+"struct.pack_into('<Q',original,0x258,0);struct.pack_into('<I',original,0x1d0,0);")
tail = tail.replace('args.output.write_text', "report['initialized_retention_counts']=joined_counts\nreport['initialized_retention_range']=[hex(RET),hex(RET_END)]\nreport['ta_caller_window']=[hex(CALLER),hex(CALLER_END)]\nreport['ta_caller_window_sha256']=hashlib.sha256(read(CALLER,CALLER_END-CALLER)).hexdigest()\nreport['usage_update_range']=[hex(USAGE),hex(PB)]\nreport['usage_update_range_sha256']=hashlib.sha256(read(USAGE,PB-USAGE)).hexdigest()\nreport['ta_retention_caller_window']=[hex(RET_CALLER),hex(RET_CALLER_END)]\nreport['ta_retention_caller_window_sha256']=hashlib.sha256(read(RET_CALLER,RET_CALLER_END-RET_CALLER)).hexdigest()\nreport['ta_parameter_loader_range']=[hex(TA_PM),hex(TA_PM_END)]\nreport['ta_parameter_loader_range_sha256']=hashlib.sha256(read(TA_PM,TA_PM_END-TA_PM)).hexdigest()\nreport['initialized_retention_range_sha256']=hashlib.sha256(read(RET,RET_END-RET)).hexdigest()\nreport['qualification']='256 actual initializer/metrics/scene/block/HWPB graphs feed full TA parameter loader and actual TA retention caller22504..22534, whole ordinary retention, fresh page mapping/release-null/generation/block/page methods. Full PM/manager/TA/state/config/block/staged/frame/page byte comparisons. PM50 metrics backing reaches TA db8. Initial PM mode1 preserved. Actual TA caller22be4..22c4c executes native UMA lock and full canSubmitLocked validation, usage update, PM usage update, PB binding and packed ring HAL. Explicit seeds/event success fixtures, randomized dirty byte flags, pool/node comparisons and logical lock ordering checked. Inherited constructor fields PM258=0/PM1d0=0, support providers/retain/mapping preparation and event/mutex services remain fixtures. Optional host tracing off; omitted caller intervals and full TA prepare not qualified. No live allocation/cache/retirement/submission. RAM restored after joined branch before separate parent manual ring checks.'\nargs.output.write_text")
exec(compile(tail, str(base), 'exec'))
