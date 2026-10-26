# m4rch

This is the historical SD-card bring-up workflow. Use `make -f Makefile.legacy`
for its targets. Current packages are documented in [packages](packages/README.md).

m4rch (pronounced “march”) builds persistent Arch Linux ARM on an SD card
for the 14-inch M4 Pro MacBook Pro.

An experimental build for **Mac16,8 · J614s · T6040**, based on
[Project Wallace](https://github.com/damsleth/wallace),
[Asahi Linux](https://asahilinux.org/) and
[Arch Linux ARM](https://archlinuxarm.org/).

```text
Internal SSD                    SD card
Apple → m1n1 → U-Boot UEFI  →  GRUB → Linux → persistent ext4
```

The internal loader stays small and fixed. Linux, its modules, desktop and
user files live on the card. Routine Linux updates need **no Recovery
enrollment**; changing m1n1, U-Boot or the embedded baseline device tree does.

First setup creates a **4 GiB internal APFS boot stub**, named **M4RCH**;
it does not install a second full macOS. `make image` prepares the pinned Apple
boot/Recovery files, and `sudo make boot` displays the internal allocation
before requesting its exact confirmation. Existing installations keep their
recorded identities and container.

## Included

| System | Defaults |
| --- | --- |
| Desktop | KDE Plasma; software-rendered Wayland configured, X11 fallback retained |
| Applications | Firefox, Konsole, Dolphin, Kate, Discover, Flatpak |
| Networking and audio | NetworkManager / `nmtui`, BlueZ, PipeWire, WirePlumber |
| Packages | Pacman, preinstalled `paru`, `base-devel`, Git, Rust |
| Project packages | `linux-m4rch`, `config-m4rch`, `grub-m4rch`, `paru-m4rch` |
| Storage | GPT image; 512 MiB FAT32 ESP and ext4 root that expands on first boot |
| Account | Alice Admin / `alice`; hostname `t6040` |

**Development defaults:** automatic login, an empty Alice password,
passwordless sudo and screen locking disabled. SSH is disabled. These are
intentional defaults for a physically controlled experimental machine.

Native testing establishes an X11 desktop, Wi-Fi, input, Bluetooth playback,
right-port USB2 security-key access, CPU frequency scaling and NVMe discovery.
Wayland's configured software backend still needs a native check. GPU
acceleration, left USB-C ports, USB3, internal audio, camera and suspend are
unfinished. See the [hardware status](docs/hardware.md) for precise limits.

The maintained kernel includes SME/SME2 and a default-enabled shallow
saved-WFI state for J614s/T6040, with a runtime disable switch. See
[CPU support](docs/cpu-performance.md) for scope, controls and evidence.

## Build and boot

Build on macOS with Python 3, Git, command-line developer tools and Apple
`container`, Docker or Podman. Allow about **50 GiB** of build space and use
a **32 GB or larger SD card** in the built-in reader.

```sh
make image                    # out/sdboot/m4rch.img
make check
make verify
make smoke                    # disposable ARM64 UEFI VM
diskutil list                 # identify the whole SD disk again
sudo make flash DISK=/dev/diskN
sudo make boot                # provision or update the internal boot stub
```

`/dev/diskN` is a placeholder. Flashing erases the selected card. Internal
loader enrollment still requires a physical Recovery entry and owner
authentication; `make boot` prints the command to run there. Follow
[setup](docs/setup.md) for the complete procedure, updates and rollback.

## Read more

- [Setup](docs/setup.md) — build, flash, enroll, update and diagnose.
- [Hardware](docs/hardware.md) — observed support and remaining work.
- [Architecture](docs/architecture.md) — Apple boot policy and the SD boundary.
- [Development](docs/development.md) — pinned inputs, tests and contributions.
- [CPU experiments](docs/cpu-performance.md) — placement, clocks and cooling.
- [Documentation index](docs/README.md) — tools, evidence and native handoff.

This is AI-assisted experimental integration, **not a clean-room
implementation or an official Asahi-supported M4 distribution**. Original
project code and upstream-derived files have different licensing scopes;
see [LICENSE](LICENSE) and [third-party attribution](THIRD_PARTY.md).
Generated images and packages contain extracted Apple firmware and remain
local build artifacts.
