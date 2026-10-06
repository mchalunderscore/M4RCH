# GPU source collaboration checkpoint — 2026-10-06

Continue on branch gpu/native-contract. CURRENT: running 7.1.3-m4rch-gpu-port;
continuous shallow WFI enabled, GFX off-0, normal recovery default 0.
Full driver registration/unload, guarded startup refusal and powered ID-only
probe passed. Owner reports normal operation. No GPU firmware has started and
there is no acceleration. The current results below supersede historical
checkpoint states and staged reboot instructions.

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

Guarded maintained full-driver compile/staging checkpoint:
7.1.3-m4rch-gpu-port is separately packaged and installed. Build ID
2a100931b29c8c425aadee3140fe697f3b9722be. Full Image/modules built and modpost
passed. First attempt lacked Rust dma_fence_is_signaled; the exact helper was
backported and compilation/linking passed. GPU compile emitted14 warnings
(deprecated API and unused code), not a warning-free build. Protected USB,
framebuffer, cpufreq, early-fault and WFI source hashes match the working stack.
Config differs from the running Rust leaf trial only by replacing the leaf
module with DRM_ASAHI_M4 and adding DRM scheduling/Rust RTKit/shmem support.
T6040 startup remains false, exact firmware gate retained, no GPU DT node added.

Matching initramfs /init, kernel release and package-ownership check verified.
Normal kernel/initramfs/EFI loader/board overlay restored byte-identically after
package hooks. Two unreferenced old trials IBATCH1 and ICONT001 were moved from
the ESP to out/gpu-port/esp-retired with per-file hash verification. Normal and
SME fallback files remain. Current running kernel is still the gpu-id trial.

Next reboot target: GRUB default3, 7.1.3-m4rch-gpu-port. The first native test is
framework boot stability and driver registration without a GPU node; no firmware
startup or rendering. After successful userspace recovery, restore default0.
If it fails before userspace, force off, boot macOS and change set default=3 to
set default=0 in the SD EFI partition's grub/grub.cfg. Phone Remote cannot
recover an early kernel hang. Do not replace Apple enrollment/loader images.
Receipt: docs/evidence/2026-10-06-gpu-maintained-port.json. Reproduce with
prepare-maintained.py in a fresh workspace, then prepare-port.py --build and
package-port.py. No macOS handoff is needed for this next native framework test.

## Native full-framework results and firmware provenance — 2026-10-06

The running build ID matches 2a100931b29c8c425aadee3140fe697f3b9722be.
The full driver refuses normal T6040 startup before mapping resources. Its
ID-only probe reads 0x0a031100, 0x0011020a, 0x00040404, 0x400c0c02,
matching the leaf trial. Standard genpd power transitions off-0 -> on -> off-0.
Temporary overlays/modules were removed. WFI remains enabled. Native receipts
are in docs/evidence/2026-10-06-gpu-maintained-port.json; raw dmesg/captures
remain local under out/gpu-port/reboot-trial.

Read-only Linux inspection confirms the stub is macOS 26.5.2 / 25F84,
with mBoot-18000.121.3 and G16S armfw_g16s.im4p. Main macOS Preboot
reports 27.0.1 / 26A434. Their IM4P GFX payloads differ: stub 3,388,496
bytes versus main 2,536,640 bytes. See the hash receipt in
 docs/evidence/2026-10-06-gpu-firmware-comparison.json.
Neither version difference alone proves an incompatible firmware ABI.
A reference captured on main macOS must identify its actual firmware payload;
it cannot silently qualify the different Linux-stub payload. No internal boot
files or installed loaders were changed. Both Preboot mounts are unmounted.

Offline loader lookup patch adds the observed 26.5.2 mBoot identifier; firmware.o
and kboot_gpu.o compile. This only fixes identification, not startup qualification.

Next implementation requirements, before enabling T6040 normal startup:
- Replace G16 Platform's fixed single-cluster 0x3ff mask and 11-entry ladder
  assumptions with the observed two-cluster masks/tables; validate serializers.
- Resolve T6040 MCC mapping from its own ADT/reference, rather than using
  g16_platform.rs MCC_BASE 0x2201c4000 from T8132.
- Qualify mailbox/IRQ roles, UAT mappings and shared initialization structures
  against the actual G16S firmware. The current exact .161.10 gate is retained.
- Only then trial firmware handshake, with startup/crash evidence and cleanup;
  command submission and Mesa rendering follow a successful handshake.

The bounded boot-provided gfx-data RAM snapshot is not identified as an executable
firmware image or proof of a compatible ABI. Its raw bytes stay local.

## Further Linux-only preparation — 2026-10-06

No macOS switch is required merely because the firmware tag differs. Offline
work continues; any eventual macOS capture needs a concrete method, not an
assumption that ordinary IORegistry exposes live firmware queues.

The stub version is an explicit M4RCH pin in stub-inputs.lock.json and
lib/firmware.py, following Wallace's pinned J614s 26.5.2/25F84 corpus. Main
macOS updates do not update that separately provisioned stub.

New incremental loader patch gravity-bootloader-t6040-cluster-metadata.patch
emits independent grouped cluster steps in experimental m4rch properties.
The GPU remains disabled; no masks, power calibration or firmware slot layout
are invented. The exact C function compiled for AArch64 and executed offline
against this boot's tables. All 132 cells match the independent Python decoder;
both clusters have 11 steps. It is not installed. Apply after the original
T6040 metadata loader patch. See REPRODUCE.md for validation commands.

Complete ADT bus-window translation now audited: SGX windows are
0x288000000+0x3758000 and 0x288d00000+0x16c000. Ten offset requirements exceed the second raw SGX window. This is not a donor
builder failure: its Linux DT resource order is ASC then the first SGX window.
First-window containment alone is not proof of the firmware register roles. T6040 MCC's four 32 MiB windows translate
to 0x220000000, 0x222000000, 0x224000000, 0x226000000. The donor MCC base
0x2201c4000 is contained, so it is a plausible candidate, not a proven wrong
address; its role and mapping size still need qualification.

FTAB/Mach-O analysis identifies the reserved gfx-data snapshot exactly as the
stub firmware b000 __DATA segment: all 1,277,952 bytes match, including all
58,592 nonzero bytes. a000 differs in 424 bytes. FTAB tags are not interpreted
as cluster IDs. Stub RTKit is 3255.120.11; main RTKit is 3514.0.15, whose data
layout includes a new __DATA_SHARED_RO segment and a smaller __DATA segment.
This is strong loaded-data provenance, not a qualified initialization ABI.
Raw firmware is retained locally only; metadata reports are in docs/evidence.

Remaining work: identify G16S initialization object/queue layouts, replace
single-cluster serializer constants and chip 0x8132 fields, qualify register
slot roles and mailbox/IRQ mappings, then prepare a guarded firmware-handshake
candidate. Do not remove the T6040 startup barrier solely because power/ID and
metadata tests pass. Continuous shallow WFI stays enabled.

## ASC/mailbox preflight and staged first-message probe — 2026-10-06

Latest native results: ASC at 0x28a600000 reads control 0, status 0x6a.
The low status bits are 2, satisfying the donor's stopped-state check.
Only registers +0x44/+0x48 were read while the known GFX/AFR domains were on.
The helper unloaded, GFX returned to off-0, no new kernel fault signatures.

The gfx-asc ADT IRQ list [1502,1501,1504,1503] maps under the matched ASC
convention to send-empty 1501, send-not-empty 1502, recv-empty 1503,
recv-not-empty 1504. Its mailbox window is 0x28a608000+0x4000.
A temporary node bound to apple-mailbox. Required send/receive IRQs were
requested disabled (NO_AUTOEN); no client/message/start was used. Overlay and
platform device removed cleanly. This proves registration, not IRQ delivery.

Correction: Gravity's Linux GPU DT orders reg resources ASC then SGX. The
builder's second resource is the large first raw SGX window, not raw SGX
window 1. Earlier wording that it necessarily selected the smaller window was
wrong. There remains a genuine fixed 64 MiB iomap requirement in the full
bootstrap, versus our 0x3758000 resource; the first-message helper bypasses
that rendering bootstrap entirely.

Read-only captures show reserved ttbs/pagetables/l2/handoff currently all zero.
Do not treat those as an already initialized firmware root. The boot TEXT
segment is declared separately by gfx-asc segment-ranges (<QQQI4x records).
Its 393,216 bytes differ from b000 TEXT in 339 bytes (versus 232,249 for a000),
with differences confined to two pages; their semantics are not yet proven.
DATA remains an exact b000 match. These are local RAM snapshots, not execution.

A separately built asc-hello module is STAGED, NOT RUN. Its default run_gate=0
was rejected natively before power/mapping. A guarded launcher dry-run passes.
It uses only the known genpd provider, ASC start/stop control, and standard
ASC FIFO registers. With explicit run_gate=1 it observes one incoming message
for at most four seconds, sends no reply, requests a core stop, and retains
mappings/power/module reference until reboot even if stop readback succeeds.
It publishes no new firmware-addressable allocations, writes no SGX/handoff
registers or initialization objects, and submits no GPU work. Missing firmware
prerequisites may produce no message; this is not a full handshake test.
A hang is possible. Owner must save work and be ready to reboot afterward.
Do not force-remove asc_hello. Normal GRUB recovery remains default 0.

After owner readiness:
  sudo python3 experiments/t6040-gpu/run-asc-hello.py out/gpu-port --run
Review out/gpu-port/asc-hello/{attempt.json,live-dmesg.txt,after-start-dmesg.txt}
before a normal reboot. The launcher is bound to this boot ID, build and module
hash; it refuses retry after an attempt. A later boot requires new qualification.
Main asahi_m4 T6040 normal-startup guard remains unchanged. Continuous WFI Y.

## First native G16S RTKit HELLO received — 2026-10-06

The staged asc-hello trial RAN after owner readiness. Firmware emitted
message 0x100000000c000c, metadata 0x10010000000000 approximately 2 ms after
the start log. Local RTKit definitions decode endpoint 0, management type 1
(HELLO), minimum protocol 12, maximum protocol 12. The host sent no reply.
No SGX/handoff writes, initialization graph, firmware buffer allocation or GPU
work submission occurred. This establishes firmware execution and initial
mailbox reception, not a complete negotiated handshake or acceleration.

ASC control changed back to 0; status 0x6e has low bits 2, satisfying the
stopped-state readback. This is not a DMA-quiescence proof. asc_hello remains
pinned at refcount 1, and its GFX power reference remains on until reboot.
DO NOT force-remove the module or power domain. Continuous WFI remains Y.
No new kernel fault signatures appeared. The launcher completed and saved
before/live/after logs under out/gpu-port/asc-hello. Native decoded receipt is
docs/evidence/2026-10-06-gpu-first-hello.json.

REBOOT REQUIRED NOW. Default remains normal recovery entry 0. After reboot,
verify module absence and normal peripherals, then prepare protocol-12 HELLO
reply, endpoint-map/crash-buffer handling and acknowledged RTKit shutdown as
the next bounded trial. Requalify the new boot's addresses and cold state;
do not reuse this boot-specific launcher receipt or force a retry.
