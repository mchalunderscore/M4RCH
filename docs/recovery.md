# Boot and authentication recovery

## Promoted Aurora-default boot (2 November 2026)

The kernel, Aura and U-Boot from the ALARM fork booted with Aurora's standard
initramfs and updater-generated multi-DTB stage two. The final candidate boot
ID was `e6a81654-428a-48c5-bb2d-e3a84209ac03`. The metadata-only J614s
transition package has been uninstalled. `user4k=on` and
`appledrm.show_notch=1` are host-local in
`/etc/default/grub.d/60-local-preferences.cfg`.

GRUB now has one persistent entry for `/boot/vmlinuz-linux-aurora` and
`/boot/initramfs-linux-aurora.img`. The regenerated default has not yet been
booted. Earlier trial entries, initramfs images and duplicate EFI loaders were
removed after their backups were verified. The prior working full-stack stage
two remains at `/boot/efi/m1n1/boot.bin.m4rch-recovery`; its matching kernel,
initramfs and module tree are in the full-stack recovery archive below.

The verified promotion snapshot is
`/var/lib/m4rch/j614s-stock-promotion-20261102/`. Earlier experiment and
boot evidence are in `/var/lib/m4rch/j614s-aurora-defaults-trial-20261102/`.
The standard updater has no local DTB override; check its selected kernel DTB
set before future kernel updates. Suspend and external displays have not been
qualified on this final trial. The live J614s tree disables the speaker card
and all six amplifier nodes, and the J614 driver keeps speakers disabled.

## Earlier booted full-stack recovery

The prior working stage two is on EFI as
`/m1n1/boot.bin.m4rch-recovery`, SHA-256
`f371f54849ece5e14a9319f03b22fad7fb0118d2bcda302a8d620b28cd981afc`.
The complete prior kernel, initramfs, GRUB files, loader copies, matching
packages and installed modules are in
`/var/lib/m4rch/merged795-promotion-20261102/`; their saved checksums were
verified after promotion.

If the new boot fails, use a Linux-capable recovery environment to mount the
Linux root (Btrfs subvolume `root`, UUID `f7eae37b-7359-4a97-9359-46f7ecd09e31`),
the ext4 `/boot` filesystem (UUID `d1941708-d4c9-44d6-81ae-a279e88cc64d`),
and EFI (UUID `E8DC-7E45`). Restore `boot.bin` from the EFI recovery copy,
and restore `vmlinuz-linux-aurora`, `initramfs-linux-aurora.img`, `grub.cfg`
and `grubenv` from the archive to their normal `/boot` locations. Restoring
the loader alone does not restore the previous kernel. Before booting the old kernel, restore the archived `running-modules` directory to `/usr/lib/modules/7.3.0-j614s-pr1-ARCH`. After booting, move that unowned tree aside and reinstall the archived old kernel, headers, config and boot packages with pacman to restore package ownership.

## Sudo authentication

The custom graphical sudo bridge is uninstalled. `/etc/pam.d/sudo` uses the prior fingerprint and password stack. The user's zsh alias invokes `run0`, which authenticates through polkit and the configured desktop agent.
