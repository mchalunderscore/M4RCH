# Native 3D SKU opcode8 records

Matched private AGX353.14 / Apple25G83. 1,024 primary and1,024 optional
secondary record cases execute actual native construction slices in emulated
RAM and match independent models. Full backing/encoder bytes and source inputs
are checked, not only named fields. No hardware touched. Numeric offsets and
names do not establish opcode execution or completion/fence semantics.

## Primary path and notification selection

Native slice 0x89d56b4..0x89d57e4 also executes its zero-notification branch
0x89d59cc..0x89d59d4. Inputs enter from the earlier SKU construction context.
The preceding caller has initialized32 bytes at frame pointer-90 to zero.

If descriptor u32+a70 is nonzero, or any of four u64 values at descriptor+a78
is nonzero, the32-byte vector at a78..a97 replaces those frame bytes and w27
becomes1. Otherwise the zero vector stays and w27 becomes0. Cases cover each
individual nonzero element and nonzero count with an entirely zero vector.

Native inserts accelerator byte+f570 bits0..1 into w27 bits2..3, then stores
its low byte at record+a4. This flag is consequently:
`has_notification_vector | ((configuration_byte & 3) << 2)` on the primary path.
The meaning of those bits is not independently proved here.

Both primary and secondary reserve0xbc bytes at encoder68 and advance the
cursor by that amount. They write u32 opcode8. Several u64 fields are unaligned.

| Record field | Primary source/value |
| --- | --- |
| u64+4 | stack70 |
| u64+c | CPU command2148 |
| u32+14 /+18 | command2150 /zero |
| u64+1c /+24 | stack38 /stack60 |
| u32+2c | 1 |
| u64+30 /+38 | stack58 /stack30 |
| u64+40 /+48 | stack48 /stack50 |
| u64+50 /+58 | stack68 /current x24 GPU command base |
| u32+60 | command+c |
| u64+64 | stack40 |
| u32+6c | descriptor byte895&1 |
| u64+70 | zero-extended current w22 |
| 32bytes+78 | selected notification vector |
| u64+98 | current x28 mapped startup payload +1ac |
| u32+a0 | stream-relative word described below |
| byte+a4 | packed notification/config flag |
| unaligned u64+a5 | GPU command base +21e8 |
| unaligned u32+ad | descriptor+c40 |
| byte+b1 | descriptor+c44 |
| unaligned u32+b2 | command2154 |
| u32+b6 /u16+ba | zero /zero |

Source roles such as GPU command base follow the earlier caller trace; map
contexts and actual valid object construction are not qualified by these slices.
The w22 mode is deliberately numeric: no boolean normalization occurs here.

## Stream-relative word

For both paths, record+a0 contains native u32 arithmetic:

```
encoder5c + low32(encoder28) - low32(previous_cursor)
```

It is computed after advancing the cursor, then adding0xbc back. For ordinary
safe backing this equals the displacement from this opcode8 record's beginning
back to the selected stream slot's beginning. Examples include zero and negative
values represented in two's complement. This establishes numeric provenance,
**not** that firmware interprets it as a jump or permits arbitrary targets.
GPU address fields use u64 wraparound, as characterized by random fixtures.

## Optional secondary opcode8 record

Slice 0x89d58b8..0x89d5980 takes saved stack/register values from a preceding
optional second startup phase. It retains the primary record layout with these
source substitutions:

| Field | Secondary source |
| --- | --- |
| +c /u32+14 | current x25 /w28 |
| +1c /+38 | current x26 /x21 |
| +50 /+58 | current x23 /x24 |
| u32+60 | stack4 |
| u32+6c | stack18 |
| u64+70 | native d8 constant100000000 |
| +98 /+a5 | stack20 /stack8 |
| byte+a4 | current w27 low byte |
| u32+ad /byte+b1 /u32+b2 | stack14 /low byte stack1c /stack2c |

Other pointer fields come from the same stack offsets as the primary table.
The32-byte vector comes from frame-90 without new selection. The audit supplies
saved register values, and supplies d8 after verifying the literal u64 constant
at712d7f0. It does not execute the entire preceding optional phase or prove its
selection condition. Arbitrary w27 fixture bits characterize this writer; they
are not valid protocol flags.

## Integration status

The startup7 envelope, timestamp3 records, conditional wait4 records, both
opcode8 tails, terminator and size publication now have checked numeric models.
Remaining work includes full upstream startup payload construction, optional
phase transformation/callback effects, whole-stream integration, native pool
sizes, mapping/cache policies, shader/target/parameter storage, live kick and
completion. No executable draw or accelerated desktop is claimed.

The failed warm INIT probe remains retained: normal reboot before hardware
experiments, no forced unload or repeat warm INIT. Offline work is still useful.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-sku-end.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/sku-end.json
```
