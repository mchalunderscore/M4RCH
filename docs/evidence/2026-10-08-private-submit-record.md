# Matched AGX submission and event transport findings

Private-derived analysis of AGX353.14 / Apple25G83, not a clean-room specification.
Binary SHA256: `3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
No hardware execution or live probe changes in this pass.

## Submission record

`AGXArmFirmware::encodeAcceleratorRingCommand`, address
`0xfffffe00089c934c`, patches a 24-byte data-master ring record:

| Record offset | Width | Observed source |
| --- | --- | --- |
| 0x00 | 8 | Untouched by this encoder; ownership/meaning unresolved |
| 0x08 | 8 | Channel object +0x80; address role not established here |
| 0x10 | 4 | Engine/type argument |
| 0x14 | 2 | Low 16 bits of submit-info first word |
| 0x16 | 1 | Low 8 bits of channel object +0x18 |
| 0x17 | 1 | `1 & ~channel[0x3c]` |

The TA and 3D callers pass type 0 and 1 respectively at
`0xfffffe00089a77b0` and `0xfffffe00089a72e4`. Both execute DMB ISH
immediately after the encoder and before publishing the ring write cursor.
These are transport records, not the full render/compute job descriptions.
The matching data-master cursor getters require indices below 256.
Their shared-state offsets are read +0x00, CFI +0x10, write +0x20,
from object +0x08 (CPU view). GPU pointer getters use object +0x10
with the same offsets. These facts do not by themselves establish whether a
particular live cursor allocation is RAM or hardware backed.

## Event consumer

`AGXFirmwareRingValidator::fetchNextEntry`, address
`0xfffffe00089b7360`, copies a complete 72-byte entry to caller scratch,
checks its first u32 against an allowed-type bitmask, advances the read index
modulo capacity, executes DMB ISH, then stores the consumer index through its
state pointer. It does not clear the source record in this slice.
AArch64's variable shift masks the type to six bits; the model preserves that
behavior without claiming that types >=64 are valid protocol messages.

The validator initialized at firmware object +0x800 is configured with
mask `0x2000ffd3` and capacity 256, from the constant pair at
`0xfffffe000712dd60`. Its state and ring pointers come from firmware object
+0x8c0 and +0x8e0 and move to +0x808 and +0x810 at
`0xfffffe00089ad140` through `0xfffffe00089ad15c`. Their allocation identity
and main-graph channel correspondence still need tracing. Do not infer a
512-entry event ring solely from another allocation's byte size.

## Doorbell qualification

The CL wrapper constructs class 0x83 with low payload
`2 | ((priority & 7) << 2)` after the base submit call. The generic kick path
also has class 0x87 selection; these are distinct paths, not a license to
replace every kick with one constant. Submission checks firmware state !=2
and an indirect predicate. ASC vtable slot +0xad8 resolves to
`0xfffffe00089b7934`, which reads bit 0 at accelerator object +0x682
(via firmware +0x298). The meaning of that accelerator flag is not yet named.

## Reproducible offline verification

Run:

```
python experiments/t6040-gpu/audit-private-submit-record.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-submit-record.json
```

The checker pins the full binary SHA and emulates two reviewed, call-free
instruction slices in Unicorn RAM, stopping before return/PAC epilogues.
An independently written Python model matched 1,024 submit cases across all
256 flag-byte values, randomized source fields, all native engine values and
a u32 boundary value. Prefilled record prefixes remained intact.
72 event cases cover ordinary and wraparound cursors across capacities
1/2/256/512, type-bit selection, preserved source bytes, destination bounds,
returned type and consumer publication. Synthetic capacities and masks test
the consumer algorithm; only capacity 256/mask 0x2000ffd3 are established for
the specific native validator above. Error paths and dispatch are not emulated.
DMB's opcode is checked, but emulation cannot prove cache/DMA coherency.

## Implementation consequences and next work

1. Trace channel +0x80 initialization and record prefix ownership before
   submitting a real queue. Keep these transport helpers separate from job ABI.
2. Trace event state/ring allocations to their main-graph descriptor, then add
   a bounded raw event capture with these offsets and sizes.
3. Trace complete TA/3D job construction, buffer lifetimes and completion/fence
   handling; a valid transport record alone cannot render a triangle.
4. Resolve matched provider wake/reset behavior before repeating warm INIT.
   Current retained probe still needs a normal reboot before hardware work.

No kernel, package, boot entry or live cursor publication changed in this pass.
