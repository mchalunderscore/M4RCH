# Native RCE append and register overrides

AGX353.14 matched binary, hashes in JSON. Actual append (0x89df538..5a4),
override (0x89df5a4..6ec), getEntry (0x89df6ec..714) and encodeEntry
(0x89df714..73c) execute in emulated RAM. The G16 encoder vtable slots0/8
are checked against the matched image. PAC is bypassed for unsigned fixture
pointers; there are no stubbed external services in these tests.

1,024 randomized override fixtures, 256 SPM-model backing fixtures and512
whole native append cases pass. Override execution performs230,816 native
getEntry calls and10,198 matching native encodeEntry calls. Fixtures exercise
empty tables, zero entries, unmatched keys, duplicate keys, masks0/allones/random,
flag0/1 and unchanged reserved header bits. Full backing and table/encoder memory
are checked, not just selected fields. Append tests include128 count-wrap cases.
SPM backing uses the previously checked Python model, not a new native SPM call.

## Table source and iteration

From accelerator+0x5b0, load object pointer; from object+0x380, load table owner.
Owner u32+0x980 is row count. Rows begin at+0x800, stride24:

| Row offset | Width | Role |
| --- | --- | --- |
| +0 | u64 | replacement mask |
| +8 | u64 | replacement value |
| +0x10 | u32 | exact register key |
| +0x14 | 4bytes | not consumed by this method |

Zero table count returns unchanged without examining the encoder backing. A
nonzero table count with zero backing u16+0x708 also returns unchanged.

The outer loop visits rows in order. The inner loop scans every entry indicated
by backing u16+0x708, reading entries from the start of backing, irrespective of
backing u16+0x70a cursor. Native scan address is `(index*12)&0xfffc`; large counts
can truncate addresses. This audit uses counts0..48, avoiding truncation and
metadata overlap; it does not qualify large-count behavior or table bounds.
Rows0..16 are fixture coverage, not a proven protocol maximum.

getEntry decodes register&0x3fff8 and flag&1. The decoded register is compared
against the **entire u32 table key**; the key is not normalized with0x3fff8.
For every match, encodeEntry rewrites the same entry with:

```text
new_value = (old_value & ~mask) | (replacement_value & mask)
```

Register and flag come from getEntry; reserved header bits are preserved by the
native encoder. All matching entries are patched. A match does not end the
scan. Repeated rows for the same key act cumulatively in table order, so later
rows win where masks overlap. No entry is appended or removed; counters and
cursor remain unchanged. A mask0 match still calls the encoder but changes no
entry bytes for these fixtures.

## Append

Actual ABI: x0 encoder, w1 register, w2 flag, x3 value. Native append obtains
backing pointer from encoder+8 and u16 byte cursor at backing+0x70a; calls virtual
slot0 on backing+cursor, then rereads backing and advances cursor by12 and count
at+0x708 by1. Both stores are u16; count65535 wraps to0. No capacity check occurs
in the function. Fixtures keep cursor and destination clear of metadata and
within allocated RAM; metadata overlap/out-of-space behavior is excluded.

## Consequence for constructing work

An actually empty override table adds no hidden register writes. A nonempty table
can modify multiple phases and repeated matching entries. The source and intended
contents of that table remain to trace; the empty table used in the assembled
parent-generator audit is synthetic, not verified live accelerator state.
No GPU job, descriptor validation, allocation policy or live firmware acceptance
is established by these RAM-only tests.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-rce-overrides.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/rce-overrides.json
```
