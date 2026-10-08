# Whole native G16 3D SKU stream construction

Private-derived from AGX353.14 / Apple25G83. Offline only; no kernel, boot-entry
or hardware changes. Binary SHA256 and function hash are in the adjacent JSON.

## Native execution scope

The audit executes the complete `AGX3DChannelG16::encode3DCommandSKUStream`
function at `0xfffffe00089d517c..0xfffffe00089d5a30`, including its native
buffer selection, timestamp encoding, channel WFI callback and finalization.
It compares all bytes of the stream backing, encoder object and output command
against the independently checked startup/timestamp/wait/end models. The input
descriptor must remain unchanged. This closes the earlier gap between isolated
record slices and their integration in the native caller.

The G16 vtable at `0xfffffe0007eaa560`, address point +16, slot +0x258 resolves
to `0xfffffe00089d4b54`: `encodePixelEndRenderWFI`. Its native code appends a
four-byte opcode 1 and advances the stream cursor. This is a GPU stream record;
it is unrelated to the CPU shallow-WFI idle work.

## Record ordering

The primary sequence is:

1. Optional wait-begin: 0x14 bytes, opcode 0x88000004.
2. Startup: 0x1ec bytes, opcode 7 and 0x1e8-byte payload.
3. Optional timestamp-begin: 0x4c bytes, opcode 0x80000003.
4. WFI: four bytes, opcode 1.
5. Optional timestamp-end: 0x4c bytes, opcode 3.
6. Optional wait-end: 0x14 bytes, opcode 0x08000004.
7. End: 0xbc bytes, opcode 8.

When accelerator +0xed48 bit0 and descriptor +0xc48 bit0 are both set, a
second startup/WFI/end sequence follows. Its startup changes payload +0x90
as a u64 to 0x100000000; its end record uses the corresponding mode value.
Finally opcode 0x40000002 terminates the stream. Finalization reports size
rounded up to 64 bytes, leaving backing padding untouched.

With the fixture's selected slot offset of 4096, the firmware mapper receives
resource GPU base +4096+optional leading wait size+4 for the first startup
payload. End records refer to that mapping +0x1ac. Finalization separately
maps resource GPU base +4096 and stores its return at command +0x14, with
rounded size at +0x1c. Every mapper input and call count is checked.

## Verification

Run:

```
python experiments/t6040-gpu/audit-private-3d-stream.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-stream.json
```

1,024 deterministic cases pass: 768 single-phase, 256 second-phase,
512 timestamp pairs, 192 wait pairs, 512 notification-present and 512
notification-absent. Fixtures also toggle optional timestamp pointers and
use HWDSID counts within the confirmed native bound of sixteen. Full memory
comparison detects unexpected writes, including output beyond the emitted
records. Counts are exercised but not every count/branch Cartesian product.

## Qualifications and next implementation work

Unicorn executes the matched instructions in RAM. PAC is bypassed. External
resource/firmware mapping, availability, event association and memcpy calls
are explicit synthetic contracts. This does not prove provider semantics,
DMA/cache coherence, concurrent ownership, or GPU execution. Buffer capacity
is two with a deterministic available slot; the separate pool audit covers
wraparound and full-pool behavior.

This is the native G16 SKU builder. Its vtable and callback must not be assumed
to describe G16_SKSM without tracing that separate path. We still need valid
shader/state inputs, command-pool stride provenance and complete register
initialization before submitting a real render job. The retained failed warm
INIT probe needs a normal reboot before hardware tests. No triangle or GPU
accelerated desktop is proved by this audit.
