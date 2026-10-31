# Packages

These recipes describe the packages installed on the J614s system. The current
versions, boot state and operational notes are in [system status](../docs/status.md).
Recipes may include subsequent packaging-only changes that have not been installed.

| Package | Purpose |
| --- | --- |
| linux-m4rch | Kernel, modules, initramfs preset and device tree |
| m1n1-m4rch, u-boot-m4rch, grub-m4rch | Boot chain |
| mesa-m4rch | Native Mesa graphics drivers |
| linux-firmware-vendor-m4rch, avd-fw-m4rch | Machine firmware and AVD firmware |
| alsa-ucm-conf-m4rch, asahi-scripts-m4rch | Audio configuration and hardware setup |
| mbpfan-m4rch, power-profiles-daemon-m4rch | Fan and CPU power policy |
| steam-m4rch, proton-arm64-sme | Native Steam launcher and installed Proton compatibility tool |
| vesktop-m4rch, signal-desktop-m4rch, paru-m4rch | Desktop applications and AUR helper |

Patch provenance and package-local attribution are described in
[patch organization](PATCHES.md) and the package source records. Firmware and
calibration are machine-specific and are not supplied by a clone. Built-in
speakers remain disabled; see the [speaker safety assessment](../docs/j614s-speaker-safety-investigation.md).

## Native package builds

On native Arch Linux ARM, use an ordinary user account with `makepkg` and the
package's build dependencies installed:

```sh
make prepare-package PACKAGE=linux-m4rch
make packages PACKAGE=linux-m4rch
make packages PACKAGE=mesa-m4rch
```

Supported names are `linux-m4rch`, `m1n1-m4rch`, `u-boot-m4rch`, and
`mesa-m4rch`. Each command uses a fresh directory under `out/native/`;
`python3 packages/tools/native.py --help` describes the options. Builds do not
install packages or dependencies. Other recipes are not integrated into this
native workflow.

The ALSA, platform configuration, vendor firmware, mbpfan and Vesktop
recipes relied on local source archives and generated checksum lists from the
retired preparer. Those archives are no longer present, and these five recipes
do not contain complete checksums; they cannot be rebuilt directly as checked
in. Their package files and patches record the installed system, but rebuilding
requires recovering or reconstructing the inputs and verifying their hashes.
The Steam recipe pins the launcher archive digest recorded during its previous
package build. The archive must be downloaded to rebuild it; that download was
not independently verified during this audit.
The Signal recipe uses the cached Signal and Vesktop binary packages as inputs;
see its [package notes](signal-desktop-m4rch/README.md).

The boot package commands verify and repackage retained binaries. The current
kernel and U-Boot inputs are in `cache/mtp-promotion/inputs/`; m1n1 remains in
`cache/installed-20261031/`. They do not compile a new kernel or bootloader.
The previous kernel's historical source tree was not fully reconstructed.
Mesa instead builds its pinned Aurora source. Check dependencies and disk space
before building. `make check` checks recipe syntax, recorded patch digests and
Steam launcher behavior; it does not check that every recipe has the inputs and
checksums needed to build. It also does not test hardware boot, rendering or
recovery. Read [recovery](../docs/recovery.md) before installing a new boot chain.

The native workflow follows Aurora's [package builder](https://github.com/aurora-silicon/alarm-aurora/blob/main/scripts/build-package);
its [Mesa pin](https://github.com/aurora-silicon/alarm-aurora/pull/65) contains
the packaged Mesa revision. The local preparer supplies the machine-specific
boot artifacts and source records.
