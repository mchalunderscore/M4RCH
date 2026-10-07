# GPU resumed: upgraded-firmware handshake passed — 2026-10-07

Owner reports peripherals working after the promoted 7.1.13-m4rch-gravity
kernel reboot. Continuous shallow WFI remains enabled. Internal NVMe remains
the boot/root device; normal GRUB default 0 is retained.

Fresh boot ADT confirms stage-two mBoot-18000.161.10 (26.6.2 / 25G83).
ASC addresses, mailbox geometry and reserved TEXT/DATA extents match the
previous capture. This is metadata evidence, not a payload-byte identity check.
New standalone Discord ABI reference has unchanged numeric values but clearly
separates channel-state and queue-pointer objects. Treat its layouts as candidate
25G83/G16S contracts; author machine has 20 cores, ours has 16 (3db/3db).

Current-kernel-built bounded ASC probe negotiated protocol 12 and received
endpoint maps for 0, 1, 32, 33; both ACKs completed. No application endpoints
started, no DMA addresses supplied, no GPU work submitted. Stop readback was
control=0/status=0x6e. This does not prove DMA quiescence: power, mappings and
module remain pinned until reboot. Never force module removal.

NEXT: normal Linux reboot (not macOS required). Then qualify the 25G83 firmware
payload/reserved mappings and prepare explicit G16S ABI serializers with
separate channel-state/queue-pointer types, correct unaligned fields and our
16-core topology. Before full rendering, establish RTKit crashlog/application
endpoint lifecycle and firmware-accessible buffer teardown. Keep normal startup
gated until those contracts are validated. Current maintained kernel has Rust
GPU driver disabled; later integration requires a separately built trial kernel.
Do not transplant donor single-cluster constants or claim acceleration yet.

Evidence: docs/evidence/2026-10-07-gravity-gpu-handshake.json and
2026-10-07-gpu-abi-reference.json. Raw logs and matching helper build are retained
in ignored out/gpu-gravity-20261007. Earlier next-step notes below are historical.

# Maintained Gravity kernel promoted; USB fixed — 2026-10-07

Owner requested promotion despite first-boot USB regression. linux-m4rch is now
7.1.13-3, release 7.1.13-m4rch-gravity, on Gravity commit 3b85d81f6. Separate
linux-m4rch-gravity-trial package removed in the same transaction. Internal
NVMe normal GRUB default 0 now boots the promoted kernel and matching generated
initramfs; stage-two boot.bin unchanged. Kernel/initramfs package identity and
NVMe root UUID/bounds/storage dependencies verified. GPU work remains paused.

USB regression diagnosed and fixed live:
- Gravity required a DWC3 reset-control absent from T6040's live DT; reset is
  provided by the exercised PHY path. Optional reset lookup restored for T6040
  only; mandatory requirement retained on other boards.
- Gravity parent Type-C Makefile used renamed TPS6598X_CORE config, omitting
  our retained TPS6598X transport. Parent build wiring corrected.
Three host controllers initialize successfully. Owner's left-front YubiKey
1050:0407 enumerates, including HID/FIDO interface. Other ports/orientations
not physically tested this round. USB service restart passes with persistent
installed modules. First raw Type-C insmod lacked core dependency; loading
Type-C core resolved it; normal modprobe resolves that dependency.

NEXT: normal Linux reboot to verify maintained kernel/initramfs and automatic
USB loading. Confirm left-front key and optionally other ports, input/network,
SME/WFI and NVMe mounts. No revert requested. Earlier 7.1.3 boot files and module
archive are in ignored out/gravity-kernel-alignment/boot-backup and
maintained-modules-before.tar.gz, not an active menu fallback. Old GRAVK001
initramfs expects removed trial pkgbase: do not select it after promotion.

Receipt: docs/evidence/2026-10-07-gravity-kernel-promotion-usb.json. USB compile
and live logs in out/gravity-kernel-alignment. Reproducible fixed source recipe:
experiments/kernel-alignment. make kernel-gravity builds this profile;
make packages-gravity creates maintained package in a fresh workspace.
Historical generic image/kernel/package pipeline retains old pins and must
not be used to rebuild this promoted installation pending full image-pipeline
integration. Source patch replay and hash match verified on fresh checkout.

Earlier checkpoints follow and are historical.

# Gravity kernel alignment — staged reboot checkpoint, 2026-10-07

NEXT BOOT: 7.1.13-m4rch-gravity, separate linux-m4rch-gravity-trial 7.1.13-1
package. Gravity source 3b85d81f656af14d0fc4bea3eef87fe040c424f9, current default
upstream revision verified. GPU work paused at owner's request; optional Apple
display/SIO driver excluded, maintained software framebuffer retained.

Internal NVMe GRUB default 1 selects /GRAVK001/vmlinuz and initramfs.img.
Working 7.1.3 kernel/initramfs remain unchanged at entry 0. m1n1, U-Boot, Apple
stub and enrollment unchanged. Rollback from macOS: mount internal M4RCHESP,
copy GRAVK001/grub-before.cfg over grub/grub.cfg, sync. This is an internal
kernel fallback, with no SD dependency. Do not automatically reboot.

Full Image/modules build and modpost passed. Final pass had no compiler warnings
or errors. Source patch applies to fresh pinned Gravity checkout. WFI, early
fault handling, framebuffer, USB2 PHY and SPMI/Type-C files retain exercised
sources. DockChannel/HID transport and shared power/NVMe/CPU APIs reconciled.
Two compile/link issues fixed: PMGR skip-auto-enable field restored; optional
Apple display module lacks exports and was excluded. Native packaging required
because sandbox fakeroot rejected ownership preservation. Logs retained locally.

NVMe trial initramfs verified: exact root UUID, PARTUUID/bounds, kernel release,
trial package identity and Apple NVMe/SART module dependencies. Working boot
artifacts matched backup hashes after installation; grub-script-check passed.
Receipt: docs/evidence/2026-10-07-gravity-kernel-trial.json. Reproducible source
recipe/config/patch: experiments/kernel-alignment. Local build/logs/package:
out/gravity-kernel-alignment. No native trial boot or hardware stability claim yet.

After reboot: verify release and NVMe mounts, collect dmesg/config, WFI activity,
SME/SME2, CPU capacities/frequency, input, USB/YubiKey, Wi-Fi/Bluetooth and usual
audio. Check failures against maintained baseline. Once stable, restore default
0 while deciding package promotion. Do not resume GPU work until the aligned
kernel baseline is verified; then use supplied Discord ABI document and saved
handshake evidence. Loader cold and warm boot checks previously passed.

Earlier checkpoint notes follow; their next-task states are superseded.

# Native loader validation — 2026-10-07

This cold boot passed: owner reports desktop, input, USB, Bluetooth and usual
audio all work normally. Both root and boot are internal NVMe; maintained kernel
7.1.3-m4rch unchanged. Continuous shallow WFI Y; SME and SME2 are advertised.
No failed services. Native collector completed; return archive is
/boot/loader-alignment/return-20261007T095925Z-lHqhGP.tar.gz.
Kernel log retains ANS PANICLOG-not-written and PCIe timeout-mask messages;
these are not evidence of an observed storage I/O failure.

NEXT: one ordinary Linux reboot to validate the new stage-two chain on warm boot.
Keep kernel/firmware fixed for this remaining loader comparison. After that,
resume owner's requested Gravity kernel-version alignment using the updated
repo's protected T6040/NVMe/USB/SME/WFI stack. Earlier GPU/native handover is
preserved at docs/evidence/2026-10-07-pre-loader-handover.md.

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
