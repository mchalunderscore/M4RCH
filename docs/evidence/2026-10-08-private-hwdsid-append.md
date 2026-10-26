# HWDSID startup entry producer and its 16-entry bound

Matched private AGX353.14 / Apple25G83. Native append paths inside
AGXCommandQueue::populateCommandHWDSIDData, both3D caller argument slices and
descriptor initialization execute in RAM. Independent models compare full
outputs. 2,048 append attempts,512 caller cases and512 initialization cases
pass. No hardware touched. Binary/slice hashes and path counts are in the JSON.

This resolves the previous startup-entry-count question for the two traced
producer paths. The consumer's lack of a local guard is not itself evidence of
a native-driver vulnerability: the checked producer enforces a16-entry limit.
This does not claim every possible descriptor writer or untrusted input path
has been exhaustively examined.

## Caller and descriptor layout

Fast render caller8995768..899577c and ordinary render caller8998cc8..8998cdc
prepare these arguments to populateCommandHWDSIDData at89940f4:

- x0 command queue, x1 hardware command, x2 channel from queue838.
- w3=8, used as a filter mask by the larger function; **not** array capacity.
- x4=3D descriptor970, the HWDSID structure base.

Relative to that structure, entries begin at0 and use16-byte slots; its u32
count is at100. Thus the count is descriptora70, exactly the consumer field.
Native descriptor initialization895db6c..895dbc0 clears970..aa7, covering the
16-entry array, count and following notification-related storage.512 random
full-descriptor fixtures prove this initialization slice changes only that range.

## Bounded appends

Both producer paths test current u32 count against15 using unsigned comparison.
Counts0..15 permit an append and increment to1..16; count16 or larger leaves the
entire structure unchanged. Cases include17 andffffffff, guarding signedness.

| Entry offset | Written field |
| --- | --- |
| u64+0 | selected address |
| u32+8 | current w26 numeric length/size |
| byte+c | HWDSID low byte |
| byte+d | **unchanged** |
| u16+e | current w22 low16 if enable bit0, otherwise0 |

This matches the startup consumer's fieldwise copy: it reads0/8/c/e and omits+d.
The producer does not need to initialize the omitted byte on each append.

The direct path89945d0..8994618 applies after selection of identifier100.
It uses a configuration word's low byte for+c and current w15 bit0 to select
+e. It stores the supplied current x0 address and increments structure100.
Our slice enters after the earlier budget/filter checks; it does not model their
full arithmetic or declare arbitrary selected addresses valid.

The resolved path8994658..89946a8 first tests w0 from preceding getHWDSID.
A zero result skips with no writes. Nonzero proceeds to the same count bound,
uses a previously returned identifier byte at frame-51 for+c, current w14 bit0
for+e, and saved address at stack60. The actual lookup/provider is outside this
slice. Cases separately distinguish missing lookup, full array and accepted append.

On successful appends only the named fields and count change; full-structure
comparison checks preserved padding and unused entries. No external calls or PAC
bypass are required in the checked append/caller/initialization slices.

## Consequence for our implementation

Initialize the structure, use the bounded producer contract, then feed only its
0..16 count to startup construction. The prior17..24 consumer fixtures remain
useful malformed-input characterization, not a valid operating path. Implement a
local Linux bound rather than assuming all callers will provide valid state.

This is also new provenance: the previously anonymous startup entries belong to
AGXCommandHWDSIDData according to the native symbol/callers. Full HWDSID hardware
semantics, provider mapping/context and upstream resource selection remain open.

Next: whole-stream integration with optional phase/callback effects, native pool
configuration, live resource maps/cache/shader/target and kick/completion.
No executable draw is claimed. Retained warm INIT requires normal reboot before
hardware trials; offline analysis remains productive.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-hwdsid-append.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/hwdsid-append.json
```
