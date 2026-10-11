#!/usr/bin/env python3
"""Join actual native priority execution to the new full queue component offline."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_ARM64_REG_PC, UC_ARM64_REG_X1,
                                UC_ARM64_REG_X2, UC_ARM64_REG_X3,
                                UC_ARM64_REG_X4, UC_ARM64_REG_X30)

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]
AGX = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
AGX_SHA = '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
START, END = 0xfffffe00089bff08, 0xfffffe00089c004c


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def qualify(output):
    output.mkdir(parents=True, exist_ok=False)
    raw = AGX.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AGX_SHA
    cursor = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        command, size = struct.unpack_from('<II', raw, cursor)
        if command == 25:
            vm, _, offset, extent = struct.unpack_from('<QQQQ', raw, cursor + 24)
            if vm <= START and END <= vm + extent:
                code = raw[offset + START - vm:offset + END - vm]
        cursor += size
    assert len(code) == END - START
    machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    machine.mem_map(0x100000, 4096)
    machine.mem_write(0x100000, code)
    machine.mem_map(0x200000, 4096)
    model = ROOT / 'experiments/t6040-gpu/private_channel_reset.py'
    spec = importlib.util.spec_from_file_location('frozen_reset_model', model)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence = ROOT / 'docs/evidence/2026-10-09-native-scheduler-state.json'
    # Frozen reset/scheduler/native-pointer proofs are composed, not rerun.
    reset_evidence = ROOT / 'docs/evidence/2026-10-08-private-channel-reset.json'
    pointer_evidence = ROOT / 'docs/evidence/2026-10-08-private-queue-pointer.json'
    for path in (evidence, reset_evidence, pointer_evidence):
        assert path.is_file()
    contexts = [0, 1, 2, 3, 4, 5, 6, 0x7fffffff, 0x80000000, 0xffffffff]
    qos_values = [0, 1, 2, 3, 4, 5, 0x80000000, 0xffffffff]
    cases, tests = [], []
    for index, (context, qos) in enumerate((c, q) for c in contexts for q in qos_values):
        capacity = [2, 3, 16, 256, 65536][index % 5]
        pid = (0x12340000 + index) & 0xffffffff
        sub = (index * 0x10101 + 19) & 0xffffffff
        pointers = [0xfffffc2000200000 + index * 0x1000 + off for off in (0x100, 0x400, 0x300)]
        channel_context = 0xfffffc2000300000 + index * 0x40
        state, queue = module.reset_prefix(bytes([0xa5] * 0x80), pointers,
                                          capacity, pid, channel_context)
        machine.mem_write(0x200000, state + bytes([0xa5] * 16))
        for reg, value in ((UC_ARM64_REG_X1, 0x200000), (UC_ARM64_REG_X2, context),
                           (UC_ARM64_REG_X3, sub), (UC_ARM64_REG_X4, qos),
                           (UC_ARM64_REG_X30, 0x100800)):
            machine.reg_write(reg, value)
        machine.emu_start(0x100000, 0x100800, count=200)
        assert machine.reg_read(UC_ARM64_REG_PC) == 0x100800
        expected = bytes(machine.mem_read(0x200000, 0xd0))
        assert expected[0xc0:] == bytes([0xa5] * 16)
        state_file, queue_file = output / f'state-{index}.bin', output / f'queue-{index}.bin'
        state_file.write_bytes(expected)
        queue_file.write_bytes(queue)
        lane = struct.unpack_from('<I', expected, 0x28)[0]
        last = struct.unpack_from('<I', expected, 0x40)[0]
        scheduler = bytearray([0xa5] * 0x50)
        scheduler[:0x38] = bytes(0x38)
        struct.pack_into('<H', scheduler, 0, 0xffff)
        scheduler[5], scheduler[0x26], scheduler[0x33] = 1, index, 0xff
        scheduler_file = output / f'scheduler-{index}.bin'
        scheduler_file.write_bytes(scheduler)
        config = bytearray([0xa5] * 0x70)
        slot = 0xfffffc2000400000 + index * 0x40
        # Explicit fixture-owned IDs include zero and differ from native init's sentinel.
        buffer_id = index
        struct.pack_into('<Q', config, 0x4a, slot)
        struct.pack_into('<III', config, 0x56, buffer_id, pid, last)
        config_file = output / f'config-{index}.bin'
        config_file.write_bytes(config)
        tests.append(f'''{{
let priority=q::PriorityInputs{{context_priority:{context},requested_subpriority:{sub},qos_level:{qos}}};
let input=q::ChannelInputs{{state_pointer_00:{pointers[0]},state_pointer_08:{pointers[1]},state_pointer_10:{pointers[2]},channel_context:{channel_context},process_id:{pid},capacity:{capacity},priority}};
let mut state=[0xa5;0xd0];let mut pointers=[0xa5;0x80];
assert!(input.write_initial(&mut state,&mut pointers).is_some());
assert_eq!(&state,include_bytes!({json.dumps(str(state_file))}));
assert_eq!(&pointers,include_bytes!({json.dumps(str(queue_file))}));
assert_eq!(priority.firmware_lane(),{lane});
let scheduler=q::SchedulerInputs{{firmware_slot:{slot},hardware_buffer_id:{buffer_id},owner_byte_120:{index}}};
let mut slot_bytes=[0xa5;0x50];assert!(scheduler.write_initial(&mut slot_bytes).is_some());
assert_eq!(&slot_bytes,include_bytes!({json.dumps(str(scheduler_file))}));
let mut config=[0xa5;0x70];assert!(scheduler.write_config_companions(&state,&mut config).is_some());
assert_eq!(&config,include_bytes!({json.dumps(str(config_file))}));
}}''')
        cases.append(dict(context_priority=context, qos_level=qos, requested_subpriority=sub,
                          capacity=capacity, process_id=pid, native_firmware_lane=lane,
                          native_getter_subpriority=last, fixture_owned_hardware_buffer_id=buffer_id,
                          expected_state=pin(state_file), expected_queue=pin(queue_file),
                          expected_scheduler=pin(scheduler_file), expected_config=pin(config_file)))
    component = KIT / 'g16_t6040_queue_v7.rs'
    source = output / 'queue-tests.rs'
    source.write_text(f'''#![allow(dead_code)]
#[path={json.dumps(str(component))}] mod q;
fn main(){{
assert!(!q::QUEUE_COMPLETE);
{''.join(tests)}
// Full queue and corrupt geometry return no publication plan; wrap returns offset then zero.
let mut pointers=[0xa5;0x80];
pointers[0x60..0x64].copy_from_slice(&3u32.to_le_bytes());
pointers[0x40..0x44].copy_from_slice(&2u32.to_le_bytes());
pointers[..4].copy_from_slice(&1u32.to_le_bytes());
assert_eq!(q::pointer_publication(&pointers,24),Some(q::PointerPublication{{ring_byte_offset:16,next_write:0}}));
pointers[..4].copy_from_slice(&0u32.to_le_bytes());
assert!(q::pointer_publication(&pointers,24).is_none());
pointers[..4].copy_from_slice(&3u32.to_le_bytes());
assert!(q::pointer_publication(&pointers,24).is_none());
pointers[..4].copy_from_slice(&1u32.to_le_bytes());
assert!(q::pointer_publication(&pointers,16).is_none());
let priority=q::PriorityInputs{{context_priority:0,requested_subpriority:17,qos_level:0}};
for capacity in [0,1,65537,u32::MAX] {{
let input=q::ChannelInputs{{state_pointer_00:1,state_pointer_08:2,state_pointer_10:3,channel_context:4,process_id:9,capacity,priority}};
let mut state=[0xa5;0xd0];let mut p=[0xa5;0x80];
assert!(input.write_initial(&mut state,&mut p).is_none());assert_eq!(state,[0xa5;0xd0]);assert_eq!(p,[0xa5;0x80]);
}}
let input=q::ChannelInputs{{state_pointer_00:1,state_pointer_08:2,state_pointer_10:3,channel_context:4,process_id:9,capacity:3,priority}};
let mut state=[0xa5;0xbf];let mut p=[0xa5;0x80];
assert!(input.write_initial(&mut state,&mut p).is_none());assert_eq!(state,[0xa5;0xbf]);assert_eq!(p,[0xa5;0x80]);
let mut state=[0xa5;0xd0];let mut p=[0xa5;0x63];
assert!(input.write_initial(&mut state,&mut p).is_none());assert_eq!(state,[0xa5;0xd0]);assert_eq!(p,[0xa5;0x63]);
println!("80 joined native priority/reset/scheduler/config images and 10 boundary cases passed");
}}
''')
    commands = []
    for command in (['rustc', '--edition=2021', '-D', 'warnings', str(source), '-o', str(output / 'queue-tests')],
                    [str(output / 'queue-tests')]):
        result = subprocess.run(command, capture_output=True, text=True)
        commands.append(dict(command=command, returncode=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('New queue qualification failed; terminal result preserved')
    report = dict(schema='m4rch.gravity-native-t6040-queue-qualification.v7', passed=True,
                  component_source=pin(component), actual_priority_range=[hex(START), hex(END)],
                  private_binary_sha256=AGX_SHA, priority_slice_sha256=hashlib.sha256(code).hexdigest(),
                  joined_cases=cases, joined_case_count=len(cases), boundary_case_count=10,
                  composition=dict(frozen_reset_prefix_cases_not_repeated=256,
                                   frozen_pointer_publication_cases_not_repeated=554,
                                   frozen_scheduler_allocator_cases_not_repeated=True),
                  inputs=[pin(p) for p in [Path(__file__), component, AGX, model, evidence,
                                          reset_evidence, pointer_evidence, source, output / 'commands.json']],
                  native_policy_transfer=False, queue_complete=False, hardware_actions=[],
                  qualification='Actual matched native priority instructions execute in sequential emulated RAM. The compiled Rust component produces identical full reset-plus-priority images, preserves all specified untouched queue/slot bytes, and joins config PID/subpriority to those state bytes. Process, policy, QoS, mappings and scheduler associations are explicit fixtures. Pointer plans do not publish caches/DMA or MMIO; no GPU execution, Work construction or retirement is proved.')
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, qualification=pin(output / 'qualification.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    qualify(args.output.resolve())
