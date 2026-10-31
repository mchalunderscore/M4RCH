# Boot recovery

The normal boot chain is `/boot/boot.bin`, `/boot/vmlinuz-linux-m4rch`,
`/boot/initramfs-linux-m4rch.img` and `/boot/grub/grub.cfg`. GRUB has one
persistent default. The J614s keyboard worked in GRUB and Linux with the MTP
handoff trial. The owner chose promotion without rebooting, so the rebuilt
`7.3.0-m4rch` default has not yet booted. Restore the loader and kernel together: the retained-MTP U-Boot requires
a kernel that understands that handoff.

Until the first final boot has been verified, a temporary EFI-only fallback is
also present: restore `/boot/boot.bin.old` to `/boot/boot.bin` and
`/boot/grub/grub-handoff-recovery.cfg` to `/boot/grub/grub.cfg`. That
configuration selects the hidden, tested trial kernel and initramfs, whose
modules remain installed. Verify both copies before rebooting. This temporary
fallback will be removed after the final default is verified.

A verified pre-promotion recovery pair and its SHA-256 manifest are in
`cache/mtp-promotion/recovery/`, relative to this repository. These copies are
on the same physical disk; retain a separate external backup for disk failure.
The pre-promotion working tree, including unique untracked source records, is
saved in `cache/mtp-promotion/pre-promotion-worktree.tar.gz`.

To restore the previous `7.3.0-m4rch-upstream-23827f` kernel and loader from
external recovery:

1. Mount the Linux root at `/mnt/root` and its FAT EFI partition at `/mnt/esp`
   (adjust these paths for the recovery environment). Locate
   `/mnt/root/home/michal/Projects/m4rch/cache/mtp-promotion/recovery` and run
   `sha256sum -c SHA256SUMS` there.
2. Restore the previous kernel modules from the retained package. Verify its
   SHA-256 is `297d15ebe6fa151e215cbd444195867d29d9c4aa357a7a500ca9a2f4a80a9f87`,
   then extract its matching module directory into the mounted root:

   ```sh
   M4RCH_ARCHIVE=/mnt/root/home/michal/Projects/m4rch/cache/installed-20261031/packages/linux-m4rch-7.3.0-25-aarch64.pkg.tar.xz
   printf '%s  %s\n' '297d15ebe6fa151e215cbd444195867d29d9c4aa357a7a500ca9a2f4a80a9f87' "$M4RCH_ARCHIVE" | sha256sum -c - && \
     bsdtar -xpf "$M4RCH_ARCHIVE" -C /mnt/root usr/lib/modules/7.3.0-m4rch-upstream-23827f
   ```

3. Copy the recovery directory's `esp/boot.bin`, `esp/vmlinuz-linux-m4rch`,
   `esp/initramfs-linux-m4rch.img` and `esp/grub/grub.cfg` to the corresponding
   paths on the mounted EFI partition. Compare each copy with its backup and
   sync before rebooting.

Restoring files this way does not roll back the pacman database. After boot,
reconcile packages before updates; package hooks can rewrite the boot files.
The archived pre-existing, unowned `7.3.0-m4rch` module tree is separately
preserved as `preexisting-unmanaged-modules-host.tar.gz` in the recovery
folder; it is not the module set for the recovery kernel above.
