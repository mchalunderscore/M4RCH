#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise matched sampler/RTKernel wake and ACK paths in synthetic RAM.

Usage: audit-sampler-kernel-wake.py SAVED_TEXT OUTPUT
Reads one saved regular TEXT file. The output is exclusive numeric evidence;
private instructions and byte dumps are never emitted. There is no hardware
access. Real asynchronous context switching and pointer authentication remain
explicit fixture boundaries, so this cannot authorize recovery or retirement.
"""

import argparse
import hashlib
import json
import stat
import struct
from pathlib import Path

import unicorn as u
import unicorn.arm64_const as c

from firmware_text_contract import qualify


SPANS = [
    (0x3ad94, 0x3b2b4, '7e3abbae985df98425ec52f0249ad997090cf095988219ff6b461339767844b8'),
    (0x3d358, 0x3d3ac, '710fe075c10a48a38f64ffabea81f5f230700b54c9987e4d20705951a84c3d31'),
    (0x44ca0, 0x450f4, 'b9aed0bd10075721fc55ab77c2db7b9a07ed7474a3ea554a36467960456ff977'),
    (0x4518c, 0x45560, 'cfa66592c77a1c6dba2198ee226f352a7eb932caa7ebdc4945d5a0205f3a7c29'),
    (0x458d0, 0x45ba8, '63ded8445eab6aaae88f23d5c4bd7ea147626ff3e5c85ff0b0d982f05de0aa53'),
    (0x4ce00, 0x4d740, '1d8247ac36e3bfa6796ab87568024dc3f3acc080de7d090bef84922ae53cd364'),
]
RETURN = 0x200000
MAX_INSTRUCTIONS = 10000
CURRENT = 0x100000
SAMPLER = 0x101000
RECOVERY = 0x102000
EVENT = 0x18e920
ACK = 0x18e430


def require(condition, message):
    if not condition:
        raise ValueError(message)


class KernelRAM:
    def __init__(self, text):
        self.m = u.Uc(u.UC_ARCH_ARM64, u.UC_MODE_ARM)
        # Execute LSE CAS/LDSET instructions rather than substituting atomics.
        self.m.ctl_set_cpu_model(c.UC_CPU_ARM64_MAX)
        self.m.mem_map(0, 0x200000)
        self.m.mem_write(0, text)
        self.m.mem_map(0x300000, 0x40000)
        self.events, self.steps = [], 0
        self.stop_schedule, self.stop_at = False, None
        self.m.hook_add(u.UC_HOOK_CODE, self.hook)
        self.q(0x82598, CURRENT)
        # Empty native intrusive queues retain a tail pointing at their head.
        for priority in range(64):
            self.q(0x195798 + priority * 16 + 8, 0x195798 + priority * 16)
        self.q(0x82590, 0x82588)
        self.q(0x195f60, 0x104000)
        self.w(0x195f68, 8)
        for index, task in enumerate((CURRENT, SAMPLER, RECOVERY)):
            self.q(task + 0x10, index)
            self.q(0x104000 + index * 8, task)
            self.b(task + 0x28, index + 2)
        self.ready(CURRENT, 2)

    def q(self, address, value):
        self.m.mem_write(address, struct.pack('<Q', value))

    def w(self, address, value):
        self.m.mem_write(address, struct.pack('<I', value))

    def b(self, address, value):
        self.m.mem_write(address, bytes([value]))

    def readq(self, address):
        return struct.unpack('<Q', self.m.mem_read(address, 8))[0]

    def readw(self, address):
        return struct.unpack('<I', self.m.mem_read(address, 4))[0]

    def readb(self, address):
        return self.m.mem_read(address, 1)[0]

    def ready(self, task, priority):
        head = 0x195798 + priority * 16
        tail = self.readq(head + 8)
        self.q(task, 0)
        self.q(task + 8, tail)
        self.q(tail, task)
        self.q(head + 8, task)
        self.q(0x195788, self.readq(0x195788) | (1 << priority))
        self.w(0x195790, self.readw(0x195790) + 1)
        self.b(task + 0x2a, 0)

    def blocked(self, task, wait, state=2):
        tail = self.readq(0x82590)
        self.q(task, 0)
        self.q(task + 8, tail)
        self.q(tail, task)
        self.q(0x82590, task)
        self.q(task + 0x18, wait)
        self.b(task + 0x2a, state)

    def hook(self, machine, pc, _size, _user):
        self.steps += 1
        if pc == 0x44cf4:
            self.events.append(dict(boundary='scheduler/context-switch', pc=hex(pc)))
            if self.stop_schedule:
                machine.emu_stop()
            else:
                machine.reg_write(c.UC_ARM64_REG_PC, machine.reg_read(c.UC_ARM64_REG_LR))
            return
        require(pc != 0x2a8c, 'Native canary trap reached')
        if self.stop_at is not None and pc == self.stop_at:
            machine.emu_stop()
            return
        word = self.readw(pc)
        if word in (0xd503237f, 0xd50323ff):
            machine.reg_write(c.UC_ARM64_REG_PC, pc + 4)
        elif word == 0xd65f0fff:
            machine.reg_write(c.UC_ARM64_REG_PC, machine.reg_read(c.UC_ARM64_REG_LR))

    def call(self, pc, args, stop_at=None, stop_schedule=False, sp=0x330000):
        self.stop_at, self.stop_schedule = stop_at, stop_schedule
        self.steps, self.events = 0, []
        self.m.reg_write(c.UC_ARM64_REG_SP, sp)
        self.m.reg_write(c.UC_ARM64_REG_LR, RETURN)
        for index, value in enumerate(args):
            self.m.reg_write(getattr(c, 'UC_ARM64_REG_X' + str(index)), value)
        self.m.emu_start(pc, RETURN, count=MAX_INSTRUCTIONS)
        require(self.steps < MAX_INSTRUCTIONS, 'Instruction budget exhausted')
        actual_pc = self.m.reg_read(c.UC_ARM64_REG_PC)
        expected_pc = 0x44cf4 if stop_schedule else (stop_at if stop_at else RETURN)
        require(actual_pc == expected_pc, 'Unexpected execution endpoint')
        return dict(instructions=self.steps, return_value=self.m.reg_read(c.UC_ARM64_REG_X0),
                    stop_pc=hex(actual_pc), events=list(self.events))

    def sampler_branch(self):
        for index, value in {19: EVENT, 21: 8, 22: 0x18e000}.items():
            self.m.reg_write(getattr(c, 'UC_ARM64_REG_X' + str(index)), value)
        return self.call(0x3ae1c, [], stop_at=0x3ae50)


def audit(text):
    identity = qualify(text)
    spans = []
    for start, end, expected in SPANS:
        digest = hashlib.sha256(text[start:end]).hexdigest()
        require(digest == expected, f'Matched range differs at {start:x}')
        spans.append(dict(start=hex(start), end_exclusive=hex(end), sha256=digest))
    notify, registration, signals, joined = [], [], [], []
    for priority in (1, 3, 63):
        k = KernelRAM(text)
        k.b(SAMPLER + 0x28, priority)
        k.blocked(SAMPLER, EVENT)
        k.q(EVENT, 8)
        result = k.call(0x4518c, [EVENT])
        require(k.readq(SAMPLER + 0x18) == 0 and k.readb(SAMPLER + 0x2a) == 0 and
                k.readq(0x82588) == 0 and k.readq(0x195798 + priority * 16) == SAMPLER and
                result['return_value'] == 0, 'Matching blocked notification failed')
        notify.append(dict(case='matching-blocked-sampler', priority=priority, result=result,
                           wait_after=0, state_after=0, pending_after=k.readq(EVENT),
                           ready_count=k.readw(0x195790)))
    k = KernelRAM(text)
    k.blocked(SAMPLER, EVENT + 8)
    k.q(EVENT, 8)
    result = k.call(0x4518c, [EVENT])
    require(k.readq(SAMPLER + 0x18) == EVENT + 8 and k.readb(SAMPLER + 0x2a) == 2 and
            result['return_value'] == 0x20001, 'Nonmatching notification changed task')
    notify.append(dict(case='nonmatching-wait-pointer', result=result,
                       task_wait_after=hex(k.readq(SAMPLER + 0x18)), pending_after=k.readq(EVENT)))
    k = KernelRAM(text)
    k.ready(SAMPLER, 3)
    k.q(SAMPLER + 0x18, EVENT)
    result = k.call(0x4518c, [EVENT])
    require(k.readq(SAMPLER + 0x18) == 0 and k.readw(0x195790) == 2 and
            result['return_value'] == 0, 'Ready registered task notification failed')
    notify.append(dict(case='already-ready-registered-sampler', result=result,
                       wait_after=0, ready_count=2))

    for wait in (0, EVENT):
        k = KernelRAM(text)
        k.q(0x82598, SAMPLER)
        k.ready(SAMPLER, 3)
        setter = k.call(0x4528c, [0, 7, wait])
        require(setter['return_value'] == 0 and k.readq(SAMPLER + 0x18) == wait,
                'Native wait-pointer registration failed')
        state = k.call(0x4528c, [0, 6, 2])
        require(state['return_value'] == 0 and k.readb(SAMPLER + 0x2a) == (2 if wait else 0),
                'Native blocking state differs from registration model')
        registration.append(dict(case='state2-with-registered-event' if wait else
                                 'state2-with-cleared-registration', registration=setter,
                                 state_set=state, task_wait=hex(k.readq(SAMPLER + 0x18)),
                                 task_state=k.readb(SAMPLER + 0x2a),
                                 blocked_head=hex(k.readq(0x82588))))

    for initial in (0, 1, 2, 3):
        k = KernelRAM(text)
        k.q(ACK, initial)
        result = k.call(0x458d0, [ACK])
        require(k.readq(ACK) == (1 if initial == 0 else initial), 'Signal low-state behavior differs')
        signals.append(dict(case='signal-no-pointer', initial=initial, result=result,
                            semaphore_after=k.readq(ACK)))
    k = KernelRAM(text)
    signal = k.call(0x458d0, [ACK])
    wait = k.call(0x45a54, [ACK])
    require(k.readq(ACK) == 0 and wait['return_value'] == 0, 'Earlier signal was not retained')
    signals.append(dict(case='signal-before-wait', signal=signal, wait=wait, semaphore_after=0))

    k = KernelRAM(text)
    k.q(0x82598, RECOVERY)
    k.ready(RECOVERY, 4)
    park = k.call(0x45a54, [ACK], stop_schedule=True)
    require(k.readq(ACK) == RECOVERY and k.readb(RECOVERY + 0x2a) == 3,
            'Native waiter did not register its TCB')
    registers = [getattr(c, 'UC_ARM64_REG_X' + str(index)) for index in range(31)]
    registers += [c.UC_ARM64_REG_SP, c.UC_ARM64_REG_NZCV, c.UC_ARM64_REG_PSTATE]
    saved = {register: k.m.reg_read(register) for register in registers}
    frame = k.readq(RECOVERY + 0x18)
    require(k.readq(frame) == ACK, 'Wait frame does not identify ACK semaphore')
    k.q(0x82598, SAMPLER)
    signal = k.call(0x458d0, [ACK], sp=0x31f000)
    require(k.readq(ACK) == 0 and k.readq(RECOVERY + 0x18) == 0 and
            k.readb(RECOVERY + 0x2a) == 0, 'Signal did not clear and ready recovery waiter')
    for register, value in saved.items():
        k.m.reg_write(register, value)
    k.q(0x82598, RECOVERY)
    k.stop_at, k.stop_schedule, k.steps = None, False, 0
    k.m.emu_start(0x45b70, RETURN, count=MAX_INSTRUCTIONS)
    require(k.steps < MAX_INSTRUCTIONS and k.m.reg_read(c.UC_ARM64_REG_PC) == RETURN and
            k.m.reg_read(c.UC_ARM64_REG_X0) == 0, 'Preserved native waiter did not return')
    signals.append(dict(case='wait-before-signal-preserved-context-resume', park=park,
                        wait_frame=hex(frame), wait_frame_event=hex(ACK), signal=signal,
                        resumed_return=0, resumed_instructions=k.steps, semaphore_after=0,
                        wait_after=0, task_state_after=0))

    for hold in (0, 1, 0xffffffff):
        for held in (0, 0x12):
            k = KernelRAM(text)
            k.w(0x18e938, hold)
            k.q(0x18e930, held)
            result = k.sampler_branch()
            require(k.readq(ACK) == 1 and k.readq(0x18e930) == 0 and
                    k.readw(0x18e938) == 0 and k.readq(EVENT) == held,
                    'Joined sampler notify and ACK behavior differs')
            joined.append(dict(case='normal-sampler-ack-real-notify-signal', hold=hold,
                               held_mask=held, result=result, semaphore_after=1,
                               hold_after=0, held_after=0, pending_after=held))
    return dict(schema='m4rch-normal-sampler-joined-rtkernel-ram-v1',
                firmware_identity={key: identity[key] for key in
                                   ('raw_sha256', 'normalized_sha256', 'qualification')},
                matched_ranges=spans, checks=len(notify) + len(registration) + len(signals) + len(joined),
                notify_cases=notify, registration_cases=registration, signal_wait_cases=signals,
                joined_normal_sampler_cases=joined,
                unicorn_cpu='ARM64MAX; native LSE CAS executes',
                actual_privileged_lock_execution=True,
                context_switch_boundary='44cf4 intercepted. Notification and registration cases '
                'resume the caller without switching; the blocking wait case stops, preserves its '
                'fixture CPU context and separately resumes after the actual signal. Real '
                'asynchronous IRQ/context switching is not emulated.',
                authentication_boundary='PACIBSP/AUTIBSP skipped; RETAB uses plain LR. '
                'No pointer authentication is qualified.', other_service_hooks=[],
                native_task_fields=dict(next=0, previous_link=8, registry_id=16,
                                        wait_pointer=24, priority=40, state=42),
                kernel_globals=dict(blocked_head='0x82588', blocked_tail='0x82590',
                                    current_task='0x82598', ready_bitmap='0x195788',
                                    ready_count='0x195790', ready_buckets='0x195798',
                                    task_registry_pointer='0x195f60', task_registry_capacity='0x195f68'),
                qualification='Matched instructions execute in synthetic RAM at explicit '
                'scheduling/authentication boundaries. This is not a live task, cache-coherency, '
                'GPU recovery, rendering or DMA-retirement proof.', hardware_actions=False,
                recovery_reuse_verified=False, dma_retirement_verified=False, rendering_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('text', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        require(stat.S_ISREG(args.text.stat().st_mode), 'Input must be a saved regular TEXT file')
        require(not args.output.exists(), 'Output already exists')
        report = audit(args.text.read_bytes())
        source = Path(__file__).resolve()
        report.update(input_path=str(args.text), output_path=str(args.output),
                      harness=dict(path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
                      firmware_contract_sha256=hashlib.sha256(
                          source.with_name('firmware_text_contract.py').read_bytes()).hexdigest())
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(f'Passed {report["checks"]} offline cases; wrote {args.output}')
    except (OSError, ValueError, u.UcError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
