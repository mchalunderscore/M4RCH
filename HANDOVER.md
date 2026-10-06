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


Successful trial boot: 7.1.3-m4rch-gpu-id reached the desktop, WFI Y. Owner
confirms desktop/input/USB/networking feel normal. Native modprobe read_ids0
registered the Rust platform driver, with no bound GPU devices, and unloaded
cleanly; no new dmesg lines during that load/unload. No GPU MMIO or firmware
startup occurred. Framework module parameters have perm0 and are intentionally
absent from sysfs; the attempted sysfs check was corrected using the explicit
load command and framework source. No BUG/Oops/panic/call-trace signatures in
captured boot log. This qualifies the Rust toolchain/kernel/module baseline,
not GPU identification or performance. Normal GRUB default restored to0; trial
remains available. See docs/evidence/2026-10-06-gpu-trial-boot.json.
Next: qualify the power/reset/clock path and a live loader resource-node handoff
before resource-only binding, then opt-in IDs. Existing GFX is off; no_ps gates
400/402 are not direct PMGR state registers. Retain firmware-version barrier.


Further native Linux progress, same trial boot:
- Temporary metadata-only OF overlay populated a dedicated simple-bus subtree.
  Rust read_ids0 bound to 288000000.gpu-preflight and validated the exact named
  SGX resource. GFX stayed off0. Driver and overlay removed; node/device gone.
- Existing registered GFX provider was exercised with of_genpd_add_device and
  standard runtime-PM calls. No invented phandle, direct GPU mappings, resets,
  clocks or firmware calls. genpd went off0 -> on -> off0, runtime suspend0;
  consumer and helper removed. Source PMGR callback polls actual state0xf.
- Owner confirms desktop/input/USB/networking still normal. WFI Y, normal GRUB
  default0. Exact running/build GNU build ID matched before each native test.

Receipts: docs/evidence/2026-10-06-gpu-resource-bind.json and
2026-10-06-gfx-genpd-trial.json. Sources and reproducible W=1 builds:
experiments/t6040-gpu/{resource-overlay,gfx-power-test}, build-helper.py.
Initial unaligned FDT rejected before adding nodes; aligned overlay required
explicit subtree population to create the child device. Both failures cleaned
up and were corrected. External helper sets expected persistent out-of-tree
kernel taint; no new BUG/Oops/panic from these tests.

These tests qualify resource-only binding and parent-domain runtime power,
not safe GPU MMIO, reset/clock sequencing or firmware startup. Raw clock ID315
and no_ps gates400/402 still need their exact role reviewed. Continue from
Linux with captured ADT and pinned source; no macOS roundtrip is required for
this checkpoint. Retain exact firmware barrier and keep read_ids0 until the
remaining access qualification is explicit. No GPU firmware/DRM/rendering yet.


Native raw GPU identification subsequently succeeded. Published loader PMGR
recursion treats gates400/402 as virtual/no_ps, and powers parent GFX386/AFR385.
Its initial ID path uses that power-enable without a separate clock/reset call.
After the successful existing-provider power trial, this supported four bounded
ID reads with GFX held on and both read_ids1 + ID-review acknowledgement set.
Raw version/counts/clusters: 0x0a031100, 0x0011020a, 0x00040404, 0x400c0c02.
Rust bound, read, then unmapped/unloaded; overlay removed; GFX returned off0.
No firmware, DRM, interrupts, MCC programming, resets, clock/voltage changes.
Native receipt: docs/evidence/2026-10-06-gpu-raw-identification.json.

Variant/revision bit fields interpret as S/B1. Generation field is10, rejected
by old generic regs.rs; never spoof G13/G14/G16G. G14X-style counts cross-check
matches ADT two clusters/ten slots; enabled0x3db masks remain ADT evidence.
Offline raw-id.py tests preserve those limits. ID overlay is separate, requiring
--reviewed-id-reads in build-helper.py; hold GFX active for its entire lifetime.

Firmware qualification correction (owner runs macOS 27.0):
The captured OS/stage-two firmware is mBoot-18000.121.3, while system/stage-one
is mBoot-20457.1.29. macOS version alone therefore does not identify the firmware
context used for this Linux boot. Boot-stub provenance remains to be established;
these two tags are observations, not proof of an outdated installation.
mBoot is bundled with macOS; do not propose an independent mBoot update or a
downgrade. Gravity's exact .161.10 gate records its exercised firmware profile.
No incompatible queue/object ABI has yet been demonstrated for our .121.3.
Its loader lookup does not recognize .121.3, so unknown-version handling and
firmware qualification are concrete implementation work, not a proven hardware
incompatibility. Keep the gate and T6040 no-startup guard while reviewing this.

Continue from Linux: reconstruct the maintained kernel in a separate workspace,
port the guarded M4 driver and required framework APIs, compile without altering
the current working kernel, and review ABI/source differences. No macOS roundtrip
is required merely because the firmware strings differ. A macOS capture may
later help establish exact provenance, but is not a prerequisite for this work.
Use native IDs and ADT for T6040 MCC/ASC/AIC and memory handoff review; do not
import T8132 calibration or firmware objects blindly.

Linux has reached the resource/power/raw-ID milestone without another reboot.
The current Rust trial remains usable; next default is normal kernel0. All test
helpers are gone, GFX off0, WFI enabled. Full private native captures/build logs
are retained locally (an ESP return archive has not yet been assembled); shared source/evidence is
on gpu/native-contract. No further firmware execution was attempted.
