# Arch packages

This guide describes the local packages for the 14-inch M4 Pro J614s. As of
27 October 2026, the installed package versions include `linux-m4rch 7.3.0-9`,
`m1n1-m4rch 20261025-2`, `u-boot-m4rch 2026.07-3`, and
`power-profiles-daemon-m4rch 0.30-1`. The normal GRUB entry booted with the
promoted `7.3.0-m4rch-vrr-ext` stack. Built-in speakers remain disabled. See
[external-display promotion](../docs/external-display-investigation.md) and
[power profiles](../docs/power-profiles-investigation.md).

The normal GRUB entry now permits device-driven driver autoloading. The running
session passed the one-boot autoload trial and a lid wake; the normal entry
also booted, while external output under autoload remains untested. Installed
`asahi-scripts-m4rch 20261026-3` and `mbpfan-m4rch 2.4.0-4` remove the old
service and fan dependency. See the [driver-autoload record](../docs/driver-autoload-investigation.md).

| Package | Contents |
| --- | --- |
| linux-m4rch | Kernel, modules, mkinitcpio preset and boot device tree |
| mesa-m4rch | Native Mesa/GBM/DRI/EGL/GLX/Vulkan under /usr/lib |
| mesa-flatpak-m4rch | Freedesktop 25.08 and 26.08 GL.host extensions |
| m1n1-m4rch | Aurora second-stage m1n1 |
| u-boot-m4rch | Aurora U-Boot |
| linux-firmware-vendor-m4rch | Locally extracted firmware and ALS calibration |
| avd-fw-m4rch | Asahi open-source AVD v5 tier 1 firmware |
| alsa-ucm-conf-m4rch | Stock ALSA profiles plus J614 microphone and J616-labelled jack profiles |
| asahi-scripts-m4rch | Upstream update-m1n1 and hardware configuration |
| virglrenderer-m4rch | Asahi native-context backend paired with Aurora Mesa |
| steam-m4rch | Native ARM64 Steam launcher using 4 KiB user processes |
| mbpfan-m4rch | mbpfan with macsmc RPM target and temperature sensor support |
| power-profiles-daemon-m4rch | J614s CPU frequency caps integrated with desktop power profiles |
| vesktop-m4rch | Vesktop with Electron 45's corrected libyuv SME build |
| signal-desktop-m4rch | Signal desktop with the local Electron runtime |
| paru-m4rch | AUR helper |
| grub-m4rch | GRUB EFI boot manager |

The retired muvm/FEX guest recipes for the older Steam setup are available in
Git at `e7baa0e`; the current Steam package does not depend on them. The
separate installed custom ARM64 Proton compatibility tool remains documented
in [its source notes](proton-arm64-sme/README.md).

The existing GRUB package and enrolled first-stage loader remain installed.
The bootloader pair uses the previous native-working m1n1 and U-Boot binaries.
The local NVMe timeout-recovery candidate was withdrawn after a native boot
loop. A later audit found that the reconstructed source for the installed
U-Boot binary contains a separate generic post-M4 timeout/reset path; the
rebuilt binary matches the installed U-Boot byte for byte. Whether that path
corresponds to the withdrawn candidate or has ever run on this machine has
not been established. See [the boot comparison](../docs/boot-upstream-comparison.md).

## Installation and updates

The older kit under `/var/cache/pacman/pkg/m4rch/` predates the promoted VRR,
external-display, microphone and power-profile changes. Its installer writes
boot files and regenerates GRUB. Do not run that older kit over the current
system without reviewing and rebuilding it for the current package versions.
The bulk package builder and installer do not yet include
`power-profiles-daemon-m4rch`.

Subsequent updates use ordinary pacman. Stock depmod/mkinitcpio hooks maintain
`/boot/vmlinuz-linux-m4rch` and `/boot/initramfs-linux-m4rch.img`. Asahi's
unmodified update-m1n1 maintains `/boot/boot.bin` and `/boot/boot.bin.old`.
Regenerate GRUB with `sudo grub-mkconfig -o /boot/grub/grub.cfg` when needed.

## Package and runtime notes

The earlier October 26 package candidate paired Aurora kernel integration commit
`9cbdd0734d9e186c5f5f5949a21b909d10c2571b` with Mesa commit
`f2c9dc3fb59c81fdaf51f19884175c856e3d1889`. It retains this machine's
16-core GPU support, firmware identity, boot handoff and DCP settings.
Kernel configuration enables KVM, vhost networking and vsock. Fan writes are
opted in with macsmc_hwmon's fan_control parameter. The enabled mbpfan service
uses macsmc's RPM targets and CPU/GPU/SoC temperatures, with firmware-provided
RPM limits. The 2.4.0-3 quiet trial filters ordinary temperature changes with
an eight-second time constant, ramps from 75 to 90 degrees Celsius, and requests
full cooling immediately at a raw 90 degrees or on invalid sensor data. The
curve is an initial tuning, not a measured reproduction of macOS. Stopping the
daemon restores firmware automatic operation.
The revised fan driver was tested on the J614s, including a fresh boot,
both fans tracking requested speeds, and handoff back to firmware control.
The owner reports that the fans have remained responsive during extended Linux
use since boot; longer-term reliability remains to be established.

The main kernel package also carries the Asahi deferred handle-close fix in
`patches/linux-asahi-deferred-close-rebind.patch`. It prevents pending cleanup
from removing a successfully rebound GEM mapping. The owner confirmed that the
same fix resolved the KWin Alt+Tab freeze and that Alt+Tab works on the main
kernel. A rebound
object's older mappings can remain until a later handle close or VM teardown;
the main kernel booted successfully on 27 October.

The main kernel package also contains the fan changes in
`patches/experimental-aurora-pr512-fan.patch` and
`patches/experimental-j614s-fan-unlock-retry.patch`. The tested retry uses a
three-second delay and a 30-second retry bound after the SMC unlock; a failing
hwmon operation can therefore block for roughly 33 seconds. The main kernel
booted on 27 October with both fans tracking mbpfan's targets.

The earlier U-Boot `2026.07-2` promotion removed the experimental `/AURD001/mode` selector and uses
the normal GPU handoff without reading an ESP mode file. The older ESP bundle
and mode file were removed, and their temporary archive retired after the
normal boot on 28 October. That
loader booted successfully on 27 October; the removed selector's framebuffer mode
is unavailable with it. This removes one local dependency, but the custom
`archnvme` boot path remains distinct from upstream U-Boot standard boot.

The native Vesktop package retains hardware acceleration. Electron 45 includes
the libyuv build correction for SME-capable Apple CPUs without ordinary SVE;
the old runtime crashed in CopyRow_SME while rendering GIFs. The Flatpak app
bundles its own Electron and is not replaced by this native package.

Flatpak uses the standard unmanaged GL.host extension locations for both
runtime branches. These are built against their respective Freedesktop SDKs;
they do not bind host /usr/lib into applications. The package includes LLVM
runtime libraries absent from the Freedesktop Platform. Flatpak continues to
manage applications and runtimes normally. Older runtime branches are not
covered by these extensions.

DCP keeps parsing recognized power reports. Unknown optional desktop 26.6
power telemetry is logged at debug level instead of repeatedly warning; its
format has not been implemented. ALS calibration is copied unchanged from
this machine's macOS IORegistry and stays in the local firmware package.

AVD firmware availability does not establish working hardware video decoding.

## Steam

The installed `steam-m4rch 1.0.0.81-11` launches Valve's ARM64 Steam client
as the regular user with Aurora's `userpages` helper. It requires the kernel's
4 KiB user-process mode (`user4k=on`) and an existing ARM64 Steam installation
under `~/.steam/root`; the launcher reports an error if either is missing.
The client and local support libraries live in the user's Steam directory, so
reinstalling the package alone does not create a complete fresh Steam setup.
Proton may use FEX for Windows game code. The launcher uses an Aurora guest
Mesa graphics provider when available. See the [graphics investigation](../docs/gpu-reclaim-investigation.md)
and [Steam history](../docs/steam-acceleration.md) for tests and limitations.
The older muvm/FEX launcher and Debian guest rootfs are historical, not the
installed Steam package's default path.

## Build

The historical `make packages` workflow uses a macOS `container` command and
an Arch ARM build VM. It prepares and builds ordinary PKGBUILDs and runs
validation against a mounted root; it is not a native Linux one-command build.
The bulk preparation, build, validation and installer package lists now include
the installed power-profiles daemon and omit the retired muvm/FEX guest set.
`validate.sh` targets `7.3.0-m4rch-vrr-ext`, the current boot options and the
speaker-module blacklist. The 14-package installer and boot hooks passed a
disposable reinstall test with the limitations described in the [maintenance
inventory](../docs/installation-maintenance.md). The newer audio and platform
configuration package candidates have been built but not installed or tested
in that transaction; the macOS bulk builder and a fresh install have not been
qualified. Local build inputs
are under `out/packages/source/`; firmware inputs are machine-local. Kernel
configuration and patches are included in the kernel package. The Flatpak
build helper uses Freedesktop SDK 25.08/26.08 and LLVM 22; its pinned Mesa and
SPIR-V source inputs were recorded under `out/candidate-20261026/`.
Some local build inputs, including `out/packages/source/`, are absent; prepare
the required source archives and firmware again before running
`make packages`. Some promoted boot artifacts remain under
`out/external-investigation/promotion/`. The repository alone does not contain these machine-local inputs.
`make check` checks host helper syntax and runs the retained Python unit tests.
Standalone tests in `packages/tools/` may need patched upstream source trees or
local socket access; they are not part of this check. Linux hardware behavior is
validated by booting the candidate, separately from the container build checks.
