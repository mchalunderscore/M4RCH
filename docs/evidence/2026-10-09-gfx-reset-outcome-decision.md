# Checked GFX reset outcome decision

This is an offline decision aid for the first retained-owner experiment on boot
`ce6572c9`. It does not record the experiment's result. Root owns all hardware
operations. The reviewed checked API, resident owner, and matched 25G83 RTBuddy
implementation are the inputs; no hardware, sysfs, module, mount, reboot, or test
operation was performed for this note.

## Classify the API before interpreting reset scope

| Saved outcome | What it establishes | Next bounded action |
| --- | --- | --- |
| Owner refusal with `attempted=0` | The owner never entered the API. Its one-attempt gate is consumed. | Preserve the refused precondition and retained backing; diagnose that condition offline. |
| API `BEFORE` is invalid, or `reset_users_present=1` | The checked implementation cannot reach its first PMGR update without a successful `BEFORE` read, and existing reset users are refused before that read. No pulse writes occurred. | Preserve the provider/read/reference error; no retry on this instance. |
| Valid `BEFORE` has `domain_on=0`, ACTUAL/TARGET other than 15, or RESET31/DEV_DISABLE10/PS_RESET12/BUSY11 set, and API returns `-EBUSY` | The checked precondition refused before the first update. | Record the exact forbidden field, not only the errno. No retry on this instance. |
| Eligible valid `BEFORE`, then nonzero operation error | At least the first update may have reached the device. Absent later valid fields do not prove absent writes. | Treat scope/final hardware state as uncertain; examine cleanup error and valid cleanup readback. Keep all backing and publication sealed. |
| Result and both errors zero, primary valid bits `0x7f`, and auto policy restored | Each pulse-stage poll reached its expected PMGR mask. This establishes command/readback completion. | Compare immediate and bounded later ASC/shared-memory observations; do not infer retirement or restart from the API return. |

Valid bits qualify successful register reads, including the last read of a
timed-out poll. A valid `ASSERTED` field must still have the expected asserted
mask to establish assertion. The same applies to every other stage. Conversely,
an attempted bus write can commit and then report failure without producing a
subsequent valid field. `cleanup_error=0`, a valid cleanup field with RESET31 and
DEV_DISABLE10 clear, and restored auto policy qualify line release/policy
restoration; they do not turn the failed operation into a successful reset.

The pulse masks require active ACTUAL/TARGET15, AUTO28 clear during the pulse,
and no PS_RESET12/BUSY11. DEV_DISABLE10 is first set; RESET31 is then set and
cleared; DEV_DISABLE10 is cleared. Final AUTO28 matches the original policy.
When the original AUTO policy was enabled, final ACTUAL may already be gated;
that is explicitly permitted by the API. Historical flag bits8/9 are not a
coverage or retirement signal.

All branches consume the owner/wrapper gate. A lost result or interrupted sysfs
write is an uncertain attempt. The only admitted operations afterward are
sample, read-only GFX snapshot, and packet-free stop. No branch authorizes a
second pulse, warm START/INIT, a new graph, unload, unmap, or backing release.

## What the existing observations can and cannot distinguish

Preserve the before/after PMGR observation, ASC CONTROL40/CONTROL44/STATUS48,
recovery counter/phase/request/host-stop/control cursors, timestamped command
logs, and the owned-object captures already produced by the wrapper. If root
chooses further diagnostics, two bounded read-only snapshots with an explicit
time interval are sufficient to ask whether already known firmware-owned shared
fields continue changing. No receive drain or new packet is needed.

Changed firmware-owned fields after the pulse are positive evidence that an
agent still accesses those pages. Unchanged fields establish only lack of
observed progress over that interval. The copies invalidate CPU cache lines and
serialize against host writes, but they are not an atomic GPU snapshot or a
proof that firmware has no dirty private cache lines or future writes.

The receive journal is a host capture. The owner cancels its receive worker and
seals publication before entering the API, so unchanged journal count/status/
doorbells after the command are expected even if firmware keeps producing
messages. They cannot establish cessation. Compare firmware-owned producer
fields in owned captures where their ownership/layout is already qualified;
do not treat a frozen host-consumed prefix as a frozen device.

The actual AppleASCWrapV6 idle predicate is `(STATUS48 & 3) != 0`; either low bit
passes. CONTROL44 START bit4 clear plus a passing idle predicate can support a
narrow stopped/idle ASC observation. Neither predicate proves that all GPU
engines, UAT/DART translations, caches, or in-flight DMA stopped. Packet-free
host stop clears START once and retains everything; it supplies no independent
DMA retirement boundary.

Therefore this candidate can establish PMGR command completion and detect some
continued access, but its saved observations alone cannot establish whole-GPU
cessation or authorize freeing the 174 pages. A release contract needs a checked
boundary for every possible bus master plus completion of outstanding accesses,
or a qualified device isolation/translation-disable and drain sequence. Its
physical completion predicates and reset coverage remain to be established.
The matched mapper `setActive(false)` and provider power implementation are
concrete offline targets for that boundary; successful register readback or
bounded memory stability must not substitute for their scope.

## Separate stopping from reconstructing firmware

A pulse that clears ASC START or stops observed shared-memory changes is a
useful reset-scope lead. It does not demonstrate a fresh firmware boot state.
Owned graph captures are host allocations, not a fresh image of the reserved
firmware DATA target. The saved TEXT identity establishes matching code only.

For this exact GFX personality, native preloaded fixup skips `copyToTarget`.
The saved ADT lacks `sram-index`, and TEXT/DATA segment flags do not select the
separate SRAM backup/restore route. Native stopped ON chooses options0, enabling
power/mapper/map/mailbox/timebase/CPU operations; its iBoot mapping flag can make
map reconstruction a no-op. The reviewed bodies do not program a reset vector
or restore DATA bytes. These are separate restart gaps, not reasons to repeat
the already failed warm START/INIT trials.

Before constructing a new restart experiment, qualify which reset domains
actually stopped and what state survives, bind the existing reserved firmware
segments and translation ownership, identify a coherent fresh/retained DATA
contract and CPU entry point, and reconstruct the stopped-start mailbox/mapper
lifecycle in one typed owner. Keep the old backing until a separate retirement
contract is demonstrated. Successful cold execution and safe retirement are
distinct outcomes; both are needed for repeatable teardown and rerun.
