# Initialized parameter buffers through retention and native TA binding

Private implementation-derived numeric research, AGX353.14/25G83. Offline
Unicorn execution only; no GPU command, kernel change, resource reset or reboot.
This closes the earlier gap between the concrete initializer and the separate
ordinary-retention fixture. It does not establish a submittable complete job.
All offsets below are hexadecimal.

## What is joined

256 actual full parameter-manager initializers include actual metrics registration,
concrete scene setup/block creation and native HWPB factory/reset. Each resulting
object graph first runs the complete native TA parameter loader8a20cbc..8a20ea0,
including its actual3D tail and both sets of three native zero getters. The
actual allocated vectors supply values; whole1800-byte descriptor and unchanged
PM/vector comparisons pass. The TA caller window8a22504..8a22534 then dispatches
the whole ordinary `prepareAndRetain` method89fa7a8..89fb0d4, with its actual
argument construction checked. Capacity2..33, one initial block, config write1/read0/done0.
PM28 remains the initializer's actual value1. We do not change it to0 to obtain
the older reused-page fixture path.

The actual page-mapping method89fe494 calls actual release89fe44c with a null
old mapping, then creates a fresh mapping. Its two arrays have capacity64/count1,
contain the created GART and its backing support object, and total length20000.
Full object/array bytes, including untouched trailing storage, are checked.
Actual page-generation getter89fe440 returns1. The retention ring loop calls
actual block preparation89fea44 and actual page builder89fb414, producing four
32KiB frame entries. The resulting staged cursor is1 and PM28 becomes3.

The TA descriptor retains these same initialized identities:

| TA field | Resource |
| --- | --- |
| d78 | Newly created page mapping |
| d88 | HWPB kernel resource20 mapping object |
| d90 | HWPB28 mapping object |
| d98 | Discard backing inner object |
| da8 | PM40 internal resource |
| da0 | HWPB90 internal resource |
| dc0 | PM30 internal resource |
| db0 | PM58 scene resource20 inner object |
| db8 | **PM50 metrics resource produced by actual registration** |

There are2,304 checked descriptor attachments and1,024 generated page entries.
Full PM, HWPB,1800-byte TA backing, staged/config/block/frame/page/state buffers
compare against explicit numeric expectations.

## Actual TA caller window

The same retained graph next executes actual TA `prepare` instructions
8a22be4..8a22c4c. This now executes actual TA UMA lock/validate8a20c0c and
its full native `canSubmitLocked`8a29f88..8a2a080 for both pools, followed by
actual TA UMA usage update8a20b48. Pool seeds and successful event comparisons
are explicit inputs. Randomized node flag bytes cover both dirty-bit states;
full pool/node comparisons check that only reached low-bit dirty flags clear.
Logical lock ordering matches: pool0 lock, pool1 lock, usage updates, pool1
unlock, pool0 unlock. Real concurrent mutex behavior is not tested.

The caller then invokes actual PM usage-event update89fe138..89fe1b4,
then actual `loadPBDesc`89fe1b4 and the actual G16 packed hardware-ring loader.
256 bindings cover request indices0..31. PM/HWPB/state/ring/scenes/TA/page bytes
are checked after this caller window, rather than manually passing independent
replacement objects into `loadPBDesc`.

The usage updater makes two argument-checked external event-service calls per
case: TA dc8 with kernel-resource18+40, then TA80 with kernel-resource18.
These512 calls establish argument flow, **not event contents or fence behavior**.
Other intervals of full TA `prepare` remain omitted, including the interval
between the retention and binding windows. We execute two actual windows with
manual orchestration between them; full caller ordering is not claimed.

## Explicit fixture limits

The PM-specific initializer does not initialize PM258 and PM1d0. This harness
explicitly supplies inherited-constructor outputs0 for those fields before
initialization. Resource support providers, retain vtable methods and mapping
length are explicit external constructor/service fixtures; their implementations
are not inferred from zero-filled RAM. Mapping preparation and support generation
services remain argument-checked fixtures. UMA mutex/event-copy/comparison
services are also explicit fixtures; optional host tracing is disabled.
No actual allocator, CPU/FW physical
identity, cache visibility, firmware publication or retirement is established.

After verifying the independent joined branch, the harness restores its emulated
RAM and runs the parent manual PB-ring comparison. It does not concatenate those
two branches into one live command stream. Binary and instruction bytes remain
private/local; the exported JSON carries image and method-range hashes only.

## Next work

Parameter-data loading and the earlier UMA lock/update are now joined on the
checked success path; companion private-uma-validation.json also covers failure
unwinds. Assemble the complete matched TA/3D work and microsequences
from the Linux-owned resources and our shaders/target, not base-M4 donor objects.
Resolve completion payload identity and retirement before resource reuse. The
running failed warm INIT still pins probe resources; a normal reboot is needed
before live integration. Offline preparation remains available now.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-pm-initialized-retain.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/initialized-retain.json
```
