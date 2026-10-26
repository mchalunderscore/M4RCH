# Gravity kernel alignment trial

GPU bring-up is paused at the owner's request. Target: Gravity Linux commit
3b85d81f656af14d0fc4bea3eef87fe040c424f9, kernel 7.1.13. Trial release:
7.1.13-m4rch-gravity. The working NVMe 7.1.3 installation is retained.

Preparation currently lives in ignored out/gravity-kernel-alignment. Its
port-audit.json, merge-audit.json, source-receipt.json, configure.log and build.log
record reconciliation and compilation. No kernel installation or boot selection
has occurred. Initial all-file three-way apply failed atomically on relocated
DockChannel and missing board sources; per-file merge then resolved the port.

The exercised SPMI/Type-C implementation is carried as a unit. Shared APIs use
three-way reconciliation. The maintained mailbox DockChannel implementation is
built from Gravity's soc/apple directory; maintained HID transport is separately
enabled while Gravity's alternate transport is disabled. NVMe/core alignment,
USB cable lifecycle, software framebuffer, CPU frequency, fault handling and
shallow WFI changes are carried forward. Compilation and native boot validation
are still required; this is not a claim of functional equivalence.

Next: finish compilation, review configuration changes and package a separate
matching trial with NVMe initramfs. Inspect actual boot updater/root identity;
do not reuse historical SD initramfs or unqualified old modules. No GPU startup
or new firmware work is part of this trial.

Compilation and module linking now pass. A separate package and NVMe initramfs
are installed/staged; native boot remains pending. See the trial receipt and
current HANDOVER.md. The optional Apple display/SIO driver was disabled after
unresolved exports; no rendering enablement is part of this alignment.

Reproduce source preparation with prepare.py SOURCE NEW_DESTINATION, then:
`make -C NEW_DESTINATION KERNELRELEASE=7.1.13-m4rch-gravity LOCALVERSION= -j4 Image modules`.
Package with package-trial.py WORKSPACE after successful compilation. Run
makepkg natively so fakeroot ownership recording works. The temporary NVMe hook
used for this trial is under out/gravity-kernel-alignment/hookdir; it replaces
only the init's pkgbase check with the trial identity and retains native root
UUID, PARTUUID and bounds. No installed boot updater or hook was changed.

## Maintained promotion and USB correction

The first native boot reached userspace but all USB controllers failed because
Gravity made DWC3's reset-control mandatory. T6040's live DT has no DWC3 reset
specifier and uses the exercised PHY reset. Optional reset lookup is now scoped
to T6040. Gravity also renamed the parent Type-C build symbol, silently excluding
our retained TPS6598x transport; parent Makefile wiring is corrected.

Both fixes compiled, loaded live and enumerated the owner's left-front YubiKey
1050:0407. Three host controllers initialized; other physical ports/orientations
remain untested in this round. Type-C core was loaded before the raw insmod;
normal modprobe/service loading resolves that dependency automatically.

Promoted to linux-m4rch 7.1.13-3 with pkgbase linux-m4rch, proper preset and
kernel-release metadata. The separate trial package was removed in the same
transaction. Normal updater generated matching NVMe initramfs and selected main
entry 0. Stage-two loader bundle stayed unchanged. Current hot fixes persist
in installed modules; reboot validation is still pending.

Use `make kernel-gravity` for this maintained source profile and
`make packages-gravity` to produce its normal package in a fresh workspace.
The historical generic image/kernel/package recipes retain their old pins;
do not use them to rebuild the promoted installation until full image-pipeline
alignment is implemented. Source/profile changes must regenerate recorded
hashes. The build command refuses source drift rather than discarding edits.
