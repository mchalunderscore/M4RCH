#!/usr/bin/env python3
"""Recover native shared ownership from matched 25G83 inputs, in RAM only."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import re

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as reg

BASE = 0xfffffe0000000000
HOST_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'


def pin(path):
    b = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def prepare(macho, output):
    b = macho.read_bytes()
    if hashlib.sha256(b).hexdigest() != HOST_SHA:
        raise ValueError('Only the matched 25G83 AGX input is supported')
    segments, p = [], 32
    for _ in range(struct.unpack_from('<I', b, 16)[0]):
        command, n = struct.unpack_from('<II', b, p)
        if command == 25:
            segments.append(struct.unpack_from('<QQQQ', b, p + 24))
        p += n

    def read(a, n):
        offsets = [off + BASE + a - va for va, _, off, sz in segments
                   if va <= BASE + a and BASE + a + n <= va + sz]
        if len(offsets) != 1:
            raise ValueError('Source span not uniquely backed')
        return b[offsets[0]:offsets[0] + n]

    spans = []
    for name, lo, hi in [
        ('support_27_children', 0x89ab988, 0x89abbd8),
        ('support_range8_allocation', 0x89abbb8, 0x89abc24),
        ('native_alignment_loop', 0x89a7c70, 0x89a7cf4),
        ('channel_pointer_producer', 0x89a9650, 0x89a9f5c),
        ('DM_pointer_getters', 0x89b59bc, 0x89b5a08),
        ('control_pointer_getters', 0x89b5870, 0x89b58bc),
        ('shared_zero_and_header_initialization', 0x89a9b74, 0x89a9fac),
        ('native_shared_pointers', 0x89be47c, 0x89be7c8),
        ('root_native_bindings', 0x89cd914, 0x89cdc4c),
        ('prepareFirmwareForBoot', 0x89ca4c8, 0x89ca56c),
        ('selected_G16X_a88_noop', 0x89ea1c4, 0x89ea1cc),
        ('native_init_record_setters', 0x89d1694, 0x89d181c),
        ('rx_validator_initialization', 0x89ad000, 0x89ad168),
        ('native_status_initialization', 0x89aa0f8, 0x89aa14c),
        ('AONPTD_allocation_descriptor', 0x89abca8, 0x89abd2c),
    ]:
        code = read(lo, hi - lo)
        spans.append({'name': name, 'start': hex(lo), 'end': hex(hi), 'bytes': len(code),
                      'sha256': hashlib.sha256(code).hexdigest()})

    ram = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for va, vsize, off, size in segments:
        if size:
            start, end = va & ~0xfff, (va + vsize + 0xfff) & ~0xfff
            ram.mem_map(start, end - start)
            ram.mem_write(va, b[off:off + size])
    obj, stack, shift = 0x10000000, 0x20010000, 0x30000000
    ram.mem_map(obj, 0x40000)
    ram.mem_map(0x20000000, 0x20000)
    ram.mem_map(shift, 0x1000)
    ram.reg_write(reg.UC_ARM64_REG_X19, obj)
    ram.reg_write(reg.UC_ARM64_REG_SP, stack)
    ram.reg_write(reg.UC_ARM64_REG_X29, stack + 0x330)
    ram.reg_write(reg.UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def execute(lo, hi, limit):
        ram.emu_start(BASE + lo, BASE + hi, count=limit)
        if ram.reg_read(reg.UC_ARM64_REG_PC) != BASE + hi:
            raise ValueError('Native producer did not reach stop')

    execute(0x89ab988, 0x89abbb0, 500)
    # x22 is the stack children pointer in this part of allocFirmwareData.
    ram.reg_write(reg.UC_ARM64_REG_X22, stack + 0x20)
    ram.reg_write(reg.UC_ARM64_REG_X23, obj + 0x858)
    execute(0x89abbb0, 0x89abbd8, 100)
    descriptor = stack + 0x330 - 0x88
    outer = struct.unpack('<QQB7xQI4xQ', bytes(ram.mem_read(descriptor, 48)))
    if (outer[0] - obj, outer[1] - obj, outer[2], outer[3], outer[4], outer[5]) != (
            0x590, 0x598, 8, stack + 0x20, 27, 0):
        raise ValueError('Support pool descriptor differs')
    before = bytes(ram.mem_read(stack + 0x20, 27 * 24))
    ram.mem_write(BASE + 0x7ea2388, struct.pack('<Q', shift))
    ram.mem_write(shift, struct.pack('<I', 14))
    ram.reg_write(reg.UC_ARM64_REG_X1, descriptor)
    execute(0x89a7c70, 0x89a7cf4, 1200)
    after = bytes(ram.mem_read(stack + 0x20, 27 * 24))
    children = []
    for i, (cpu, mapping, size, offset) in enumerate(struct.iter_unpack('<QQII', after)):
        expected = 0 if not i else (children[-1]['offset'] + children[-1]['bytes'] + 63) & ~63
        if offset != expected:
            raise ValueError('Support pool native alignment differs')
        children.append({'index': i, 'cpu_owner': hex(cpu - obj), 'mapping_owner': hex(mapping - obj),
                         'bytes': size, 'offset': offset})
    logical = children[-1]['offset'] + children[-1]['bytes']
    backing = (logical + 0x3fff) & ~0x3fff
    if ram.reg_read(reg.UC_ARM64_REG_X21) != backing:
        raise ValueError('Support pool page rounding differs')

    entry = read(0x7eaee20, 8)
    target = 0x7004000 + (struct.unpack('<Q', entry)[0] & 0xffffffff)
    if target != 0x89ea1c4:
        raise ValueError('Selected G16X init register callback differs')
    noop_target = target
    # Execute the selected leaf itself. It has no memory accesses or stores.
    ram.reg_write(reg.UC_ARM64_REG_X0, obj)
    ram.reg_write(reg.UC_ARM64_REG_X1, 1)
    ram.reg_write(reg.UC_ARM64_REG_X30, BASE + 0x89ea1cc)
    before_obj = bytes(ram.mem_read(obj, 0x40000))
    execute(0x89ea1c4, 0x89ea1cc, 4)
    if bytes(ram.mem_read(obj, 0x40000)) != before_obj:
        raise ValueError('Selected no-op callback changed RAM')

    # Owned CPU allocations plus an explicit identity GPU-VA translation service
    # fixture. Actual pointer getters and producer stores execute from the image;
    # no kernel mapping/allocation provider or pointer authentication is emulated.
    bundle, support, vtables = 0x50000000, 0x51000000, 0x52000000
    ram.mem_map(bundle, 0x24000)
    ram.mem_map(support, backing)
    ram.mem_map(vtables, 0x3000)
    native_bundle = [(0x2b8,0x300,0,0x2718),(0x2c0,0x308,0x2740,0xc18),
        (0x2c8,0x310,0x3380,0x1048),(0x2d0,0x318,0x4400,0xe10),
        (0x2d8,0x320,0x5240,0x6578),(0x2e0,0x328,0xb7c0,0x68),
        (0x2e8,0x330,0xb840,0x800),(0x2f0,0x338,0xc040,0),
        (0x2f8,0x340,0xc040,0x88),(0x440,0x448,0xc100,0x1800),
        (0x418,0x420,0xd900,0x1800),(0x3f0,0x3f8,0xf100,0x1800),
        (0x3c8,0x3d0,0x10900,0x1800),(0x4e0,0x4e8,0x12100,0x1800),
        (0x4b8,0x4c0,0x13900,0x1800),(0x490,0x498,0x15100,0x1800),
        (0x468,0x470,0x16900,0x1800),(0x580,0x588,0x18100,0x1800),
        (0x558,0x560,0x19900,0x1800),(0x530,0x538,0x1b100,0x1800),
        (0x508,0x510,0x1c900,0x1800),(0x858,0x878,0x1e100,0x4c0),
        (0x8b0,0x8b8,0x1e5c0,0x4000)]
    def qwrite(a,v): ram.mem_write(a,struct.pack('<Q',v))
    for cpu, mapping, offset, _ in native_bundle:
        qwrite(obj+cpu,bundle+offset)
        qwrite(obj+mapping,bundle+offset)
    for child in children:
        qwrite(obj+int(child['cpu_owner'],16),support+child['offset'])
        qwrite(obj+int(child['mapping_owner'],16),support+child['offset'])
    qwrite(obj,vtables)
    qwrite(obj+0x860,bundle+0x1e120)
    qwrite(obj+0x868,bundle+0x1e2c0)
    qwrite(obj+0x298,obj+0x10000)
    ram.mem_write(obj+0x94c,struct.pack('<I',7))
    for host in [0x3b0+i*0x28 for i in range(4)] + [0x450+i*0x28 for i in range(4)] + [0x4f0+i*0x28 for i in range(4)]:
        qwrite(obj+host,vtables+0x1000)
    qwrite(obj+0x898,vtables+0x2000)
    for table, targets in [(vtables+0x1000,(0x89b59fc,0x89b59dc,0x89b59bc)),
                           (vtables+0x2000,(0x89b58b0,0x89b5890,0x89b5870))]:
        for slot,target in zip((8,0x18,0x28),targets): qwrite(table+slot,BASE+target)
    # This local private disassembly supplies mnemonics to bypass unsupported PAC
    # operations only; neither it nor instruction bytes are copied into reports.
    assembly = Path('out/private-apple/agx-disassembly.txt').read_text()
    ops = {}
    for line in assembly.splitlines():
        match = re.match(r'([0-9a-f]{16}):\s+(?:[0-9a-f]{2} ){3}[0-9a-f]{2}\s+(\S+)\s*(.*)',line)
        if match: ops[int(match[1],16)] = (match[2],match[3])
    services = {'GPU_VA_translation_identity':0,'bzero':0,'PAC_bypassed':0,'native_getters':0}
    def hook(uc,pc,size,_):
        mnemonic, operands = ops.get(pc,('', ''))
        if mnemonic in ('pacibsp','autibsp','autda','xpacd'):
            services['PAC_bypassed'] += 1
            uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
        elif mnemonic == 'retab':
            uc.reg_write(reg.UC_ARM64_REG_PC,uc.reg_read(reg.UC_ARM64_REG_X30))
        elif mnemonic == 'blraa':
            x0 = uc.reg_read(reg.UC_ARM64_REG_X0)
            if pc == BASE+0x89ca544:
                uc.reg_write(reg.UC_ARM64_REG_X0,0x54000000)
                uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
            elif pc == BASE+0x89ca508:
                if uc.reg_read(reg.UC_ARM64_REG_X8) != BASE+noop_target or uc.reg_read(reg.UC_ARM64_REG_X1)!=1:
                    raise ValueError('Selected native boot callback fixture differs')
                uc.reg_write(reg.UC_ARM64_REG_X30,pc+4)
                uc.reg_write(reg.UC_ARM64_REG_PC,BASE+noop_target)
            elif x0 == obj:
                services['GPU_VA_translation_identity'] += 1
                uc.reg_write(reg.UC_ARM64_REG_X0,uc.reg_read(reg.UC_ARM64_REG_X1))
                uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
            else:
                target_reg = reg.UC_ARM64_REG_X8 if operands.startswith('x8,') else reg.UC_ARM64_REG_X9
                target = uc.reg_read(target_reg)
                if target not in [BASE+x for x in (0x89b59fc,0x89b59dc,0x89b59bc,0x89b58b0,0x89b5890,0x89b5870)]:
                    raise ValueError('Unexpected native channel getter')
                services['native_getters'] += 1
                uc.reg_write(reg.UC_ARM64_REG_X30,pc+4)
                uc.reg_write(reg.UC_ARM64_REG_PC,target)
        elif mnemonic == 'bl':
            if operands != '0xfffffe000b744da0' and '_bzero' not in operands:
                raise ValueError('Unexpected direct service in native channel producer: '+operands)
            address, count = uc.reg_read(reg.UC_ARM64_REG_X0),uc.reg_read(reg.UC_ARM64_REG_X1)
            uc.mem_write(address,bytes(count))
            services['bzero'] += 1
            uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
    h = ram.hook_add(UC_HOOK_CODE,hook)
    ram.reg_write(reg.UC_ARM64_REG_X19,obj)
    execute(0x89a9650,0x89a9fac,4000)
    ram.reg_write(reg.UC_ARM64_REG_X0,obj)
    ram.reg_write(reg.UC_ARM64_REG_X30,BASE+0x89be7c8)
    execute(0x89be47c,0x89be7c8,1000)
    ram.hook_del(h)
    main_image = bytes(ram.mem_read(bundle+0x1e100,0x4c0))
    records = [list(record) for record in struct.iter_unpack('<QQQQ',main_image[0x20:0x240])]
    ram.reg_write(reg.UC_ARM64_REG_X19,obj)
    execute(0x89aa0f8,0x89aa100,8)
    ram.reg_write(reg.UC_ARM64_REG_X22,1)
    ram.reg_write(reg.UC_ARM64_REG_X10,obj+0x30000)
    execute(0x89aa134,0x89aa14c,12)
    support_image = bytes(ram.mem_read(support,backing))
    # Native host validator constructors contain no calls in the bounded span.
    ram.reg_write(reg.UC_ARM64_REG_X19,obj)
    execute(0x89ad000,0x89ad138,500)
    validators = []
    for off in [0x5f0+i*0x30 for i in range(9)] + [0x7a0,0x7d0]:
        host, state, ring, cached, kind, capacity = struct.unpack('<QQQQQQ',bytes(ram.mem_read(obj+off,48)))
        validators.append({'host_owner':hex(off),'state':state,'ring':ring,'kind':kind,'capacity':capacity,
                           'record_bytes':0x48,'cursor_read_offset':0,'cursor_write_offset':0x20})
    qwrite(obj+0x298,obj+0x10000)
    # Event validator follows the clears, which preserve vector zero from the
    # constructor. Start just at the event pointer loads to preserve ownership.
    ram.reg_write(reg.UC_ARM64_REG_Q0,0)
    execute(0x89ad140,0x89ad168,100)
    off=0x800
    host,state,ring,cached,kind,capacity=struct.unpack('<QQQQQQ',bytes(ram.mem_read(obj+off,48)))
    validators.append({'host_owner':hex(off),'state':state,'ring':ring,'kind':kind,'capacity':capacity,
                       'record_bytes':0x48,'cursor_read_offset':0,'cursor_write_offset':0x20})
    # Execute complete native prepareFirmwareForBoot, including the selected
    # G16X no-op leaf and native stores into a nonzero RAM allocation fixture.
    region_a=0x54000000
    ram.mem_map(region_a,0x4000)
    ram.mem_write(region_a,b'\xa5'*0x4000)
    qwrite(obj+0x10000,vtables)
    qwrite(vtables+0xa88,BASE+noop_target)
    qwrite(obj+0x16a0,obj+0x9000)
    qwrite(obj+0x9000,vtables)
    h=ram.hook_add(UC_HOOK_CODE,hook)
    ram.reg_write(reg.UC_ARM64_REG_X0,obj)
    ram.reg_write(reg.UC_ARM64_REG_X30,BASE+0x89ca56c)
    execute(0x89ca4c8,0x89ca56c,300)
    ram.hook_del(h)
    region_a_image=bytes(ram.mem_read(region_a,0x4000))
    cursor=struct.unpack('<I',bytes(ram.mem_read(obj+0x1710,4)))[0]
    if cursor!=24 or region_a_image!=bytes(20)+b'\xa5'*(0x4000-20):
        raise ValueError('Native Region A terminator or padding differs')
    # Execute actual native root translator payload copy and root word28.
    root=0x55000000
    ram.mem_map(root,0x4000)
    uat_payload=bytes((i*37)&255 for i in range(104))
    qwrite(obj+0x10000+0x18d08,obj+0x30000)
    ram.mem_write(obj+0x30000+0x18,uat_payload)
    ram.reg_write(reg.UC_ARM64_REG_X19,obj)
    ram.reg_write(reg.UC_ARM64_REG_X20,root)
    execute(0x89cdab4,0x89cdb00,80)
    root_payload=bytes(ram.mem_read(root+0x28,0x70))
    ram.reg_write(reg.UC_ARM64_REG_X19,obj)
    execute(0x89abca8,0x89abcec,120)
    aon_outer=struct.unpack('<QQB7xQI4xQ',bytes(ram.mem_read(stack+0x20,48)))
    if (aon_outer[0]-obj,aon_outer[1]-obj,aon_outer[2],aon_outer[4],aon_outer[5])!=(0xc20,0xc28,9,1,0):
        raise ValueError('Native AONPTD outer descriptor differs')
    ram.reg_write(reg.UC_ARM64_REG_X1,stack+0x20)
    execute(0x89a7c70,0x89a7cf4,150)
    aon_cpu,aon_mapping,aon_bytes,aon_offset=struct.unpack('<QQII',bytes(ram.mem_read(aon_outer[3],24)))
    if (aon_cpu-obj,aon_mapping-obj,aon_bytes,aon_offset,ram.reg_read(reg.UC_ARM64_REG_X21))!=(0xc38,0xc30,0xe4,0,0x4000):
        raise ValueError('Native AONPTD child alignment differs')

    report = {'schema': 'm4rch.native-t6040-shared-v7.source.v1', 'macho': pin(macho),
        'source_spans': spans, 'support_children': children, 'support_logical_bytes': logical,
        'support_backing_bytes': backing, 'support_range': 8, 'alignment': 64,
        'page_shift_fixture': 14, 'allocator_provider_executed': False,
        'source_execution': {'support_descriptor_and_alignment': True, 'selected_a88_leaf': True,
                             'native_main_channels_shared_pointers':True,'native_RX_validators':True,
                             'prepareFirmwareForBoot_complete_with_owned_resource_fixture':True,
                             'root_UAT_payload_copy':True,
                             'support_descriptor_before_sha256': hashlib.sha256(before).hexdigest(),
                             'support_descriptor_after_sha256': hashlib.sha256(after).hexdigest()},
        'selected_init_register_callback': {'class': 'AGXAcceleratorG16X', 'vtable_address_point': '0x7eae398',
            'slot': '0xa88', 'entry': '0x7eaee20', 'entry_sha256': hashlib.sha256(entry).hexdigest(),
            'target': hex(noop_target), 'supplied_bool': 1, 'native_noop': True,
            'region_a_cursor_owner': '0x1710', 'record_stride': 24,
            'terminator_zero_bytes': 20, 'terminator_padding_preserved': 4},
        'cursor_storage': {'kind': 'allocated RAM', 'range': 8, 'work_state_child_bytes': 48,
            'read': 0, 'prefetch': 16, 'write': 32, 'SGX_MMIO_alias_required': False},
        'native_main_fixture': {'bundle_base':bundle,'support_base':support,'initial_status':7,
            'channels':records,'main_sha256':hashlib.sha256(main_image).hexdigest(),
            'main_hex':main_image.hex(),'services':services,'RX_validators':validators,
            'native_allocation_translation_provider_executed':False,
            'pointer_authentication_executed':False,
            'support_sha256':hashlib.sha256(support_image).hexdigest(),
            'status_a_hex':support_image[0xee40:0xee60].hex(),
            'status_b_prefix_hex':support_image[0x340:0x350].hex(),
            'status_b_last_word_hex':support_image[0xe774:0xe778].hex(),
            'extra_0_status_hex':support_image[0xeda4:0xedac].hex()},
        'region_a_fixture':{'backing_bytes':0x4000,'before_byte':0xa5,'cursor_after':cursor,
                           'sha256':hashlib.sha256(region_a_image).hexdigest(),
                           'resource_CPU_address_provider_executed':False},
        'root_fixture':{'UAT_payload_hex':uat_payload.hex(),'copied_root_28_98_hex':root_payload.hex(),
                        'translator_UAT_payload_constructor_executed':False},
        'AONPTD_allocation':{'CPU_owner':'0xc38','GPU_mapping_owner':'0xc30','range':9,
                            'logical_bytes':aon_bytes,'backing_bytes':0x4000,'offset':aon_offset,
                            'native_descriptor_and_alignment_executed':True,
                            'provider_executed':False,'ARM_power_pointer_offset':'0x6318'},
        'hardware_actions': [], 'private_binary_or_instruction_bytes_exported': False,
        'normal_startup_qualified': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        f.write(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('macho', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    r = prepare(args.macho, args.output)
    print(json.dumps({'children': len(r['support_children']), 'logical': r['support_logical_bytes'],
                      'backing': r['support_backing_bytes'], 'a88': r['selected_init_register_callback'],
                      'hardware_actions': []}))
