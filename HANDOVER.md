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

Maintained 7.1.3 integration now builds: isolated Rust-enabled Image and
matching leaf m4rch_gpu_identify.ko, with the protected USB/FB/cpufreq/WFI hashes
retained. The build recipe explicitly excludes Asahi firmware startup and PMP/
RTKit drivers newly defaulted by Rust. The read gate is u32 (0 disabled, 1 opt-in).
Initial bool-parameter compile failure is preserved, followed by the fixed build.

Next: validate SGX power/reset/clocks, DT, mailbox and interrupt mapping before
actual identification reads. Linux genpd reports gfx off-0; boot ADT gate 400
GFX-SGX has no_ps and parent GFX386; gate402 GFX-BUSY also has no_ps. Existing
ps_gfx matches the parent metadata, but neither gate is a direct state register.
See docs/evidence/2026-10-06-gpu-power-contract.json.

The first Linux-to-Linux trial is Rust baseline/module-loading validation. It
keeps the live boot DT, which has no GPU node, so there is no resource probe or
GPU MMIO on this trial. The disabled candidate identify-preflight.dtsi compiles
offline; do not substitute a captured live FDT across boots. A later resource/
power trial needs the live loader DT contract qualified. Do not insmod the 7.1.13+ module
into this boot or install unqualified firmware/packet layouts. A Linux-to-Linux
trial must set GRUB default explicitly and retain the working matching fallback,
because keyboard input in GRUB is unavailable.

Owner has configured phone-based Codex Remote, KDE autostart, autologin and
SDDM at boot. This is a potential recovery path for display-only failures if
the kernel, networking and Codex session remain alive; failure recovery has
not been exercised. Keep the matched boot fallback for earlier hangs.


Isolated trial is installed as linux-m4rch-gpu-id 7.1.3-1, release
7.1.3-m4rch-gpu-id; it has a separate initramfs/package identity. See
docs/evidence/2026-10-06-gpu-maintained-trial.json for hashes and checks.
Normal kernel/initramfs match the pre-install backup byte for byte. GRUB has
next_entry=m4rch-gpu-id with consume-before-boot logic; persistent default is
normal entry0. GRUB's runtime environment consumption remains to be exercised.
There was no reboot yet. Current maintained WFI is Y.

After reboot: confirm uname -r, WFI Y, input/USB/network/display normal, and
capture dmesg/config. Load m4rch_gpu_identify with default read_ids0 to test
Rust/platform-driver registration, verify its parameter, then unload. With
no live GPU node it should not bind/map/read any GPU resource. Treat this as
a Rust-enabled baseline checkpoint, not hardware GPU identification or speedup.


First reboot update: normal 7.1.3-m4rch booted, WFI Y. next_entry remained
m4rch-gpu-id, so the one-shot selection was not consumed. This is a boot-selection
failure, not evidence that the trial kernel failed. No trial module was loaded
into the normal kernel. See docs/evidence/2026-10-06-gpu-first-reboot.json.
Replaced environment selection with direct GRUB default=2, explicitly requested
by the owner because GRUB keyboard input is unavailable. Trial image/initramfs
hashes verified before staging. This selection persists until restored to0;
after the trial reaches userspace restore default0. If it hangs before recovery,
macOS can set /grub/grub.cfg on the SD EFI partition back to default0. Both
normal entries and matched fallback files remain present.
