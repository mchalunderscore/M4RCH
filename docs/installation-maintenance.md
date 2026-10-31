# Installation and maintenance

This guide describes the installed J614s setup as checked on 31 October 2026.
Use [current status](status.md) for versions and qualification, and verify
live package and boot state before an update. Earlier installation records and
recovery artifacts are retained outside the active boot partition.

## Boot and package records

The owner reported a successful keyboard handoff trial in GRUB and Linux.
The current `7.3.0-m4rch-touchid` kernel and m1n1/U-Boot bundle booted
after the SD and jack packages were promoted. The sole GRUB entry selects
`/boot/vmlinuz-linux-m4rch` and `/boot/initramfs-linux-m4rch.img`; the ESP
loader is `/boot/boot.bin`. `update-m1n1` assembles the bundle from the
installed second-stage m1n1, J614s DTB and U-Boot. The DTB and loader form a
coordinated hardware handoff and should be updated and checked together.

For versions, source bases, patch order and build limitations, use the
[package guide](../packages/README.md) and each package's source record:
[Linux](../packages/linux-m4rch/promoted-source/source-stack.md),
[m1n1](../packages/m1n1-m4rch/promoted-source/source-stack.md) and
[U-Boot](../packages/u-boot-m4rch/promoted-source/source-stack.md). The
current kernel package contains prebuilt binaries, its configuration and
recorded patches. The preceding kernel's historical build tree was removed at the owner's
request; its exact source reconstruction and a reproducible build have not
been established. The package records must not be read as proof otherwise.

Current kernel and U-Boot promotion inputs are machine-local under
`cache/jack-promotion/`; m1n1 inputs and prior package archives remain in
`cache/installed-20261031/`. Firmware and per-device calibration must remain
private and be backed up separately; they are not supplied by this repository.
The old installer and deleted `out/` artifacts are not the current installation
or a verified fresh-install path. The full package rebuild and fresh-install
workflow require separate qualification.

## Local configuration

The normal command line uses `mem_sleep_default=s2idle`, `user4k=on`,
`appledrm.t6041_dcpext=1`, and blacklists the internal speaker amplifier
modules. The installed platform package remains at `20261026-3`; a machine-local
`/etc/systemd/sleep.conf.d/90-m4rch-suspend.conf` enables suspend while
keeping hibernation, hybrid sleep and suspend-then-hibernate disabled. Earlier
suspend tests do not establish a fresh post-rebase test.

See [current status](status.md) for native Mesa and graphics qualification.

## Recovery

See [boot recovery](recovery.md) for the retained loader, package archives,
backup hashes and the procedure for restoring the prior boot chain. GRUB has
one entry. The internal keyboard worked in the MTP handoff trial; the saved
recovery backups reside on the same disk.
