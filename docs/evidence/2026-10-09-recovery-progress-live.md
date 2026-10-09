# Native recovery tracing narrows the remaining failure

Boot `1730bf24-0823-4be9-a338-7e136762d076` ran the reviewed candidate once.
All three PD drivers and USB role providers were present before GPU activity;
no reprobe was needed. Module SHA256:
`37c5fb6313a52d94a8e932bfce8a34ba2d5b825194905ec4f4fb32ece4ecef39`.

The journal retained **17,994 valid records with zero status flags**:
9,595 native trace records over18 cursor wraps and8,399 statistics records
over32 wraps. All32 initial controls were consumed. Tracing is visibly active.

Recovery accepted token0, reached counter1/phase1, and the host drained and
logged prefix7792 before acknowledging phase2. Sequence7794 is the sole
recovery-role marker: packed event`0x04000046`, function0, arguments
`(0,0x1000,4,0)`, firmware timestamp3720473107. All trace timestamps are
monotonic; no earlier recovery-role record can contaminate this boundary.
The matched firmware source supports reaching64c0 after the first worker wait
and recovery-lock release, before subsequent queue clears and worker waits.
This is progress on this invocation, not a sampled live PC or a completed cycle.

Phase3 did not arrive within five seconds. Final counter1/phase2, host_stop1,
request state0/flag1, controls32/32/32 and completed0/2 seal the session.
The startup counter still increases600→1201 over roughly five seconds, almost
identically to the previous trial. Native2/40ms defaults did not resolve that
behavior. A typed diagnostic sample at uptime237.598s still shows phase2,
with startup count13286 and all six observed MMIO operands zero.

One read-only reserved firmware DATA snapshot was captured at uptime364.451s.
Its receipt binds SHA256
`ff6e62d4e648370615d7ddb85d2459fe231b46dfddc42849b9f2853f7ab46462`.
Firmware private-cache writeback freshness remains unproven. Saved task frames
and zero semaphore values alone cannot identify the current wait. The new
trace is stronger evidence of progress than the independently sampled IRQ
frame containing the old phase1 polling address.

**No triangle was submitted.** The main module and all174 DMA pages remain
pinned; only typed sample/stop is permitted. Do not repeat this candidate
unchanged, retry a warm wake sequence, or force unload the retained context.
Repeatable recovery, teardown, GPU execution and rendering remain unverified.

The adjacent JSON binds the complete handshake, journal, firmware identity,
later diagnostic and PD baseline. Independent trace and policy comparisons
are in `2026-10-09-recovery-progress-trace-live.json` and
`2026-10-09-recovery-progress-policy-live.json`.
