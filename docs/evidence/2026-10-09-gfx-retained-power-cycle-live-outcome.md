# Actual retained-cycle boundary on boot5bf0

The first shutdown succeeded again. The subsequent retained-cycle experiment
successfully acquired a new PM reference and brought the physical GPU domain to
ACTIVE, then refused before its second paired ON or START because fresh ASC
STATUS was `0x6c`, while this candidate requires `0x6a`. No second handshake,
management request, CPU-stop sequence, paired OFF or PM put occurred. The second
reference remains held. This is a boundary refusal, with restart still untested.

Boot: `5bf0a178-e6d8-4def-8088-74ad7ea87727`.
Kernel: `7.1.13-m4rch-gpu-native-reset`.
Owner: `out/gfx-retained-power-cycle/candidate`, SHA
`abf4ef3c709c3a775db2fa897dbbe1ba7edbb9868000848ac8283417f9fb7608`.
Receipt: `1762f50dcaa0a321c0003cee3ad63dba83cb50159599bc72bbf9c2444b5afe69`.
Preparation: `aca3b33c2b35cafe31b1e8d6463f8b56181f0644dc2499a14fc5c4a4fcde7aed`.
The [JSON evidence](2026-10-09-gfx-retained-power-cycle-live-outcome.json) binds
67 actual raw, software-identity, source and receipt inputs.

Fresh preflight passed kernel, USB/PD/roles, resources and all candidate inputs.
One cold load returned zero and published the graph/root while retaining all
174 pages. Startup remained diagnostic at zero of two recovery cycles; work,
targets and completion bytes were untouched. Root's initial note-extraction
command accidentally rewrote the on-disk ELF layout. Its rewritten file was
preserved separately, and the untouched qualified module was restored before
terminal commands. The loaded note matches both layouts and the restored
original; source, receipt, kernel and loaded owner were unchanged. Subsequent
identity recording used the existing pure byte parser. The correction is bound
in the startup evidence and was not a runner rebuild.

The first terminal operation drained eight exact EP32 notifications and added
766 records, bringing the journal from 50410 to 51176. Own PWRGATE202 at
261.824600 received native EP0/type7/low8=1 ACK after five polls. Fresh RX empty,
native idle and two fresh CPU clears/readbacks0/0 preceded paired OFF. One PM put
returned zero, with held0/usage0/suspended/error0. At261.829518 the first physical
sample was `0x0f000300`, BUSY clear, domain OFF and strict mask clear. The full
returned report, log delta, objects, all owned pages and journal rebuild the
first-OFF admission proof exactly.

At288.315897 reentry freshly observed that same strict OFF. One
`pm_runtime_resume_and_get` returned zero, owned the second reference and
produced physical ACTIVE `0x1f0003ff` at288.315932. Its next fresh operands were:

| Operand | Observed | Interpretation |
| --- | --- | --- |
| CTRL44 | `0x0` | START clear |
| STATUS48 | `0x6c` | Fails this experiment's exact `0x6a` predicate |
| RX114 | `0x20001` | RX EMPTY set; outbox enable bit already set |
| TX110 | `0x20001` | TX FULL clear |
| PM state | held1/usage1/status0/error0 | New reference retained, ACTIVE |

The syscall returned EBUSY. The host report remains complete=false and
operation_uncertain=true, despite clean final captures. Both durable intents
are consumed. First-epoch provider-OFF/accounting-success fields remain
historical and cannot describe current power after the new PM get.

One admitted later snapshot at353.648340 still showed physical ACTIVE and
held1/usage1/ACTIVE/error0. It skipped ASC/SGX/mailbox/PMP/PMC reads and retained
power+652c19110/journal51176/doorbells8. Entire object, all-owned and journal
captures were byte-identical across first OFF, the refused cycle and later
diagnostic, spanning91.818822 seconds. These non-atomic samples support local
cessation in those captured buffers; they do not identify every writer or
establish joined DMA retirement.

Long v6 printk rows truncate at about1024 bytes and lose their newline. The
immediate cycle capture omitted the final return row; a later saved read-only
kernel log contains result-16/refused_condition=cold-boundary-unqualified and
the later current-second-state marker. The visible operands independently
identify the sole failed predicate. Missing truncated fields are not treated as
zeros. Future distinct code should emit short, complete state records.

All174 pages, root/maps/context, consumer, MMIO/exclusive claims and module
remain pinned. Only this family's existing typed `sample` and `gfx-snapshot`
are admitted. There is no retry, second PM put, paired-ON bypass, START/INIT,
reset/control/work, new owner, detach/free/unload permission. Same-owner
roundtrip, application rejoin, pixels and retirement remain unverified.

The [bounded native follow-up](2026-10-09-gfx-retained-cycle-status6c-native-start.md)
shows that the native memory-preserving start route has no exact STATUS6a gate.
The missing second paired ON and known6c boundary support a distinct future
ordered hypothesis after actual PWRGATE/strictOFF/newACTIVE. They do not grant
permission to retry or change this frozen loaded owner.
