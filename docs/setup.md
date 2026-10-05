# Setup

## Before building

Supported target: **14-inch M4 Pro MacBook Pro, Mac16,8 / J614s / T6040**,
using its built-in SD reader. Other models and USB card readers are not
supported targets of these scripts.

First setup creates a dedicated **4 GiB internal APFS container**, named
**M4RCH**, holding Apple's boot/recovery subset and the fixed Linux
loader. It is not a second full macOS installation. The default allocation
shrinks the running macOS APFS container by about **4.125 GiB**, including
partitioning space; setup displays the exact sizes and checks the permitted
resize limit before any change. Keep a current macOS backup and connect power.

An existing installation is reused by its recorded UUIDs, including stubs
previously named **Arch M4 Boot**.
Keep its original `out/internal-boot-state.json`: it records the dedicated
container and this Mac's identities. Setup does not adopt an unknown volume
because its name matches. Restore missing state from your backup instead of
deleting or inventing it to force another installation.

To give an existing **Arch M4 Boot** System volume the new name, mount that
verified volume in Disk Utility, then run in macOS:

```sh
sudo mount -u -w "/Volumes/Arch M4 Boot"
sudo diskutil rename "/Volumes/Arch M4 Boot" M4RCH
```

This changes its volume name; the recorded UUIDs and enrolled loader stay the
same. Use the new mount path in subsequent commands.

Install Python 3, Git, Apple's command-line developer tools and an ARM64 Linux
container runtime. The scripts prefer Apple `container`, then Docker or
Podman; select an alternative with `RUNTIME=docker` or `RUNTIME=podman`.
Use a card of at least 32 GB and allow roughly 50 GiB of build space. Builds
default to eight CPUs and 8 GiB RAM; `MEMORY=6G` lowers the memory limit.
Initial builds need internet access.

For Apple `container`:

```sh
container system start
container system status
```

If a Nix-installed executable cannot locate its plugins, start it with its
real installation directory:

```sh
container_root=$(python3 -c 'import pathlib, shutil; print(pathlib.Path(shutil.which("container")).resolve().parent.parent)')
export CONTAINER_INSTALL_ROOT="$container_root"
container system start --install-root "$container_root"
```

Defaults live in `sdboot/config.json`; personal overrides go in ignored
`sdboot/config.local.json`. The development image uses `alice`, an empty
password, automatic login and passwordless sudo. Change those inside Linux
if the machine will be shared.

## Build a fresh card

Run from the repository directory as your ordinary macOS user:

```sh
make image
make check
make verify
make smoke
```

The complete raw GPT image is `out/sdboot/m4rch.img`. It contains a FAT32
EFI partition and persistent ext4 root. `make image` also builds the normal
NVMe-aware internal loader and an SD-only fallback, and stages verified Apple
boot/Recovery files under `out/stub/`. Those pinned restore assets are fetched
and extracted on macOS before running privileged disk setup. This does not
install another macOS or flash machine firmware. Build output stays in the
project and container storage; these commands do not alter disk layouts.

`make smoke` tests a disposable copy under QEMU UEFI. It cannot establish
native Apple boot-policy, SD-reader, graphics or peripheral support.

Flashing is a **fresh installation** and erases the card. Back up an existing
Linux environment first. Insert the card and identify its whole disk by
the **Built In SDXC Reader** media name and capacity:

```sh
diskutil list
sudo make flash PYTHON="$(command -v python3)" DISK=/dev/diskN
```

Replace `/dev/diskN` with that current whole-disk identifier. The flasher
checks the target, asks for its exact erase phrase, verifies the write and
relocates the backup GPT to the card's real end. It ejects the card when done.
**Remove and reinsert it.** Disk numbers can change.

On the first native boot, the ext4 partition and filesystem expand to fill
the card. Subsequent boots retain data. macOS mounts the FAT partition as
`ARCHBOOT`; Linux mounts it at `/boot`. macOS does not mount the ext4 root.

## Set up and enroll the internal loader

Skip this section if the required loader is already enrolled and only the
SD kernel or configuration changed. Otherwise, in ordinary macOS:

```sh
sudo make boot PYTHON="$(command -v python3)"
```

On a fresh Mac, `make boot` verifies the **already built** NVMe-aware loader
and neutral Apple payload, identifies the running macOS container, and
prints the exact resize/new-container command. It requires the displayed
phrase **`CREATE INTERNAL <macOS physical-store UUID>`** before changing the
internal partition map. It then creates the stub's System/Data volume group,
Preboot and Recovery, copies the verified files and stages the current
owner's recovery metadata. No SD card is needed or written by this step.

With a recorded ready installation, it skips provisioning and reuses the
same container. A loader update retains the preceding boot object and
enrollment files, asks for confirmation and stages the new object. If the
same loader is already enrolled, it leaves startup selection unchanged.

Apple's `bless` prompt requests the macOS owner's credentials to select the
startup target. The script then prints the Recovery command. Save its backup
path and retain `out/internal-boot-state.json`,
`out/sdboot/initial-enrollment-state.json` and, after a loader update,
`out/sdboot/enrollment-state.json`. Keep the printed on-stub backups too.
`sudo make boot-status` inspects that state.

Provisioning records durable phases before partition changes. After an
interruption, rerun the same `sudo make boot`: it identifies a recorded
created partition and resumes role/payload setup without shrinking again.
Unknown files or a changed layout stop for inspection; setup does not automatically
undo an APFS resize or allocate another container. Preserve the state and
reported error if it stops.

The restored first-install path has fixture coverage for interrupted writes
and enrollment transitions. Fresh native provisioning has not been rerun
since this restoration; the existing enrolled installation remains the
hardware-tested baseline.

To replace a verified pending build before enrolling it:

```sh
sudo make boot REPLACE_PENDING=1
```

Finish with the Mac physically present:

1. Shut down fully. Hold the power button continuously until startup options
   appear, then choose **Options → Continue**.
2. Authenticate with the ordinary macOS owner's credentials when requested.
3. Open **Utilities → Terminal** and run the command printed by `make boot`,
   for a new installation:

```sh
sh "/Volumes/M4RCH/Finish Installation.app/Contents/Resources/enroll.sh" --enroll
```

For a later loader update, the printed command uses `--update`. Use the printed
path, which follows the actual mounted volume name. If it is not mounted, open Disk Utility,
choose **View → Show All Devices**, select the printed boot-stub volume and
mount it.

The script checks the machine, volume group, loader and physically entered
paired Recovery. Initial `--enroll` authorizes the dedicated stub's custom
boot policy before `kmutil configure-boot`; `--update` requires its prior
enrollment receipt. Complete Apple's authentication prompt, then reboot with
the card inserted and select **M4RCH** (or the previous name on an older stub).

Selecting Arch directly boots its current m1n1; it does not automatically
start enrollment. Recovery entry and launching the script remain manual.
If pairing is rejected, return to macOS, stage the same pending build again,
then repeat the full shutdown and **Options** entry. Do not bypass the checks.

## Update Linux without enrollment

Ordinary application updates run inside Linux:

```sh
sudo pacman -Syu
paru -Syu
nmtui
```

Run `paru` as Alice; it requests sudo for package transactions. A first-boot
service initializes the pacman keyring. Check
`systemctl status m4rch-pacman-init.service` if it is still starting.

For project changes, build on macOS without sudo:

```sh
make kernel       # omit for configuration-only changes
make packages
```

The current `out/sdboot/update-ID/` kit contains exact package versions,
checksums, `install.sh` and diagnostics. Copy it to the **actual mounted**
`ARCHBOOT` partition. Replace `/dev/diskNs1` with that partition's current
identifier; this block checks its real mount path before copying:

```sh
(
set -eu
partition=/dev/diskNs1
sudo diskutil mount "$partition"
mount=$(diskutil info -plist "$partition" | python3 -c '
import pathlib, plistlib, sys
d = plistlib.loads(sys.stdin.buffer.read())
p = d.get("MountPoint")
if (d.get("DeviceIdentifier") != sys.argv[1].removeprefix("/dev/")
        or d.get("VolumeName") != "ARCHBOOT"
        or d.get("FilesystemType") not in ("msdos", "vfat")
        or not isinstance(p, str) or not pathlib.Path(p).is_mount()):
    sys.exit("Not the mounted ARCHBOOT FAT partition")
print(p)
' "$partition")
test -f "$mount/EFI/BOOT/BOOTAA64.EFI"
kit=$(python3 -c 'import json; print(json.load(open("out/sdboot/custom-packages-manifest.json"))["update_directory"])')
cp -R "out/sdboot/$kit" "$mount/"
sync
printf 'In Linux: sudo sh /boot/%s/install.sh\n' "$kit"
)
```

A stale `/Volumes/ARCHBOOT` folder can exist while the real card mounts as
`ARCHBOOT 1`. Do not create a destination folder to bypass a failed check.
Eject normally with `diskutil eject /dev/diskN`, then boot Linux and run the
printed installer command. It verifies checksums and installs the matching
packages in one pacman transaction. Its hook regenerates the SD kernel,
initramfs, overlay and GRUB. Resolve any hook failure and rerun
`sudo m4rch-boot-update` before rebooting.

Use this installer for custom package updates, including migration from the
old package names. It preserves `/etc/arch-m4/boot.conf` before pacman can
remove the previous package, checks the running root and ESP identities, and
verifies successful boot-file generation. A direct `pacman -U` transaction
does not provide that preservation. If it replaces the file and a boot hook
rejects the resulting identity, restore the previous file and successfully
run `sudo m4rch-boot-update` before rebooting.

Repository signatures remain required. Explicit local packages use
`LocalFileSigLevel = Optional`; there is no project package server, so
`pacman -Syu` does not fetch custom kernel/configuration builds.

## Diagnostics and recovery

Inside Linux:

```sh
uname -r
pacman -Q linux-m4rch config-m4rch grub-m4rch paru-m4rch
findmnt --mountpoint /
findmnt --mountpoint /boot
systemctl --failed
sudo sh /boot/update-ID/diagnose.sh
```

Use the kit's actual directory name. Its collector writes a unique diagnostic
archive beside the kit; `--non-interactive` skips cable prompts. Reports can
contain device identities and personal logs: inspect them before publishing.
When Linux cannot boot, `sudo make diagnose DISK=/dev/diskN` reads selected
saved ext4 logs from macOS without mounting, repairing or writing the card.

For a Linux regression, reinstall the previous matching kernel/configuration
packages together and ensure their boot hook succeeds. A boot failure may
require a Linux rescue environment because macOS cannot modify ext4.

For an internal NVMe-aware loader regression, `sudo make boot-safe` stages
the retained SD-only UEFI loader and prints its Recovery enrollment steps.
It leaves Linux on the card; the NVMe service skips initialization without
the ANS handoff marker. Restoring an internal loader still requires enrollment.
Keep complete internal backups and local state rather than copying a boot
object alone.
