#!/usr/bin/env python3
"""Check joined queue ownership/publication; compose frozen native codecs.

This qualification is for the source stage and its new ownership glue. Full
startup, GPU execution and retirement remain separate hardware requirements.
"""
import argparse
import json
from pathlib import Path
import subprocess

from stage_v4 import pin

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def qualify(staging, output):
    receipt = staging / 'stage-receipt.json'
    stage = json.loads(receipt.read_text())
    if stage['schema'] != 'm4rch.gravity-native-t6040-components.stage.v7':
        raise ValueError('Distinct native v7 stage required')
    for row in stage['inputs'] + stage['source_files']:
        if pin(row['path']) != row:
            raise ValueError('Staged input changed: ' + row['path'])
    source = staging / 'source/linux/drivers/gpu/drm/asahi'
    composed = [ROOT / 'docs/evidence' / name for name in [
        '2026-10-11-gravity-native-t6040-queue-v7.json',
        '2026-10-11-gravity-native-t6040-qos-v7.json',
        '2026-10-11-gravity-native-t6040-shared-v7.json',
        '2026-10-11-gravity-native-t6040-ksm-resource-v7.json',
        '2026-10-11-gravity-native-queue-bindings-v7.json',
    ]]
    for path in composed:
        json.loads(path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    test = output / 'joined-queue-owner.rs'
    code = '#![allow(dead_code)]\n'
    for name in ['g16_t6040_queue', 'g16_t6040_qos', 'g16_queue_owner']:
        code += f'#[path = "{source / (name + ".rs")}"] mod {name};\n'
    code += r'''
fn u32_at(b: &[u8], o: usize) -> u32 { u32::from_le_bytes(b[o..o+4].try_into().unwrap()) }
fn u64_at(b: &[u8], o: usize) -> u64 { u64::from_le_bytes(b[o..o+8].try_into().unwrap()) }
fn main() {
    use g16_queue_owner::*;
    let owner = Owner { allocation: 0xfffffc2200000000, process_id: 1234, vm_id: 4, queue_id: 7 };
    let mut pool = LeasePool::new();
    let leases = pool.reserve_initial_owner(owner).unwrap();
    assert_eq!(leases.hardware_buffer_id, 0);
    assert_eq!(leases.work_queue_id, [0,1,2]);
    assert_eq!(pool.reserve_initial_owner(owner).unwrap().work_queue_id, [0,1,2]);
    assert!(pool.reserve_initial_owner(Owner { queue_id: 8, ..owner }).is_none());
    let input = Inputs { process_id: owner.process_id, public_priority: 1,
        pointers: owner.allocation + 0x40, ring: owner.allocation + 0x8000,
        timestamp_list: owner.allocation + 0x4100,
        scheduler: g16_t6040_queue::SchedulerInputs { firmware_slot: owner.allocation+0x4140,
            hardware_buffer_id: leases.hardware_buffer_id, owner_byte_120: 2 },
        capacity: 0x500, producer: 0 };
    let images = input.images().unwrap();
    assert_eq!(images.lane, 2);
    assert_eq!(u64_at(&images.state, 0x10), input.timestamp_list);
    assert_eq!(u32_at(&images.state, 0x48), owner.process_id);
    let config = input.configuration(0x7200008000, leases.work_queue_id[0], 99, [0,0], 0).unwrap();
    assert_eq!(u64_at(&config, 0), 15);
    assert_eq!(u64_at(&config, 8), 0x7200008000);
    assert_eq!(u64_at(&config, 0x10), input.ring);
    assert_eq!(u64_at(&config, 0x4a), input.scheduler.firmware_slot);
    assert_eq!(u32_at(&config, 0x56), leases.hardware_buffer_id);
    assert_eq!(u32_at(&config, 0x5a), owner.process_id);
    assert_eq!(u32_at(&config, 0x66), 0);
    let mut resource = [0xa5; g16_t6040_qos::RESOURCE_BYTES+16];
    g16_t6040_qos::write_initial(&mut resource).unwrap();
    let mut queue = g16_t6040_qos::QueueState::new();
    let mut manager = g16_t6040_qos::ManagerState::new();
    for stage in [1usize,0] {
        queue.write_submission(&mut manager, &mut resource, g16_t6040_qos::SubmissionInputs {
            hardware_buffer_id: leases.hardware_buffer_id, work_queue_id: leases.work_queue_id[stage],
            data_master: stage as u32, scheduler_slot: input.scheduler.firmware_slot,
            weight: initial_weight(input.public_priority).unwrap(), share_ratio: 8192, native_ticks: 24 }).unwrap();
    }
    assert_eq!(u64_at(&resource, 0x800), input.scheduler.firmware_slot);
    assert_eq!(u32_at(&resource, 0xc00), 8192);
    assert_eq!(resource[1], 4); assert_eq!(resource[9], 4);
    assert_eq!(manager.submission_count, 2);
    assert!(resource[g16_t6040_qos::RESOURCE_BYTES..].iter().all(|b| *b==0xa5));
}
'''
    test.write_text(code)
    binary = output / 'joined-queue-owner'
    compile_run = subprocess.run(['rustc', '--edition=2021', '-Dwarnings', str(test), '-o', str(binary)],
                                 capture_output=True, text=True)
    (output / 'compile.stderr').write_text(compile_run.stderr)
    if compile_run.returncode:
        raise ValueError('Joined queue owner compilation failed; inspect compile.stderr')
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    (output / 'run.stderr').write_text(run.stderr)
    if run.returncode:
        raise ValueError('Joined queue ownership check failed; inspect run.stderr')
    runtime = (source / 'g16_runtime.rs').read_text()
    startup = (source / 'g16.rs').read_text()
    assert 'if !native_t6040 { session.submit_barrier(pdev)?; }' in startup
    assert 'if self.transport.native_t6040 || shutdown.is_err()' in startup
    assert 'self.write_native_configuration(queue, stage,' in runtime
    assert 'self.publish_native_qos(queue, &[1, 0])?' in runtime
    report = dict(schema='m4rch.gravity-native-t6040-components.qualification.v7',
        inputs=[pin(receipt), pin(__file__), pin(test)] + stage['inputs'] + stage['source_files'] + [pin(p) for p in composed],
        complete=True, scope='Joined queue ownership/codec continuity and staged source pins; module build is separate',
        composed_without_repeating_native_codec_tests=True,
        joined_queue_owner_compile=compile_run.returncode, joined_queue_owner_run=run.returncode,
        native_startup_omits_donor_boot_work=True, native_shutdown_retains_storage=True,
        normal_startup_enabled=False, region_c_complete=False, bundle_complete=False, power_complete=False,
        hardware_actions=[], triangle_trial_ready=False,
        remaining=['Complete ARM power provider integration and qualification',
                   'Native UAT/root input and firmware-loader reservation integration',
                   'Full Work publication/layout and bounded live launcher',
                   'Execution/completion and qualified GPU OFF retirement proof'])
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['complete','joined_queue_owner_run','triangle_trial_ready']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    qualify(args.staging.resolve(), args.output.resolve())
