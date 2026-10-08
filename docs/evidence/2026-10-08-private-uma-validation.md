# Native UMA pool validation and usage updates

Private implementation-derived research for AGX353.14/25G83. Offline native
instruction execution only, with external mutex and event operations substituted
by argument-checked fixtures. Binary/code is not exported.

Actual TA UMA validation8a20c0c..8a20c9c executes full native pool
`canSubmitLocked`8a29f88..8a2a080, covering both reached pools. Actual TA usage
update8a20b48..8a20c0c runs after successful validation.

1,024 cases:64 successful validations,640 seed mismatches,320 event rejections.
All64 successful cases run usage updates;79 descriptor-event update calls
occur across randomized flag bytes. Whole1800-byte descriptor,220-byte pool and
200-byte usage-node buffers compare against independent expectations.

## Observed numerical contract

Pool1e0 is compared against the caller-supplied64-bit seed. A mismatch returns
e00002d5 without invoking the event services or incrementing pool48.
With an equal seed, pool1d8 provides the usage node, node28 provides a context,
and context140 supplies the external event-service receiver. The first service
receives node138/node178. The comparison service receives the descriptor event
(TA dc8 for pool0, TA80 for pool1) and node178. Its **low return bit** determines
success; other return bits do not affect this branch.

An event rejection returns e00002be and increments pool48, with tested64-bit
wraparound. This is a numerical attempt/rejection field observation, not a
complete semantic identification of the counter. Optional trace work is off.

Pool208 supplies its lock. Validation acquires pool0 first; pool1 is only reached
if pool0 succeeds. A failure releases acquired locks in reverse order. Success
leaves both logically held for the following usage-update method.

Usage update calls the external operation with node178/node138 for each pool.
If node1b8 bit0 is set, it also calls the operation with the corresponding TA
event and nodef8, then clears the **whole flag byte**. If bit0 is clear, the
remaining flag bits stay untouched. Finally it releases pool1 then pool0.

External event operation implementations are unavailable in this binary; this
does not establish their contents, comparison semantics, fence signaling or
retirement. Likewise the mutex calls establish argument/order evidence rather
than real concurrency safety. No page allocation, cache visibility or GPU job
has been proved by this test.

## Connection to the first-job graph

The initialized PM/retention audit now runs actual TA caller8a22be4..8a22c4c
through these methods, PM usage-event update and PB binding using the same
retained resource graph.256 success chains compare descriptor, pool/node,
PM/HWPB/state/page/ring/scenes. Earlier actual TA parameter loading and the
retention caller8a22504..8a22534 are also checked. Omitted intervals of full TA
preparation still prevent claiming the full parent method is qualified.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-uma-validation.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/uma-validation.json
python experiments/t6040-gpu/audit-private-pm-initialized-retain.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/initialized-uma.json
```

Next priorities are matched complete TA/3D work/microsequence assembly, Linux
resource address/cache/queue integration and completion identity/retirement.
The current failed warm INIT still retains resources; a normal reboot is needed
before live integration. No forced reset/unload was attempted here.
