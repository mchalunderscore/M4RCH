# J614s SEP and DCP reservations

> Historical cache paths below describe past trials and are not current recovery instructions; most of those artifacts are no longer in the checkout. For the current boot recovery path, see [recovery](recovery.md).

On the Touch ID trial, Linux reported two overlapping reserved-memory pairs and
refused to mark two DCP OS-log nodes `no-map`. The pre-Touch ID boot had no
such errors. This is a real handoff conflict, not just a cosmetic warning:
Linux's `early_init_dt_reserve_memory()` refuses to mark any overlapping
previously reserved region `no-map`.

The live Apple device tree reports `SEPFW` as a 0x5ac000-byte span. On the
observed boot, two DCP `__OS_LOG` ranges and an ASC firmware range intersected
that span. The DCP addresses are not calculated from the SEP descriptor. The live ADT
records these values, but their original provenance has not been established:
a chainloading stage can relocate SEPFW and update the ADT. The same pattern
appeared on three candidate boots with different absolute addresses. Whether
SEP firmware itself accesses all bytes of its descriptor after warm attach is
not established. The running SEP uses Aurora's warm-registration path; the
kernel maps the full `sepfw` region only in its cold-boot path.

Aurora m1n1's [`dt_set_sep`](https://github.com/aurora-silicon/m1n1/blob/6918c029cc0919015844839fee3505b3a4e65e46/src/kboot.c)
publishes the whole descriptor as one mapped `sep-firmware` reservation. Its
[J616s DCP handoff](https://github.com/aurora-silicon/m1n1/pull/51) publishes
the DCP log nodes independently; its discussion contained no resolution of the
combined SEP case when checked on 31 October. Current `aurora-wip` still uses
the same SEP reservation approach. No corresponding upstream combined fix was
found. The local J614s U-Boot handoff therefore splits the SEP *reservation*,
not the firmware or the DCP buffers: existing intersecting `no-map` ASC/DCP
nodes retain their addresses and phandles, and the remaining pieces of the
full SEPFW range get their own reserved-memory nodes. The unneeded `sepfw`
reference is removed only for the J614s warm SEP when a split is needed. The
code refuses unexpected overlaps and falls back to the original live tree if
admission or editing fails. This preserves the entire descriptor while avoiding
intersecting reserved-memory nodes; it does not establish whether the firmware
considers the descriptor's contents exclusively owned.

The actual U-Boot transformation was run against this machine's real boot
FDT in memory: the original SEP interval was covered exactly once, and DCP/ASC
addresses, `no-map` flags and phandles were unchanged. A one-time boot on
31 October used the resulting U-Boot with the Touch ID kernel. Its log showed
all three DCP OS-log nodes as `no-map` and no reservation-failure or overlap
warnings; SEP restored one enrolled identity, the sensor came online, and the
xART guard reported no refusals. A further qualification boot used the same U-Boot with the final kernel; the
user confirmed the display, keyboard and trackpad worked, and the enrolled
right index finger matched. This evidence does not
prove suspend reliability, external display behavior, or the meaning of every
byte of the Apple firmware descriptor.

## Upstream design constraint — 1 November 2026

Aura adds display reservations before `dt_set_sep()` and adds further firmware
reservations afterwards. A final pass before handoff could see those ranges
before handing the tree to U-Boot.
Moving the existing split there would remove a later U-Boot rewrite, but must
keep the full SEPFW interval reserved and distinguish a verified warm SEP from
a cold-start path that requires the contiguous `sepfw` resource. A single
`reserved-memory` node with multiple `reg` tuples is not a safe shortcut:
this kernel's `__reserved_mem_reserve_reg()` explicitly uses only the first
tuple. Nor can the full range be represented as `/memreserve/` before the
overlapping DCP `no-map` nodes: `early_init_dt_reserve_memory()` refuses to
mark an already-reserved intersection `no-map`. Aurora/m1n1 PR #9 addresses
missing SEP properties, not this overlap; Aura's T6041 DCP handoff similarly
does not resolve a later overlapping SEP reservation.


## Aura ownership prototype — 1 November 2026

The [experimental Aura change](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/aura-j614s-sep-overlap-experiment.patch)
ports the existing local split into a final device-tree pass, after Aura has
published its other firmware reservations. It is restricted to J614s and keeps
the existing DCP/ASC nodes and their phandles. Where no overlap exists it
leaves the original SEP region alone. When there is an overlap, it removes the
warm-attach SEP's contiguous `sepfw` reference and reserves the uncovered
pieces, refusing unexpected layouts. The pass aborts tree preparation on an
error rather than handing off a partially edited tree.

The `kboot.o` object compiled against Aura source `a9cad94` with no reported
warnings. This is only an ownership prototype: it has not been run on the
actual pre-U-Boot device tree or booted, and a J614s board check alone does not
prove what an arbitrary future kernel's SEP bootstrap requires. Review the
warm-attach contract and all reservations added by downstream U-Boot before
considering an upstream submission. The current USB/HDMI trial is independent
and does not contain this prototype.

The currently installed kernel selects the T6040 profile for `apple,j614s`;
that profile inherits T8140's warm-register bootstrap. This supports the
prototype's premise for the present stack, but does not establish a contract
for every kernel a user might boot. The package-managed U-Boot still adds ISP
reserved-memory nodes and may add ANS RTKit `no-map` nodes after Aura's pass,
as well as an ANS malloc-arena `/memreserve/`. On the running camera-trial
tree, a read-only comparison found neither ISP firmware region overlapping a
`sep-retained` or other reserved-memory node. The observed tree has no
`ans-rtkit@` nodes, so this says nothing about the wake path that creates
them. Later reservations must be checked explicitly before replacing the
U-Boot split; moving it earlier by itself is insufficient evidence.

## Combined board and SEP trial

A stage-two trial combines #795 board head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537` with the Aura SEP split prototype.
The board source adds the existing local loader-compatibility include for ISP,
AOP and USB handoffs; the running kernel remains the installed patched Aurora
kernel. The candidate uses the package-managed Aura source plus the SEP
prototype and reconstructed package-managed U-Boot with only its duplicate SEP
split removed. The other U-Boot handoffs are retained. This is not a boot of a
stock upstream stack or an isolated test of #795.

The board tree compiled with the same warnings as the unmodified #795 tree;
the loader images built without reported warnings. The trial bundle had SHA-256
`73a525e154fe597252e67578a26fa487560f35259e25856f3f74216551a8c70f`.
The trial has ended and its cached artifacts were removed. See
[current recovery](recovery.md) for the present boot stack and recovery path.

The combined trial failed before starting U-Boot or Linux: Aura reported
`cannot retain J614s SEP memory without reservation overlap` and refused FDT
preparation. That diagnostic covers several guard failures; it does not say
which one occurred and is not proof of a specific overlap. The owner recovered
to the prior Linux setup. The selected EFI loader was verified against the
known-good package-managed hash. Its EFI recovery copy was missing after
recovery, so it was recreated from the verified loader and its hash checked.
The prototype has therefore not passed the hardware trial and must not be
promoted or represented as a validated fix. The trial does not establish
whether the #795 board tree would boot with the original handoff.

## Unsplit SEP trial

At the owner's request, a follow-up bundle uses the same #795-derived board
DTB and U-Boot without our SEP split, but restores the package-managed Aura
binary and omits the experimental Aura check entirely. This exercises the
existing Aura behavior of publishing the SEP reservation without our local
split; the full boot stack still carries other J614s integration changes.
The bundle SHA-256 is
`ecc61d152bcffa61e1cfe3d8989a95e7fbcd413428cef89b4e43c220d3a18ed4`.
It was selected after verifying and archiving the prior package-managed loader
and EFI recovery copy. The candidate remains selected until explicitly
restored. After boot inspect the reserved-memory errors as well as Touch ID
and internal display behavior. Previous unsplit boots reported DCP no-map
failures, so working devices alone would not establish that the reservations
are safe. If it cannot boot, from macOS or recoveryOS copy
`m1n1/boot.bin.m4rch-before-sd-gpio` over `m1n1/boot.bin` on EFI; do not move
or delete the recovery copy.

The first unsplit trial reached U-Boot but failed with `FDT_ERR_BADVALUE`
during the local J614s runtime device-tree import, before Linux. The new
#795 board tree already describes the SD reader: its PCIe bus range is
`0..2`, the SD port is enabled and uses bus 2. Our old U-Boot SD rewrite
requires the input range `0..1` and a disabled port before rewriting them,
so its guard rejects that already-updated board description. A source-built
SD trial had previously booted without this rewrite. This explains the
observed rejection; it does not establish the result of the unsplit SEP boot.
The owner recovered the prior Linux loader; its hash and a recreated EFI
recovery copy were verified.

The corrected trial omits both our SEP split and the obsolete U-Boot SD
rewrite. Its candidate SHA-256 is
`fe18bd94decdb3ec0b77da3dbfe020f3a72ebb8bdd8a5066ad763f5feeefecac`.
It retains the same #795-derived board tree and package-managed Aura binary.

The corrected unsplit trial booted Linux on
`a0f9a8f1-5e03-4551-b5af-e160db9d99a8`. The current #795-derived board model
was present. The live tree had four overlaps: the SEP firmware reservation
intersected three DCP OS-log `no-map` regions and one `no-map` ASC region.
Linux logged `failed to reserve memory` for all three DCP OS logs and
`OVERLAP DETECTED`; the early reserved-memory summary's `nomap` label is a
device-tree description and does not override the earlier failed-reservation
messages. The SEP driver restored an enrolled identity and subsequently logged a
matching fingerprint. The owner confirmed the internal display looked normal. The package-managed loader was
verified and restored for the next boot. The installed, earlier Aura source pin
also lacked the newer upstream ANE firmware handoff, and the kernel reported
missing ANE preload reservations; this trial does not test current Aura main.

## Corrected split trial

Running the actual prototype on an in-memory copy of the unsplit Linux boot's
device tree reproduced a refusal: an ANE firmware placeholder had a zero-size
`reg`. That tree had two such placeholders. The prototype checked every
reservation for positive size before testing whether it intersected SEP, so
it rejected these unrelated empty nodes. This is a likely explanation for the
Aura-stage refusal; the inspected tree was the post-U-Boot tree from a later
boot, not the exact tree from the failed Aura boot.

The corrected prototype skips zero-size placeholders while still rejecting
wrapped ranges. On an in-memory copy of the actual post-U-Boot tree it
retained all four intersecting `no-map` nodes, including their ranges and
phandles, covered the complete SEP range, and left no overlaps within it.
No live device tree was modified or saved. The corrected loader and the current
#795-derived board tree were built and selected as
`cache/j614s-board-sep-corrected-trial/boot.bin`, SHA-256
`6d48c2747e7891bb377256e776e888d5f335eace435e594ef5a62c4fb67f2a85`.
The obsolete U-Boot SD rewrite and its old SEP split are absent. The
package-managed loader and EFI recovery copy were verified before selection.
This trial stays selected until explicitly restored; if it fails, use macOS or
recoveryOS to copy `m1n1/boot.bin.m4rch-before-sd-gpio` over `m1n1/boot.bin`
on EFI, keeping the recovery copy.

The corrected candidate booted Linux on
`aacc45f5-45d2-4047-9871-8c9131cff55a` with the updated board model. Linux
reported no failed-reservation or overlap messages; the three DCP OS-log
regions were registered `no-map`, and a read-only check found no overlapping
pairs among 33 nonempty `/reserved-memory` nodes. SEP restored an enrolled
identity, and the owner confirmed the display and fingerprint both work.
The verified package-managed default was restored for the next boot. This
is a combined-stack trial with the installed patched kernel, not an isolated
boot of a stock upstream Aura and #795 stack.

The corrected split is submitted for review as
[Aura PR #50](https://github.com/aurora-silicon/aura/pull/50), head
`ae0ff646e4a17c3dfaffa6d18d0434871c093886`. Its split logic matches the
successful integrated hardware trial; its refusal message is more general.
It builds on current Aura main, including the newer ANE preload code, but that
exact branch has not been booted. The PR explicitly describes the warm-attach
assumption, failure policy, and remaining downstream reservation and hardware
coverage limitations.
