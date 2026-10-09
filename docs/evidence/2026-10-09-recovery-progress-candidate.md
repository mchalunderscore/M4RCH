# Native idle defaults and recovery progress trace

Built and independently reviewed; **executed once** on boot
`1730bf24-0823-4be9-a338-7e136762d076`. Candidate:
`out/recovery-progress/candidate`. GPU module SHA256:
`37c5fb6313a52d94a8e932bfce8a34ba2d5b825194905ec4f4fb32ece4ecef39`.
Native tracing worked, but the first recovery still failed in phase2. The
current boot remains sealed with retained backing. See
`2026-10-09-recovery-progress-live.md/.json`. Do not repeat this candidate unchanged.

The private Apple driver publishes GPU/Fender idle delays of **2/40 ms** to
**RegionC+9b8/+9bc**, distinct from the runtime power object. Our owned fields
were zero. All32 initial opcode22 controls were consumed. The actual firmware
handler at4b1c enables its configuration mirror, calls30a8, then clears the
one-shot enable at3388. Two full RAM paths ran186 instructions each: changing
the configuration defaults changes whole firmware DATA only at18ef78/18ef7c.
A later mirror-enable zero is expected and does not exclude prior consumption.
This justifies correcting the defaults; it does not identify the repeated
startup-counter caller or establish the cause of the phase2 stall.

The third field, **status_a+0=1**, enables native trace-mask bit0. After the
first power-worker return and recovery-mutex unlock, firmware64c0 emits a
type5 recovery marker into the existing512-record trace ring. The host drains
RX records and logs its journal prefix immediately before acknowledging
phase2. This prefix is an observation boundary; other firmware producers may
continue running.

Filter journal ring10/type5 for packed event`0x04000046` (recovery role4),
function0, arguments`(0,0x1000,flags,0)`, at or after the logged prefix.
Use firmware timestamps and phase/token chronology. Event46 appears elsewhere,
so its event number alone is insufficient. A qualified marker supports reaching
64c0 before subsequent queue clearing and worker waits. Absence cannot locate
the stalled PC, and the marker does not distinguish those later waits. Native
tracing introduces its normal mutex and ring-space path; healthy concurrent RX
servicing remains a runtime requirement.

Exactly three nonzero graph bytes change, atc9b8/c9bc/3c000. All mappings,
pointers, control records, RX service and the56-page immutable triangle remain
identical. The only host behavior change is one bounded pre-ack drain and
prefix log. `W=1` build, artifact/source/graph receipts and preservation checks
passed. The adjacent JSON binds the final native proofs, build and review.
Two defaults and tracing are batched, so success would not isolate one cause.

This executed candidate is now historical. The first recovery failed, so
neither the second resident recovery nor the retained triangle was published.
Only typed sample/stop is permitted; all174 DMA pages and the module stay
pinned. No recovery, teardown, GPU execution or rendered triangle is established.

Address erratum: the earlier pinned policy proof mislabeled the Fender mirror
destination as18ef80. The actual contiguous second u32 is18ef7c; the RAM audit
and candidate RegionC+9bc value were already correct. Preserve the historical
proof/receipt hashes; consult the corrected policy evidence for future staging.
