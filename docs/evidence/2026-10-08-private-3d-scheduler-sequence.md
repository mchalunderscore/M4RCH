# Native extra-NOP loop and 3D scheduling sequence

Private-derived matched AGX353.14 / Apple25G83, offline only. The checker executes
the enclosing3D submit slice895bfc8..895c154, including actual NOP scheduler
method89dc07c, complete3D wrapper89db63c, their real common encoding/conversion
and LSE publication. This connects caller bookkeeping to actual emitted records.

## Extra-NOP count and guard

All offsets/addresses below are hexadecimal. Arithmetic bit counts are decimal.
The selected NOP scheduler is acceleratorf938 indexed by caller x22. The baseline
is u32 at accelerator140 object's2050 + signed32(x22)*4. Caller w21 supplies the
current event-machine value. Native calculation is:

```
difference = (current - baseline) modulo 2^32
extra = ((difference >> 8) - 1) modulo 2^32
require extra < selected_scheduler.capacity
```

The comparison is unsigned. Zero difference, or a difference below256, produces
ffffffff and takes diagnostic entry895c438 before emitting anything. Capacity
and greater counts are also rejected. The checker stops at diagnostic entry;
it does not execute the external diagnostic or claim recoverable error handling.

For a valid count, the caller builds a two-word zero payload and32-byte zero
notification mask and calls scheduler slot148 exactly `extra` times with x3=x22
and x4=w21. Actual G16 vtable target is encodeNOPKickEntry89dc07c. Each complete
native NOP method zeros its selected200-byte slot, encodes a dependency, advances
timestamp48, publishes pending44 and updates cached98/a0.

After the loop the caller adds `extra` to descriptor2dc. It then invokes the
original scheduler's slot168 with the descriptor, real payload and mask.
Complete3D wrapper/common encoding executes; the return is saved in x22.
Finally descriptor2dc increments once for the actual3D entry.

## Actual payload and mask construction

The real3D payload contains the original caller x25 and channel80; the caller
stores these before replacing x25 with queue ID. These are caller-supplied
values, not inferred CPU/GPU address semantics in this checker.

Its first three notification u64s are zero. Fourth-word flags are:

- bit63 when firmware380 object'se1c bit0 is set;
- bit62 when descriptor470 pointer is nonzero;
- bit61 when accelerator6d7 low two bits are nonzero.

All eight combinations are exercised. These high-word flags differ from the
zero mask used for the scheduling NOPs. Do not silently reuse one for both.

## Independent verification

```
python experiments/t6040-gpu/audit-private-3d-scheduler-sequence.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-scheduler-sequence.json
```

1024 complete caller sequences pass. They emit34943 native NOP records plus
1024 native3D records. Capacities2/3/16/256, varied starting slots, wraparound
and zero/nonzero padding counts are covered. Independent models build every
record from zero backing, calculate each timestamp/pending/cache update and
compare the full backing ring, including untouched slots. Descriptor2dc equals
extra+1 from its initialized zero value; the actual3D timestamp returned into
x22 also matches. Both initial cached/uncached priors, auxiliary sources and
QoS branches remain covered from the earlier complete-wrapper audit.

64 additional guard cases (capacity,capacity+1,ffffffff) stop before any callback,
record/queue/descriptor mutation. This establishes the reviewed guard behavior;
invalid fixtures are not evidence of reachable native-driver failures.

Fixtures select the same scheduler object for the event-index table lookup and
original3D scheduler. The native caller obtains them separately; this checker
does not establish when differing identities are valid. It starts after prior
resource/config construction and ends before owner registration/post-kick work.

PAC is bypassed. Owner lookup and zero-memory services use explicit synthetic
contracts; native getters, NOP/common3D code, event conversion, DMB and atomics
execute in emulator RAM. Optional provider-assisted tracing is disabled. The
binary and caller range are pinned/recorded. No hardware/DMA/cache/concurrency,
firmware acceptance, fence completion or executable draw is proved.

## Implementation consequence and next gap

Linux must account for emitted scheduling NOPs as well as the actual3D entry
before emitting opcode14's count and later releasing pending counts. A constant
one kick per descriptor does not reproduce this path when padding is required.
The event baseline/current-value source and ownership invariant must be matched;
constructing arbitrary inputs that pass this arithmetic is not sufficient.

Next connect actual scheduler return/count to the already checked post-kick
records and native pointer publisher, including intervening owner registration.
Then finish resource/mapping/cache and real shader/target preparation with a
bounded completion path. Retained failed warm INIT requires a normal reboot
before new hardware trials. No kernel/default change or hardware submission.
