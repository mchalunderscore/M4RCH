# Native parameter-manager creation through hardware descriptor-ring load

Private-derived AGX353.14, Apple25G83, offline Unicorn only. No GPU commands,
kernel changes, live allocation, reboot or firmware acceptance in this batch.
The Apple binary and extracted executable bytes remain local and excluded from
handover exports. Numeric tools and receipts are reproducible against the
pinned binary SHA recorded in each JSON.

## Complete initialization

`audit-private-pm-native-hwpb.py` replaces the prior final HWPB factory fixture
with the actual native factory89fd3a8..89fda5c and nested HW reset89fb720..89fb8f4.
256 entire PM initializers return1 with restored stack. Full PM, manager, hardware
state, counter, vectors, scene records and registration scratch compare with
independent struct models. External services are checked for arguments and order.
Both accelerator6d0 bit47 allocation-flag branches pass.128 cases release an old
manager in the initializer,128 resize the support object before mapping.
The factory's own old-manager replacement branch is not exercised: initialization
already releases/clears the old pointer before the factory runs.

Offsets and sizes below are hexadecimal:

- Kernel resource size is PM148(u32) * PM1d8(u64) *4 modulo64 bits.
- Bit47 clear requests flags4000000003/range5; set requests5000000003/range1.
- The factory requests an internal hardware-state resource ofc0 and a counter
  resource of4 bytes, with accelerator18e00 OR63 flags.
- Manager88/90 own those internal resource objects; manager48/50 hold the
  CPU-dereferenced mapping results and58/60 the separate other mapping results.
  Mapping service roles depend on object class; a virtual-slot number alone does
  not identify CPU versus firmware address semantics.
- PM228 increments, PM20 binds the new manager, then the actual reset initializes
  the mapped state and counter. The manager's retained publication happens before
  reset and its final release after reset.
- The support-size comparison uses kernel-resource28 object's78(u32). HW-reset
  state30 instead uses kernel-resource78 low32. These are distinct objects/fields.

Inherited init, allocation, resource init, lazy-map prerequisites, registration,
PM readiness, statistics and mapping/translation services remain explicit fixtures.
The factory success path is actual code, but this does not establish valid Linux
allocation identities, capacity policy or firmware visibility.

## Per-job binding and hardware packed ring

`audit-private-pm-pb-load.py` runs actual loadPBDesc89fe1b4..89fe330:
928 successful cases,464 first-use provider calls,96 expected generation assertions.
Modes use the low byte of the argument. Mode3 activates/snapshots a generation;
mode2 clears activation when its generation check passes. A first-use manager
writes request to HW state+c, calls accelerator virtual10f8, then advances
manager30 by2. Reuse skips that call. The selected scene's48(u32) clears.
Generation-mismatch assertions are stopped at their diagnostic branch entries;
the assertion provider itself is not executed.

The G16X encoded vtable at7eae388+16+10f8 resolves to89d6f54, the actual
halLoadPBDesc. `private_pb_ring.py` models its16-byte packed entry and the native
halStorePBDesc counterpart89d6eb4. `audit-private-pb-ring.py` checks1024 whole-ring
load/store roundtrips against independent bitfield calculations. Cursor quantities
are22-bit; saved bit31 and bit0 flags are extracted/restored. Address bit42 selects
an adjustment, and selected high address bits pack into the entry. Other entry
bits and all other ring entries are preserved. These facts do not establish a
live ring's capacity or acceptable firmware address range.

`audit-private-pm-pb-ring-chain.py` runs the PM job loader through the actual G16
provider,928 successes/96 assertions;464 native ring writes compare independently.
Only resource60 virtual138 returning the CPU ring pointer remains external in
that nested provider. Requests0..31 are tested, separately from scene index0..15.

Finally `audit-private-pm-job-chain.py` joins:

```
complete PM init -> native HWPB factory -> native HW reset
-> native loadPBDesc -> native G16 packed descriptor-ring load
```

256 joined cases compare whole PM/manager/state/counter/scenes/ring at both
initialization and job boundaries. The ring job uses the actual initialized
manager/state, not freshly invented replacement objects. First-use mode3 jobs,
requests0..31, scene index0. This is still an offline service-fixture chain.

## Reproduce

For each audit name below, run:

```
python experiments/t6040-gpu/AUDIT.py /boot/GPUC003/private-apple/com.apple.AGXG16X OUTPUT.json
```

- audit-private-pm-native-hwpb
- audit-private-pm-pb-load
- audit-private-pb-ring
- audit-private-pm-pb-ring-chain
- audit-private-pm-job-chain

JSON receipts with matching names are beside this document.

## Remaining implementation gaps

Do not mistake these numeric initialization and packed-ring tests for a
submission-ready Linux driver. Next trace ordinary prepareAndRetain89fa7a8..89fb0d4,
which prepares/retains mappings, binds TA descriptor resource objects, observes
mapping generations and stages page-list updates. Its staged outputs and
full descriptor association must be joined to the existing TA/3D recipes.

Then replace external mapping/allocation/registration fixtures with Linux-owned
resources, bind work/root/KSM queue/event/stamp identities, publish with actual
cache/ownership ordering, and connect a firmware completion consumer to retirement
and coherent image readback. Prepared donor TA/3D objects still have layout and
lifecycle gaps; they are not interchangeable with the native paths.

The existing failed warm INIT probe remains retained on boot
fa78dd48-b214-46fc-8786-cae63897ad78. A normal reboot is required before live GPU
integration; no forced unload/reset or additional warm retry. Offline work can
continue without macOS. There is no rendered triangle or accelerated desktop yet.
