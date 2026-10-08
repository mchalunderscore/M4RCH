# Packed scheduler kick records in the native NOP path

Private-derived matched AGX353.14 / Apple25G83 evidence. No live GPU submission.

`AGXChannel::submitNopUnprepared` is not an isolated empty-record constructor.
It branches on command type, inspects descriptor/event state, and can request
KSM configuration updates and entry signals before an add-kicks command.
The accelerator flag at +0xee5f bit0 selects between two record patches at
0xfffffe000897f040..0xfffffe000897f0b0. Its higher-level meaning is unresolved.

## Observed record patches

With flag bit clear, the result of the named
`requestChannelCommandKSMKickQueueAddKicks` receives:

| Offset | Width | Value/source |
| --- | --- | --- |
| 0 | 4 | Opcode 14 |
| 4 | 2 | Low 16 bits of stack +0x24 |
| 6 | 2 | Constant 1 |
| 8 | 1 | Low 8 bits of scheduler object +0x1c |
| 9 | 8 | x27 pointer supplied by earlier construction |
| 0x11 | 4 | Stack +0x20 |

This patch writes 21 bytes. The uploaded spec describes a 24-byte opcode-14
record, which is consistent with this prefix; the remaining bytes are not
written here. This pass does not independently prove the total allocation
extent. The named request method uses its pool's runtime stride from firmware
+0x1578 and publishes an output GPU address separately from its returned CPU
address, through the resource mapping methods.

With flag bit set, a separately allocated non-null record receives:

| Offset | Width | Value/source |
| --- | --- | --- |
| 0 | 4 | Opcode 16 |
| 4 | 2 | Low 16 bits of stack +0x24 |
| 6 | 8 | Same x27 pointer |
| 0x0e | 4 | Constant 0xfe |

This patch writes 18 bytes; total allocation size and complete opcode-16 role
remain unresolved. Do not confuse this per-channel opcode 16 with the
accelerator device-control opcode 16 tested in earlier graph batches.

The path loads its selected output GPU address into x1, keeps the CPU record
pointer in x2 and calls channel virtual slot +0x188 with x3=0. This correlates
with `writeChannelCommandPointer`'s signature (u64 GPU address, CPU command
pointer, optional tracking value). The TA, 3D and CL G16 vtables all resolve slot +0x188 to the exact
`writeChannelCommandPointer` implementation at 0xfffffe0008981048. The
checker verifies these three targets from encoded native pointers.

## Reproducible test and limits

`audit-private-kick-records.py` executes only the two reviewed call-free patch
slices in emulated RAM, with the actual pinned binary. Independent numeric
models in `private_kick_records.py` match **256 randomized cases per variant**,
including truncation of input fields, packed unaligned pointers and preserved
unknown tails. No allocation, mapping or external callback executes.

The helper names describe observed transport roles, not authorization to send
these incomplete records. A valid x27 kick pointer, scheduler configuration,
entry-signal/stamp handling and complete allocation lifetime are prerequisites
still to establish. Calling this routine 'NOP' does not make it independent
of that state or prove it safe as the first live command.

Next trace the earlier x27 construction and configuration/entry-signal records,
and corroborate the packed format with firmware
consumers. This narrows the first-job path but does not yet produce a render job.
