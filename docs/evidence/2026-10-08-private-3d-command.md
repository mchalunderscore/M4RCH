# Native SKSM 3D command header, state copies and metadata tail

Matched AGX353.14 / Apple25G83 private binary. Four slices of
AGX3DChannelSKSM::submitBuffer run in emulated RAM against independent numeric
models: 1,024 ordinary headers, 1,024 FastBlit headers, 1,024 ordinary state-copy
blocks and 1,024 ordinary metadata tails. Full 0x2300-byte destination fixtures
match, including unchanged bytes. Descriptor/source inputs remain unchanged;
full serial-owner/channel objects match their expected counter updates.
No hardware touched. The fixture extent is **not** proof of command allocation
size or pool stride. Binary and slice hashes are in the JSON.

## Header and serial

Ordinary slice 0x895b388..0x895b410 selects descriptor+0x438 CPU backing and
sets the tail working pointer to command+0x1f38. FastBlit slice
0x895af28..0x895af8c selects descriptor+0x420 and working pointer+0x8bc.

Both use an external lookup at 0xbeaf410 with descriptor+0x60 and an address
0xc6e6298. The audit explicitly intercepts this call and returns a synthetic
object. It then executes the native read of object+0x5e8, increments that u64
with wraparound, and places its **old** value at command+4. No lookup, locking,
serial lifetime or concurrency semantics are established by this fixture.

| Command field | Ordinary 3D | FastBlit |
| --- | --- | --- |
| u32 opcode+0 | 1 | 2 |
| unaligned u64+4 | old serial | old serial |
| u32+c | descriptor144 | descriptor144 |
| byte | 21e7 <-descriptor148 | 997 <-descriptor148 |
| u32 | 2170 <-descriptor140 | 8fc <-descriptor140 |
| u32 | 2174 = (descriptor byte960 ==2) | 900 =0 |
| 24 bytes from frame pointer-b8 | 2178..218f | 904..91b |

Ordinary additionally sets u32+2100=descriptor byte897&1 and clears u32+20f8.
Frame/stack inputs are synthetic; their construction earlier in submit remains
outside these slices. Opcode1 agrees with the supplied ordinary-fragment spec;
FastBlit opcode2 is a distinct branch, not a replacement for ordinary 3D.

## Ordinary state-copy block

0x895b604..0x895b8f8 increments channel u32+204 (wraparound), then copies
state into the command. Complete destination/source/width triples are in the
JSON and `private_3d_command.py`; register/shader semantics are not inferred
from numeric copy offsets.

Command40 <-descriptor8a0 (u64), 48 <-8b8 (u64), 50 <-8c8 (u32),
54 <-8d0 (u32), 58 <-**low32** of descriptor8c0, 70 <-8e8 (8bytes),
78 <-8f8 (u32). These connect to the preceding checked render-input loaders.
Command60 receives16 bytes from the object saved at stack60, source offset2f0.
The same object contributes16 bytes from+a0 to command1f10 and8 bytes from
+1b4 to command1f88. Its identity/preparation is not proved here.

A large continuous copy maps descriptor4e8..657 to command1d58..1ec7.
Additional descriptor fields between4b0 and7c0 populate command1d20..1fd7,
including unaligned vector copies at1f74 and1f94. These are full byte copies;
unaligned destinations and untouched gaps must be preserved.

Native writes zero bytes across command1fdc..20ef, clears u32+1fd8 and
u32+20f0. This does not clear the entire command. It is important to distinguish
this state mirror from the earlier four generated register lists.

## Ordinary tail and completion-associated fields

0x895b92c..0x895b9d8 follows a channel callback. The audit supplies its return
in x0; this low byte is stored at command90. Callback semantics remain open.

| Command destination | Source/value |
| --- | --- |
| u32 20fc | descriptor byte88c&1 |
| u32 2208 | descriptor u32c40 |
| byte220c | descriptor bytec44 |
| u32 2104 | descriptor byte868&1 |
| 12bytes2108 | descriptor86c..877 |
| 16bytes2114 | zero |
| 16bytes21a8 | descriptorab0..abf |
| u64 21b8 /21c0 /21ce | descriptorac0 /ac8 /b70 |
| u64 2198 /21a0 | descriptor878 /880 |
| u64 2140 /2148 | stack50 /40 |
| u32 2150 /2154 | w21 /w22 |
| u32 2158 /215c | stack4c /48 |

The +21ce field is unaligned. Native writes at+2140 agree with the supplied
completion-metadata boundary. This slice proves construction, **not** the
meaning of all fields or completion/fence behavior. Earlier code must still
establish the stack/register values and resource mappings.

## Next integration work

Combine these checked fields with the register-generation recipe, but do not
submit random fixtures. Still needed: command allocation stride provenance,
SKU microsequence generation, phase0's full independent model, real shader and
target/parameter storage, map contexts/cache synchronization, live kick and
completion. The failed warm INIT probe remains retained; normal reboot before
new hardware trials. No forced unload or repeat warm INIT is justified here.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-3d-command.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/3d-command.json
```
