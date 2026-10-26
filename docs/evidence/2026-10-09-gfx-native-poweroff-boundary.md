# GFX mapper and provider boundary after the native reset trial

This is a source-derived recommendation for a distinct future retained, no-work
candidate. No hardware, source API, owner, boot, mapping or power-state change
was performed by this review. The current boot's sealed owner does not admit
power-off, restart or backing release. The adjacent JSON binds the matched
25G83 kernelcache, the actual boot `a1f61d61` ADT, exact native ranges and
vtable slots, and the inspected Gravity Linux sources.

The concrete next observation is an ordinary suspend of the owner's GFX genpd
consumer, followed by the existing driver-owned GFX snapshot and DRAM-only
sampling. Retain all 174 pages, page tables, published mappings, consumer device
and module. A successful suspend return alone is insufficient: require
independent GFX `ACTUAL=TARGET=0`, `AUTO28=0` and software `domain_on=0`.

## The actual mapper is AGX UAT, not Apple DART

The current saved `gfx-asc` node's `iommu-parent=437` (`0x1b5`) resolves uniquely
to `/device-tree/arm-io/mapper-gfx-asc`. That node has compatible
`iommu-mapper,gfx`, and the matched AGX personality selects
`AGXArmFirmwareMapper` with provider `AppleARMIODevice`. It is not an
`AppleT8110DART` stream or DART register bank.

`AppleA7IOP::_setMapperActive`, `0xfffffe0008a43bd0..8a43c2c`, sends the
`setActive` platform function to its mapper. The actual mapper's
`callPlatformFunction`, `0xfffffe00089d37d4..89d38c4`, handles only
`retrieveVMLimits` directly and forwards other functions to inherited
`IOService::callPlatformFunction`. Its `IOMapper` super vtable resolves that
method to `0xfffffe000bf3905c`. The reviewed generic body forwards through
`getProvider`; the actual `AppleARMIODevice` also inherits this forwarding.

Saved `arm-io,t6041` selects `AppleH16GFamilyIO` from
`com.apple.driver.AppleT6041`. Its platform-function override and clock/power
overrides are resolved and bounded in the JSON. The platform override handles
two selected functions and otherwise forwards to its superclass; this review
does not resolve the terminal `setActive` handler or those initialized function
objects. Consequently **there is no qualified GFX translation-disable or drain
acknowledgement in the mapper method reviewed here**. This is not a claim that
the eventual platform call is a no-op.

Gravity Linux `apple-dart.c` has an `IOMMU_DOMAIN_BLOCKED` implementation, but it
targets registered DART stream maps, writes disabled TCR values, and rejects
locked DARTs. It has no completion/readback/drain check in the blocked attach
body. Applying it to an unrelated DART would not reproduce this GFX mapper.

The existing Gravity `asahi/mmu.rs` is the appropriate UAT base. Its cached
mapping teardown requires remapping uncached, TLB invalidation, a firmware FwCtl
cache-flush exchange with handoff completion, then unmapping and another TLB
flush. A wedged or stopped firmware cannot be presumed to complete that
exchange. Clearing retained UAT root entries or calling mapping destructors is
therefore not an acceptable substitute for an isolation observation.

## Provider identity and a usable Linux observation

The saved ASC clock and power gate lists both contain virtual gate401,
GFX-ASC. The saved PMGR descriptor makes its real parent GFX386, whose state
word is `0x288e80110`. The Linux provider already owned by this experiment is
`/soc/power-management@288e80000/power-controller@110`.

Native `AppleA7IOP::_enablePower(false,0)` calls the provider's clock-disable
operation for index0, then its power-disable operation for index0. It ignores
both statuses and returns zero. `AppleARMIODevice` translates index0 through
its saved gate arrays before delegating upstream; the matched H16 IO overrides
then invoke initialized platform-function objects. Their terminal PMGR function
binding and complete native refcount/notification semantics remain unresolved.
The saved parent graph qualifies GFX386 as the Linux power-off hypothesis; it
does not establish instruction-for-instruction equivalence with native power
disable.

Gravity Linux's normal `apple_pmgr_ps_power_off` calls the existing state method
with `PWRGATE=0`, `auto_enable=false`: it clears AUTO/command/target bits, writes
TARGET0, and polls ACTUAL0. This is a concrete driver-owned transition already
used by the pre-firmware GFX power test. Its generic implementation ignores
`regmap_write` errors, and the genpd runtime-suspend path calls a void
`genpd_power_off` and returns zero even when power-off is refused, deferred or
the provider callback fails. Those returns must never become OFF proof.

The root-collected software genpd summary after the current stop reports GFX
ON with only `m4rch-asc-crashlog` active, and AFR ON with child GFX. It is useful
eligibility evidence for a future normal owner suspend, not physical-state or
transaction-drain evidence.

The existing `apple_pmgr_t6040_gfx_snapshot` does not require the domain to be
ON. It identity-checks the bound GFX provider and reads its PMGR word under the
genpd lock while preserving register-read validity/error. It can supply the
independent post-suspend observation without adding a raw PMGR write API.

## Distinct future retained candidate

Use a fresh boot and a separate owner profile with one terminal power-off
attempt. Before that attempt, sample the native idle predicate and clear START
through the owner, retaining its graph, pages and mappings. Seal host packet
publication and operation admission before consuming the owner's single PM
reference with `pm_runtime_put_sync_suspend`. Keep the consumer attached; do
not enter the existing cleanup function, which unmaps/releases backing and
detaches the consumer.

After any OFF attempt, successful or uncertain, permit only driver-owned PMGR
snapshots and captures of qualified firmware-owned DRAM words. Do not access
ASC, SGX or mailbox registers: physical power may already have collapsed even
when the suspend return or software state is ambiguous. The current capture
helpers and owner predicates assume an active PM reference, so the future
profile needs explicit retained/OFF-aware capture admission.

For a qualified OFF observation require a valid PMGR read, software
`domain_on=0`, ACTUAL0, TARGET0, AUTO28 clear, and RESET31, DEV_DISABLE10,
PS_RESET12 and BUSY11 clear. Historical bits8/9 are not acknowledgements. Bind
the PM-reference accounting and each snapshot to the sole attempt. Sample the
same firmware-owned DRAM words over a bounded interval after OFF; changing
words contradict cessation of that observed writer, while stable words only
support cessation over that scope and interval.

Keep every page and mapping pinned on all results. No second suspend, automatic
resume, START, INIT, work submission, unmap, free, consumer detach or module
unload follows from this candidate. A normal OFF observation can test the
missing provider boundary without claiming mapper isolation or full drain.

## Remaining retirement and restart limits

ACTUAL0 plus stable qualified DRAM is stronger evidence than START-clear and
native ASC idle. It still does not establish completion of outstanding fabric
transactions, private cache writeback, all UAT contexts or all GPU DMA engines,
and cannot authorize freeing joined backing. The mapper's terminal `setActive`
effect remains unresolved.

Preloaded native fixup skips copying firmware DATA, saved GFX SRAM backup/restore
is unselected, and the reviewed stop/start paths do not program a reset vector.
Fresh firmware DATA, mapping/root lifetime and a repeatable restart protocol
remain separate requirements. No warm START/INIT-only retry is justified by
these findings.
