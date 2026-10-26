# Gravity bootloader alignment

This profile updates only ESP `/boot.bin`: m1n1 stage 2, the working J614s DT
and gzip-compressed U-Boot. It requires the existing, hardware-tested internal
split boot. Stage 1 and Apple enrollment stay unchanged.

| Component | Pinned source |
| --- | --- |
| m1n1 stage 2 | [Gravity 08f691e](https://github.com/GravityLinux/bootloader/tree/08f691e951e6c3284f9b3bc0fb058e3c4dc06f6f) |
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

## Source refresh — 2026-10-17

The stage-2 profile now includes two commits after the previous `a49e1e1` pin:

- [3c5b962: full VRAM mapping](https://github.com/GravityLinux/bootloader/commit/3c5b96201bdafe75a752c4c8a848edd9b5208fc4)
  maps at least the ADT VRAM reservation size as Normal-NC. The existing
  `display_get_vram` helper checks that the reservation starts at the boot
  framebuffer base; failed lookup falls back to the visible framebuffer size.
  The upstream fault report concerns Neo, so J614s benefit remains unverified.
- [08f691e: Rust freestanding build](https://github.com/GravityLinux/bootloader/commit/08f691e951e6c3284f9b3bc0fb058e3c4dc06f6f)
  enables `no_builtins` outside tests to prevent LLVM 23 introducing unavailable
  libc calls. Host tests retain their normal configuration.

The existing J614s patch applies unchanged. Its framebuffer result hash was
updated; display-header and Rust-source hashes are now checked as well. Other
previously checked J614s file hashes remain identical. The pin stops before
upstream's later PMU panic-counter clearing commit.

Validation: pinned-source patch application and all recorded result hashes;
Linux AArch64 compilation of `build/fb.o` and `build/display.o`; upstream Rust
host test (one passed) and freestanding `build/librust.a` with the existing
Debian builder and its Rust 1.85.1 compiler. This does not directly reproduce
LLVM 23 code generation. Local loader contract tests passed. No complete
stage-2 bundle was built or installed, and no native boot was performed.

See [the hypervisor review](gravity-hypervisor-review.md) for the separate GPU
research opportunity. The newer ARCHROOT checkout and its dirty working files
were preserved locally before making this source refresh.

## Native trial staged — 2026-10-19

The complete updated m1n1 and U-Boot components were compiled in the existing
ARM64 Debian builder, with all pinned patch/result hashes and resolved U-Boot
configuration checked. Added m1n1 cleanup/ANS progress messages, U-Boot bridge
progress banners and early green-square framebuffer writes were removed.
Failure diagnostics and all shutdown, mapping and handoff checks remain.
Version banners now use `v1.6.0` and `2026.07` without project branding.
The legacy NVMe bridge generator also no longer emits the green-square code.

The Mac-local checkout lacked the original ignored split-loader manifests.
`scripts/stage-gravity-refresh.py` therefore verifies the installed boot.bin
against its existing ESP alignment manifest, extracts its single aligned DTB
and compressed ARM64 U-Boot payload, and checks the baseline DTB hash against
that same manifest. It validates the J614s model and complete ANS power map,
then reuses the installed DTB byte for byte. It binds staging to the existing
internal EFI partition's UUID, extent and internal-disk identity. Before replacing
boot.bin, the existing installer helper copies and hash-verifies the prior file;
replacement is atomic and its readback is checked. The prior alignment kit is
also preserved locally.

Staged candidate SHA-256:
`4de31bba9eb209aada9b3ce40f5d7af1303ea79022d4edead2c909aeea7a71a2`.
Verified rollback SHA-256:
`cb3ab77bdac7f276b5331d8580a5ee1b81f8bd215c0cba1449391a73d790ef09`.
Rollback directory: `out/split-boot-backups/20261019T091612117012Z/`.
Its ROLLBACK.txt has the exact restore command and expected readback hash.
The component build log and recipe are retained in `out/sdboot/`.

Only ESP boot.bin and the loader-alignment diagnostic kit were updated.
Stage 1, enrollment, GRUB, kernel and rootfs were not changed. GRUB still defaults
to the NATI001 integrated GPU trial entry; the retained USBR001 entry remains
available for a comparison. Do not start a GPU trial as part of this loader test.
Boot with the SD removed, check peripherals/idle/shutdown/reboot, and run
`sudo sh /boot/loader-alignment/collect.sh`. Native boot success is pending.

Validation: full component compilation and bundle framing, matching installed
baseline, installed candidate and rollback hash readbacks, diagnostic-kit
readbacks, and 22 targeted tests passed; three tests requiring another cached
U-Boot source layout skipped. `git diff --check` passed.

## Native boot confirmed — 2026-10-19

The owner reports that the updated loader booted normally, with no observed
regressions. A subsequent macOS readback confirms ESP boot.bin still matches
candidate `4de31bba9eb209aada9b3ce40f5d7af1303ea79022d4edead2c909aeea7a71a2`.
The preserved rollback copy was reverified against its recorded previous hash.
This is owner-confirmed native boot evidence; separate shutdown/reboot and
individual peripheral checks were not supplied. No new loader-alignment
collector archive for this trial was found. The build/staging manifests retain
their original pre-test status; the native result is recorded separately in
[evidence/2026-10-19-gravity-native-boot.json](evidence/2026-10-19-gravity-native-boot.json).

The new ESP MACOS-HANDOFF.md requests macOS GPU runtime reference captures.
It and its companion collector/restart guide are preserved under ignored
out/esp-handoffs/2026-10-19-macos with checked hashes. Its suggested macOS source
path, /Users/michal/Projects/Personal/m4rch, does not exist; the recovered source
work remains in this arch-m4 checkout on codex/archroot-gravity-updates. The
handoff describes a Linux watchdog mitigation but does not establish the cause
of the earlier resets. No GPU capture or source publication was performed while
reviewing this handoff.
