# T6040 idle trial

The default-off patch permits the existing Apple deep-idle sequence only on
J614s/T6040 with `cpuidle_apple.experimental_t6040_idle=1`. The normal entry keeps
that parameter absent. Early/fallback `idle=nop arm64.nowfxt` stays in both.
This is experimental reuse of the existing sequence, not proven M4 retention.

Trial kernel/initramfs live separately under `/boot/idle-trial`. Select by editing
`set default` in `/boot/grub/grub.cfg`; GRUB keyboard input is unavailable here.
After a hang, force off, boot macOS, and restore `m4rch-normal` in the same config
at `/Volumes/ARCHBOOT/grub/grub.cfg`. Never overwrite normal boot artifacts.

`collect.py NEW_OUTPUT_DIR` requires the adjacent generated `build.json`, the
exact kernel and active driver parameter. It records idle-state counters and
brief pinned user arithmetic/timer-wake tasks. It changes no idle policy,
registers, governor or fan settings and rejects the fixed-counter probe module.
CPU PD counters matter: the shallow state's WFI label still uses the nop fallback.
Successful completion is a smoke test, not full SIMD/debug or boost qualification.
No hotplug, suspend-to-idle or benchmark is part of the first trial.

## Single-CPU fault trace

The first opt-in trial faulted on CPU4 before userspace with an undefined
instruction; the photo lacked PC/backtrace. The follow-up adds a separate,
default-off trace parameter, `cpuidle_apple.experimental_t6040_idle_trace=1`.
Together with the opt-in it permits one attempt on CPU4 only. Other entries
use nop. Checkpoints bracket CPU_PM_ENTER, the original Apple register accesses,
WFI and cleanup. A saved-frame fault print precedes the normal dump. No new
hardware register addresses or masks are introduced.

The generated `idle-trace-01` kit includes linked instruction addresses,
System.map, receipts and a guarded rollback script. Only its GRUB entry adds
`nokaslr`, allowing direct PC mapping. Record boot video; early resets may still
prevent full capture. If Linux starts, `collect-trace.py NEW_OUTPUT_DIR` reads
the journal and counters without exercising a workload. Tracing changes timing
and is not a retention fix or performance experiment.

## Saved WFI alternative

The native trace identified an undefined-instruction fault on the first Apple
control-register MSR; WFI was not reached. A separate default-off
`experimental_t6040_idle_wfi_only` mode therefore skips all Apple control-register
accesses, saves x0–x30 on an aligned stack, executes one DSB/WFI, and restores
the GPR frame before returning into C. Existing CPU_PM notifiers remain.
It requires both idle/trace opt-ins and the J614s/T6040 board. CPU4 gets one
attempt; others and later calls retain nop. It assumes PC/SP and sufficient
system state survive, and is not a full retention implementation.

The `idle-saved-01` handover/receipt describes selection and rollback.
`collect-saved.py` checks all three parameters and reads the full journal and
counters without workloads. The candidate shares normal's verified initramfs;
its kernel stays separate. A successful one-shot return is a reason to extend
coverage, not evidence of sustained idle reliability or a performance gain.

## Bounded runtime batches

The first native saved-WFI attempt returned through CPU_PM_EXIT on CPU4.
The batch candidate retains that assembly and introduces root-only runtime
controls: target CPU4/5, an absolute budget0..64 per selected core, and atomic
attempt/completion snapshots. Default is CPU4 with one attempt. Budget0 returns
to nop. Switching cores requires budget0 and no incomplete attempt; counters
cannot reset. No other core can enter this path.

`batch/run-batches.py` verifies the exact generated kit/build/board, then arms
CPU4 budgets2/32 and CPU5 budgets1/32. A pinned assembly worker checks user GPR,
SIMD and FPCR/FPSR state across syscall sleeps. Each phase captures counters,
progress and journals; a failure stops later phases, and exit disables WFI.
Use the generated HANDOVER for native commands and rollback. The successful
one-shot image and normal kernel are retained separately. Continuous idle,
all-core/debug-state coverage, wake latency and power gains remain future work.

## Sequential all-core candidate

The CPU4/5 batches passed 32 wakes each and 512 user state checks. The all-core
patch retains the saved assembly, starts with budget0, and accepts one online
CPU0..11 at a time. `batch/run-allcores.py` verifies the generated kit and runs
budgets1/4 per core, E cores first: 48 wakes and 768 user sleeps in one boot.
Guards stop on errors; exit disables WFI. This candidate is not yet native-tested.
Use HANDOVER for the exact build, commands and retained normal rollback.

## Continuous all-core trial

The owner chose sustained/concurrent idle directly after the CPU4/5 result.
`experimental-t6040-wfi-continuous.patch` adds a default-off boot/runtime switch,
per-core counters and quiet repeated entry through the same saved assembly.
The generated trial enables it at boot. Disabling returns subsequent entries to
nop because the bounded budget stays zero. Normal boot is retained separately.
`collect-continuous.py` captures states/counters, sensors and the kernel journal;
HANDOVER supplies exact commands and rollback. Power savings are unmeasured.

## Shallow saved WFI

`shallow-wfi.patch` keeps the saved sequence and registers one shallow state
only for the continuous opt-in. The inherited10ms target previously left short
idle gaps spinning; the candidate sets1us target residency and10us provisional
exit latency. Those are experimental settings, not measured tuning. Disabled
continuous mode returns to nop. Working continuous and normal boot remain as
rollback entries. `power/` compares enabled/disabled behavior within one boot.
