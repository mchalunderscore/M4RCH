# Architecture

This describes the historical SD-card workflow. For the current Aurora-based
package setup, see the [package guide](../packages/README.md).

```text
Internal 4 GiB APFS boot stub                 SD card
┌────────────────────────────────┐          ┌──────────────────────────┐
│ Apple boot/recovery metadata    │          │ FAT32 EFI partition      │
│ Enrolled m1n1 + baseline DT     │─────────→│ AArch64 GRUB             │
│ U-Boot UEFI firmware            │          │ Kernel, initramfs, DTBO   │
└────────────────────────────────┘          ├──────────────────────────┤
                                            │ Persistent ext4 root     │
                                            │ Modules, KDE, user files │
                                            └──────────────────────────┘
```

## Why the internal stub exists

Apple Silicon boots authenticated objects associated with an APFS volume
group and its LocalPolicy. An ordinary FAT EFI partition does not create a
selectable Apple startup installation. The stub supplies Apple's boot and
paired-Recovery metadata; it is not a second full macOS installation.

The project follows the Asahi stub/enrollment approach while keeping
machine-specific identities and owner authorization out of reusable images.
Changing the enrolled boot object uses `kmutil configure-boot` in physically
entered, paired Recovery. Normal macOS can stage files and select a startup
target but cannot replace that authorization step. See
[Asahi's m1n1 installation guide](https://asahilinux.org/docs/sw/m1n1-user-guide/#installation)
and [Apple's LocalPolicy description](https://support.apple.com/en-gb/guide/security/secc745a0845/web).

First-time `make boot` creates a separate 4 GiB internal APFS container after
checking and displaying the macOS shrink plan and receiving its exact typed
confirmation. Phased local state identifies the new installation for resume
and later updates. Existing ready installations retain their container and
recorded UUIDs; their labels are not proof of ownership. The retired all-on-SD
APFS experiment is not the current design.

## The fixed bridge

m1n1 prepares the machine and live device tree. U-Boot completes the J614s
SD endpoint's reset/link sequence, reads the card conservatively through
PIO and provides AArch64 UEFI services to GRUB. Its configured bridge has
no USB/NVMe storage or filesystem-writing path. Firmware keyboard input is
not implemented, so GRUB boots its timed default entry.

The default loader also performs a guarded ANS initialization/shutdown
handoff for Linux's NVMe driver, before entering U-Boot. It does not read or
write NVMe namespaces. Failed prerequisites stop handoff; only successful
completion adds the live marker used by Linux. The separate SD-only loader
is retained as a fallback.

GRUB inherits m1n1's live device tree through UEFI. The SD overlay is applied
to a copy of that tree, preserving memory reservations, CPU release state,
firmware and calibration fixups. Replacing it with a generic static DTB
would discard those machine-specific values.

The internal object contains **no Linux kernel or initramfs**. Rebuilding a
kernel, its modules or the SD overlay therefore does not change Apple's
enrolled object. Changes to m1n1, U-Boot or the embedded baseline DT do.

## SD files and packages

| Location | Purpose |
| --- | --- |
| `EFI/BOOT/BOOTAA64.EFI` | Patched AArch64 GRUB |
| `grub/grub.cfg` | Root identity, kernel arguments and trial-disabled fallback |
| `vmlinuz-linux-m4rch` | Installed kernel copied by the package hook |
| `initramfs-linux-m4rch.img` | Matching early userspace |
| `dtbs/board.dtbo` | SD-side peripheral overlay |
| ext4 root | Pacman state, matching modules, firmware, services and user data |

`linux-m4rch` owns the kernel and matching modules in Linux.
`config-m4rch` owns services, boot hooks and platform policy. A package
transaction rebuilds the initramfs and publishes the corresponding ESP files.
It checks `/boot` first; copying a kernel from macOS alone would leave modules
and pacman's database inconsistent. See [package layout](../packages/README.md).

The 512 MiB ESP remains fixed. Early native boot verifies the GPT/card/root
identities and grows ext4 before mounting it. Generated manifests record the
original image, so their payload hashes need not match after legitimate
package updates. They are provenance, not a command to restore old boot files.

Fresh images mount `/boot` as root-owned 0755 directories and 0644 files:
`uid=0,gid=0,fmask=0133,dmask=0022`. FAT permissions come from mount options;
changing these masks requires a fresh mount. `/etc/fstab` is installation
state, so upgrading the configuration package does not rewrite an existing
installation's entry.

## USB2

Type-C cable events create and remove the right-port USB host through the
SN201202x/TPS6598x path. The paired Apple PHY must be initialized, its clocks
active and host reset released **before** DWC3's core reset and probe. Releasing
reset only at shutdown leaves DWC3 unable to complete initialization.

The driver tracks the PHY's hardware lifecycle across attachment and removal.
Failed DWC3 probes release their devres group and clear stale binding state
before retry; successful bindings retain their proper lifetime until removal.
Repeated attach/detach is native-tested. Forced probe-failure cleanup is covered
by compiled fixtures rather than physical fault injection. See
[the retained USB patch provenance](usb-patchset-provenance.md).

## Desktop boundary

SDDM's greeter remains X11. Autologin selects Plasma Wayland with
`KWIN_COMPOSE=Q` in the KWin user service, plus software Qt/OpenGL rendering.
Plasma 6.8 removed its X11 session; fresh images provide Plasma Wayland only.
These are userspace choices; neither supplies an M4 GPU driver.
Wayland's native backend remains unverified until the next hardware test.
