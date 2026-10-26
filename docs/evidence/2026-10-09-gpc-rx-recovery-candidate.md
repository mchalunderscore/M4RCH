# Receive service for repeated GPU recovery

Candidate: `out/gpc-rx-recovery/candidate`.
Module SHA256:
`f123d1dbe97705f1ad9bfe3b98aa1e4f33cea95ee7002de3a553ecbf98ce0650`.
Executed once on boot `bba7a8f2-e6d3-49b8-88ed-bc5be2d17c0a`. RX servicing
passed the observed workload; the first recovery stalled in phase2. See
`2026-10-09-gpc-rx-recovery-live.md/.json`. Do not repeat this unchanged candidate.
Its GPU graph and immutable draw bytes are identical to the telemetry candidate.

The host accepts exactly EP32/`0042000000000000` as a receive doorbell and
consumes validated records instead of echoing a mailbox reply. All twelve native
receive rings have generated, extent-checked state/ring offsets, capacities and
type masks. Records are copied across potentially noncontiguous16KiB pages
before only the host consumer is advanced. Firmware producers are not reset.
The cache publication follows Gravity's invalidate/store/clean path; its live
behavior remains part of this hardware trial.

A read-only CPU journal retains up to65536 raw records with ring/index/sequence
metadata. It is separate from the174 retained DMA pages. Its fixed snapshot is
5242944bytes; only the immutable prefix identified by the first header's `used`
count is authoritative. Both runners save the binary and decoded JSON. No
record is overwritten when the journal fills: the session is sealed instead.

Observation, recovery waits and shutdown service the same transport. A bounded
10ms delayed worker keeps it serviced between resident commands and throughout
the single triangle observation. It shares the command/snapshot mutex. Stop
disables the resident session and cancels pending work while all backing and
the module remain retained. The old64-message cap is a per-poll work bound, not
a crash condition; any number of valid doorbells may arrive during a timed wait.

Native event0 is consumed with its proven no-op callback. Event1's completion
mask is preserved with selector<24 validation; this does not authorize freeing
jobs. Unsupported event callbacks, invalid records/cursors, a crash endpoint or
journal overflow seal the session. Worker faults propagate through saved journal
flags to the runners' quarantine state.

Validation: `W=1` build; complete source/artifact receipts; unchanged graph and
draw; nine decoder tests; eight actual-header C replay scenario groups. The C
replay uses the captured255 statistics records, distinct16KiB CPU pages, wrap,
concurrent producer append, cursor bounds, journal-full behavior, event0/1 and
mailbox classification. The pinned native consumer independently consumes the
same255records correctly in emulated RAM. None of these establish live recovery,
safe teardown, GPU execution or rendering.

This historical candidate has run and must not be repeated unchanged. Its
failed session permits only typed sample/stop, with all backing retained.
The next distinct candidate is documented in
`2026-10-09-recovery-progress-candidate.md/.json`.
