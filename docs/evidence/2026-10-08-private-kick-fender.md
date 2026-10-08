# Native Fender gating connected to scheduler kick writes

Private-derived matched AGX353.14 / Apple25G83; offline only.

## Callback identity and provenance

The previously synthetic callback pair is now identified. Firmware initializer
`89acfa8` calls accelerator virtual`0xbd8`, then `89acfac` stores its returned
object at firmware`0x210`. The actual G16X accelerator vtable at`7eae388`
resolves that slot to `AGXAcceleratorG16::halNewFenderController` at`89d81cc`.
The factory installs `G16::AGXArmFenderChinook` vtable`7eabd90` (address point+16).
Its slot58 resolves to native `disableDynamicFenderGating` at`89d8268`;
slot50 resolves to `enableDynamicFenderGating` at`89d8358`.
These vtable entries are decoded and asserted from the matched binary. The
initializer/factory control flow is inspected, not fully emulated.

## Native register behavior

Both complete Fender methods execute inside complete native `addKicks`:

1. Read logical GFX register`0xd06030`.
2. Disable dynamic gating by writing `old | 4`, followed by a readback.
3. Write scheduler control at supplied kick MMIO base+4090, then count at+4098.
4. Read the Fender register again.
5. Enable dynamic gating by writing `old & ~6`, followed by a readback.

Thus the operation is not a generic mutex bracket, and enable is not an exact
restore of the incoming register: both bits1 and2 end cleared. The semantic
names derive from native symbols; hardware bit behavior is not independently
measured by this offline audit.

Native mode selector is accelerator`0xc774`. When it equals1, Fender methods
use the supplied mapping at accelerator`0xf8e8`, adjusting logical register
addresses by the configured offset at`0xc980`. The read path loads that offset
as64-bit, while the write path loads32-bit. The fixture supplies a consistent
zero-extended offset, not arbitrary upper bits. Other modes call
`readGFXReg32`/`writeGFXReg32`; these two providers use explicit synthetic
register-access contracts in the checker.

## Verification

```
python experiments/t6040-gpu/audit-private-kick-fender.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-kick-fender.json
```

2048 connected cases pass: all128 valid seven-bit queue IDs, eight count values,
and both generic-provider/direct-mapping paths. Initial gate-register bits vary
randomly. A combined event trace verifies callbacks, reads, writes and readbacks
in order. Whole accelerator, queue, kick MMIO backing and Fender mapping page
comparisons check exact changes and preserved bytes. Counts above65535
characterize native encoding; they do not establish valid pending-count ranges.
Native PAC instructions are bypassed; tracing is disabled.

## Implementation implication and remaining gap

The native G16X flag producer from the preceding audit selects this
Fender-bracketed kick path unless later code overrides it. A first Linux kick
implementation needs the corresponding power/gating precondition and readback
ordering, alongside submission visibility. Reuse of the native constants alone
would omit a real part of its submission sequence.

Physical mappings for accelerator358 and Fenderf8e8 remain unresolved here.
No real MMIO, power-transition handshake, concurrency, cache coherency, firmware
acceptance/completion, shader execution or rendered pixels is proved. No
kernel/default changes. Retained warm INIT still needs a normal reboot before
hardware trials. No private binary/full disassembly exported.
