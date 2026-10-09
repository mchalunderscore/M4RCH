# Driver and ABI comparison: remaining process gaps

Offline synthesis against source checkpoint `d98fee4` and the prepared recovery
dispatch candidate. No hardware operation, candidate edit, or new execution
qualification. The current sealed GPU instance remains diagnostic-only.

Rechecked inputs:

- Apple25G83 / AGX353.14 driver SHA256:
  `3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
- Uploaded `M4-PRO-GPU-HARDWARE-ABI.md` SHA256:
  `2818ced00eea77f662be9339ee6dae717bd1330e2a46bc927e53190edf6b98db`.
- Matched normalized firmware TEXT SHA256:
  `190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac`.

The document is a useful layout inventory. The driver adds constructors,
publication ordering, policy gates and resource lifetimes. Neither passing a
serializer comparison nor mocking a service proves that the corresponding
GPU-visible transition happened. Review whole operation chains and identify
every remaining supplied service or policy input.

| Area | Current evidence and remaining work |
| --- | --- |
| ABI adaptation | The document's queue producer `+0x50` conflicts with matched native publication at `+0x40`; `+0x50` is the reset sentinel. Its J616s has 20 cores; this J614s has 16. Live builders already use the corrected queue field and `0x3db/0x3db` masks. TA wire extent and native allocation stride must remain separate concepts. |
| Idle recovery | Request/token checks, phase acknowledgements and mapped-ring/mailbox draining are implemented. Native `resetFirmwareForRecovery` is a no-op, and native phase helpers contain checks/barriers/stores; no additional mandatory idle host reset/MMU action emerged. The exact later worker ACK failure remains unknown. |
| Recovery after submitted work | Not implemented. Current code rejects recovery after submission and rejects active TA recovery records. Native recovery reconciles 128 submitted timestamps, fences, retained resources and client queues. These omissions are valid for the empty experiment, but must be resolved before post-work recovery/reuse. |
| Scheduler context | Native allocation and initialization are now reconstructed offline. The seed prefix matches when the supplied owner byte is2. Current config PID/subpriority0/0 differs from staged state PID1/2 and subpriority1. Actual task/VM association, QoS registration and intended identity policy remain unjoined; no connection to the idle stall is established. |
| Power features | Profile A and QoS backing are present; Profile B source mapping and AON construction remain incomplete. Documented table geometry or identifiers alone do not establish their producer inputs, placement, gates or relevance to the current failure. |
| Completion and retirement | Four hardware completion configurations were installed on the older submission trial; no completion or target pixels changed. RX transport is qualified within its scope, but full client completion/error callback semantics and joined DMA retirement remain incomplete. RTKit shutdown acknowledgements alone do not qualify freeing or reusing memory. |

## Concrete scheduler-context target

Matched native `AGXCommandQueue::allocateSchedulerState` spans
`0x89897cc..0x8989bf8`. The mapped subslot pointer is formed from a resource
mapping plus an allocated offset and stored to queue `+0x8b8` at
`0x89899ec/0x89899f0`. Configuration construction copies that pointer to
config `+0x4a` at `0x895be4c..0x895be64`; companion fields `+0x56/+0x5e/+0x5a`
are produced at `0x895be68..0x895bf00`.

Our `prepare-owned-scheduler-pair.py:46` explicitly borrows a base-M4 seed.
`prepare-owned-work-publication.py:23` supplies its owner pointer and zero
service fields. `prepare-owned-scheduler-start.py:30` shares the TA context
and enables the owner update, while its receipt preserves the zero companion
fields as hypotheses. The later header-selector trial is independently inferred;
it does not prove the native scheduler-state/UAT association.

Root checked the current candidate's actual `backing.bin`: both state `+0x9c`
and config `+0x4a` point to `0xfffffc2000b18200`; config
`+0x52/+0x56/+0x5a/+0x5e` are `[1,0,0,0]`. The new native audit identifies
config `+0x56` as a QoS hardware-buffer ID, `+0x5a` as PID and `+0x5e` as
subpriority. The native getters copy PID from channel state `+0x48` and
subpriority from `+0x40`, exposing the staged config/state inconsistency.
QoS begins with an `0xffff` sentinel, but registration can assign ID0; zero
alone is not proof of a bad QoS value. No replacement identity policy follows
merely from installing UAT context1. The prepared candidate remains unchanged.

The offline batch is recorded in `2026-10-09-offline-gpu-work.md/.json`.
Its native-scheduler-state, recovery-bookkeeping-contract and
completion-identity-contract reports add bounded actual-instruction RAM
checks and decoder validation. The new recovery-dispatch analyzer checks
saved chronology conservatively; it does not grant recovery or retirement
qualification. These are contracts and diagnostics, not live execution proof.

## Newly resolved power feature boundaries

Profile B publication at native `0x89cb440..0x89cb508` is gated by
accelerator `+0x505` bit0. Enabled publication includes count/frequency at
hardware `+0x1cd8/+0x1cdc`, core rows at `+0x1d1c`, and SRAM rows at `+0x211c`.
Matched firmware `0x2f7a4..0x2f7b8` copies the block to runtime power `+0xba0`.
The gate's actual native default and frequency-profile assignment remain
unresolved. Zero Profile B is not established as an error on this machine.

AON init `0x89ccc40..0x89ccc88` passes the state beginning at power `+0x6318`
to G16X identifier population at `0x89e92fc..0x89e9388`. Two cluster identifiers
and the die identifier are stored at `+0x6320/+0x6324/+0x6368`. Native
`0x8977bf4..0x8977ea8` obtains complete 12-byte records from ApplePTD
`ptd-data-table-dict` or `ptd-data-table`; the remaining record bytes cannot be
invented from the names. Native `0x89cce14..0x89cce40` publishes a converted
FW-object `+0xc30` pointer at power `+0x6318`. This requires an owned graph,
not just three inline tags. Enablement expectation reads accelerator `+0x6d7`
bit3 at `0x89e92c4..0x89e92d0`; its producer/default and the allocation lifecycle
remain unresolved. Firmware `0x396a0..0x396bc` has a null-pointer alternate
path at `0x3a9b4`. No causal link to the current phase2 failure is established.

## Evidence required at each transition

Use a current, stage-specific ledger: request accepted -> fresh recovery marker
-> scheduler bit25 entry -> matching exit -> phase3 -> host phase0 and a fresh
control consumed. The prepared mask3 candidate supplies the next observations.
A bit25 entry supports passing the first later wait; its exit supports the
handler returning after signalling the second semaphore. Neither proves
semaphore consumption or the final power acknowledgement. Missing markers do
not identify a live PC.

The latest live marker supports progress to firmware `0x64c0`, despite an
off-core saved frame still containing `0x6410`. Private-cache freshness is
unproven; use trace timestamps, token and phase chronology together. RAM
callback checks omit scheduling, cache effects and trace locking.

For execution, require separate observations of hardware work progress,
completion and changed target pixels. For release, establish queue/context/DMA
retirement independently. Four clean idle recovery cycles would establish
idle reuse within that retained instance, not recovery after a submitted job
or safe unload.

Existing evidence: `2026-10-09-abi-reference-recheck.md`,
`2026-10-09-recovery-host-contract.md`, `2026-10-09-recovery-progress-live.md`,
`2026-10-09-recovery-worker-ack-path.json`,
`2026-10-09-recovery-empty-callbacks.json`, and
`2026-10-09-owned-hw-completions-live.md`. Older mailbox-only wording and
inherited broad unresolved lists must be read against the current implementation.
