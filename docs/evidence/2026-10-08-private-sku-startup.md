# Complete native 3D SKU startup payload and publication

Matched private AGX353.14 / Apple25G83. Slice0x89d5344..0x89d5630 builds
the full0x1e8 startup payload and publishes its opcode7 envelope. 1,024 cases
with0..16 entries match an independent model, followed by256 cases with17..24
entries characterizing metadata/stack overlap. Full stack, encoder and stream
backing outputs match, including unchanged bytes; descriptor/command sources
remain unchanged. No hardware touched. Binary/slice hashes are in the JSON.

## Construction inputs

The slice enters with x19=CPU command, x20=channel, x21=stack80 payload base,
x22=channel state, x24=mapped GPU command base, x25=mapped parameter-management
input, x26=descriptor. Previously saved stack70 contains an index and stack78
a translated firmware address. These inputs are synthetic fixtures, following
the earlier caller provenance. We set w23=0 to exclude the conditional leading
wait branch, whose record construction was checked separately.

Native code clears payload bytes stack80..267 before field construction.
Two authenticated virtual resource calls are explicitly intercepted:

- descriptor58 resource, slot1e0: return low32 becomes payload5c.
- `*(*(descriptorb90 +30) +58)` resource, slot158: its returned address plus
  descriptor u32b98 becomes payload1c4.

Their actual provider/type/mapping semantics are not established by these stubs.
PAC is bypassed for unsigned fixture objects.

## Payload fields

All offsets in this table are relative to the0x1e8 payload, not its stream
record's opcode. CPU command and GPU command base refer to the same caller
roles, but their actual map/cache contexts remain unresolved.

| Payload destination | Source/value |
| --- | --- |
| u64+10 /+18 | GPU command+a0 /mapped PM input |
| u64+20 /+28 | saved firmware address+8 /GPU command+20f0 |
| u64+30 /+38 | mapped PM+54 /GPU command+2130 |
| u64+40 /+48 /+50 | GPU command+2134 /channel state /GPU command |
| u32+58 /+5c /+60 | command+c /resource slot1e0 low32 /descriptor190 pointee+8 |
| u32+64 /+68 /+6c /+70 | descriptor900 /byte897&1 /descriptor140 /command2158 |
| u32+74 | descriptor byteb48&1 |
| u64+78 /+80 | GPU command+1fd8 /GPU command+2178 |
| u32+88 /+8c | descriptor byte895&1 /byte894&1 |
| u32+90 | descriptor bytec48&1 if accelerator byteed48 bit0, else0 |
| u32+98 | descriptor byte960 ==2 |
| unaligned u64+9c | saved index from stack70 |
| 16-byte entries starting+a4 | descriptor970 entries, described below |
| u32+1a4 | descriptor a70 count, initially0 if count0 |
| u64+1ac /+1b4 | descriptorb70 /b80 |
| u32+1bc | descriptorb88 |
| unaligned u64+1c4 | resource slot158 return +descriptor u32b98 |
| byte+1cc /+1cd | accelerator byte6d5&1 /zero |
| unaligned u64+1d4 | command+4 serial |
| u32+1dc /byte+1e0 | command2154 /descriptorc44 |

The rest of the initial payload stays zero unless overwritten by the unchecked
entry loop. The builder also saves pointer/state fields outside the payload for
later opcode8 construction; full-stack comparison covers these auxiliary saves.
All pointer additions use u64 wrap. The secondary-phase flag at payload90 is
returned in w22 and checked for all flag combinations; no earlier condition is
inferred merely from that value.

## Variable entries and local lack of bounds checking

For each descriptor u32a70 entry, the source is descriptor970+i*16 and the
destination payloada4+i*16. Native copies u64+0, u32+8, byte+c and u16+e.
Byte+d is not copied. For0..16 entries it remains zero from initialization.
This is a fieldwise copy, not memcpy16.

There is no count limit in this local loop. With count17, entry16 begins at
payload1a4 and overwrites the previously stored count. Larger counts overwrite
fixed metadata, and sufficiently large counts write beyond the payload into
adjacent stack bytes. The256 extra fixtures with counts17..24 explicitly
characterize this behavior while keeping all emulated memory mapped; they are
**not valid jobs** and do not establish an allowed maximum. Upstream validation
must be traced before assigning a valid count range. Do not reproduce malformed
counts in a live driver.

## Stream mapping and publication

After building the payload, native code calls the SKU encoder's resource at
slot158 and computes its returned address plus the u32 difference between
current cursor and CPU backing base, plus4. It supplies that address to the
firmware mapper slot2d8 with x2=0. The independent translated result is saved
in x28 for later use. It points numerically to the payload after the opcode;
actual GPU mapping/context/cache behavior is not tested.

The builder then advances encoder68 by1ec, writes opcode7 at the old cursor,
and copies the full1e8 payload to cursor+4. The audit implements only the external
memcpy byte-copy contract and checks its arguments. Entire backing and encoder
comparisons prove publication alongside construction, without a fake builder.

## Remaining integration

This closes the ordinary startup payload's numeric construction gap. Still
needed: whole-function stream integration with begin/end/timestamps/callback
ordering and optional second-phase transformation, native command/pool sizes,
real resource providers/maps/cache, phase0 full recipe, shader/target/parameter
storage, live kicks/completion. No executable draw is claimed.

Retained failed warm INIT still requires normal reboot before hardware trials.
Offline analysis remains productive; no forced unload or repeated warm INIT.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-sku-startup.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/sku-startup.json
```
