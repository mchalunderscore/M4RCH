#!/usr/bin/env python3
"""Decode closed v13 teardown evidence; never opens hardware or sysfs."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BOOT = '29800a86-c89b-4072-b121-c40e264982dc'
SESSION = ROOT / 'out/gfx-native-full-power-trial-v24/candidate-v13/asc-graph-init' / ('boot-' + BOOT)

def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def main():
    cycle = json.loads((SESSION / 'cycle-attempt.json').read_text())
    rows = cycle['raw_cycle_rows']
    physical = [r for r in rows['gfx-postdraw-native-cycle-physical'] if r['phase'] == 'after-off']
    assert len(physical) == 101
    assert {r['word'] for r in physical} == {0x0f000b00}
    assert all(r['result'] == 0 and r['valid'] == 1 and r['domain_on'] == 0 for r in physical)
    word = physical[0]['word']
    strict_mask = physical[0]['state_mask']
    assert strict_mask == 0x90001cff and word & strict_mask == 0x800
    before = [r for r in rows['gfx-postdraw-native-cycle-physical'] if r['phase'] == 'before-off']
    assert len(before) == 1 and before[0]['word'] == 0x1f0003ff
    off = rows['gfx-postdraw-native-cycle-off'][-1]
    assert off['pm_put_result'] == 0 and off['accounting_ok'] == 1 and off['coordinate_off_complete'] == 1
    assert off['cpu_stopped'] == 1 and off['idle_observed'] == 1 and off['ack_observed'] == 0
    policy = [r for r in rows['gfx-native-idle-policy-state'] if r['phase'] == 'processing-observed'][0]
    assert policy['policy_command_processed'] == 1 and policy['firmware_gpu_off_observed'] == 0
    native = json.loads((ROOT / 'docs/evidence/2026-10-09-gfx-native-power-side-effects.json').read_text())
    # Reverify the native function bytes, rather than deriving confidence from
    # an old green report. Raw bytes/disassembly remain in ignored local output.
    cache = (ROOT / 'out/private-apple/kernelcache.decoded').read_bytes()
    selected = []
    for r in native['native_ranges']:
        if r['name'] not in ('ApplePMGR writeReg32', 'ApplePMGR _setPSLevel', 'AppleT6041PMGR isPsReg'):
            continue
        raw = cache[r['file_offset']:r['file_offset'] + r['bytes']]
        assert hashlib.sha256(raw).hexdigest() == r['sha256']
        selected.append(r)
    assert len(selected) == 3
    disassembly = ROOT / 'out/private-apple/agx-disassembly.txt'
    instructions = {}
    for line in disassembly.read_text().splitlines():
        match = re.match(r'^([0-9a-f]{16}):\s*((?:[0-9a-f]{2} ){3}[0-9a-f]{2})\s', line)
        if match:
            instructions[int(match[1], 16)] = bytes.fromhex(match[2])
    recovery_ranges = []
    for name, start, end in (
        ('blockForRingEmpty send and cursor wait', 0xfffffe00089c8a68, 0xfffffe00089c8b34),
        ('stopFirmwareForRecoveryInspection request bounded drain and result', 0xfffffe00089ca56c, 0xfffffe00089ca784),
        ('getNumDeviceRecoveries and stoppedForHostRecovery getters', 0xfffffe00089ca3ec, 0xfffffe00089ca41c),
    ):
        raw = b''.join(instructions[address] for address in range(start, end, 4))
        recovery_ranges.append(dict(name=name, start=hex(start), end_exclusive=hex(end),
                                    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                    provenance='Instruction bytes from pinned local AGX disassembly; numeric evidence only'))
    report = dict(
        schema='m4rch.v24-v13-saved-teardown-provider-comparison.v1', boot_id=BOOT,
        hardware_actions=[], raw_disassembly_exported=False,
        inputs=[pin(SESSION / n) for n in ('cycle-attempt.json', 'cycle-operation-delta.log')]
            + [pin(ROOT / 'experiments/t6040-gpu/gfx-native-reset-capability/pmgr-pwrstate.c'),
               pin(Path(__file__).resolve()), pin(ROOT / 'docs/evidence/2026-10-09-gfx-native-power-side-effects.json'),
               pin(disassembly)],
        observed_off=dict(samples=len(physical), word=word, word_hex=hex(word),
            strict_mask=strict_mask, blocking_bits=word & strict_mask,
            actual=(word >> 4) & 15, target=word & 15, auto_enable=(word >> 28) & 1,
            auto_state=(word >> 24) & 15, busy=(word >> 11) & 1,
            historical_clock_gated=(word >> 9) & 1, historical_power_gated=(word >> 8) & 1,
            reset31=(word >> 31) & 1, ps_reset12=(word >> 12) & 1, device_disable10=(word >> 10) & 1,
            physical_off_strict=False, provider_actual_target_off=True,
            normal_pm_put_succeeded=True, paired_accounting=True,
            firmware_policy_processed=True, firmware_gpu_off=False,
            management_ack=False, nmi_fallback=True, cpu_stop_observed=True),
        native_ranges_reverified=selected,
        additional_native_recovery_ranges=recovery_ranges,
        additional_native_recovery=dict(
            ring_empty_packet=0x0085000000000000, ring_empty_send_w2=0,
            ring_cursor_pointer_owner_offset=0x16c0, ring_read_offset=0, ring_write_offset=0x10,
            recovery_packet_base=0x0086000000000000, recovery_payload_bits=44, recovery_send_w2=1,
            generation_owner='Accelerator pointer firmware+0x298, accelerator+0x688',
            inspected_branch='RestartInfo byte+8 equals1; optional object+210 vtable+d8 check',
            awaited_generation='Firmware vtable+1d8 result equals supplied generation+1',
            likely_getter='getNumDeviceRecoveries89ca40c returns u64 status_b+48f0; actual vtable1d8 bound by native-recovery-pipeline-v10 report',
            stopped_flag_getter='isFirmwareStoppedForHostRecovery89ca3ec returns status_b+4910 u32 nonzero; actual vtable1e0 resolved to89ca3ec',
            bounded_wait='Acceleration property+284 times1000 plus1;1ms sleep and drainFirmwareRings(false)',
            implemented_in_v13=False, packet_ready_for_live_use=False,
            missing_binding='Identify caller restart reason, actual firmware generation getter and shared memory placement, transport w2 role, complete success/fallback tail before integration'),
        source_bindings=dict(
            gravity_off='apple_pmgr_ps_power_off calls apple_pmgr_ps_set(0,false); poll verifies ACTUAL0 only',
            gravity_on='apple_pmgr_ps_power_on calls apple_pmgr_ps_set(15,true); poll verifies ACTUAL15 then sets AUTO_ENABLE',
            gravity_busy='Generic provider does not require BUSY11 clear for either transition',
            apple_busy='writeReg32 object+b0 bit0/isPsReg policy waits BUSY11 clear before RESET31-set, and after writes whose TARGET<15',
            apple_target15='983cffc..983d008 branches around the BUSY postwrite wait when TARGET15',
            apple_caveat='Live Apple object+b0 policy is unobserved; helper budget0x2ee00 is not assumed to be Linux microseconds',
            exact_off_blocker='Only BUSY11, not AUTO_STATE f or historical bits8/9, blocks our mask'),
        integrated_changes=[
            'Keep strict OFF/retirement proof distinct from provider transition completion and retained-owner restart admission.',
            'Join native pending-work/cancel/completion and idle policy ownership before202; v13 policy processing is proved but GPU-off/ACK are absent.',
            'Resolve and integrate native85 ring drain /86 recovery inspection generation request where the Apple caller selects it; do not fabricate its generation or blindly send the packet.',
            'Use one bounded202 request, service notifications while waiting, then native NMI fallback only on clean timeout; CPU-stop and Fender disable preserve ordering.',
            'Use paired coordinateOFF and one normal PM put; preserve numeric physical BUSY/actual/target and both success classes.',
            'For a future integrated candidate, normal provider ON may be attempted with quarantined old mappings despite BUSY-off, then freshly verify actual/target15 and reset/disable constraints before MMIO.',
            'Pair coordinateON with new RTBuddy boot/DATA and AP handshake; use fresh protocol and application resources without replaying the previous queued draw.',
            'Release or reuse old resources only after separate completion/reset coverage proves retirement; restart success alone never grants release permission.'
        ],
        current_boot_restart_admitted=False,
        gravity_lifecycle_implementation=dict(
            module='experiments/t6040-gpu/desktop-integration/t6040-native-boot/g16_t6040_lifecycle_v10.rs',
            wiring='experiments/t6040-gpu/desktop-integration/t6040-native-boot/wire_native_lifecycle_v10.py',
            composition_applied_to='out/gpu-gravity-normal-native-render-caller-v9-v4',
            actual_hooks=['Bootstrap lifecycle owner', 'Submit receipt admission', 'Poison quarantine',
                          'Native restart caller', 'Drop avoids donor SLEEP', 'Drop retains native PM pools and PM client owners'],
            complete=False, kernel_compiled=False,
            unresolved='Integrated adapters implemented; full build and recovery job record attribution in composition; hardware restart/render/retirement not proven'),
        current_boot_reason='Loaded v24 transforms the command to boundedOFF only; its intent is already consumed. No live patch, unload, or replay.',
        unresolved=['Cause of GPU remaining active with a queued uncompleted draw',
                    'Cause of missing202 ACK and persistent BUSY after NMI/CPUstop',
                    'Fresh application/DATA lifecycle after retained-owner ON',
                    'Whole GPU DMA retirement, rendered triangle, repeatable restart'],
        counterexample='Earlier no-work boot16868560 obtained202 ACK and word0x0f000300 with BUSY0; source does not prove causality of each changed phase.')
    destination = ROOT / 'docs/evidence/2026-10-11-native-v13-teardown-provider-comparison.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(destination)

if __name__ == '__main__':
    main()
