# Native page-mapping and internal-resource lifecycle

**Correction:** the PM50 gap below is now resolved as an omitted sixth output in
the registration fixture. See private-pm-metrics.md and the actual native-method
and initialized-job receipts. The gap discussion records the earlier investigation.

Offline private-derived AGX353.14/Apple25G83, using the pinned input SHA in each
JSON receipt. All numeric offsets and addresses below are hexadecimal. No live
GPU commands or kernel/boot changes were made by the audits.

## Executed checks

| Audit | Native methods | Results |
|---|---|---|
|page-mapping|prepareAndRetainPageListMapping89fe494..89fea3c; releasePageListMapping89fe44c..89fe494|256 fresh,256 reused;512 nonempty and512 empty releases;1018 resource retains in fresh construction|
|resource-mappings|prepareMappings89ed740..89ed7c0; completeMappings89ed7c0..89ed82c|1024 cases:576 preparations succeeded,256 first failures,192 second failures,64 first-mapping unwinds;934 nonempty and90 empty completions|
|native-retain|ordinary prepareAndRetain89fa7a8..89fb0d4 with actual preparation and concrete reused page-mapping calls|512 joined paths,2560 actual internal-resource preparations,512 actual page-mapping preparations;2688 block-service calls,896 dirty-block services,256 stage-update services|

Tools live in experiments/t6040-gpu/audit-private-NAME.py and receipts in
docs/evidence/2026-10-08-private-NAME.json. The joined tool extends the independent
ordinary retention expectations and also checks complete bytes of all six
internal-resource objects. New service hooks delegate existing support/generation
calls before handling nested calls; the initial counter expectation was corrected
to match the parent fixture's first-use flags before producing passing receipts.

## Page-mapping contract

With PM28=0, a nonnull PM258 and zero PM128 reuse the current mapping. Otherwise
the fresh construction path covered here reads PM248's array of PM250 resource
objects. It allocates a mapping, invokes inherited initialization with PM10 GPU,
sets mapping90 capacity to `(count+3f)&ffffffc0`, mapping94 count, and allocates
two arrays of capacity*8 at mapping80/88. Array80 retains each resource; array88
stores resource18; mapping98 adds each nested object's virtual148 length.

The fresh initializer fixture preserves mapping98's initial bytes, and the audit
checks native addition against that initial value. This deliberately does not
claim inherited initialization sets the field to zero: that still needs its own
qualification. Count0..8 is tested; count0 uses explicit nonnull zero-size
allocation returns, not a claim about production zero-size allocator behavior.

The native method prepares the mapping through an external service, writes
TA d78=PM258, and retains it. When PM240 discard resource exists, it prepares
and retains that resource's20 object and writes TA d98. Actual release invokes
mapping virtual28, then zeros PM258; an already-null PM258 causes no service call.

The method's mode2 replacement, pending-resource append/reallocation and failure
branches are not covered by this batch. Allocation, inherited initialization,
retain/release, lengths and underlying preparation remain explicit services with
argument and ordering assertions. No lifetime/cache/DMA proof is inferred.

## Internal-resource preparation and completion

Actual prepareMappings receives a nonnull resource. It optionally prepares
resource50, then58. A first failure returns e00002be without incrementing the
counter; a second failure completes a previously prepared50 and returns that
error. Success locks resource40, increments resource38, then unlocks.

Actual completeMappings locks resource40. For a positive resource38 it completes
nonnull50 then58, decrements the counter once and unlocks. Zero count performs
only lock/unlock. The successful matched paths and failures above compare every
resource byte and external call order. The count records successful preparations;
it is **not evidence of firmware job retirement**. External mapping and mutex
services, concurrency and real service failure semantics remain unqualified.

## Joined ordinary retention and remaining lifecycle gap

The joined audit replaces the six preparation-service fixtures with actual
prepareMappings, and PM virtual1f0 with actual concrete page-mapping preparation.
It covers the parent retention ring/dirty/staged variants, but uses an existing
page mapping, PM28=0, zero pending blocks, no discard resource. Generation,
block preparation, page builder and underlying mapping services remain fixtures.

This fixture explicitly supplies PM50. The separate concrete initialized-job
chain leaves PM50 zero, while the base ordinary retention path later passes PM50
to prepareMappings at89faa40. The helper dereferences its receiver at89ed754;
the receiver itself is not null-safe. Consequently these two passing fixtures
cannot simply be joined and called a production lifecycle. This is an unresolved
fixture/subtype/caller-lifecycle question, **not a demonstrated Apple driver bug**.
Establish the actual PM subtype, inherited setup and caller lifecycle before
inventing a resource or substituting a successful return at that boundary.

Static caller inspection locates actual PB binding in TA prepare8a22090..8a22f34:
at8a22c48 it calls loadPBDesc with PM from TA d68, manager from d70, request from
1218 and byte mode from c44. Earlier calls include descriptor virtual208/210 and
PM updateUsageEventsLocked89fe138. The full caller and its allocation/locking
services are not yet executed/qualified; this is a pointer for the next audit,
not evidence that manual orchestration reproduces that ordering.

Remaining work includes this lifecycle gap, pending/replacement mapping paths,
native caller ordering, and matched Linux-owned allocations/root/work objects,
KSM queues/event/stamp ownership, publication/cache visibility and firmware
completion/coherent readback. We are not yet at submission-only readiness.

Failed warm INIT still pins asc_graph_init on the current boot. A normal reboot
is required before live integration; do not force unload/reset/warm retry.
