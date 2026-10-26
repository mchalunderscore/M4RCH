# First native PWRGATE physical-OFF success

Fresh boot `16868560-efd7-4c98-b58d-45cb88280d46` ran the finalized admission-drain
owner once. Preflight verified the unchanged native-reset kernel, loaded USB
identity, all three PD bindings/USB roles and candidate pins; no USB reprobe was
needed. The cold trial returned0, published the joined root and retained174 pages.
Initial recovery again completed0 of2 cycles at phase2/counter1. No work or
triangle was submitted.

The sole terminal operation succeeded. Admission recorded valid START0x10,
STATUS0x4e, nonempty RX and available TX, then removed eight exact EP32 application
notifications. The first service copied766 additional trace/statistics records;
the remaining seven notifications added no records. Journal50410→51176 and
doorbells0→8 remained valid. Fresh RX-empty/TX-available admission then allowed
one EP0 `0x0060000000000202` publication. This establishes a pending application
backlog on this boot; it cannot retroactively identify d841's unlogged refusal.

The fresh EP0 reply was `0x0070000000000201`, received after seven ACK polls.
Its type7 and low8=1 follow the matched native handler; no SLEEP201 request was
sent. Fresh RX was empty after ACK and again before CPU writes. Native idle was
observed on the first poll. Two fresh CTRL44 clears/readbacks succeeded with
START clear and final STATUS0x6d.

Paired OFF cleared full PMP REQ0x2000→0 and all three PMC votes4→0 with readbacks,
using the selected native STATUS0 bypass. The single normal PM put returned0,
leaving held0/usage0/suspended/error0. The first physical observation read
`0x0f000300`, with BUSY clear and `word & 0x90001cff == 0`. The kernel recorded
result0, provider_off_observed1 and accounting_ok1. This is the first verified
strict physical-OFF result for the joined174-page owner.

An admitted diagnostic105.467723 seconds later still read strict physical OFF
and suspended accounting. It skipped ASC/SGX/mailbox/PMP/PMC access. The entire
69-page object capture, all174 owned pages and full receive journal are byte
identical between terminal and later captures. Power+0x652c stayed10724 and
journal51176/doorbells8 stayed unchanged. These non-atomic, sampled buffers support
cessation over the observed interval; they do not prove every GPU writer's
identity or joined DMA retirement.

The physical shutdown succeeded once. Same-owner restart, repeatable shutdown,
application-context rejoin, release/unload and rendering remain unverified.
The current compiled owner exposes only diagnostics after its consumed intent:
no reentry command, another PM reference, START, INIT, OFF, new publication or
backing release is admitted. All174 allocations, root/maps/context, consumer,
exclusive claims and module remain pinned. Host operation_failed remains the
conservative terminal quarantine flag despite the successful kernel result.

A distinct next source will test one retained power/transport roundtrip with
a second PM reference and separate coordinator epoch, preserving first-epoch
evidence. Only fresh ACTIVE, native paired ON and the original cold ASC boundary
(START clear, STATUS0x6a, RX empty) can admit one autonomous HELLO12/map start.
No failed warm START/INIT sequence, root allocation, context reattach, queue reset
or application publication may be reused. A separately qualified management
shutdown can then test a second physical OFF. Native transport evidence does not
establish application readiness or safe joined retirement.

The [bound outcome JSON](2026-10-09-gfx-native-powergate-drain-live-outcome.json)
pins the exact cold, baseline, terminal and later capture paths, selected owner,
preflight and saved pre-terminal GNU note/refcount1. Independent reviews cover
[startup](2026-10-09-gfx-native-powergate-drain-live-startup-review.md) and
[terminal shutdown/stability](2026-10-09-gfx-native-powergate-drain-live-terminal-review.md).
The full Gravity GPU/Mesa/DCP desktop objective remains unfinished.
