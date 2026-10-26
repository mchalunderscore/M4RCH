# Complete native 3D scheduler wrapper and common encoder

Private-derived matched AGX353.14 / Apple25G83, offline only. The checker now
executes the complete AGXKSMKickQueueG16::encode3DKickEntry at89db63c..89db874,
including its real call into complete encodeKickEntry at89db230 and actual
cached/uncached conversion, record encoding and LSE pending publication. This
extends earlier common-encoder slices by resolving the3D caller's inputs.

## Descriptor inputs and dispatch

All offsets/addresses/record sizes below are hexadecimal.

| Common encoder input | Native3D source |
| --- | --- |
| event command pointer | real descriptor slot1e0 getter -> descriptor210 |
| dependency pointer | real descriptor slot1e8 getter -> descriptor218 |
| register-list metadata | descriptor820 |
| aperture metadata | descriptora98 |
| auxiliary value | descriptor168 if nonzero, otherwise acceleratorfd48[descriptor964&7f] |
| payload object | wrapper x2, forwarded to common x6 |
| notification mask | wrapper x3, passed on stack |
| first boolean |1 when descriptorc44==3, otherwise descriptor4c bit0 |
| second boolean | descriptorb48 bit0 |

The actual3D descriptor vtable7eb7898 slots1e0/1e8 bind native getters895d5e4 /
895d5d8. Scheduler G16 vtable7eac548 slot168 binds this wrapper. These targets
are checked from the original encoded vtable pointers; getters execute natively.
The table fallback uses a masked7-bit index, distinct from queue/event identity
fields. No interpretation of the auxiliary value as a GPU pointer is assumed.

## QoS provenance

Three actual owner lookups use descriptor60 and c6e6298 metadata; this external
provider returns an explicitly synthetic owner in the checker. Native code
then derives the three QoS values:

- byte0: owner898 object's10, truncated to one byte;
- u32+4: u16 from owner898->58->530 object'sc8e when c88 is nonzero,
  otherwise that object's10 object's770;
- u32+8: byte from table71307f0 at `3*selector+1`.

Selector is1 when the device object'sc68 denominator is zero. Otherwise it is
`(u64(c60)/u32(c68)) %9`. Both source branches and all nine ratio-derived table
selectors execute in the fixtures. These are observed inputs, not assigned
undocumented tuning names. QoS eventually packs into the scheduler record as
established by the earlier independent body model.

## Full common encoder execution

Queue78 backing and stride14 choose the slot from timestamp48's low byte.
Fixtures use a200-byte stride and slot0, so full native entry initialization is
bounded and independently modeled. The external zero-memory routine b744da0
is intercepted only after checking exact destination/length and supplying its
explicit zero-memory contract. No private service runs.

The remaining common encoder runs natively: aperture/payload prefix, explicit
dependencies, cached or converted prior dependency, QoS, four register lists,
notifications and auxiliary field. DMB and actual LDADDAL publish the record,
advance queue48, increment pending44 and update cached98/a0. The complete
wrapper returns the original scheduler timestamp. This is the value the earlier
3D post-kick caller places in opcode12/14/16 records.

Optional accelerator1aed4 bit3 tracing is disabled; the wrapper's provider-
assisted tracing path remains untested. Full-record success does not prove
firmware acceptance or that the resource addresses describe a valid shader job.

## Verification

```
python experiments/t6040-gpu/audit-private-3d-scheduler-wrapper.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-scheduler-wrapper.json
```

1024 complete wrapper/common-encoder cases pass. Each includes an independent
prefix/body/publication model and full200-byte record comparison. Full queue,
descriptor, synthetic owner/context/task/device/accelerator objects match their
expected contents, preserving unrelated bytes. 512 cases each cover cached /
uncached prior, descriptor / table auxiliary source and local / fallback QoS.
512 ratio-derived selectors cover0..8. Dependency counts0..8 are exercised;
these are tested counts, not an asserted protocol maximum.

Actual getters, native event conversion and atomics execute. PAC is bypassed;
owner lookups and zero-memory service are synthetic. Linked original TEXT_EXEC
is loaded locally for execution, not exported in evidence. Binary/vtable targets
and wrapper hash are pinned or recorded. Emulated RAM does not establish DMA,
cache policy, concurrent publication or job completion. No kernel/default or
hardware changes, and no executable draw.

## Next integration gap

The enclosing3D submit caller at895c080..895c104 computes extra scheduling NOPs
from an event-machine value, emits them before this wrapper and accumulates
that count in descriptor2dc. Then it emits the real3D entry and increments2dc
once more before post-kick commands. Trace that padding/count contract and
connect the already checked configuration publisher, scheduler builder and
post-kick publisher without substituting callback-return guesses. Completion
routing and valid shader/target inputs remain open. Retained warm INIT still
needs normal reboot before new hardware trials.
