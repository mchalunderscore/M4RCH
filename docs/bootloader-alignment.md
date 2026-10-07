# Gravity bootloader alignment

This profile updates only ESP `/boot.bin`: m1n1 stage 2, the working J614s DT
and gzip-compressed U-Boot. It requires the existing, hardware-tested internal
split boot. Stage 1 and Apple enrollment stay unchanged.

| Component | Pinned source |
| --- | --- |
| m1n1 stage 2 | [Gravity a49e1e1](https://github.com/GravityLinux/bootloader/tree/a49e1e170f917038206cf9ed9ad66f9581808575) |
| U-Boot 2026.07 | [Gravity a2f6913](https://github.com/GravityLinux/u-boot/tree/a2f6913694ff26908c16948af3f8372429782263), `gravity-alpha-20260925` |

`profiles/gravity-loader.json` records source revisions, rebased patch hashes
and expected patched-file hashes. The build checks these before compiling.
It retains the proven baseline DT rather than importing a T8132/M4 board DT.
Gravity's own NVMe queue registration/polling replaces the older backports.
Local changes preserve separate NVMMU registers, ANS power ancestry, firmware
shutdown guards, T6040 CTRR reservations and the MTP-only DAPF path.

## Build and deploy

```sh
make loader-gravity
sudo make stage2-gravity
```

The first command produces `out/sdboot/gravity-loader/boot.bin` and a verified
component manifest. The second checks the stage-1/ESP contract, backs up the
installed bundle, atomically replaces it and verifies the readback. It also
copies the native handover and read-only collector to `/boot/loader-alignment/`.
Boot M4RCH normally with the SD removed; no Recovery enrollment is needed.

The kernel, GRUB and packages are unchanged. This aligns bootloader sources;
it does not provide GPU acceleration. A successful build still needs native
boot, peripheral, idle and shutdown checks described in the handover.

## Rollback

Use the backup path printed by deployment:

```sh
sudo cp out/split-boot-backups/TIMESTAMP/boot.bin /Volumes/M4RCHESP/boot.bin
sync
```

Mount the internal ESP first if necessary. Restoring ESP stage 2 does not change
Apple policy or require re-enrollment. Keep the existing stage-1 files and
firmware rollback until the replacement has been tested.
