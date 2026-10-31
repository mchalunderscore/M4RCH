# m4rch

Arch Linux ARM packages and hardware enablement for the Apple MacBook Pro
14-inch M4 Pro (Mac16,8 / J614s / T6040). The Linux, m1n1, U-Boot and Mesa
work builds on [Aurora Silicon](https://github.com/aurora-silicon).

The owner confirmed the MTP keyboard handoff in GRUB and Linux on a trial
kernel. The final package-managed `7.3.0-m4rch` kernel is the default but
has not yet been booted; the owner chose promotion without a reboot. Mesa's Vulkan driver rendered on the M4 Pro;
the owner also reported that the system works in ordinary use. Earlier builds had
successful camera, microphone, sleep and external-display trials, but those
results do not independently qualify every feature of the current build.
Internal speakers remain disabled pending protection evidence.

Start with [current status](docs/status.md) for installed versions, tested
behavior and remaining gaps. For maintenance, use the [package guide](packages/README.md)
and [installation and maintenance](docs/installation-maintenance.md). Read
[boot recovery](docs/recovery.md) before changing the boot chain. The internal
keyboard worked in GRUB on the MTP handoff trial.

The boot chain uses upstream EFI/NVMe discovery together with a local J614s
handoff. The earlier `archnvme` and forced VRR/HDR experiments are historical;
their successful trials do not establish the behavior of the current stack.
Per-package source records describe the retained patches, provenance and
the kernel reconstruction limitation.

On native Arch Linux ARM, `make` lists the package commands. For example,
`make packages PACKAGE=mesa-m4rch` builds the pinned Mesa recipe without
installing it. The kernel and bootloader packages currently repackage retained
boot-tested binaries rather than rebuilding from source; see the package guide
for prerequisites and limitations.
