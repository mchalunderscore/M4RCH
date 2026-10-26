# Native Fender enable transfer for the first draw

The distinct v18 `gfx-native-fender-draw-cycle` tests one source-backed operand:
fresh `old & ~6` at logical SGX `d06030`, with one 32-bit write and fresh
readback. It runs after fresh firmware control33 and before the first draw
intent or publication. This is a transfer hypothesis about active submission,
not a demonstrated teardown operation or a complete native kick sequence.

The matched AppleAGX353.14 / Apple25G83 binary has SHA256
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
The companion [numeric evidence](2026-10-10-gfx-native-fender-enable.json)
records hashes of the native methods, provider entries and saved v17 logs.
Private binary bytes and full disassembly remain outside committed evidence.

The native `AGXKSMKickQueueG16::addKicks` at `fffffe00089dc240` checks
accelerator `6d3` bit3. When set, the exact order is:

1. Fender virtual58 at `89dc334`: fresh `old | 4`, write, readback.
2. Direct 64-bit SGX `4090` store at `89dc33c`:
   `0020040000021018 | (queueID << 43)`.
3. Direct 64-bit SGX `4098` store at `89dc340`: zero-extended u32 count.
4. Fender virtual50 tailcall at `89dc390`: fresh `old & ~6`, write, readback.

The native provider chain is queue `68` to accelerator `5b0`, firmware
`210`, then Fender virtual58/50. Its G16X factory and both methods are bound
by the actual native vtable entries. Existing connected native emulation
passed 2048 cases in both access modes; it was not repeated for this work.
The enable leaf at `89d8358..89d8448` reads logical register `d06030` and
preserves every bit except bits1/2. Mode1 resolves the register through
accelerator `f8e8` and logical bias `c980`. A captured ADT supports physical
`288d06030` conditionally on native service register ordering; the experiment
uses its already owned 16K page at `288d04000`, offset `2030`.

Native `setFenderPowerEnabled(false)` calls virtual58, the disable operation,
before conditional provider vote-disable calls. The ON branch calls
virtual50, the enable operation. This evidence does not support clearing six
as a teardown or physical BUSY reset.

Saved v17 boot `e7288eeb-bc71-46e3-a0c5-831b77bebb1d` already read six at
`d06030`; the preASC literal-six operation wrote six and read six back.
After the native NMI and successful CPU stop / coordinate OFF / PM put,
all 101 physical OFF samples were `0f000b00`; mask `90001cff` leaves
`800`. No ON was attempted. These observations motivate testing the native
active enable operand, but do not prove that six caused the residual BUSY.

The [actual helper](../../experiments/t6040-gpu/gfx-native-fender-draw-cycle/gfx-native-fender-enable.h)
retains the existing mapping, PM reference and all GPU backing. It requires
unchanged owner identities, preASC completion, fresh physical ON and control33,
no draw intent, records, producers or notification. It consumes its one-shot
intent even on refusal. A fresh GPU ID must match the preASC ID; an all-ones
register read is rejected. It writes once, verifies exact readback and issues
`DSB SY`. Failed attempted writes remain unknown and retain all resources.
The additional full barrier is experiment ordering, not a claim about an
instruction in the native enable leaf.

The [actual C qualification](../../out/gfx-native-fender-draw-cycle/fender-qualification-v1.json)
passed 45 ASan/UBSan cases. They exercise unrelated-bit preservation, fresh
baselines, ownership and state refusals, invalid reads, dropped writes,
post-write identity loss and a second call with no additional effects. The
ARM64 barrier is replaced by an asserted fixture barrier; MMIO and existing
owner services are bounded RAM fixtures. This proves helper behavior, not
real hardware, firmware acceptance, retirement, rendering or power completion.
The [actual owner hook review](2026-10-10-gfx-native-fender-enable-owner-hook-review.json)
pins prepared-owner-v1 receipt
`45d2017114725882e7bec1bbbd60f2211888c3f5f5d7f3159174cdf0da2ce6a1`.
Its locked `gfx_cold_run` orders fresh control, helper, then draw publication;
helper failure reaches retained software stop before any draw intent. The
copied helper matches the actual C qualification. This is static placement
review; the parent builds and qualifies the actual module separately.

The experiment keeps the existing firmware-mediated root work and EP33
notification. It does not write direct `4090/4098` kicks or claim EP33 is
native `addKicks`. Native guarded `addKicks` enables after its direct stores;
v18 transfers only enable before the existing firmware notification. The
equivalent native caller flag and ordering on this mediated path remain
unproved. No scheduler ACK writes, teardown clears, rejoin replay, resource
release or same-boot retry are introduced.
