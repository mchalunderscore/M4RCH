# GPU source collaboration checkpoint — 2026-10-06

Continue on branch gpu/native-contract. Exact maintained source/build pins are
now shared in this repository; normal kernel, WFI and GRUB default are unchanged.

The guarded ADT capture succeeded and unloaded its helper. Parser fix preserves
duplicate unrelated siblings; unique contract nodes remain mandatory. Linux
stage-two firmware is mBoot-18000.121.3, versus Gravity's qualified .161.10; keep
the exact barrier. Both cluster ladders match macOS. GPU memory regions lie
outside advertised RAM, but there is no GPU alias/resource template/render node.
Raw captures remain ignored local evidence, not source submissions.

Added distinct T6040 metadata/ladder, loader metadata-only and Mesa S-discovery
patches against pinned Gravity trees. Gravity 7.1.13+ vmlinux and GPU .ko build;
loader kboot_gpu.o builds; Mesa shared libraries build in a separate prefix.
Six Rust metadata tests, C topology/layout gate and parser regressions pass.
These are offline builds, with no GPU MMIO/firmware/rendering validation.

See experiments/t6040-gpu/README.md and
docs/evidence/2026-10-06-gpu-native-build.json for scope and receipts. Full
private captures/build logs/binaries are locally reachable under ignored
out/gpu-native-20261006. The patches are not enabled by make kernel.

Next: integrate the GPU identification source into the maintained 7.1.3 baseline
while retaining USB/SME/WFI; validate SGX power, DT, mailbox and interrupt mapping.
Only then stage a matched identification trial. Do not insmod the 7.1.13+ module
into this boot or install unqualified firmware/packet layouts. A Linux-to-Linux
trial must set GRUB default explicitly and retain the working matching fallback,
because keyboard input in GRUB is unavailable.

Owner has configured phone-based Codex Remote, KDE autostart, autologin and
SDDM at boot. This is a potential recovery path for display-only failures if
the kernel, networking and Codex session remain alive; failure recovery has
not been exercised. Keep the matched boot fallback for earlier hangs.
