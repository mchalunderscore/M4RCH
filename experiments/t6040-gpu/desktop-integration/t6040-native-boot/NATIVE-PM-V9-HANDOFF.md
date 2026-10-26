# Native PM owned resources and runtime join

The portable constructor is `g16_t6040_pm_v9.rs`; the Linux allocator is
`g16_t6040_pm_owned_v9.rs`. `stage_pm_v9.py` copies the frozen native clock v9
source, adds those modules and `AddressSpace::reserve_native_pm_alias`, and
creates a distinct source/build owner. Draft2 actually compiled and linked the
module, with zero errors and 42 warnings from the still gated driver. No module
was loaded. The allocator is typechecked but its runtime call is not yet joined.

`out/gpu-gravity-native-pm-v9-qualification-v3/qualification.json` compares the
actual Rust constructor with independent native reset and concrete scene models
for 96 varied scene/state/block capacities, block maps and scene geometries.
Seven complete logical owners, whole descriptor preservation, exact three
firmware translations and native scene budget arithmetic agree. Each case also
checks eight refusals. Actual native producer receipts are composed; no exported
triangle/PM fixture is used as initialization bytes.

## Final caller addresses

The actual driver at 8a225bc loads PM20 through descriptor d68. The pair at
manager50 gives counter CPU mapping in x10 and HW-state map158 in x9. Stores
8a225c4 and 8a225c8 copy x9 into descriptor1220 and908. Store8a225cc copies x10 to
940, a host operation-counter pointer. The earlier null fields in research
constructor fixtures omitted this actual caller. Numeric rows and binary pins
are in docs/evidence/2026-10-11-native-pm-descriptor-owner-v9.json and `.dis`.

TA translations are descriptor1220/1228/1250, to command20/28/30. Ordinary3D
translations are descriptor908/910/938, to command28/30/38. Both consist of the
native HW-state alias, selected auxiliary entry, and auxiliary end. The selected
scene record is separate, referenced by descriptor1230/918. Host940 must never
receive a fabricated GPU pointer; NativePm::increment implements that host
operation count and mirrors the real four-byte resource before publication.

## Owned allocation and layout

Geometry remains an explicit caller input. AllocationPlan computes eleven
separate logical resources, each with its own 16KiB-aligned mapped subrange:
HW-state c0, counter4, config80, auxiliary scene_count*80+40, scene records
scene_count*80, frame indices capacity*8, page-list capacity*factor*4, discard
8000, scene payload stride*(state_count+optional extra), and two registration
pools scene_count*registration_stride. Sizes in this paragraph are hexadecimal
except the identifiers and the expressions' input counts.

The allocator reserves the client alias range from the existing private render
arena, owns every physical page in FirmwareSpace and maps exactly those same
physical pages into the client UAT. Linux user/device addresses are the same
private client alias; firmware translations return the separate firmware alias.
Both aliases use uncached memory attributes. Actual parameter blocks come from
existing alloc_tvb_blocks: 20000-byte mappings, 8000 alignment, 8000 guard stride.
Native frame indices use the real mapping shifted15; four successive32KiB page
entries describe each block. Donor CONTEXT_BASE-relative indices are not copied.

The source resets native config and HW-state fields, prepares the initial real
block/page arrays, and constructs80-byte scene records. Scene0/8 are registered
pool firmware addresses; scene28 is the mapped scene-payload device address;
scene40 is mapped config+40. No user cycle value replaces scene28. loadPBDesc
clears scene48; a fresh owner initializes it to zero already.

No built-in T6040 device geometry policy is claimed. In particular, research
fixture divisor128/fixed8/per-unit64/alignment64 does not establish actual chip
policy. Existing Linux budgets such as eleven initial blocks, MAX_BLOCKS
capacity and36 scene leases can be preserved as explicitly selected policy.
Scene budget parameters, support count, native count154/15c and parameter1d4
must come from the selected native configuration or a recorded Linux experiment.

## Runtime integration contract

The global firmware VA allocator reserves AllocationPlan::mapped_bytes before
calling NativePm::new. It returns all typed OwnedRoles/Geometry and physical
aliases, a packed descriptor, scene leases and the operation counter. The caller
binds descriptor fields with bind_descriptor and passes translations(v) to the
native controller envelope. SceneViews exposes the real leased record/header
and scene-payload address. NativePm::new issues no packet or descriptor-table
publication. Existing ASID invalidation/context binding must follow its PTE
edits before announcing the packed PB descriptor or the first job.

All physical pages remain FirmwareSpace-owned. NativePm has no individual free
or rollback; partial mapping failure must preserve existing Bootstrap,
FirmwareSpace and AddressSpace retention. Once a device-visible reference is
published, none of those owners may be dropped on ambiguity. Release a scene
lease only after both stages and their events retire. Native growth needs its
own block/page publication proof; the donor TVB wire-image grow path must not be
applied to these resources. Root owns the final submit_render_pool call and
queue-publication integration. No hardware or frozen v24 candidate changed.
