# Boot and authentication recovery

The installed default uses `/boot/boot.bin`, `/boot/vmlinuz-linux-m4rch`,
`/boot/initramfs-linux-m4rch.img`, and `/boot/grub/grub.cfg`. GRUB has one
persistent entry. The packaged release is `7.3.0-m4rch-touchid`; the SD and
jack package promotion booted successfully on 31 October.

The immediately preceding, SD-capable boot files are in
`cache/jack-promotion/recovery/before/`, with `SHA256SUMS` verified after
copying. The preceding kernel, U-Boot and jack trial packages are alongside
that directory. To restore the boot files from recovery media, mount the
Linux root at `/mnt/root` and the EFI partition at `/mnt/esp`, then:

```sh
cd /mnt/root/home/michal/Projects/m4rch/cache/jack-promotion/recovery/before
sha256sum -c SHA256SUMS
sudo cp boot.bin vmlinuz-linux-m4rch initramfs-linux-m4rch.img /mnt/esp/
sudo cp grub.cfg grubenv /mnt/esp/grub/
sync
cmp boot.bin /mnt/esp/boot.bin
cmp vmlinuz-linux-m4rch /mnt/esp/vmlinuz-linux-m4rch
cmp initramfs-linux-m4rch.img /mnt/esp/initramfs-linux-m4rch.img
cmp grub.cfg /mnt/esp/grub/grub.cfg
cmp grubenv /mnt/esp/grub/grubenv
```

The previous SD-capable loader is retained in the verified recovery directory,
outside the active boot partition. Superseded trial loader copies were removed
from `/boot` after verification. Restoring boot files alone does not
revert the package database or the installed audio module. These backups are
on the same disk and do not protect against disk failure.

A verified complete copy of the pre-Touch-ID-promotion EFI partition and the
matching `7.3.0-m4rch` module archive are in
`cache/touchid-promotion/recovery/` within this repository. They are on the
same physical disk; retain a separate external backup for disk failure. The
root-only factory and post-enrollment SEP backup is in
`cache/touchid-candidate/private-inputs/`; restoring it does not roll back the
SEP's anti-replay state. Do not assume an old xART backup alone can undo later
SEP operations.

To recover the previous boot chain from external media:

1. Mount the Linux root at `/mnt/root` and its EFI partition at `/mnt/esp`.
2. Locate `/mnt/root/home/michal/Projects/m4rch/cache/touchid-promotion/recovery`,
   change into that directory and run `sha256sum -c SHA256SUMS`.
3. Extract the matching modules and the previous default boot files:

   ```sh
   sudo tar -xzf previous-modules.tar.gz -C /mnt/root/usr
   mkdir -p /tmp/m4rch-recovery
   tar -xzf boot-before-promotion.tar.gz -C /tmp/m4rch-recovery
   sudo cp /tmp/m4rch-recovery/boot/boot.bin /mnt/esp/boot.bin
   sudo cp /tmp/m4rch-recovery/boot/vmlinuz-linux-m4rch /mnt/esp/vmlinuz-linux-m4rch
   sudo cp /tmp/m4rch-recovery/boot/initramfs-linux-m4rch.img /mnt/esp/initramfs-linux-m4rch.img
   sudo cp /tmp/m4rch-recovery/boot/grub/grub.cfg /mnt/esp/grub/grub.cfg
   sync
   ```

   Compare each copied file to its archive extraction before rebooting. This
   restores boot files and modules, not the pacman database; reconcile packages
   after boot because package hooks may regenerate the boot chain.

The original `/etc/pam.d/sddm` and `/etc/pam.d/sudo` are preserved under
`cache/touchid-promotion/recovery/auth/` as `sddm-before-touchid` and
`sudo-before-touchid`. From recovery media, copy the relevant file back to
`/mnt/root/etc/pam.d/` if fingerprint configuration prevents authentication.
To restore the previous passwordless wheel rule, remove
`/mnt/root/etc/sudoers.d/zz-m4rch-touchid` from recovery media. The original
`sudoers.d/admin` is also saved in the `auth/` backup directory.
Password login remains configured as a fallback. SDDM fingerprint login may
not unlock KWallet, which needs the account password.
