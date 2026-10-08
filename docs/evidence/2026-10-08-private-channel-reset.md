# Channel reset prefix and type-1 notification transport

Private-derived matched AGX353.14 / Apple25G83 analysis. No hardware trial.

## Actual channel reset differs from the earlier candidate codec

The call-free prefix of `AGXChannel::resetChannelState` at
0xfffffe000897dea8..0xfffffe000897df50 clears exactly 0xc0 bytes at
channel object's +0x58 pointer, then installs:

| State offset | Width | Native source/value |
| --- | --- | --- |
| +0x00 | 8 | Channel object +0x88 |
| +0x08 | 8 | Channel object +0x90 |
| +0x10 | 8 | Channel object +0x98 |
| +0x24 | 4 | 0xffffffff |
| +0x28 | 4 | 4 |
| +0x44 | 4 | 0xffffffff |
| +0x48 | 4 | Channel object +0x4c |
| +0x9c | 8 | Channel object +0xf8 |

The adjacent host pointer at channel +0x60 supplies a separate queue structure.
The prefix writes capacity at +0x60, zeroes u32 words at +0/+0x10/+0x20/
+0x30/+0x40, and writes **0xffffffff at +0x50**. All other queue bytes remain
unchanged by this slice. State +0x18/+0x1c/+0x20 are zero; channel +0x70 and
+0xd8 are also cleared. Later code may change values before publication.
Pointer meanings and full queue allocation size are not established here.

The earlier `g16s_abi.rs` candidate only populated a subset of channel state
and initialized the queue prefix to zero. Neither constructor is currently
used to submit live jobs. Do not silently replace it with this reset prefix:
reset and final creation are different operations. `private_channel_reset.py`
provides a separate numeric model with explicit source inputs.

The actual instruction slice and independent model agree in 256 randomized
cases with prefilled memory, capacity boundaries and sentinel checks.
Bytes beyond the state extent and untouched queue/channel bytes remain intact.
This validates the prefix, not a complete valid render-job constructor.

## Type-1 event notification mask

Native general-event dispatch reads type-1 payload u64 words at record +4 and
+12. Together they form 128 notification bits. It reads a u16 at +20 and
requires it below 24 before the loop. The loop enumerates set bits in ascending
order and calls external target 0xfffffe000a7cf84c with:

- x0: accelerator object's +0x140 pointer;
- x1: notification index 0..127;
- x2: zero.

The callback implementation is outside this extracted driver. Do not claim
that this alone establishes fences, cache completion or safe allocation reuse.

`audit-private-event-flags.py` executes the reviewed loop only, replacing the
four calls to that target with a register recorder. Empty/full masks, all 128
single-bit positions and 64 deterministic random masks pass (194 cases).
No external service code executes. The read-only receive decoder now emits
these observed fields alongside unchanged raw bytes; it flags a selector >=24
without inventing a protocol meaning for that selector. Four decoder tests pass.

## Next work

Trace source pointer +0x98 and channel-state creation after reset, then trace
work-queue command encoding/publication and the external notification callback.
Correlate these fields with actual firmware consumers before first-job testing.
Current retained warm probe still requires reboot before another hardware batch.
