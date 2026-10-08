# Assembled native G16 3D generator trace

The complete common parent generator (0x89df73c..0x89e1df4), SPM helper,
empty-table overrides, native append and entry encoder execute together in
emulated RAM. 128 synthetic descriptor fixtures return normally. All384 SPM
helper outputs match the independent recipe using full backing comparisons;
all128 final descriptor patches match the independent metadata model. Native
code hashes, output hashes and fixture counts are recorded in JSON.

This qualifies integration of the pieces. Phase0's complete register recipe is
observed native output, **not yet independently modeled**. The fixtures are not
valid rendering jobs: pointer trees and resource map results are synthetic,
allocation/coherency behavior is absent, and shader/target preparation is not
reproduced. PAC is bypassed for unsigned fixture pointers. No hardware touched.

## Resolved native callback values

Matched AGXAcceleratorG16X vtable0x7eae388, address point+16:

| Slot | Native target | Symbol and returned value |
| --- | --- | --- |
| 0x10e8 | 0x89e7fe4 | halGetAgxCrUmaDefaultDupmMinCount:1 |
| 0x10f0 | 0x89e7fd8 | halGetAgxCrUmaDefaultDupmMaxCount:2 |

Both three-instruction getters execute natively in the assembled audit, rather
than being stubbed. Parent calls them at0x89e1534/1560. It combines results as
min OR(max<<32). Field semantics beyond their symbol names are not established.
Exactly one external service remains stubbed: the same resource virtual slot158
used in the SPM helper returns a synthetic mapped address. Depending on the
optional descriptor+0xb80 path, a fixture makes1 or4 calls to this service.

## Phase-zero count exception explained

The parent initializes command+0x80/+0x84/+0x88 at0x89e17d4..17f4. It later saves
phase0's current entry count from command+0x7a8 into command u16+0x80 at
0x89e1a4c..1a50, immediately after a flag1 entry for register0x1730/value1.
It then appends a flag0 entry for register0x16020/value1 and continues with tail
entries, saving other count checkpoints at command+0x82/+0x84/+0x88.

Final descriptor phase0 count+0x830 uses the saved command+0x80, whereas its
backing's final count remains at command+0x7a8. In the128 fixtures, the latter
exceeds the exported count by4 or6. Thus the asymmetry from the earlier metadata
audit is a deliberate saved prefix boundary in the native code, not a typo or
an interchangeable count field. Exact GPU semantics of that prefix/tail remain
unverified. Do not export the final total for phase0 as a symmetry shortcut.

Other phases' exported counts match their final backing counts. All four byte
cursors equal12*final_count in these fixtures. All four exported GPU addresses
match descriptor+0x440 + phase*0x720 +0xa0.

Phase0's directly written initial entry bypasses the virtual encoder hook;
recorded native encode-call counts therefore are not total entry counts.

## Fixture scope and next work

Numeric descriptor fields+0x600..0x7f8 vary between random u64 and zero. Fixtures
also vary dimensions16/32, sample selector1/2/4, optional+0xb80, flag bytes897,
88e/88f, accelerator+6d0 and a nested byte54 controlling extra parent appends.
Mandatory object pointers at descriptor190/918/b90 and acceleratorf598 are
synthetic. They describe which reads need backing; they do not establish those
objects' complete layouts or semantics. Empty override table is synthetic too.

Next trace the full phase0 numeric sequence into an independent model, then
trace preparation of its descriptor inputs, especially executable shader/state
and render-target resources. Mapping context/cache policy, job sizing, kick
MMIO offsets and firmware completion still require qualification before a live
job. Retained warm INIT failure still requires a normal reboot before hardware.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-3d-generator.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/3d-generator.json
```
