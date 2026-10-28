# Installation and maintenance inventory

This is a snapshot of the J614s system reviewed on 27 October 2026, not an
automatic inventory. Check installed versions and active boot files before an
update. Package recipes and current build limitations are in the
[package guide](../packages/README.md).

## Installed local packages

`pacman -Q` reported `linux-m4rch 7.3.0-9`, `m1n1-m4rch 20261025-2`,
`u-boot-m4rch 2026.07-3`, `mesa-m4rch 1:26.3.0.r20261026.f2c9dc3-5`,
`mesa-flatpak-m4rch 26.3.0.r20261026.f2c9dc3-1`, `virglrenderer-m4rch
1.3.0-3`, `alsa-ucm-conf-m4rch 1.2.16.1-2`, `asahi-scripts-m4rch 20261026-3`,
`avd-fw-m4rch 20261022-1`, `linux-firmware-vendor-m4rch 20261026-1`,
`mbpfan-m4rch 2.4.0-4`, `power-profiles-daemon-m4rch 0.30-1`, `grub-m4rch
2:2.16-1.1`, `steam-m4rch 1.0.0.81-11`, `paru-m4rch 2.1.0-1`,
`signal-desktop-m4rch 8.32.0-1` and `vesktop-m4rch 1.6.8-1`.
The old `muvm-m4rch`, `fex-emu-m4rch` and `fex-rootfs-debian-m4rch` packages
were not installed. Their recipes and experiments still need review before
retirement; they may contain useful historical or future maintenance work.

## System services

The current installation uses device-driven module loading. The packaged
`apple-silicon.service` was removed in `asahi-scripts-m4rch 20261026-3`, and
`mbpfan-m4rch 2.4.0-4` no longer depends on it. The normal entry booted on
28 October; the attended autoload trial also passed desktop and lid wake checks.
Fans tracked their requested targets. External output with autoload is still
untested; see the [autoload record](driver-autoload-investigation.md).

The initial M4RCH SD-image builder explicitly masked `sshd.service` and
`sshd.socket`, along with `systemd-networkd`, `systemd-resolved` and their
sockets. On 28 October the five remaining persistent image masks were removed.
The underlying networkd and resolved services and sockets were disabled before
unmasking so they would not replace NetworkManager or its DNS configuration.
NetworkManager and `sshd.service` remained active and DNS resolution succeeded.
The installed OpenSSH package does not currently provide `sshd.socket`.
The prior network/SSH unit links are archived locally under
`out/old-mask-removal-20261028/`; this ignored backup is not in Git.

At the earlier audit, remaining masks were temporary runtime masks, not
persistent policy. The old loader unit has been removed from its package.

The account-rename, VRR, external-display, Plymouth trial and driver-autoload
one-shot services and their local helpers were retired on 28 October after
checking that no associated trial or account migration was armed. Plymouth's
distribution-provided units remain installed.

## Promoted boot and build records

The promoted kernel image, J614s device tree, m1n1 and U-Boot binaries under
`out/external-investigation/promotion/` were compared byte-for-byte against
their installed counterparts. The kernel configuration and packaged patch
records were also compared against `/usr/share/doc/{linux,m1n1,u-boot}-m4rch`.
The matches identify these local artifacts; they do **not** prove a clean build
can reproduce them.

The corresponding source records are now under
[`packages/linux-m4rch/promoted-source`](../packages/linux-m4rch/promoted-source/),
[`packages/m1n1-m4rch/promoted-source`](../packages/m1n1-m4rch/promoted-source/)
and [`packages/u-boot-m4rch/promoted-source`](../packages/u-boot-m4rch/promoted-source/).
The Linux records include the combined local kernel patch, the external display
and VRR deltas and the exact configuration. The U-Boot record is the combined
patch. The m1n1 record is the external-handoff delta, not a complete m1n1 source
tree. The U-Boot patch contains this installation's ESP partition UUID; review
or parameterize that machine-specific value before publishing or building for
another installation. Consult the [external-display](external-display-investigation.md) and
[boot comparison](boot-upstream-comparison.md) notes for provenance and
limitations. These new source records are uncommitted; Git history cannot
recover them until they have been saved in a commit or another durable backup.

SHA-256 values of the matching local binaries and module archive:

| Artifact | SHA-256 |
| --- | --- |
| Kernel Image | `32b085811907861451eb3e3f5579d1d00ea23f14e481952716caf314cf42e483` |
| Module archive (not compared to installed module tree) | `35e08120b42a648e73af9b1f3a12e8b4cd53fa77979ba521ea79ef8ed2ffc6a5` |
| J614s device tree | `6bc64d21a2a45783bd48a76e3ea7447db6932592a170fc1e4213933a1b762a9d` |
| m1n1 stage two | `ce7667abd7b971e992193d6fe663bb694cfb5d0e53ee79accf4b696e4a4f9b73` |
| U-Boot | `024f76aff79e81818abfa9f92c0122f644fa76715656c0cc3f5aad42fd162a0a` |

`packages/tools/prepare.py` still requires the ignored promotion binaries and
other local package inputs. It verifies that preserved source records match
the promotion directory. The existing `make packages` and cached installer
remain unqualified for the installed stack; do not run the installer blindly.
The bulk package lists now include power profiles and omit the retired guest
packages, and the validator targets the current kernel and boot options. These
changes still need an end-to-end disposable build and transaction. Firmware and calibration are machine-local and must be backed up
separately rather than added to Git.

## Boot recovery

The machine uses an enrolled first-stage m1n1, the ESP boot bundle containing
the second-stage m1n1 and U-Boot, and GRUB on the internal NVMe. The normal
`Arch Linux` entry is selected by `GRUB_DEFAULT=0` and contains the promoted
autoload and display options. The owner reported a successful normal boot on
28 October. External output under the autoload setup remains untested.

The retired ESP backups, trial entries and services were removed at the owner's
request. Their temporary boot archive was retired after the successful normal
boot; it is no longer a recovery option. Keep independent, current backups for
recovery: GRUB keyboard input is unavailable on this machine. Upstream's
`update-m1n1` may create a new `/boot/boot.bin.old` on a future bundle update.
