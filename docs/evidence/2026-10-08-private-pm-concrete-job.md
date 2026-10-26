# Concrete PM scene/block/page preparation through native hardware ring load

Offline private-derived AGX353.14/Apple25G83. This batch replaces the previous
PM virtual150 readiness fixture with actual concrete setupSceneState, then
replaces its parameter-block creation fixture with the actual concrete creator.
No live GPU calls, allocation, kernel changes, reboot or public push.

## Checked native methods

All numeric offsets/addresses and sizes in this document are hexadecimal.
Ranges include successful paths and diagnostic/failure branches unless the
qualification explicitly says otherwise; executing one path does not qualify
all those branches. Each JSON pins the full Apple binary SHA and native ranges.

| Audit | Actual method/range | Cases/results |
|---|---|---|
|scene-setup|setupSceneState89fefb0..89ff3a4|512 success;2044 created-block fixtures,4352 scene objects,256 support resizes|
|concrete-init|entire initializer plus actual scene setup and discard getter|256 full-object success checks; block creation external|
|block-create|createParameterBufferBlock89febec..89fef68|512 success,128 early ring-full returns;256 eligibility checks/resizes|
|concrete-block-init|full init + actual setup + actual block creator + native HWPB factory/reset|256 successful combined whole-object checks|
|block-prepare|prepareParameterBufferBlock89fea44..89feafc|1024 complete PM/block/page-array comparisons|
|page-list|buildPageList89fb414..89fb658|1024 successful full-object/buffer checks;6252 page entries,512 new mapping fixtures|
|concrete-job|combined init -> block prepare -> page builder -> PB job binding -> G16 packed ring load|256 chains checked at each data boundary|

Tools are experiments/t6040-gpu/audit-private-pm-NAME.py, with corresponding
JSON docs/evidence/2026-10-08-private-pm-NAME.json. `private_pm_scene_setup.py`
contains the independent numeric setup model. The page and block models use
explicit struct writes independent from the emulated instruction sequence.

## Concrete setup behavior

The setup allocates PM248 as an array of capacity148 *8 bytes, clears PM250,
and clears config98 words0/4/8. It creates max(PM14c,PM150) initial blocks,
publishes them in manager vector1a0 by each block's c ID and increments PM138
by20000 per block.

Memory budget uses accelerator11188, or memory-provider1028(argumentc000000)
when zero. It rounds to8000-byte units, divides/rounds by PM1e8, optionally adds
an accelerator4e4/PM64/68-dependent group allowance, then computes an aligned
stride from PM1f0/1f8/200. The complete arithmetic is in the independent model;
fixtures use valid nonzero divisors and power-of-two alignments.

PM58 backing size is stride * state-count60, plus an extra stride when
acceleratored48 bit0 is set. Each scene selected through PM88 gets10..1f zero,
20 zero,28=resource map + stride * (scene index mod state-count),40=PMa0,
and optionally30=shared extra-stride address. Field30 is preserved when that
feature is off. Scene count uses acceleratorf528 override or718 fallback.
PM220 allocation requests state-count bytes. PM240 requests an8000-byte discard
resource. Both resource requests use the previously checked bit47 flags/range.
Resource mapping160 and support-size checks use the actual nested object path.

The concrete discard-page getter89fe3ec follows PM240->resource20 and invokes
that object's160 mapping. The combined initializer now executes this actual
method during HW reset rather than supplying a PM208 return directly.

## Block creator and capacity constraint

The native creator uses config98 word0 as current ID, and word8 as completed
cursor. Next ID wraps modulo capacity148; equality with completed cursor returns
null before allocations. **One slot is reserved: capacity1 starts full.** Thus
earlier initializer fixtures that supplied a successful creator at capacity1
do not establish a valid native configuration. The actual combined block/init
checks use capacities2..33. Standalone creator uses capacities2..16 and tests
128 full-ring returns explicitly.

Creation initializes a block object, requests memory of20000 bytes with8000
alignment and flags accelerator18e00 OR100063, creates/maps its resource through
an external registration provider, conditionally checks mapping eligibility,
resizes support when needed, sets blockc=current ID and block18=mapping object,
advances config word0, appends the mapping at PM248[PM250], increments PM250,
and retains/releases the block in the actual native publication order.

Allocator, inherited initialization, memory-descriptor/resource/provider and
retain/release services are explicit fixtures, with argument/order checks. The
combined harness uses disjoint backing allocations for objects and tables;
an initial overlap in the new harness was corrected before the passing receipts.
No actual allocation capacity, DMA ownership or object lifetime is established.

## Block page index and native page-list construction

Concrete block preparation invokes block virtual140, then block18 mapping160.
It writes `(mapping_address >>15) &1ffffff` as u32 to PM90 + blockID *8, preserving
the adjacent word, and sets block10 byte1.1024 cases test IDs0..31 and randomized
mapping addresses. These are numeric results, not valid live-address proofs.

The page-list builder follows the current HWPB manager's resource and either
uses or creates its CPU mapping in resourcea0. It writes state34 as the low32
product `(PM138 >>17) * PM1d8(u32)`, state54=count-1, clears manager34..43,
and stores staged/completed cursors at state3c/40.

For valid completed/staged ring indices, PM70 selects page-expansion geometry.
Units8000/10000/20000 expand source indices into consecutive u32 page values;
the source block ID is separately loaded through vector1a0. Wrapped cursor
ranges and preserved destination tail bytes are checked. Zero, sub8000 and
above20000 values characterize native early-no-copy behavior; they are not
recommended live settings. No source-index clamp is invented beyond the native
block preparation's25-bit conversion.

## Combined job preparation

The concrete-job audit reuses the block, scene, manager and hardware state made
by the actual initializer and actual creator. It then calls actual block prep,
actual page builder, actual loadPBDesc, and actual G16 halLoadPBDesc. Intermediate
whole-object comparisons check each boundary, not just final return values.
One initial block, completed cursor0/staged1, PM70=20000 and factor1d8=4 produce
four page entries. Requests0..31, positive state counts1..8, capacities2..33,
both mapping flags and optional shared-scene behavior are covered.

**Manual orchestration proves dataflow under explicit fixture services, not
native caller ordering or the entire prepareAndRetain lifecycle.** Resource and
memory creation/registration, retained-mapping preparation, cast/context/map
services, external translation and CPU mapping pointers remain external.

## Reproduction and next required work

Run each audit with the pinned private input and a numeric output path:

```
python experiments/t6040-gpu/audit-private-pm-concrete-job.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X \
 docs/evidence/2026-10-08-private-pm-concrete-job.json
```

Next execute prepareAndRetainPageListMapping89fe494..89fea3c and actual
releasePageListMapping89fe44c, then replace those and block/page services in the
complete retention/job path. Identify the real caller ordering and TA descriptor
association. Only after those match, connect matched TA/3D work objects/register
recipes to Linux-owned mappings/root/KSM queues/event/stamp lifetimes and actual
publication/completion/readback. Fixture/donor objects remain non-submittable.

Failed warm INIT remains retained on bootfa78dd48-b214-46fc-8786-cae63897ad78.
A normal reboot is still required before live GPU integration; offline methods
remain available. No forced unload, reset or warm retry. No triangle or GPU
accelerated desktop, and not yet submission-only readiness.
