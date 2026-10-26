# Common G16 ordinary work-kick prefix

Matched private AGX353.14 binary. 1,024 randomized cases matched actual native
instructions at 0xfffffe00089db298..0xfffffe00089db370 in emulated RAM. Each
compares the full 0x200-byte record, including untouched bytes. Binary/slice
hashes are in the accompanying JSON. No hardware accessed.

## Qualified fields

An optional aperture input is a 16-byte record: u64 address at0, u32 index at8,
u32 count at12. Nonzero count patches scheduler record +8:

- input index low6 bits at bits0..5;
- address shifted right5, low38 bits inserted at bits6..43;
- bits44..48 cleared by the native mask;
- count-minus1 low6 bits at bits54..59.

Count zero leaves the entire +8 word untouched. Remaining bits are retained per
native masks. Arbitrary unaligned addresses and out-of-range counts characterize
masking, not valid hardware input.

Main header begins with kind0 or kind2 according to a caller boolean. Timestamp
low47 bits shifted2 and queue ID low7 bits shifted42 match the previously checked
arithmetic, but the final mask is **0xc401fffffffffffe**, different from NOP.
Aperture presence ORs bit58. Priority occupies bits59..60 and another caller
boolean controls bit61. The mask preserves original bit58 if the aperture is
absent; actual backing initialization is outside this slice, so the audit does
not silently assume the old header is zero.

Two caller payload words are copied to +0x10/+0x18. Their semantic identities
must be traced separately for each wrapper. The native 3D wrapper itself uses
descriptor callbacks at slots1e0/1e8, internal-resource lookup and QOS state before
calling the common encoder. This prefix is therefore not a complete 3D command
or a valid triangle recipe.

## Remaining gaps

Earlier external record initialization, dependency body, QOS, notification masks,
reglist descriptors and counter/publication tail remain to qualify for ordinary
work. NOP models cannot simply be substituted for these sections. Shader, TA/3D
work structures and live firmware acceptance are separate outstanding tasks.

Kick MMIO field provenance remains unresolved. The separate parser writes
+0x18e28/+0x18e2c/+0x18e30 whereas kick consumers read +0xee28/+0xee2c/+0xee30;
no evidence connects those fields. Do not guess an adjustment from similarity.
The symbol named AGXKSMKickQueue::complete shares code with
AGXInternalResource::completeMappings and handles mapping-reference bookkeeping;
its name alone is insufficient evidence for GPU job retirement.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-work-prefix.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/work-prefix.json
```
