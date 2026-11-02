# Booted J614s upstream PR package snapshot

This is historical provenance. The current fork-based promoted stack and its
standard updater are described in [status](../../docs/status.md).

Aurora Linux [PR #795](https://github.com/aurora-silicon/linux/pull/795)
merged as `dc87ceeea59f7b1075fd5e7659869dc12dd16ca9` on 2 November 2026.
The earlier booted snapshot below predates that merge. Its
board tree is based on an earlier #795 head, not the final merged tree. The
final tree disables the J614 speaker card and amplifiers pending speaker
bring-up and protection; that behavior must be considered when rebasing.
The merged tree does not incorporate the separate AOP jack registration change.

## Rebuild on the merged tree

The installed `7.3.0.aurora1-9.6` kernel and matching headers were built
from #795 merge `dc87ceeea59f7b1075fd5e7659869dc12dd16ca9`, with the exact
upstream PR commits #821 `4ca62110a994f246c5c97806ab70974b1f0e7e32`, #804
`c6665bed9ad1dce905ee35c4cebaf44054792ebb` and #817
`f015a5c51644cea20421f7ae571fe03dd24705e9` applied on top. The clean local
source checkout has head `9fa275dd0435aa07a4a2ec507201d4fd3bde8b14`.
No local board or SEP patch is applied. This is a newer Aurora base with
other upstream changes as well; the #795 merge disables J614 speakers.

The full kernel, modules and DTBs built successfully. The kernel release is
`7.3.0-j614s-merged795-ARCH+`; the GPU and storage modules and an external
module compiled against the matching packaged headers all report that same
release. The GPU module contains BTF. The package files and build logs are in
`cache/upstream-stack/merged795-package/`:

- `kernel-build/linux-aurora-7.3.0.aurora1-9.6-aarch64.pkg.tar.xz`:
  SHA-256 `f8ee4109124994477ad38e27d05c04b34ec063d62d3ad43ce11508b0771414a8`.
- `headers-build/linux-aurora-headers-7.3.0.aurora1-9.6-aarch64.pkg.tar.xz`:
  SHA-256 `b1c3d4559831e4e12d734efc4bcf18ae50af19b6fec9159aa021488a1f18be77`.

These packages are installed as the persistent default along with config
`20261101-8`, Aura boot bundle `20261102-3`, and a newly built initramfs.
GRUB and the retained recovery archive were verified, but the new default
has not yet been booted. The previous running kernel's modules remain
temporarily available until reboot. See [recovery](../../docs/recovery.md).

The November 2, 2026 J614s boot uses Linux PR #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537` with #821, #804 and #817
merged into `c6af520e2920e3b5b2b604b23e89b2fcede369e3`; Aura merge
`3bb98101f66964c7f479d01171d6d7aaa129fc6d`; and U-Boot #29 head
`7a6dc91397981d52339be0fa7cce981bc5d47c2d`. These are upstream sources and
PR changes; the packaging does not apply additional source patches.

The snapshot PKGBUILDs package the exact binaries built and booted from these
checkouts. They deliberately reference the local build and prior package inputs
under `/home/michal/Projects/m4rch/cache/`; they are provenance for this
machine, not self-contained general release recipes. The Aura snapshot
preserves the previous package's stage-1 artifacts; it does not enroll or
update stage 1. The earlier boot bundle recipe was retired when the standard updater was enabled; the later platform configuration package was also retired after a successful Aurora-default boot.

The tested package archives, previous packages, source recipes, old boot files
and both prior loader copies are preserved in
`/var/lib/m4rch/upstream-pr-stack-promotion-20261102`. The retained EFI
recovery loader is `m1n1/boot.bin.m4rch-before-sd-gpio`. The kernel used for
the trial has booted; the final GRUB default was generated and verified but
has not yet been independently booted. On a later boot using the same stack
with an experimental GPU thermal device-tree change, a USB 3 flash drive
negotiated 5 Gb/s and passed read checks in both orientations on all three
ports, with one initial USB 2 fallback that did not recur on retry. See
[USB test details](../../docs/j614s-atc-handoff.md). HDMI, USB-C display,
USB write integrity and the wired jack remain to be tested on this stack.

Mesa PR #138 and the audio and UCM PR packages were installed for the trial.
The Flatpak graphics extension was removed because it was tied to the prior
Mesa; its rollback package remains in
`/var/lib/m4rch/upstream-pr795-trial-20261102`. Standalone FEX was not built.
