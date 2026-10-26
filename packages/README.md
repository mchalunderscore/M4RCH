# Arch packages

Modified packages use the existing package name with `-m4rch` appended.
The machine name is `Apple MacBook Pro (14-inch, M4 Pro)` and the kernel
release is `7.3.0-m4rch`. Built-in speakers remain disabled.

| Package | Contents |
| --- | --- |
| linux-m4rch | Kernel, modules, mkinitcpio preset and boot device tree |
| mesa-m4rch | Native Mesa/GBM/DRI/EGL/GLX/Vulkan under /usr/lib |
| mesa-flatpak-m4rch | Freedesktop 25.08 and 26.08 GL.host extensions |
| m1n1-m4rch | Aurora second-stage m1n1 |
| u-boot-m4rch | Aurora U-Boot |
| linux-firmware-vendor-m4rch | Locally extracted firmware and ALS calibration |
| avd-fw-m4rch | Asahi open-source AVD v5 tier 1 firmware |
| alsa-ucm-conf-m4rch | Stock ALSA profiles plus Apple profiles |
| asahi-scripts-m4rch | Upstream update-m1n1 and hardware configuration |
| muvm-m4rch | Host/guest microVM tools |
| fex-emu-m4rch | FEX x86/x86-64 emulation tools |
| fex-rootfs-debian-m4rch | Read-only Debian 13 amd64/i386 userland with paired Aurora Mesa |
| steam-m4rch | Valve launcher, Steam menu entry and automatic muvm/FEX launch |
| mbpfan-m4rch | mbpfan with macsmc RPM target and temperature sensor support |
| vesktop-m4rch | Vesktop with Electron 45's corrected libyuv SME build |

The existing GRUB package and enrolled first-stage loader remain installed.
The previous working GRUB entry uses its own kernel and initramfs.
The bootloader pair uses the previous native-working m1n1 and U-Boot binaries.
The NVMe timeout-recovery candidate was withdrawn after a native boot loop;
its controller-reset fallback is not included in the installed package.

## Install

The offline package kit is staged at `/var/cache/pacman/pkg/m4rch/`.
From a Linux terminal run:

```sh
sudo bash /var/cache/pacman/pkg/m4rch/install.sh
```

This verifies the archives, installs them with pacman, configures Flatpak's
renderer selection, and runs mkinitcpio, upstream update-m1n1 and grub-mkconfig.
It preserves the previous working entry and selects the normal Arch entry by
default. It never reboots. Boot file backups go under `/root/boot-backup-*`.

Subsequent updates use ordinary pacman. Stock depmod/mkinitcpio hooks maintain
`/boot/vmlinuz-linux-m4rch` and `/boot/initramfs-linux-m4rch.img`. Asahi's
unmodified update-m1n1 maintains `/boot/boot.bin` and `/boot/boot.bin.old`.
Regenerate GRUB with `sudo grub-mkconfig -o /boot/grub/grub.cfg` when needed.

## Candidate contents

The October 26 candidate pairs Aurora kernel integration commit
`9cbdd0734d9e186c5f5f5949a21b909d10c2571b` with Mesa commit
`f2c9dc3fb59c81fdaf51f19884175c856e3d1889`. It retains this machine's
16-core GPU support, firmware identity, boot handoff and DCP settings.
Kernel configuration enables KVM, vhost networking and vsock. Fan writes are
opted in with macsmc_hwmon's fan_control parameter. The enabled mbpfan service
uses macsmc's RPM targets and CPU/GPU/SoC temperatures, with firmware-provided
RPM limits. It ramps cooling from 55 degrees Celsius and requests full cooling
at 80 degrees; stopping the daemon restores firmware automatic operation.
Actual fan response still requires a native boot test.

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

Open **Steam** from the application menu, or run `steam` as your normal user.
The launcher starts muvm and FEX automatically, with a private D-Bus session
inside the VM for Steam's subprocess launcher. It selects Valve's 64-bit
SteamRT3 client and uses Zink with the GLX path supported by muvm's X11 bridge.
Valve's unmodified launcher
performs the usual first-launch client download and sign-in. Steam, Proton,
games and account state remain in your home directory; package upgrades replace
the read-only rootfs without replacing that state. No manual rootfs extraction,
FEX configuration, apt commands or installer run is needed after installation.

The packaged Debian 13 userland includes both amd64 and i386 Steam dependencies
and builds of the same Aurora Mesa commit as the host. Both x86 architectures
also include the Mesa device-selection layer required by Zink. The current
image vendors those layer libraries from Debian 25.0.7-2+deb13u1; subsequent
Mesa builds include the layer alongside the paired drivers. muvm discovers it at its
standard `/usr/share/fex-emu/RootFS/default.erofs` path. FEX runs inside muvm's
4 KiB-page guest on this 16 KiB-page host. Native GPU/Steam/game behavior still
requires the owner's boot test; container checks cannot establish that result.

The latest native investigation confirms that the updater installs and verifies
the client, but accelerated OpenGL also hangs for native ARM glxinfo inside
muvm. The virtual GPU reports a rejected CmdSubmit3d command with EINVAL.
Host acceleration and basic guest X11 forwarding work. A graphics protocol or
backend compatibility gap remains a hypothesis; the rejected payload has not
been identified. SteamRT also showed a separate single-instance exit after
re-execution. No graphical Steam session has been verified.

## Build

`make packages` prepares and builds ordinary PKGBUILDs in the Arch ARM build
container and validates package dependencies, boot hooks, driver availability
and native Mesa's dependency ABI against the mounted root. Local build inputs
are under `out/packages/source/`; firmware inputs are machine-local. Kernel
configuration and patches are included in the kernel package. The Flatpak
build helper uses Freedesktop SDK 25.08/26.08 and LLVM 22; its pinned Mesa and
SPIR-V source inputs are recorded under `out/candidate-20261026/`.
The Steam rootfs inputs are built using `packages/tools/build-fex-mesa.sh` and
`packages/tools/build-fex-rootfs.sh` in disposable Debian 13 amd64 build VMs.
The first needs Mesa's native and i386 development dependencies plus LLVM 19;
the second needs debootstrap, erofs-utils and permission to mount procfs.
The runtime tree produced by the first script is passed to the second at
`/work/mesa-runtime`. The resulting EROFS image, Debian package manifest and
build information belong in `out/packages/source/` before `make packages`.
Debian packages retain their copyright/license files inside the image.

`make check` checks host helper syntax. Linux hardware behavior is validated
by booting the candidate, separately from the container build checks.
