# Receive13 validator geometry and channel pointer provenance

Private-derived from matched AGX353.14 / Apple25G83, not clean-room.
No hardware trial or boot change. Current warm-failure probe remains retained.

## Receive13 is a compound descriptor

The existing allocation audit and four main+0x1c0 pointer producers identify:

| Main pointer | Native resource field | Mapped CPU field | Size | Newly established use |
| --- | --- | --- | --- | --- |
| +0x1c0 | +0x8c0 | +0x900 | 0x30 | General event ring cursor state |
| +0x1c8 | +0x8e0 | +0x920 | 0x4800 | 256 general event records of 72 bytes |
| +0x1d0 | +0x8c8 | +0x908 | 0x1b0 | Nine cursor states, each 48 bytes |
| +0x1d8 | +0x8e8 | +0x928 | 0x28800 | Nine buffers, each 256 records of 72 bytes |

Actual native initialization at 0xfffffe00089ad000..0xfffffe00089ad160
constructs nine validator objects at firmware +0x5f0 through +0x770 with
state stride 0x30 and ring stride 0x4800. Each has allowed mask 0x4
(type 2 only) and capacity 256. The general event validator at +0x800
uses the first state and buffer, mask 0x2000ffd3, capacity 256.
These extents are already correct in our fixture; the new result establishes
internal geometry and the general event ring's descriptor identity.

Nine type-2 rings are consistent with firmware logging transport, but their
payload semantics and consumption paths are not established by the setup
alone. They are distinct from the type-5 trace validator at firmware +0x7a0
initialized from resources +0x8d0/+0x8f0. Avoid conflating them.

The new offline checker executes only this reviewed call-free initializer,
with synthetic distinct pointers and actual native constants. It independently
asserts each of the ten resulting validator configurations. See matching JSON.

## Read-only capture decoder

`experiments/t6040-gpu/decode-receive13.py` consumes a copied owned-graph arena
and its receipt. It parses the general event ring and nine type-2 rings,
using u32 read/write words at +0/+0x20, stride 72 and capacity 256. It emits
bounded raw records, preserves unknown payloads, and never writes cursors.
Invalid extents/cursors are rejected. Equal cursors are interpreted as empty;
no separate phase/full flag has been established. A copied snapshot does not
prove atomicity or live cache coherency.

Three tests verify wraparound/truncation/source preservation, invalid geometry
and cursors, and the equal-cursor case. Applying it to
`out/gpu-gravity-contract/graph-retirement-candidate/graph-before.bin` and its
receipt yields zero pending entries in all ten rings, as expected for that
pre-publication fixture. This is a format check, not proof of firmware activity.

## Submission pointer narrowed

The encoder's channel +0x80 comes from native channel initialization:
resource subobject +0x50 -> virtual method +0x158 -> returned base plus
per-slot displacement -> channel +0x80 at 0xfffffe0008980270.
The same slot displacement is added to the +0x60 subobject's virtual +0x138
return to construct channel +0x58 (0xfffffe00089802f4).
The allocation source is firmware's channel-state pool (+0xe98 array,
+0xeb8 entries/block and +0xef8 stride), with resource-stack symbols naming
`_AGFIChannelState`. Cleanup calls the named `releaseChannelState`, then
clears channel +0x58 and +0x80 at 0xfffffe0008980d04..0xfffffe0008980d0c.

This supports a channel-state resource pointer, rather than naming it a raw
job command-buffer address. The external mapping method definitions and
complete channel-state construction still require tracing. Do not use the
nearby AGXInternalResource vtable indiscriminately: the called subobjects
have their own vtables, and a guessed offset may point into another table.

## Next implementation steps

- Capture all ten receive13 cursor pairs and bounded records before/after
  the next valid cold initialization; decode from copies without acknowledgements.
- Trace channel-state initialization and its work-queue pointer field, then
  correlate queue descriptors, submit-info indices and complete job constructors.
- Establish event dispatch/completion semantics before adding consumer writes.
- Continue resolving the matched firmware provider for reusable warm sessions;
  current retained probe needs normal reboot before another hardware batch.
