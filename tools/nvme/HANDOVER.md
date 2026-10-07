# NVMe root migration

Work from the running SD installation. Kit: `/boot/NVME0001`. Keep the SD root
and all existing SD kernel/initramfs files. Leave the new NVMe ESP **empty**.
The owner authorized replacing only the exFAT reservation identified in
`plan.json`. The root copy preserves the existing desktop, Alice account,
installed packages and customizations. This is not a fresh installation.

## Inspect and allocate

```sh
cd /boot/NVME0001
sha256sum -c SHA256SUMS
lsblk -o NAME,SIZE,LOG-SEC,FSTYPE,UUID,PARTUUID,MOUNTPOINTS
findmnt / /boot
uname -r
sudo journalctl -b -k --no-pager | grep -Ei 'nvme|ans|timeout|I/O error'
```

Set `DISK` to the whole internal NVMe namespace identified by the plan UUIDs
and geometry (usually `/dev/nvme0n1`, never assumed by the helper). Install
`rsync`, `gptfdisk`, `dosfstools` and `e2fsprogs` on the SD root if missing.
Verify `/usr/lib/modules/$(uname -r)/modules.builtin` contains
`drivers/nvme/host/apple.ko` before beginning. The maintained kernel needs
built-in Apple NVMe and ext4 for this minimal early-userspace path.

```sh
DISK=/dev/nvme0n1
sudo python3 migrate.py inspect --disk "$DISK"
sudo python3 migrate.py partition --disk "$DISK"
sudo python3 migrate.py format --disk "$DISK"
sudo python3 migrate.py seed --disk "$DISK"
```

The split and format each require the exact UUID confirmation displayed by the
helper. The helper backs up the GPT on SD before modifying it and compares all
protected entries afterward. No APFS formatting or resizing is performed.
Do not restore a GPT backup blindly after formatting: that does not restore the
old exFAT contents. If a command fails, inspect its phase receipt and actual GPT;
do not delete receipts/backups to bypass a guard. Preserve them in the return.

## Final copy and trial

The seed pass can run with the desktop active. Final copying requires no user
sessions and no package transaction. Stop any additional services writing
application databases before that pass. Check available space; ext4 has its
usual reserved blocks, and the live source may not fit just because the raw
partition sizes are similar. The helper fails if rsync cannot complete.

Prepare a maintenance script on SD, replacing the disk argument with the
verified namespace:

```sh
sudo tee /boot/NVME0001/FINAL.SH >/dev/null <<'SCRIPT'
#!/bin/sh
set -eu
exec >/boot/NVME0001/final-copy.log 2>&1
systemctl stop sddm
loginctl terminate-user alice
python3 /boot/NVME0001/migrate.py final --disk /dev/nvme0n1
python3 /boot/NVME0001/migrate.py boot --disk /dev/nvme0n1
sync
SCRIPT
```

Tell the owner this closes the desktop and the native Codex session. Save your
handover first. Launch it as a root system service, so the copy continues when
the user session ends:

```sh
sudo systemd-run --unit=m4rch-nvme-final /bin/sh /boot/NVME0001/FINAL.SH
```

**No automatic reboot.** Check `final-copy.log` from macOS before the next boot.
Only a successful final copy allows boot staging. Boot staging preserves
`grub-before.cfg`, adds a named trial, and selects it explicitly because the
GRUB keyboard is unavailable. Its kernel and initramfs live under `NVME0001`;
the original SD boot files and SD root are untouched.

This kit leaves `/boot` on SD. It makes a separate NVMe initramfs with fixed
root UUID, PARTUUID and bounds; no NVMe expansion code is present. It does not
change m1n1, U-Boot, Apple policy or enrollment. The empty NVMe ESP is reserved
for later Apple ANS support in U-Boot.

## Rollback and update limitation

From macOS, mount the genuine SD ESP and restore:

```sh
sudo cp /Volumes/ARCHBOOT/NVME0001/grub-before.cfg /Volumes/ARCHBOOT/grub/grub.cfg
sync
```

Confirm the actual mount location; macOS may use `ARCHBOOT 1`. The old SD root
remains the fallback. On a successful NVMe boot, capture `findmnt / /boot`,
`lsblk`, kernel NVMe logs, filesystem writes and an ordinary package transaction.
The existing boot.conf is intentionally retained: its root UUID guard blocks
kernel/config/firmware boot-update transactions on the NVMe root. Do not change
that UUID merely to bypass the guard; the SD-only updater would then generate
an invalid root initramfs or overwrite fallback files. Normal kernel update
integration is the next required follow-up, before calling this the maintained
installation. Ordinary application packages can still be installed unless they
trigger those boot hooks. Keep the trial artifacts fixed during qualification.

Return the plan, GPT JSON before/after, receipts, final-copy.log, actual mount
UUIDs, ANS errors and native write/shutdown results. Do not include user files,
private keys or a complete root copy in the return archive.
