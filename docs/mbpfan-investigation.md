# mbpfan fan control investigation

On the 27 October 2026 diagnostic-kernel boot, mbpfan was started at 08:48:38
GMT. It logged 96 `Could not set fan speed: Input/output error` messages through
08:50:31, then no more by 09:03. Earlier boot logs include a failure lasting
from 23:15 to 03:46, so the problem is not limited to early boot. The current
service stayed active without restarts.

The configured backend uses macsmc_hwmon, `/sys/class/hwmon/hwmon1`, with
firmware-reported min 2317 and max 7826 RPM and a CPU Die Max temperature
sensor. While observing the service, strace showed successful writes of 6763
and then 7826 to both `fanN_target` files, but subsequent sysfs reads reported
both target and input speeds as zero for more than a minute while CPU Die Max
was approximately 78–91 C. The owner reported fans periodically run but were
not audible at the time. No write error in the journal occurred during the
contradictory readings. A successful sysfs write therefore does not establish
that the hardware accepted or sustained that target.

The service was stopped to request its documented firmware handoff. Explicitly
writing 0 to both targets then returned EIO. Since firmware handoff was not
confirmed, the service was restarted; it requested 7826 RPM successfully.
Subsequent readings showed both fans spinning around 2300–2500 RPM, with target
readings around 2317–2502 RPM and CPU Die Max approximately 82–90 C. This is
not proof of an effective control loop or safe thermal headroom. The requested
write, reported target, actual speed, and temperature should be checked together.
No persistent service configuration was changed.

The local macsmc hwmon code can return EIO from SMC transactions, but the
existing messages do not say whether reading fan limits, writing the manual
mode key, or writing the target failed, nor do they report the requested RPM.
The 0-target handoff failure and the contradictory successful speed writes
need further investigation; the old startup-only explanation is unproven.

## J616s fan-control work and J614s read-only observations

Aurora Linux PR #512 (`https://github.com/aurora-silicon/linux/pull/512`, draft
as of 27 October, head `bc0370654f2c00cd5199c50d36285f24a8da9025`) addresses
J616s firmware that reports fan mode 3 and rejects a direct manual-mode write.
It conditionally writes the `Ftst` unlock key; J616s hardware qualification was
still listed as pending. PR #511 describes the related J616s firmware policy.
Neither PR establishes J614s behavior.

The existing running J614s driver does not expose these modes through hwmon
sysfs, and its debugfs key inventory is not registered on this machine. A small
read-only diagnostic module was built against the running diagnostic kernel,
loaded and immediately unloaded. It used only `apple_smc_get_key_info` and
`apple_smc_read`; it never wrote SMC keys. On 27 October at 09:08:32 and
09:09:18 GMT both F0Md and F1Md returned 0 (the mode called automatic by the
PR). Ftst exists with a one-byte ui8 key and readable/writable/function flags
0xd0; its value was deliberately not read and it was not written. Machine DT
identifies this as apple,j614s/apple,t6040.

At 09:09:09–09:09:11, strace observed mbpfan successfully writing 5437 then
5853 RPM to both target files. At 09:09:18 both mode reads were 0 and the fan
targets were 2317 and 2502, with actual speeds 2316 and 2516 RPM and CPU Die
Max 56.1 C. These are sequential observations, not an atomic sample; the
requested speeds also changed between samples. Nevertheless, together with the
previous sustained full-speed requests and zero/minimum readbacks they show
that successful writes do not prove manual mode or a sustained requested target.
The in-tree driver caches `manual` after a successful mode write and does not
read the current SMC mode on later target writes. That is a concrete mechanism
by which cached state may drift, but this trace does not establish exactly when
or why that happened. PR #512 also caches manual state and its unlock branch
only triggers after a refused manual request when the readback mode is 3; our
mode-0 sample does not establish that the PR would fix this system.

## PR #512 hardware test prepared

On 27 October the owner authorized direct hardware testing and external
recovery if necessary. Aurora PR #512 commit
`bc0370654f2c00cd5199c50d36285f24a8da9025` was applied from its exact GitHub
commit patch to the local 7.3 kernel source with the proven GPU cleanup fix.
The separate `7.3.0-m4rch-fan512` kernel and its modules built successfully;
this build does not claim that the PR's KUnit suite was run locally. The PR
reports 17/17 QEMU KUnit tests, with J616s hardware qualification pending.
The patch is `patches/experimental-aurora-pr512-fan.patch`.

The kernel, initramfs, and module tree are installed separately from the working
`7.3.0-m4rch-diag` kernel. GRUB entry `m4rch-fan512` was configured as the
next-entry; the persistent default remains `m4rch-gpu-diagnostic`. GRUB's
one-shot clearing depends on successful environment writes from GRUB; the
persistent entry and original boot artifacts remain available for recovery.
The test can activate Ftst if the PR's condition is met and mbpfan requests a
fan target during boot. The test is not yet hardware-validated on the J614s.
The 16 MiB test initramfs and 29 MiB test image leave about 28 MiB on /boot;
remove the test artifacts after the investigation, not the working images.

On the test boot, confirm `uname -r`, then read the journal, SMC fan modes,
reported targets, actual RPMs and CPU temperature before and during a
controlled target change. The read-only SMC key probe was rebuilt for this
kernel at `out/fan-pr512/read-only/smc_readonly.ko`. Verify both effective fan
response and handoff to firmware, and retain the previous kernel if either
fails. The GRUB configuration prior to test setup is saved at
`out/fan-pr512/grub-before.cfg`.

## Boot-partition cleanup

On 27 October the owner authorized removal of obsolete boot diagnostics and
handover material, old apt/deb/cargo caches, 22 filesystem recovery fragments,
and unused boot scripts. The temporary archive of the old boot diagnostics
was subsequently deleted at the owner's explicit request. The persistent
working diagnostic entry, pending one-time fan-test entry, installed main
kernel, EFI loader, boot.bin and boot.bin.old, and the previous recovery
entry's r12 kernel and r13 initramfs were retained. `/boot` went from 28 MiB
to approximately 663 MiB free. GRUB syntax, required boot files, and the
pending one-time fan-test selection were verified after cleanup.

On a later reboot the one-time GRUB selection did not take effect: the system
booted `7.3.0-m4rch-diag` and `next_entry=m4rch-fan512` remained in grubenv.
The cause has not been established. The owner requested a keyboard-free default,
so the persistent `GRUB_DEFAULT` was changed to `m4rch-fan512`, GRUB was
regenerated and syntax checked, and the stale next-entry was cleared. The
working `m4rch-gpu-diagnostic` and `Previous working system` entries and their
boot files remain present. The prior drop-in and GRUB configuration are saved
under `out/fan-pr512/grub-default-before-fan512.cfg` and
`out/fan-pr512/grub-before-persistent-fan512.cfg`. The test kernel remains
unbooted until the owner reboots.

## PR #512 hardware result on J614s

The test kernel `7.3.0-m4rch-fan512` booted on 27 October. At 09:48:30 the
read-only mode probe reported both fans in mode 1 with targets 6295 RPM and
actual speeds around 6100 RPM; mbpfan had logged no errors since startup.
Stopping mbpfan returned both mode keys to 3 at 09:48:55. A controlled 7000
RPM request to fan 1 then failed after the PR's ten-second retry period with
`Fan 1 refused manual mode after unlock (-5)` and a sysfs EIO. The test did
not reach the fan 2 write or the speed/handoff checks. After mbpfan restarted,
the same failure was logged for each fan, so the service was stopped to avoid
repeated unlock attempts. At 09:49:57 both mode keys again read 3, both RPM
and target readings were zero, and CPU Die Max was 61.1 C. Mode 3 is the
firmware-controlled mode described by the PR, but this observation does not
qualify its cooling policy.

The shell's tee pipeline did not propagate the test script's nonzero exit
status; the observed sysfs error and kernel logs above are the correct outcome.
The test did not prove a sustained 7000 RPM transition. The previously saved
`m4rch-gpu-diagnostic` GRUB default and configuration were restored; the test
entry is retained. mbpfan is stopped for this running test session but remains
enabled and will start under the default kernel after a reboot. No claim is
made that either kernel resolves the fan-control issue.

## J614s retry candidate and live fan test

On the fan-test kernel, with mbpfan stopped and firmware mode 3, a temporary
module was built from PR #512 with a 3-second delay after setting Ftst, a
30-second retry bound instead of 10 seconds, and bounded trace logging of mode,
write result and Ftst readback. It was loaded without a reboot; the original
PR module is saved as `out/fan-pr512/macsmc-pr512-original.ko`. The incremental
patch is `patches/experimental-j614s-fan-unlock-retry.patch`.

On 27 October at approximately 09:53 GMT a 7000 RPM request to fan 1 succeeded
and the fan held around 6967–7037 RPM for twelve seconds. A zero-target handoff
subsequently restored both fan mode keys to 3. In a second controlled test at
09:54, both fans held about 6967–7042 RPM against 7000 RPM targets for twenty
seconds; a concurrent probe reported mode 1 for both. Returning both targets
to zero restored mode 3 for both. The trace showed Ftst=1 and mode=0 while
mode-1 writes were temporarily rejected before the successful transition.

mbpfan was restarted against the loaded candidate at 09:54:47. At 09:56:42
both fan modes were 1, their actual speeds tracked the changing targets during
a 30-second observation, and the service logged no further errors. This is
encouraging but neither a long-duration qualification nor proof whether the
3-second delay, 30-second bound, instrumentation, or timing variability caused
the improvement. The larger timeout can delay failure reporting and a hwmon
operation for up to 33 seconds.

The exact tested module was installed to the separate
`7.3.0-m4rch-fan512` module tree; it is not included in the initramfs, so the
module-tree copy is used after boot. The fan-test GRUB entry is again persistent
default; the diagnostic kernel and previous working entry remain available. The
module's behavior has not yet been tested from a fresh boot or promoted to the
main kernel package.

## Fresh boot of the revised fan driver

On 27 October the owner rebooted into `7.3.0-m4rch-fan512` with the revised
module installed. mbpfan started successfully at 09:57:45. The kernel logged
transient refused mode writes while Ftst was enabled at 09:57:48 and 09:57:50,
without a subsequent timeout or mbpfan error. At about 09:59 both actual fan
speeds were close to their requested targets, and a read-only SMC probe reported
both F0Md and F1Md as 1. The service was active without a restart. This verifies
one fresh-boot startup on this machine; it does not establish long-term
reliability or which change in the retry candidate is responsible. The
experimental kernel remains the default and the earlier diagnostic kernel is
retained as a fallback. The fan patch has not been promoted to the main package.

## Promotion to main kernel

On 27 October, the owner requested promotion. The PR and J614s retry patches
were applied to the previously built main-kernel tree; the resulting hwmon
source matched the fresh-boot-tested source byte for byte. The module was
rebuilt for `7.3.0-m4rch` against that build and packaged as `linux-m4rch
7.3.0-4` with the existing GPU fix. The package was installed and its normal
initramfs and m1n1 hooks completed. The installed module matches the rebuilt
module and the installed kernel image matches the packaged image. The main
kernel has not yet been boot-tested.

GRUB's automatic Arch entry selected the fan-test image, so an explicit
`m4rch-main` entry was added for `/vmlinuz-linux-m4rch` and its corresponding
initramfs and made the persistent default. The fan-test and diagnostic entries
and their artifacts remain available. GRUB syntax was checked and the saved
one-time boot selection was empty.

The active customized U-Boot also needs `/boot/AURD001/mode`, containing
`test\n` or `framebuffer\n`, before it hands off to GRUB. It was mistakenly
removed as an apparently obsolete experiment artifact during the ESP cleanup,
which can stop boot before Linux logs exist. It has been restored as `test\n`
and must be preserved with the current bootloader. Its purpose is implemented
in `experiments/aurora-direct/prepare_loader.py` and present in the installed
U-Boot binary.

## U-Boot normal handoff without the mode file

On 27 October the owner requested removing the experimental mode dependency
and aligning with normal U-Boot practice. The installed source patch applied
cleanly to Aurora U-Boot revision `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`.
`patches/uboot-j614s-default-handoff.patch` removes the ESP mode read and uses
the same normal GPU handoff selected previously by `test`; the handoff's own
checks and automatic fallback on missing GPU data remain. The separately
selectable framebuffer handoff is no longer provided by this loader. The
experiment source generator was updated as well.

The loader was built using the reconstructed source and packaged as
`u-boot-m4rch 2026.07-2`. The package's normal m1n1 hook installed it in
`/boot/boot.bin`. Image header/footprint checks passed, its compressed payload
was checked against the installed U-Boot binary, and it contains no reference
to `/AURD001/mode`. `/boot/boot.bin.old` matches the saved working prior boot
image at `out/uboot-default/boot-before.bin`; the old image still requires the
retained `test` mode file. The GRUB main-kernel default and fan/diagnostic
entries remain in place. Native boot of the new loader is still untested.
This removes the private file dependency but is not a complete conversion of
our custom `archnvme` boot path to upstream standard boot.

## Main kernel and new loader boot

On 27 October at 10:19 GMT the owner rebooted successfully. Linux reported
`7.3.0-m4rch` with `/vmlinuz-linux-m4rch` as its boot image. The installed ESP
`boot.bin` matched the new U-Boot payload and the prior image remained intact
as `boot.bin.old`. EFI reported U-Boot; the journal did not independently
identify its precise build version. Asahi and Apple DRM bound to the GPU and
display. mbpfan started without restarts or logged errors: both fans tracked a
7778 RPM target around 7757–7784 RPM, and later tracked a 5437 RPM target as
it changed. The driver logged two transient rejected writes during the unlock,
then recovered without a timeout. The owner reported that the boot worked.
The GPU initialized in this brief check.

## Extended use reported

Later on 27 October, the owner reported using Linux all day, with the fans
remaining responsive since boot, and confirmed that Alt+Tab works. These are
user observations during normal use; no continuous fan trace was collected.

## Quiet curve trial

On 27 October the owner requested a quieter response to short spikes. Aurora
PR [#512](https://github.com/aurora-silicon/linux/pull/512) concerns the SMC
manual-mode handoff already adapted in the main kernel, not the userspace
curve. Upstream mbpfan's three-threshold algorithm changes speed based on
temperature changes; the local package now replaces that policy with a linear
75–90 C curve driven by an eight-second exponential filter. Raw readings at
or above 90 C bypass the filter and immediately request full speed; invalid
sensor reads also request full speed. Both fans use their firmware limits.
`low_temp` remains in the configuration for compatibility but is not used by
the new curve. The current exposed control sensor is CPU Die Max; this is not
a calibrated copy of Apple's multi-sensor thermal policy.

`mbpfan-m4rch 2.4.0-3` was built and installed. Actual controller code passed
simulated brief-spike, sustained-load, emergency and invalid-sensor cases.
The service stayed active with zero restarts; after the SMC handoff both fans
tracked the 2317 RPM target at a CPU reading of about 65 C. The owner has
subsequently verified cooling and fan behavior as about as good as on macOS;
further cooling qualification is no longer an active project priority.

The previous package is `/var/cache/pacman/pkg/m4rch/mbpfan-m4rch-2.4.0-2-aarch64.pkg.tar.zst`
and the former config is `/var/lib/m4rch-fan-trial/mbpfan.conf.before-quiet`.
To revert, install that package with `sudo pacman -U`, restore the saved config
to `/etc/mbpfan.conf`, and restart `mbpfan.service`. The trial package is in
`out/fan-quiet-trial/`; the source patch and config are in
`packages/mbpfan-m4rch/`.
