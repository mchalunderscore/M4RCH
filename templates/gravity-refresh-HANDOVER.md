# Native bootloader test — 2026-10-19

The candidate contains Gravity m1n1 08f691e with the full VRAM Normal-NC mapping
and Rust no_builtins fixes, plus the retained J614s NVMe/CTRR/DAPF guards.
U-Boot keeps its existing internal-only, read-only EFI handoff. Added progress
banners and the green-square drawing code have been removed; failures remain
visible. The installed baseline device tree is reused byte for byte.

Only ESP /boot.bin and this diagnostic kit are staged. Apple enrollment/stage 1,
GRUB, kernel and rootfs are unchanged. This is not a GPU or hypervisor trial.

1. Boot M4RCH with the SD removed. Confirm the desktop and keyboard/trackpad.
2. Check the existing USB devices, Bluetooth, audio and CPU idle behavior.
3. Run `sudo sh /boot/loader-alignment/collect.sh` and record observations in
   the returned HANDOVER.md. Recreate its archive after adding observations.
4. Check a normal shutdown/cold boot and a reboot. Record any regression and
   whether the green squares and added progress banners are absent.

The staging command prints the Mac-local rollback directory. Its receipt.json
records both candidate and previous SHA-256 hashes. To roll back from macOS,
mount the internal M4RCHESP and restore that directory's boot.bin to its root,
then sync and verify its SHA-256 against previous_sha256. Do not replace stage 1
or re-enroll Apple boot artifacts for this rollback.

Native boot success is pending until these observations are returned.
