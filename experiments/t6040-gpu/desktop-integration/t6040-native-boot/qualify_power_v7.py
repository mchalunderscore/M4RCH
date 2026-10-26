#!/usr/bin/env python3
"""Qualify the native power lifecycle component against saved ARM64 source in RAM."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as reg

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
BASE = 0xfffffe0000000000
AGX = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
AGX_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
FW, ACC, POWER, HARDWARE, REGION, NODE, RAW, STACK = [0x10000000 + i * 0x40000 for i in range(8)]
STOP = 0x10300000


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class Native:
    """Unmodified saved instructions; hooks model typed external RAM services only."""
    def __init__(self, properties, maximum, ticks, preserved):
        self.raw = AGX.read_bytes()
        assert hashlib.sha256(self.raw).hexdigest() == AGX_SHA
        self.segments, cursor = [], 32
        self.ram = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for _ in range(struct.unpack_from('<I', self.raw, 16)[0]):
            command, size = struct.unpack_from('<II', self.raw, cursor)
            if command == 25:
                vm, virtual, off, extent = struct.unpack_from('<QQQQ', self.raw, cursor + 24)
                self.segments.append((vm, virtual, off, extent))
                if extent:
                    start, end = vm & ~0xfff, (vm + virtual + 0xfff) & ~0xfff
                    self.ram.mem_map(start, end - start)
                    self.ram.mem_write(vm, self.raw[off:off + extent])
            cursor += size
        self.ram.mem_map(FW, 0x400000)
        self.properties, self.maximum, self.ticks = properties, maximum, ticks
        self.calls = []
        self.instructions = {}
        disassembly = ROOT / 'out/private-apple/agx-disassembly.txt'
        for line in disassembly.read_text().splitlines():
            match = re.match(r'([0-9a-f]{16}):\s+(?:[0-9a-f]{2}\s+){4}(\S+)\s*(.*)', line)
            if match:
                self.instructions[int(match[1], 16)] = (match[2], match[3])
        self.ram.hook_add(UC_HOOK_CODE, self.hook)
        self.ram.reg_write(reg.UC_ARM64_REG_CPACR_EL1, 3 << 20)
        self.put64(FW, BASE + 0x7ea8678)
        self.put64(ACC, BASE + 0x7eae398)
        self.put64(FW + 0x298, ACC)
        self.put64(FW + 0x2d8, POWER)
        self.put64(FW + 0x2b8, HARDWARE)
        self.put64(FW + 0x380, REGION)
        self.put64(FW + 0x968, FW + 0x10000)
        self.put64(ACC + 0x130, NODE)
        self.put32(ACC + 0x4a0, 28)
        self.put64(ACC + 0xf590, FW + 0x980)
        self.put64(ACC + 0x1aee0, NODE + 0x3000)
        self.put64(NODE + 0x3078, NODE + 0x4000)
        self.put64(NODE, NODE + 0x1000)
        self.put64(NODE + 0x1000 + 0x2d8, 0x101000)
        self.put64(RAW, RAW + 0x1000)
        self.put64(RAW + 0x1000 + 0x198, 0x102000)
        self.put64(RAW + 0x1000 + 0x160, 0x102004)
        # External OSData metaclass service input, not an instruction patch.
        self.put64(BASE + 0x7ea2490, NODE + 0x5000)
        self.put32(ACC + 0x196d0, 16)
        self.put32(ACC + 0xedb0, int.from_bytes(properties['gpu-pwr-sample-period-aic-clks'], 'little'))
        rows = properties['perf-states']
        for i in range(16):
            self.put32(ACC + 0x196d8 + i * 4, struct.unpack_from('<I', rows, i * 8)[0])
        # The secondary CPU owner is supplied independently for arithmetic
        # qualification. It is not claimed to be a bound ADT/provider domain.
        self.secondary = [24000000 + i * 73000111 for i in range(16)]
        for i, value in enumerate(self.secondary):
            self.put32(ACC + 0x19f20 + i * 4, value)
        self.ram.mem_write(POWER, bytes([0xa5]) * (0x6578 + 16))
        self.ram.mem_write(HARDWARE, bytes([0xa5]) * (0x2718 + 16))
        self.ram.mem_write(REGION, bytes([0xa5]) * (0xe58 + 16))
        self.ram.mem_write(POWER + 0x6530, preserved[0])
        self.ram.mem_write(POWER + 0x2888, preserved[1])

    def read_source(self, address, length):
        address += BASE
        matches = [off + address - vm for vm, _, off, size in self.segments
                   if vm <= address and address + length <= vm + size]
        assert len(matches) == 1
        return self.raw[matches[0]:matches[0] + length]

    def put32(self, address, value):
        self.ram.mem_write(address, struct.pack('<I', value))

    def put64(self, address, value):
        self.ram.mem_write(address, struct.pack('<Q', value))

    def x(self, number):
        return self.ram.reg_read(getattr(reg, f'UC_ARM64_REG_X{number}'))

    def setx(self, number, value):
        self.ram.reg_write(getattr(reg, f'UC_ARM64_REG_X{number}'), value)

    def hook(self, ram, address, size, _):
        mnemonic, operands = self.instructions.get(address, ('', ''))
        if mnemonic in ('pacibsp', 'autibsp', 'autda', 'xpacd', 'pacda'):
            ram.reg_write(reg.UC_ARM64_REG_PC, address + 4)
        elif mnemonic == 'retab':
            ram.reg_write(reg.UC_ARM64_REG_PC, self.x(30))
        elif mnemonic in ('blraa', 'braa'):
            number = int(re.match(r'x(\d+)', operands)[1])
            value = self.x(number)
            target = value if value in (0x101000, 0x102000, 0x102004) else BASE + 0x7004000 + (value & 0xffffffff)
            if mnemonic == 'blraa': self.setx(30, address + 4)
            if target == 0x101000:
                key = bytes(ram.mem_read(self.x(1), 128)).split(b'\0')[0].decode()
                data = self.properties.get(key)
                self.calls.append(dict(kind='raw_property', key=key, present=data is not None))
                if data is not None: ram.mem_write(RAW + 0x2000, data)
                self.property_size = len(data) if data is not None else 0
                self.setx(0, RAW if data is not None else 0)
                ram.reg_write(reg.UC_ARM64_REG_PC, self.x(30))
            elif target in (0x102000, 0x102004):
                self.setx(0, RAW + 0x2000 if target == 0x102000 else self.property_size)
                ram.reg_write(reg.UC_ARM64_REG_PC, self.x(30))
            else:
                self.calls.append(dict(kind='native_virtual', site=hex(address - BASE), target=hex(target - BASE)))
                ram.reg_write(reg.UC_ARM64_REG_PC, target)
        elif mnemonic in ('bl', 'b'):
            target = int(re.search(r'0x([0-9a-f]+)', operands)[1], 16) if '0x' in operands else None
            if target in (BASE + 0xb744da0, BASE + 0xb744bf0, BASE + 0xbeaf410,
                          BASE + 0xb928a20, BASE + 0xb7b13c4, BASE + 0xb7b27c0,
                          BASE + 0xbfec11c):
                self.calls.append(dict(kind='external_service', target=hex(target - BASE)))
                if target == BASE + 0xb744da0: ram.mem_write(self.x(0), bytes(self.x(1)))
                elif target == BASE + 0xb744bf0: ram.mem_write(self.x(0), bytes(ram.mem_read(self.x(1), self.x(2))))
                elif target == BASE + 0xb928a20: self.setx(0, self.ticks)
                ram.reg_write(reg.UC_ARM64_REG_PC, address + 4 if mnemonic == 'bl' else self.x(30))
        # Calculated maximum power is intentionally an external fixture here:
        # source scalar writer still executes, fuse calculation is not claimed.
        if address == BASE + 0x89ac630:
            self.put32(ACC + 0xf2a0, self.maximum)
            ram.reg_write(reg.UC_ARM64_REG_PC, BASE + 0x89ac694)

    def execute(self, start, end=STOP, owner=FW):
        self.setx(0, owner)
        self.setx(30, STOP)
        self.ram.reg_write(reg.UC_ARM64_REG_SP, STACK + 0x30000)
        try:
            self.ram.emu_start(BASE + start, end, count=30000)
        except Exception as error:
            raise RuntimeError(f'Native RAM execution stopped at {self.ram.reg_read(reg.UC_ARM64_REG_PC):#x}; calls {self.calls[-4:]}') from error
        assert self.ram.reg_read(reg.UC_ARM64_REG_PC) == end


def qualify(output):
    output.mkdir(parents=True, exist_ok=False)
    v6 = ROOT / 'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json'
    saved = json.loads(v6.read_text())
    assert pin(v6)['sha256'] == 'df3411781630ef92d84c37d50c40ca2d243d63be928993cc77994e401a13d1bd'
    adt = next(Path(row['path']) for row in saved['source_pins'] if row['path'].endswith('/boot.adt'))
    adt_parser = ROOT / 'experiments/t6040-gpu/adt.py'
    spec = importlib.util.spec_from_file_location('native_v7_power_adt', adt_parser)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    node = parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx']
    component = KIT / 'g16_t6040_power_v7.rs'
    baseline_float = ROOT / 'out/gpu-gravity-normal-boot-v6/source/linux/drivers/gpu/drm/asahi/float.rs'
    float_text = baseline_float.read_text()
    float_text = float_text[:float_text.index("impl<'a> TryFrom<of::Property")]
    float_text = re.sub(r'use kernel::\{.*?\};', '', float_text, flags=re.S)
    float_text = float_text.replace('unsafe impl Zeroable for F32 {}', '')
    (output / 'float.rs').write_text(float_text)
    # Only exact original SGX bytes are supplied to the actual Rust constructor.
    keys = ['perf-state-count', 'perf-state-table-count', 'perf-states']
    optional = re.search(r'OPTIONAL_WORD_PROPERTIES:.*?= &\[(.*?)\];', component.read_text(), re.S)[1]
    keys += re.findall(r'"([^"]+)"', optional)
    properties = []
    for index, key in enumerate(keys):
        if key in node:
            fixture = output / f'property-{index}.bin'
            fixture.write_bytes(node[key])
            properties.append((key, fixture))
    def property_constructor(rows):
        return '&[' + ','.join('(%s,include_bytes!(%s).as_slice())' %
                              (json.dumps(key), json.dumps(str(path.resolve())))
                              for key, path in rows) + ']'
    constructor = property_constructor(properties)
    tests, cases = [], []
    for index, (maximum, ticks, sentinel) in enumerate([
            (25000, 0x123456789abcdef, 0),
            (12000, 1, 0x37),
            (0x7fffffff, 0xffffffffffffffff, 0xe7),
            (18000, 0x8877665544332211, 0x52)]):
        preserved = (bytes([sentinel]) * 8, bytes((sentinel + i) & 255 for i in range(48)))
        selected_node = dict(node)
        overrides = {} if index != 3 else {
            'gpu-pwr-min-duty-cycle': 50, 'gpu-perf-base-pstate': 2,
            'gpu-pwr-filter-time-constant': 21, 'gpu-pwr-integral-gain': 0x3f800000,
            'gpu-pwr-integral-min-clamp': 0xffffffe7, 'gpu-pwr-proportional-gain': 0x40000000,
            'gpu-perf-filter-time-constant': 9, 'gpu-perf-filter-time-constant2': 17,
            'gpu-perf-filter-drop-threshold': 2, 'gpu-perf-integral-gain': 0x3f000000,
            'gpu-perf-integral-gain2': 0x3f800000, 'gpu-perf-integral-min-clamp': 0xffffffd0,
            'gpu-perf-proportional-gain': 0x3fa00000, 'gpu-perf-proportional-gain2': 0x40200000,
            'gpu-perf-tgt-utilization': 72, 'gpu-perf-dz': 3,
            'gpu-perf-limiter-filter-time-constant': 11, 'gpu-device-max-power': 7500}
        selected_properties = list(properties)
        for key, value in overrides.items():
            selected_node[key] = struct.pack('<I', value)
            path = output / f'override-{index}-{key}.bin'
            path.write_bytes(selected_node[key])
            selected_properties.append((key, path))
        selected_constructor = property_constructor(selected_properties)
        native = Native(selected_node, maximum, ticks, preserved)
        native.execute(0x89ea270, owner=ACC)
        native.execute(0x89e9678, owner=ACC)
        native.execute(0x89ac408)
        native.execute(0x89cad50, end=BASE + 0x89caf20)
        # ARM's period store is already bound by frozen v6 source execution;
        # emulate that selected store as part of the new whole-buffer fixture.
        native.put32(HARDWARE + 0xed8, 8)
        fixtures = {}
        for name, address, extent in [('power', POWER, 0x6578), ('hardware', HARDWARE, 0x2718)]:
            path = output / f'{name}-{index}.bin'
            path.write_bytes(bytes(native.ram.mem_read(address, extent + 16)))
            fixtures[name] = path
        # Only +84/+88/+8c belong to this Region C component; preserve all
        # other bytes and exclude native independent shared-object producers.
        region = bytearray([0xa5] * (0xe58 + 16))
        for offset in (0x84, 0x88, 0x8c):
            region[offset:offset + 4] = native.ram.mem_read(REGION + offset, 4)
        fixtures['region'] = output / f'region-{index}.bin'
        fixtures['region'].write_bytes(region)
        tests.append(f'''{{
let data=p::PowerData::from_adt({selected_constructor}).unwrap();
assert_eq!(data.maximum_index,15);assert_eq!(data.period_ms,8);
let mut power=[0xa5;p::LOGICAL_BYTES+16];
power[0x6530..0x6538].copy_from_slice(&[{','.join(str(v) for v in preserved[0])}]);
power[0x2888..0x28b8].copy_from_slice(&[{','.join(str(v) for v in preserved[1])}]);
let providers=p::LifecycleProviders::capture(&power,{maximum},{ticks}).unwrap();
assert!(data.write_lifecycle_component(&mut power,&providers).is_some());
std::fs::write({json.dumps(str((output / f'actual-power-{index}.bin').resolve()))},power).unwrap();
assert_eq!(power.as_slice(),include_bytes!({json.dumps(str(fixtures['power'].resolve()))}));
let mut hardware=[0xa5;p::HARDWARE_LOGICAL_BYTES+16];
assert!(data.write_hardware_component(&mut hardware).is_some());
assert!(data.write_secondary_hardware_component(&mut hardware,&[{','.join(str(v) for v in native.secondary)}]).is_some());
assert_eq!(hardware.as_slice(),include_bytes!({json.dumps(str(fixtures['hardware'].resolve()))}));
let mut region=[0xa5;p::REGION_C_LOGICAL_BYTES+16];
assert!(data.write_region_c_component(&mut region,&providers).is_some());
assert_eq!(region.as_slice(),include_bytes!({json.dumps(str(fixtures['region'].resolve()))}));
}}''')
        cases.append(dict(calculated_maximum_fixture=maximum, native_absolute_ticks_fixture=ticks,
                          preserved_input_pattern=sentinel, secondary_frequency_owner='independent supplied fixture, provider unbound',
                          synthetic_raw_word_overrides=overrides,
                          native_calls=native.calls, expected_buffers={key: pin(path) for key, path in fixtures.items()}))
    tests.append(f'''
let data=p::PowerData::from_adt({constructor}).unwrap();
assert!(!p::POWER_COMPLETE);
let mut short=vec![0xa5;p::LOGICAL_BYTES-1];
assert!(data.write_component(&mut short).is_none());assert!(short.iter().all(|b|*b==0xa5));
assert!(p::LifecycleProviders::capture(&short,25000,1).is_none());
let power=vec![0xa5;p::LOGICAL_BYTES];
assert!(p::LifecycleProviders::capture(&power,0,1).is_none());
assert!(p::LifecycleProviders::capture(&power,0x80000000,1).is_none());
let mut properties=({constructor}).to_vec();
properties.push(properties[0]);assert!(p::PowerData::from_adt(&properties).is_none());
let zero=[0u8;4];let bad=[0u8;3];
for key in ["gpu-pwr-filter-time-constant","gpu-perf-filter-time-constant","gpu-perf-filter-time-constant2","gpu-perf-limiter-filter-time-constant","gpu-perf-base-pstate"] {{
let mut properties=({constructor}).to_vec();properties.push((key,zero.as_slice()));
assert!(p::PowerData::from_adt(&properties).is_none());
}}
let mut properties=({constructor}).to_vec();let excessive_dz=100u32.to_le_bytes();properties.push(("gpu-perf-dz",excessive_dz.as_slice()));
assert!(p::PowerData::from_adt(&properties).is_none());
let mut properties=({constructor}).to_vec();properties.push(("gpu-pwr-integral-gain",bad.as_slice()));
assert!(p::PowerData::from_adt(&properties).is_none());
''')
    source = output / 'power-tests.rs'
    source.write_text('#![allow(dead_code)]\n#[macro_use]\n#[path="float.rs"] mod float;\n'
                      + '#[path=%s] mod p;\nfn main(){\n%s\n}\n' %
                      (json.dumps(str(component)), '\n'.join(tests)))
    compiler = subprocess.run(['rustc', '--edition=2021', str(source), '-o', str(output / 'power-tests')],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (output / 'compile.stdout').write_text(compiler.stdout)
    (output / 'compile.stderr').write_text(compiler.stderr)
    if compiler.returncode: raise ValueError('Power component Rust compilation failed')
    run = subprocess.run([str(output / 'power-tests')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (output / 'run.stdout').write_text(run.stdout)
    (output / 'run.stderr').write_text(run.stderr)
    if run.returncode: raise ValueError('Power component differs from actual native RAM producer')
    spans = [('G16X_controller_defaults', 0x89ea270, 0x89ea464),
             ('base_controller_defaults', 0x8963724, 0x8963b40),
             ('G16X_sram_scale', 0x89e9678, 0x89e974c),
             ('generic_setup_config', 0x89ac408, 0x89acecc),
             ('generic_power_lifecycle', 0x89a862c, 0x89a8ddc),
             ('ARM_preserve_and_array', 0x89cad50, 0x89caf20),
             ('interface_limits', 0x89a8ddc, 0x89a91d4)]
    report = dict(schema='native-t6040-power-component-v7', component_source=pin(component),
                  inputs=[pin(path) for path in (AGX, adt, adt_parser, v6, baseline_float, Path(__file__))],
                  source_spans=[dict(name=name, start=hex(start), end=hex(end), bytes=end-start,
                                     sha256=hashlib.sha256(native.read_source(start,end-start)).hexdigest())
                                for name,start,end in spans],
                  original_adt_properties=[dict(name=key, fixture=pin(path)) for key,path in properties],
                  native_lifecycle_cases=cases, whole_power_comparison_bytes=0x6578 + 16,
                  whole_hardware_comparison_bytes=0x2718 + 16,
                  region_c_component_offsets=['0x84','0x88','0x8c'],
                  rust_compile_returncode=compiler.returncode,rust_run_returncode=run.returncode,
                  power_complete=False, normal_startup_qualified=False, hardware_actions=[],
                  unbound_providers=['calculated maximum power: G16X chip fuse508374000/voltage/topology result',
                      'native absolute-time domain provider', 'secondary CPU frequency owner19f20',
                      'remaining ARM override controller/tails after89caf20'],
                  fixture_scope='RAM service hooks and chip class28 select the matched source. Maximum/ticks/secondary values and one synthetic raw-property override case are explicit fixtures; no hardware provider qualification. Full ARM override is not executed.',
                  preserved_lifecycle='capture6530..6538 and2888..28b8 before whole6578 clear, then restore',
                  frozen_v6_composed=True, private_binary_or_instruction_bytes_exported=False)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(native_cases=len(cases), rust_compile=compiler.returncode,rust_run=run.returncode,power_complete=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    qualify(parser.parse_args().output)
