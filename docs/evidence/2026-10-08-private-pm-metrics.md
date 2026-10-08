# PM metrics registration supplies the previously omitted resource

This supersedes the PM50 gap in private-pm-mapping-lifecycle.md. The earlier
initializer fixture omitted a required output of its external registration
service. It was not evidence of a native missing allocation or driver bug.
All numeric offsets and addresses here are hexadecimal. Input AGX353.14/25G83
SHA is pinned in both numeric JSON receipts; no live GPU commands were executed.

## Evidence and caller contract

PM init89fc624 first makes X21=PM48 at89fc6b0, then X22=PM50 at89fc6f4.
At registration call89fcf1c, X1=PM, X2=PM48 (index output), X3/X4/X5 are
CPU/map output addresses on the stack, and X6=X22=PM50. The vtable228 service
was previously modeled as setting only index and three map pointers. It must
also return the retained metrics resource through X6.

Actual requestPMPageMetricsBuffer89f740c..89f7890 loads the selected allocation
record's8 resource, writes it to `[X6]` at89f7530 and invokes its virtual20
retain at89f754c. This explains why later base prepareAndRetain can prepare
and retain PM50 and publish it at TA db8. The original zero PM50 was an audit
fixture omission, now corrected in audit-private-pm-creation.py with an explicit
sixth-output assertion and independent whole-PM expectation.

The native input's AGXGart method is used as the concrete registration endpoint.
The emulator supplies the provider/endpoint object; live endpoint identity and
the registration-provider implementation are not established by these checks.

## Standalone native method audit

audit-private-pm-metrics.py executes1024 complete calls and checks full pool,
bitmap, allocation-record and output bytes against an independent numeric model:

- 512 successful existing-pool allocations and512 empty-pool returns;
- groups0..7, first free bits0..63, singleton and non-singleton masks;
- slots per allocation64/128, strides4/8/10/20;
- all combinations of optional three map outputs,768 output writes;
- 512 resource-output/retain paths and256 support resizes.

The selected slot is first-set outer-group*40 plus first-set inner-bit. The
selected allocation record is `slot / pool60`; offset within the resource is
`(slot % pool60) * poola0`. The block vector uses its encoded48 byte span; these
fixtures cover zero upper bias and enough lower span. Each success increments
the allocation record's0 u32 counter and clears the corresponding free bit.
If its inner word becomes empty, the outer group's availability bit is cleared.
Then it unlocks, writes the slot index, and applies support-size policy.

The three optional outputs derive from resource50 virtual158, resource58
virtual158 and resource60 virtual138, respectively, plus the slot offset.
The sixth output always receives the resource on success. Empty pool returns0
and indexffffffff; the remaining outputs are preserved. Existing backing only
is tested; lazy pool growth, low-water mode1 and invalid-span traps remain open.
Standalone block vector entries alias one record, explicitly a fixture choice.

Retain/map/mutex/support services are external argument/order fixtures. These
results establish arithmetic and native publication, not live address validity,
cache coherency or kernel/firmware ownership.

## Joined concrete initialized-job audit

audit-private-pm-metrics-job.py replaces the original registration fixture with
the actual native method inside the complete PM initializer.256 cases then
continue through actual concrete scene setup/block creation, HWPB factory/reset,
block preparation, page-list construction, PB binding and packed hardware ring
load. Existing whole-object/buffer comparisons remain in place, including PM50;
extra checks require the exact retained resource, incremented allocation-record
counter and consumed singleton free bit.

Cursor0..1f, pool slots40 and caller stride variants are covered. Fixture map
bases are chosen so the method's derived outputs match the prior independently
modeled pointers. This models native offset derivation; it does not validate
those fixture addresses for a live GPU. Parent creation/full-init/HWPB/job/scene/
block audits are rerun after the correction, so their current receipts include
the sixth output instead of perpetuating the original omission.

The ordinary retention audit still needs joining to this initialized-job chain
and actual caller ordering. Native pool growth/release, pending/mode2 page mapping,
Linux allocations/root/work/KSM queues/events/stamps, publication/cache visibility
and actual completion/readback remain. Submission-only readiness is unproven.
Failed warm INIT remains retained; normal reboot before live trials, no forced
unload/reset/warm retry.
