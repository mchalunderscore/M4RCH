# J614s USB and HDMI tuning handoff

> This is a chronological investigation. Statements about the installed stack,
> selected trials and recovery files refer to the recorded time unless a later
> update says otherwise. Historical cache artifacts are mostly unavailable.
> For the present boot recovery path, see [recovery](recovery.md).

The earlier package-managed U-Boot overlay copied per-device ADT tuning into the
Linux tree for three USB-C PHYs and controllers, and for the HDMI PHY. Its
HDMI path staged tuning while leaving the PHY disabled for Aurora's display
power gate; the final Linux tree on the DAPF trial had all four PHY nodes
enabled and their expected tuning property names present. This observation
does not independently test the USB-C ports or validate the tuning values.

In that earlier stack, Aura called `kboot_setup_atc()`, but its path first resolved
`atcphy0` through `atcphy3` aliases. None of those aliases is present in the
trial J614s tree. Moreover, that Aura fallback ATC table wrote a different
set of property names and offsets from the local T6040 U-Boot handoff. Adding
aliases alone therefore does not establish equivalence. Aurora's current
[`kboot_atc.c`](https://github.com/aurora-silicon/aura/blob/main/src/kboot_atc.c)
also lacks the local T6040-specific lane tuning names as checked on 1 November
2026. This comparison is of code and property presence, not a byte-for-byte
comparison of per-device tuning data.

The later installed Aura pin contains the J614s USB and HDMI exporter associated
with [#49](https://github.com/aurora-silicon/aura/pull/49) and [#53](https://github.com/aurora-silicon/aura/pull/53); the installed U-Boot pin is
[#29](https://github.com/aurora-silicon/u-boot/pull/29). The following analysis describes the earlier U-Boot handoff and remains useful for review.
The upstream direction was to adapt Aura's existing ATC exporter for
the actual T6040 DT binding and then remove the U-Boot duplication, preserving
its fail-closed behavior and the separate HDMI display gate. Before trying
that, compare every source property, destination, bias, range check and
failure path against the Linux PHY and USB drivers, then compare the produced
trees and exercise the affected ports on hardware. The known-working combined
stack produced a working HDMI display, but USB-C display output and each
individual USB port have not been qualified by that observation.

## Consumer contract

In the tested kernel's `drivers/phy/apple/t6040-usb2.c`, the first nine
PHY properties in the U-Boot table are parsed in order against their named
register resources; missing or invalid USB3 tuning falls back to USB2.
`apple,tunable-pipehandler` is also required for USB3, whereas
`apple,tunable-usb2-host` is parsed only when present. The USB controller's
five properties are consumed separately by `drivers/usb/dwc3/dwc3-apple.c`.
The HDMI PHY receives the nine common PHY properties but not the USB-only
pipe-handler or USB2-host properties. The local handoff requires all of the
properties it copies; its policy is therefore stricter than simply matching
what the USB2-only fallback accepts.

Aura's existing `dt_append_atc_tunable()` validates record width and alignment
and checks offsets against a table-specific resource size before appending
big-endian tuples. The local U-Boot converter checks 32-bit records, alignment
and a generic offset bound, then applies each destination's bias. A migration
must compare these limits to each actual resource rather than assume that the
two validators are interchangeable. The earlier HDMI helper staged changes in
a scratch tree and refused the display handoff on failure; its USB loop logged
an error and relied on the input PHY starting disabled. These distinct failure
paths need explicit tests before either implementation is replaced.

On the 1 November DAPF trial boot, a read-only check decoded the live tree's
PHY tuning tuples and compared their aligned 32-bit offsets with the sizes of
the named `reg` resources selected by the kernel PHY driver. All 662 tuples
across the three USB-C PHYs and the HDMI PHY fit their respective resources.
The check printed only property names, counts and failures; it did not save or
publish calibration values. This supports resource-specific validation for
this boot, not assumptions about other machines or whether the tuning itself
is correct. The same check compared the three controllers' 45 tuning tuples
with their driver's global, debug, link and `drd-cfg` subranges; all were
aligned and within bounds. No device access or boot change was made for these
checks.

The compiled board DTB bundled into the historical trial was recorded at
`cache/j614s-pr795-trial/board.dtb`. Inspecting it without extracting or
printing calibration data shows that all four PHY nodes start disabled but
already contain nonempty tuning properties; the three USB controller nodes
start enabled and likewise contain tuning properties. Comparing the input
DTB to the final Linux tree showed that some, but not all, property payloads
changed on every port. This comparison does not identify which boot stage
changed any particular property. It does establish that mere property
presence cannot prove successful per-device export, and a replacement must
not silently treat the compiled-in values as newly validated firmware data.
Failure handling must account for enabled controller nodes as well as disabled
PHY nodes. Confirm the exact input tree immediately before U-Boot, because Aura
can modify the compiled DTB between these observations.

In the pinned Aura tree, `kboot_setup_atc()` runs before `dt_set_display()`.
That ordering makes it possible to validate and stage HDMI PHY tuning before
the display handoff, but the existing external-DCP admission validates its
firmware and reserved-memory descriptors, not the local HDMI tuning result.
An Aura implementation must explicitly connect those outcomes: a failed PHY
export cannot simply leave the existing external-DCP handoff eligible. The
earlier U-Boot code removed the relevant DCP's `memory-region` after export
failure; preserve the resulting admission behavior while moving ownership,
and independently verify that an internal-only display still starts.

## Combined ownership trial — 1 November 2026

The local [Aura prototype](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/aura-j614s-atc-experiment.patch)
reuses Aura's ATC parser and validates each output against the corresponding
kernel register window. It stages each port on a scratch tree. The HDMI PHY
must start disabled and stays disabled for the existing display power gate;
if HDMI tuning fails, the external DCP is denied its firmware handoff. The
[board-tree experiment](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/j614s-atc-dts-experiment.patch)
adds aliases and disables the devices before the loader prepares them. This
requires a coordinated loader transition and is not safe to merge alone on
systems with an older loader. The matching [U-Boot experiment](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/uboot-atc-aura-ownership-experiment.patch)
removes only its duplicate USB and HDMI producers.

A combined trial was built from the package-managed Aura and U-Boot sources,
with the ATC changes above and the previously booted #795-derived board tree.
The candidate stage two has SHA-256
`2f428613a034a67da3b729ec652f89325186b894dd98af025271f7cb98ea2f26`.
Its component hashes and the unbooted status are recorded in
`cache/j614s-atc-ownership-experiment/trial-receipt.json`. The selected EFI
loader and recovery copy were verified during staging. For comparison after
boot, `baseline-property-hashes.json` contains hashes of all 57 tuning
properties from the prior running tree, without their calibration values.
The alias-based trial was replaced before boot. Its old recovery copy and
instructions are historical; see [current recovery](recovery.md). USB-C and
HDMI needed hardware testing on that candidate.

The device-tree experiment has also been refreshed onto board PR #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537`. It compiled using that revision's
exact device-tree includes; its compiler warnings matched the unmodified board
tree. The resulting DTB resolves all seven aliases to the intended PHYs and
controllers and starts those nodes disabled. This source-built DTB is not the
DTB staged for the pending hardware trial, which uses the older boot-tested
board tree with the equivalent alias/status edits. The refreshed experiment
retains the same old-loader compatibility concern and is not yet a standalone
upstream submission.

## Alias-free alternative

The updated #795 tree already contains all seven expected fixed device paths;
its three USB PHYs and controllers start enabled and its HDMI PHY starts
disabled. The local
[alias-free Aura prototype](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/aura-j614s-atc-no-alias-experiment.patch)
uses those already-checked paths directly instead of requiring seven new DT
aliases. It compiles as `kboot_atc.o` and removes the need for the proposed
DT-only coordination change if the rest of the handoff proves correct. An older
Aura sees the unchanged board tree; a new Aura performs the per-device export
and disables a port on export failure. This changes when the handoff runs on
older J614s trees, so the interaction with their existing U-Boot producer must
be reviewed and boot-tested rather than inferred from compilation. The alias-free alternative was subsequently selected and tested as described
below.

The old U-Boot producer can complicate a failed export. It starts from Aura's
output and enables a USB PHY after its own, less restrictive conversion; it
does not re-enable a USB controller that Aura disabled. However the board's
USB-C display routes can also reference those PHYs independently of the USB
controller. Thus disabling the controller alone does not establish that a
PHY rejected by Aura stays unused when the old producer runs afterward. For
HDMI, Aura's failed-export path removes the external DCP `memory-region` and
the old producer does not restore it. The alias-free alternative must resolve
the USB-C failure case or be coordinated with removal of the older producer
before claiming a safe transition. This is a source-level edge case; the
captured tuning on this Mac passed the proposed resource bounds.

The historical [ownership checker](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/check-atc-ownership.py) compared 57 properties against the trial baseline without printing calibration data. Its saved baseline hashes are in the private cleanup archive. A match needs separate physical USB testing and is not proof of HDMI operation.

## Selected alias-free trial

At the owner's request, the earlier alias-based trial was replaced before its
boot with the alias-free candidate. The selected bundle has SHA-256
`dc6c2230593816af478cfb1e86c2b4230eeeae62c40ce33ec050cf5422d1a92e`;
its receipt and exact Aura binary are in `cache/j614s-atc-no-alias-trial/`.
It uses the previously booted #795-derived board DTB without added aliases,
and the U-Boot trial image without the duplicate USB/HDMI producer. The EFI
known-good recovery copy and both trial bundles were verified and archived
when this candidate was selected. The package-managed default was restored after boot. The old restoration helper and recovery instructions are historical; see [current recovery](recovery.md). This trial did not by itself qualify HDMI.

The alias-free trial reached Linux on boot
`962a0ea0-87ed-48f1-a5d3-e4f00aabb210`. All 57 live tuning properties
matched the earlier working boot's hashes, and the intended nodes were enabled.
The owner confirmed a USB device was detected in all three USB-C ports; kernel
logs show USB 2.0 enumeration through each corresponding PHY. Although the
USB3 PHYs reported tuning, the full-speed device did not test USB 3 data or
USB-C display output. The package-managed stage two was restored and verified
for the next boot; the restoration did not interrupt that trial session. HDMI remains
untested on this candidate.

## Submitted USB-only change

[Aura PR #53](https://github.com/aurora-silicon/aura/pull/53) extends the
USB proposal with the HDMI PHY handoff. The integrated trial above
confirmed that the HDMI tuning properties were copied, but it did not test a
connected display. The changed files compiled and linked in a reconstructed
Aura tree; the complete exact PR branch has not been built or booted. HDMI
output still needs a cable and display before the change can be qualified.

[Aura PR #49](https://github.com/aurora-silicon/aura/pull/49) proposes the
three USB-C ports without the separate HDMI handoff. Its only changed file is
`src/kboot_atc.c`, based on Aura `main` at `212e3d1`; the per-port conversion is
the one used in the combined-stack trial, with the HDMI branch removed. The
USB-only ESP image built successfully from an earlier source pin with the same
unmodified ATC file, reusing a source/config-verified Rust library. The exact
USB-only branch and stock Aurora stack have not been booted. The PR records
the successful USB 2.0 test on all ports, matching hashes for the 48 USB
properties, and the outstanding USB 3, USB-C display, suspend and error-path
checks. It also calls out the downstream U-Boot producer's potential to
re-enable a PHY after a failed Aura export.

## USB 3 flash-drive test — 2 November 2026

On boot `18f0bfc9-9e32-4d9d-8c68-9fa6ac42f514`, running
`7.3.0-j614s-pr1-ARCH`, a SanDisk USB 3.2 Gen 1 flash drive enumerated at
5,000 Mb/s in both plug orientations on all three controllers
(`38a280000.usb`, `382280000.usb`, `392280000.usb`). In each port and
orientation, two direct 128 MiB reads from the unmounted drive matched. These
were read-only checks; no filesystem or user data was modified.

The first connection on `38a280000.usb` initially enumerated at USB 2's
480 Mb/s. Flipping it negotiated 5,000 Mb/s, and a later retry in the original
orientation also negotiated 5,000 Mb/s and passed both reads. The initial
fallback was not reproduced by that retry; its cause is unknown.

This boot used the upstream PR-stack kernel and loader components with the
experimental GPU thermal device-tree change running. The installed normal
loader had already been restored for the next boot. The test establishes
5 Gb/s link and read operation for this device, not write integrity, 10 Gb/s,
suspend/resume, hubs or USB-C display support.
