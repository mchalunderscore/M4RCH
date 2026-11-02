# Boot and authentication recovery

## Current boot and recovery

The persistent GRUB configuration selects `/boot/vmlinuz-linux-aurora` and
`/boot/initramfs-linux-aurora.img` by default. The GPU observation trial entry,
kernel, initramfs and modules were removed after a verified archive was made at
`/var/lib/m4rch/gpuobs-retired-20261102/trial.tar.zst` (SHA-256
`f381c026a39782295499902f1933013123f04a7b103ed228713343490b98181f`).
That archive is for trial provenance, not normal boot recovery.

The running kernel was booted from `/vmlinuz-linux-aurora`; the normal
initramfs currently on disk has not been independently verified as the one
used for this boot. `user4k=on` and `appledrm.show_notch=1` are host-local in
`/etc/default/grub.d/60-local-preferences.cfg`. The normal kernel, initramfs,
GRUB configuration and environment, and EFI loaders were unchanged when the
trial was retired. The GRUB configuration passed `grub-script-check`.

The standard updater has no local DTB override; check its selected kernel DTB
set before future kernel updates. The EFI and filesystem recovery copies below
are on the same disk; keep independent recovery media available. Their saved
checksums were verified on 2 November 2026, including the 2,137 entries in
the full-stack recovery archive. Check them again before a boot change.

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
