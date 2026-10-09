## GPUC003 platform trial

Current graph has 21 object pages and 36 device leaves (57 VAs). Ten device
pages writable: previous eight SGX leaves and exact slot0/11 platform mappings.
The native trial passed both platform consumers and stopped on a primary SGX
slot17 write-permission fault at physical2880040a0. See
`docs/evidence/2026-10-07-gpuc003-platform-result.json`. Later USB failure was
reported; pre-trial baseline lacked USB drivers too. Check USB BEFORE further
GPU activity on the next boot. Older sections below are historical.

## Current batch (2026-10-07)

The current sparse graph maps 21 object pages and 34 device leaves (55 VAs)
with two owned page tables. Eight qualified pages are writable; see
`graph-map.h` and `graph-register-batch.py` for the exact whitelist.
The cold native batch passed MCW programming and now faults on missing
platform slot 0 GPCAICSWInt. Slot 11 telemetry configuration is used next.
Neither mapping has been enabled speculatively. Six serializer tests passed.
See `docs/evidence/2026-10-07-gpu-write-batch-result.json` for exact readbacks,
permissions, crash decode and the focused platform-resource investigation.
The following sections describe earlier trials and are historical.

# Experimental structural GPU initialization

Current GPUC002 helper publishes21 structural object pages and32 device pages.
Slots33 Bumper and35 DFenderMGPUCfg use matching25G83 static mappings, qualified
by five exact native reads. Only their two16KiB device pages are writable;
other device leaves remain read-only. Hardware mask input is0xf6fdb at+0x2560,
third word0 at+0x2568. Slot32 ScratchRam extent is0x20000 from the matching map.
Opaque zero objects remain fixtures, not a complete production configuration.
No rendering work is submitted.

`build-root-envelope.py` validates the maintained kernel/config/source and
records generated artifacts. `run-root-envelope.py --graph --run` checks fresh
ADT/kernel/firmware identity, validates shadow allocation/walk, unloads the
shadow-only instance, then publishes once after cold RTKit startup. Object
and firmware DATA snapshots are captured after stopping ASC. No auto reboot.
Published backing/mappings and power stay pinned until normal reboot; never
force-unload them. A returned helper is not proof of full initialization.

GPUC002 programmed the real Bumper mask (readback0xf6fdb/0/0) and passed the
former slot35 null write. It stopped on a slot41 counter write-permission fault
at+0x60, physical0x288e1f860. Current dense per-bank GPU virtual packing also
needs replacement with SGX-relative virtual offsets: firmware later subtracts
0xd10000 from slot29's virtual address. Review overlap permissions, complete
TLBI coverage and qualified address ranges before the next cold trial.

Earlier diagnostic RAM surrogate demonstrated only mask-consumer behavior;
it has been removed from this real-bank variant. Earlier speculative bank
scanner caused a system hang and remains quarantined. Do not rerun it.
See docs/evidence/2026-10-07-gpuc002-real-register-result.json and its linked
input source provenance/native captures. No GPU acceleration established.

Current sparse variant: common MMIO base0xfffffc2000200000 plus SGX-relative
offsets;32 unique device leaves,21 object pages. Aliased clock/counter page
0x288e1c000 receives effective write permission; counter second page remains
read-only. Explicit sparse TLBI loop replaces contiguous-range invalidation.
Slot17 extent is0x21400 from matching static map. Native counter readback
0x70700777 confirms its write; next fault is read-only slot31 MCW+0.
See2026-10-07-gpu-sparse-counter-result.json and next-qualified-write-plan.json.

## Explicit retained GFX reset scope trial

The separately selected `GFX_RESET_SCOPE_TRIAL` feature adds `gfx-snapshot` and
`gfx-reset` to the resident recovery owner. It requires the joined recovery
fixture without startup work, `run_gate=2`, `resident_session=1`, and no warm
restart, automatic shutdown or release request. The ordinary build does not
include either command or the PMGR API header. A new candidate must be built
against the separately prepared kernel containing the reviewed driver-owned
PMGR interface; the running baseline kernel cannot supply those API symbols.

`gfx-snapshot` invokes the read-only driver snapshot and logs its complete valid
mask, valid register fields, domain/reset-user state, return value, operation
error and cleanup error. It also records ASC CONTROL40/CONTROL44/STATUS48,
retained recovery fields and the receive-journal prefix. It does not drain the
receive transport, ACK firmware, publish cursors or modify power/queue state.
An API/ownership failure seals publication and cancels the receive worker.
Diagnostics remain available after a reset attempt or explicit feature stop.

`gfx-reset` accepts exactly phase 0 with a healthy session or diagnostic phase 2
with a sealed recovery session. It requires the resident module pin, active
runtime-PM ownership, both mapped ASC/mailbox regions, installed root and retained
context, all 174 owned pages, no previously submitted work, all 36 work cursor
words zero, no active entry among 256 TA records, and equal consumed control
cursors within the staged range 32..128. These are host admission checks; they
are not a hardware-idle or DMA-retirement proof.

An explicit reset command consumes a dedicated permanent gate even if admission
fails. The API-attempt flag stays false on admission failure. After admission,
the owner sets the attempt flag and permanent session seal before entering the
checked driver pulse, because the API may commit a write before reporting an
error. Every result retains the pages, mappings and PM ownership. There is no
automatic RUN, INIT, resume, root/control publication or work submission.
Only `gfx-snapshot`, `sample`, and the explicit host `stop` remain useful.
A second `gfx-reset` returns EALREADY.

When this feature is compiled, `stop` always cancels the worker, seals the reset
and publication gates, and clears only ASC START using a fresh CONTROL44 read.
It sends no AP_QUIESCED, IOP_SLEEP or receive ACK packet. It keeps the resident
owner and all backing for subsequent diagnostics; a repeated stop is idempotent.
It does not report native idle, reset coverage, recovery or retirement.
Feature-off stop retains its existing management and resident-state behavior.

The worker and typed commands share `graph_io_lock`. Cancellation is deliberately
nonsynchronous under that mutex: a pending worker can acquire it afterward, see
the permanent session seal and exit without receive processing or requeue. The
owner does not acquire driver device, reset-controller or domain locks; those
remain internal to the sleepable API.

The actual owner C replay is offline:

```sh
python3 experiments/t6040-gpu/test-gfx-reset-owner.py \
    --output out/gfx-reset-owner-c-replay.json
```

The replay includes the complete `gfx-reset-scope.h`, actual typed handler,
worker, idle checks and recovery-field logger. 513 cases pass under ASan/UBSan,
covering every page guard, work cursor and active TA record, phase/control gates,
API refusal/operation/cleanup uncertainty, attempt-before-entry, poisoned invalid
observations, worker sealing, and stop before/after reset with retained diagnostic
access. API/MMIO/PM/transport calls are recording stubs; real kernel concurrency,
provider lifetime, hardware reset scope and DMA retirement are unqualified.
The existing feature-off trace/cycle/typed-handler replay still passes 88 cases.
The checked driver's separate 98 core fault cases are not duplicated here.
