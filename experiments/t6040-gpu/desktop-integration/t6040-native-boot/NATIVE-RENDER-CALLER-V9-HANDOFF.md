# Compiled native Gravity render caller

Frozen source stage: `out/gpu-gravity-normal-native-render-caller-v9-v6`, based
on `out/gpu-gravity-normal-native-flight-retirement-v9`. Actual kernel module
compile/link exited0, with117warnings and0errors. The module is919952bytes,
SHA256 f8a569d5a5dc76c85d5eeb71bf08e47417fa8085d3185efd570405bdf4d41ca1.
All94staged source pins match their build-owner copies. No module was installed
or loaded, no kernel was rebuilt, no GPU hardware action occurred. Startup and
BUNDLE_COMPLETE remain gated. This is a compiled caller, not GPU acceptance.

The reproducible source is `native_render_caller_v9.rs` plus
`stage_native_render_caller_v9.py`. The staging script adds the qualified
components and locally copies ignored private-generated semantic RCE source.
Do not track or export that generated source or the staged kernel tree.

## Actual connected route

`submit_render_queue` selects the native branch before donor Tvb creation. It
pins each client owner before PM allocation, reserves global firmware VA using
the concrete native AllocationPlan, creates real NativePm aliases/blocks and
leases a native scene. Scratch comes from Gravity's retained client allocator.
The native leased scene supplies its actual payload address/header; no donor
scene30/cycle arithmetic enters this branch. Packed PB descriptor publication
uses the support lease's existing table admission.

The Work layout uses the retained1c000 allocation. Native command pages have
same-PA device aliases. Actual client status pages get retained external
firmware aliases; FW completion addresses are not guessed device pointers.
RCE/descriptor/context/SKU backing is borrowed from a31KiB heap allocation,
not a kernel-stack command/descriptor temporary. Actual parameters plus typed
private-aperture conversion enter provider10. Native PM translations feed the
construction envelope. The caller then constructs native SKU, actual exported
register-list counts, complete KSM records and opcode14 postkicks.

Hardware KSM records are copied through stage_native_scheduler_entry into
separate actual scheduler backing. Firmware pointer-ring records are typed
ordinary48-byte dependency records, native BM-init18 when needed, and the
postkick24byte backing. The pointer ring never publishes Work's KSM record.
Fragment has the original TA hardware timeline dependency in both scheduler
and firmware records. Existing VDM dependency routing is retained. Exact
pointer-ring admission includes configuration, BM/dependency/postkick records.
Dependency records borrow three0x80 slots in each SKU page's unused suffix
atSKU+2000, disjoint from the SKU writer's2000capacity and next Work page.

Native stamps retain original submitted hardware timestamps/queue IDs.
Dependencies lacking these identities, including donor compute stamps,
explicitly refuse. Both stages' original identities remain with their Flight.
Queue owners retain separate pending-entry state and original cached prior.

## Failure and retirement custody

The native branch sets render_failed before scene-associated allocation or
publication and clears it only after successful Flight retention. FW backing
and Work leases remain allocated on failure. Client ownership is pinned before
partial alias creation. Native PM scene leases remain held. A native error
must not release its event lease merely because queue.pending is still0.

NativeCreditStaging is placed in Bootstrap before any scheduler slot copy or
firmware announcement. Each successful non-copy scheduler credit is installed
there immediately. A failed second slot/configuration/transport write cannot
drop the first credit. Credits transfer to Flight only after successful Flight
insertion; on error the retained staging record preserves owner, Work and all
committed credit identities. Interrupted slot writes preserve quarantined
native scheduler state. No credit retirement is inferred from staging.

The completion consumer validates native scene ownership before spending any
credit, validates both credits, then retires them once. Scene release uses
NativePm rather than donor TVB. Actual existing firmware/driver stamps,
notifier count, channel cursors, queue cursors and growth-transport predicates
still gate all resource/context/scratch reuse. Native growth/partial event
service explicitly refuses while retaining all owners; it never applies donor
TVB growth wire images to native resources.

## Explicit experiments still requiring source/live validation

The stage receipt records exact policy values: eleveninitialblocks,
36scene/stateleases, independent4000registration/payloadstrides, configured
Linuxblockcapacity, native configuration counts/1d4zero and supportcount1.
Scheduler capacity256 starts at the requested Linux fw_counter_start with
an invalid-before-first prior; Apple's accelerator ee48 equality is unproved.
No scheduling NOPs are emitted in this first-draw policy. Event banks start1,
public stamps use existing Gravity progression, notifier storage is a real
uncached Work subrange18100 with experimental initialized fields. QoS0/16/0
and placement of actual ADTcoremasks in the firsttwo maskwords are experimental.
Private TA allocator-relative addressing uses the retained Linux private base
1000000000. Ordinary zero envelope source/frame/context policy is not a
source-resolved initialization sequence. Internal/native timestamp emission
is suppressed; requested profiling remains unsupported. Growth SKU flags are
explicitly disabled for the initial owned blocks; protected/secondary/native
partial and growth policies still need complete implementation. Native Work
cached/uncached alias equivalence inherits Gravity and is not hardware-proved.

These are explicit gated hypotheses, not driver-derived defaults. The next
source priority is native notifier/event initialization plus the real geometry
and scheduler configuration policy. Live triangle/teardown remains the root's
separate frozen v24 candidate; this source stage does not change it.
