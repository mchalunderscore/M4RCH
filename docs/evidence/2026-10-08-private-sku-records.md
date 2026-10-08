# Native SKU timestamp and 3D startup/wait records

Matched private AGX353.14 / Apple25G83. Actual native timestamp encoding,
startup copy and two conditional wait-record slices execute in RAM against
independent numeric models. 1,024 timestamp cases, 1,024 startup copies,
1,024 each begin/end wait records, and6 unsupported-opcode assertion captures
pass full-byte checks. Source inputs remain unchanged. No GPU hardware touched.
Function and binary hashes, constant vectors and tables are in the JSON.

## Timestamp record

AGXSKUEncoder::encodeTimeStamp 0x8a16cdc..0x8a16ed0 receives encoder in x0,
u32 index in w1, CPU command in x2, GPU command base in x3, u64 state in x4,
and begin selector in w5. It reserves0x4c bytes at encoder68 and writes opcode3,
OR80000000 when w5 is nonzero (not only when equal1).

Command u32 opcode selects one of four layouts:

| Command opcode | First/second timestamp | Optional pair | Optional pointer/value | Control | Constant pointer pair |
| --- | --- | --- | --- | --- | --- |
| 0 | 8fe/906 | 90e | 91e/926 | 8f6 | 95e/86a |
| 1 | 2198/21a0 | 21a8 | 21b8/21c0 | 2190 | 21f8/2104 |
| 2 | 948/950 | 958 | 968/970 | 93c | 9a8/91c |
| 3 | f7c/f84 | f8c | f9c/fa4 | f74 | fe4/f1c |

Offsets are hexadecimal bytes relative to the command. Numeric naming reflects
the encoder, not independently proven timestamp storage/completion semantics.
The native constant pointer pairs are read from712df70/60/50/40 for opcodes
0/1/2/3 respectively and checked against the table.

The0x4c-byte stream record contains the u32 header followed by **unaligned u64**
fields at4,c,14,1c,24,2c,34,3c,44:

- +4: GPU command base+control offset.
- +c: GPU base+first timestamp offset in both begin/end forms.
- +14: GPU base+first offset for begin, second for end.
- +1c: supplied x4 state/address, unchanged.
- +24: GPU base+optional pair offset if either CPU command u64 in that pair
  is nonzero, else0. It is a pointer to the pair, not the pair's first value.
- +2c/+34: GPU base+the constant pointer offsets.
- +3c: GPU base+optional pointer offset if the command's u64 value field
  is nonzero, else0. Pointer offset and presence-check offset differ.
- +44: zero-extended w1 index as u64.

All GPU additions wrap u64 in the checked native code. Random values expose
numeric behavior; they are not valid resource addresses. Optional pair cases
cover neither/first/second/both nonzero for each command opcode; w5 includes
0/1/2/ffffffff. No external callbacks or PAC bypass are needed on valid paths.

Unsupported command opcodes reach assertion code at8a16e98. Importantly, the
cursor is already advanced0x4c and the header already written before rejection.
The audit intercepts that path before external assertion execution and checks
the partial mutation. A failed encode must not be treated as transactional.

## 3D startup copy

Slice 0x89d5610..0x89d5630 enters with x8=SKU encoder, x20=channel and the
previously constructed startup payload at stack80. It advances encoder68 by
0x1ec, writes u32 opcode7 at the previous cursor, and copies0x1e8 payload bytes
to cursor+4 using external memcpy b744bf0. The audit implements exactly this
byte-copy contract and checks its source/destination/length arguments.

This qualifies the envelope and copy, **not** all payload fields. Earlier native
code constructs the stack payload from mapped resources, descriptor/state and
conditional flags. That upstream construction remains to qualify fully.

## Conditional wait records

Native branch slices 0x89d59d4..0x89d59fc and0x89d5a00..0x89d5a28 append
0x14 bytes and advance encoder68 accordingly. They take the encoder from
channel+a8 and copy descriptor u32+86c, current w27 and current x24:

| Stream offset | Begin branch | End branch |
| --- | --- | --- |
| u32+0 | 88000004 | 08000004 |
| u32+4 | descriptor86c | descriptor86c |
| u32+8 | w27 | w27 |
| unaligned u64+c | x24 | x24 |

The preceding caller computes a condition involving descriptor893, accelerator
configuration and descriptor868. These slices do not establish that condition,
full ordering or the hardware meaning of bit31/bit27. Names begin/end describe
placement around the checked 3D startup/timestamp sequence, not proof of a
complete synchronization protocol. No live wait execution or fence is tested.

## Integration status

We now have checked record encoders plus the previous native buffer finalizer
(terminator40000002 and aligned size publication). Still missing are a complete
startup payload, subsequent end/control records, real mapping/cache semantics,
phase0's full model, valid shader/target/parameter storage, live kick/completion.
No executable draw is claimed. Retained failed warm INIT still requires a
normal reboot before hardware experiments; do not force unload or blindly retry.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-sku-records.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/sku-records.json
```
