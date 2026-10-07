# Gravity bootloader alignment

The owner has booted Linux successfully without an SD card using the split
m1n1 chain and the upgraded 26.6.2/25G83 Apple stub. This trial replaces only
ESP `/boot.bin`; Apple firmware, enrolled stage 1, GRUB, kernel and rootfs stay
as they were. No Recovery enrollment is required.

Sources are pinned in `/boot/loader-alignment/profile.json`:

- Gravity m1n1 `a49e1e170f917038206cf9ed9ad66f9581808575`.
- Gravity U-Boot `a2f6913694ff26908c16948af3f8372429782263`, from
  `gravity-alpha-20260925` (U-Boot 2026.07).

J614s changes retain the separate NVMMU aperture, complete ANS power-domain
mapping, checked firmware shutdown, MTP-only DAPF initialization and internal
ESP selection by PARTUUID. Gravity's CTRR reservation now covers T6040.
The U-Boot bridge remains read-only and has no SD fallback. GPU enablement is
outside this trial; the desktop should continue using software rendering.

## Native check

1. Boot M4RCH with the SD removed. Confirm `/` and `/boot` are on internal NVMe.
2. Check desktop, keyboard/trackpad, USB, Bluetooth, existing audio, CPU idle
   and SME for regressions. Do not change firmware or install another kernel
   during this comparison.
3. Run `sudo sh /boot/loader-alignment/collect.sh`. Add observations and any
   errors to the returned directory's `HANDOVER.md`, then recreate its archive:
   `sudo tar -czf DIRECTORY.tar.gz -C /boot/loader-alignment DIRECTORY_BASENAME`.
4. Test one shutdown/cold boot and one reboot. Return the archive on the
   internal ESP, together with the final observations. If boot fails, photograph
   the last complete screen and return to macOS.

## Rollback from macOS

Deployment prints a verified Mac-local backup under `out/split-boot-backups/`.
Mount the internal ESP, then restore that backup's `boot.bin` to
`/Volumes/M4RCHESP/boot.bin` with `sudo cp`, followed by `sync`. Restore only the
ESP bundle; stage 1 and the Apple stub do not need re-enrollment for this rollback.
