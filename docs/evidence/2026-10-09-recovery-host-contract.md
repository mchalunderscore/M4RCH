# Native host recovery contract and idle Linux trial

This is a read-only, private implementation-derived audit of AGX 353.14 from
Apple 25G83, followed by review of the new bounded idle recovery implementation.
The private binary SHA256 is
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
Addresses and field offsets below are hexadecimal unless stated otherwise.
No hardware result is claimed here. Recovery, control consumption, DMA retirement
and GPU execution are separate observations.

The existing cold structural detach evidence remains valid only for its no-job
scope. The failed START-only, START + INIT and power-held INIT wake attempts are not
new candidates. The proposed trial keeps ASC and the same GFX allocation lifetime
alive across two application recovery cycles. The later resident interface
keeps the allocation and power lifetime alive after this check.

`AGXArmFirmware::stopFirmwareForRecoveryInspection` at 89ca56c sends
`0x0086000000000000 | (token & ((1<<44)-1))`. The token is the 64-bit host recovery
generation at accelerator+688; firmware-host+298 points to that accelerator.
The send uses the absent provider at firmware-host+1668, virtual slot 8a8, with
its second argument true. The host binary alone does not establish the endpoint.
Independent matched firmware analysis binds the handler to EP33 and requires the
packet token to equal status_b+48f0 before accepting the request. That makes the
current device counter a qualified starting token for the idle Linux trial;
blindly sending a fixed 0 is unnecessary.

The host counter getter reads u64 at status_b+48f0. The phase predicates read u32 at
status_b+4900, with 1 for pre-recovery and 3 for post-recovery. The stopped-for-host
predicate reads u32 at status_b+4910 and tests nonzero. The existing firmware parser
binding from root+b0 to DATA18ee70 identifies this object as the owned graph's
status_b, rather than an unrelated power object.

The ASC vtable at 7ea8668 has address point +16. Image-specific decoding uses
`fffffe0007004000 + (encoded_pointer & 0xffffffff)`. Eleven relevant slots were
checked against the matched private binary, including both resume methods:

| Slot | Native target | Meaning |
| --- | --- | --- |
| 1a8 | 89ca56c | stopFirmwareForRecoveryInspection |
| 1d8 | 89ca40c | getNumDeviceRecoveries |
| 1e0 | 89ca3ec | isFirmwareStoppedForHostRecovery |
| 200 | 89ca3a0 | updateLastSubmittedHWTimestamp |
| 210 | 89c9d9c | processFirmwareTACommandsRecovery |
| 460 | 89d1650 | resetFirmwareForRecovery, no-op |
| 468 | 89c28b8 | resumeFirmwarePreRecovery |
| 470 | 89c2828 | resumeFirmwarePostRecovery |
| 478 | 89c2808 | isFirmwareStoppedForRecovery |
| 480 | 89c27e8 | isFirmwareStoppedForPreRecovery |
| 488 | 89c27c8 | isFirmwareStoppedForPostRecovery |

The pre-resume helper checks phase 1, executes a dmb ish, writes 2, then executes
another dmb ish. The post-resume helper similarly requires 3 and writes 0. Neither
helper detaches an allocation, changes a translation, stops RTKit or establishes
that a GPU context can be freed.

`AGXAccelerator::restartWorkQueue` at 8963f74 provides the enclosing host sequence.
It calls stop inspection at 8963ffc/4010. Stop inspection drains firmware rings
while waiting for device_counter==host_token+1, and requires the host-stop
predicate. The enclosing host routine performs inspection/reporting, updates
submitted timestamp bookkeeping for 128 host queue slots, resets host fence state,
and increments accelerator+688 at 8966534..653c. It then calls pre-resume at
896663c/664c and waits for post-phase 3 at 8966680..66c8. That native post wait is
unbounded; the Linux trial deliberately adds a 5-second limit.

One pre-resume virtual call initially resembling an unexplained restart action
is the performance sampler at accelerator+f598, slot 190. The base, Gen11 and Gen15
sampler vtables resolve it to handleGPURestart; Gen15 uses 8a034dc. This returns
immediately when the sampler has no profiling client at +20. The submitted
timestamp helper writes 16-byte entries through firmware-host+2e8, rather than
performing an MMIO reset. These findings support an idle-only trial that has no
matching submitted host queues, fences or profiling client to reconstruct.
They do not justify skipping those operations when real work is active.

At post-phase 3, the native caller invokes processFirmwareTACommandsRecovery with
status_b+40b8 at 89666e4/66f8. The function scans 256 records of 8 bytes, ending at
status_b+48b8. It acts on records for which `(flags & 9) == 9`, obtains the stamp
index as `(flags >> 4) & 0x7f`, and operates on retained host work/resource
objects. The enclosing routine also processes/restarts client work before
calling post-resume at 8966bec/6bfc. The Linux idle trial checks that every active
TA-record predicate is false and aborts on any active record instead of
inventing client recovery behavior.

Review of `recovery-cycle.h` supports the following narrow experiment: before
publication, suppress all 12 work producers, retain the joined context and every
owned mapping, and stage two additional operand-free control opcode 0x16 records.
Control opcode 0x16 is decimal 22 and is distinct from work opcode 0x10 (decimal 16),
which is the fragment hold-release command. After the initial controls have
been consumed, require phase 0, request state 0, request flag 0, empty work
cursors and no active TA recovery records. Send 86 using the current counter; require phase 1, counter+1 and host-stop 1
before writing 2. Require phase 3 with the same counter and host-stop 1 before
writing 0. Expose one previously staged fresh control record, send 84 on EP33,
and require both firmware read/prefetch indices to advance to the new producer.
Also require the request object state at RECOVERY_REQUEST and flag at
RECOVERY_REQUEST+4 both to return to 0.
Only then count the cycle as complete and attempt the second cycle. The shared
host-stop flag at status_b+4910 remains 1 in the reviewed firmware path even
after phase 0; it must not be mistaken for a flag that clears on completion.

The host-written phase 0 alone is not a liveness observation. Fresh control
consumption after each cycle is the necessary additional evidence of firmware
reuse. It remains a control-path result, not rendering or safe retirement.
The implementation preserves all firmware-owned cursors; it neither zeros them
after recovery nor overwrites already published ring entries.

The control read, prefetch and producer values occupy offsets 0/8/16 of one
cursor allocation and can share a CPU cache line. Before its producer write,
the helper requires all three indices to equal the previous producer, invalidates
the affected line, modifies only the host producer, then cleans/barriers before
notification. Firmware phase writes use the same refresh/store/clean discipline
while firmware is waiting for that acknowledgement. The runner disables its
concurrent sysfs snapshot observer to avoid invalidating a line containing an
unpublished host write. The trial must not be inspected through another
concurrent raw snapshot reader while these host writes are in progress.

On any failed prerequisite, unexpected record or timed-out phase, the
implementation stops issuing additional recovery packets and fresh controls.
It logs the final counter/phase/request/cursors and completed cycle count.
The first two live candidates then attempted QUIESCED/SLEEP/core-stop; neither
completed a recovery cycle. The next diagnostic candidate keeps ASC/GFX and
every allocation held on failure when resident mode was requested, seals the
session, and permits only sample/stop commands. It does not retry recovery.
The joined release_on_shutdown/warm_restart prohibition and root_release
lifetime guards remain in force. Stopping ASC is not a recovery success.

The current typed sysfs interface serializes sample/control/recover/submit/stop
with snapshots under one mutex. Only two completed initial cycles, each with
fresh control consumption, admit normal resident operation. It permits one
immutable prepared triangle publication and prohibits further publication or
recovery after that submission. Neither backing reuse nor joined context
retirement is implemented. The userspace runner binds the loaded module's ELF
build note, kernel, boot, candidate sources and original attempt, persists
command intent before issuing it, and permanently seals an interrupted or
failed operation before allowing further samples. A failed recovery retains
diagnostic access but never qualifies submission.

Native inspection drains DMA-backed firmware rings as well as receiving mailbox
notifications. The current helper logs/drains only the mailbox. Independent
firmware review resolves the direct forced-host path: its nonzero host request
selects 61f4..6230, clears the recovery information records, and skips directly
to 63dc without publishing the recovery event. The spontaneous path instead
builds a 72-byte event in the main+1c0/1c8 ring and sends an EP32 class42
notification at 63c0..63cc. This supports two idle forced-host cycles without
implementing that direct event drain. It does not qualify handling spontaneous
recovery or arbitrary task-generated events.

Numeric range hashes and the 11 ASC/3 sampler slot checks are saved locally in
`/tmp/gpu-native-recovery-host-audit.json`. Private binary, full TEXT and full
disassembly are excluded from this report.
