# T6040/G16S GPU bring-up — Gravity baseline

Focus on GPU now. Use `/boot/GPU0001`; work in
`/home/alice/Documents/Codex/2026-10-05/he/outputs`. Preserve the working main
kernel, WFI enabled, desktop and `/boot/MAIN0001` / `/boot/SMEK0001` rollback.
No repeat of CPU validation or enrollment this round.

## Accepted baseline

The maintained kernel return is verified: 563 manifest files, archive SHA256
2231360d6e2a45472992d7d95681480641d45785fb30d5e429dcd308ca6d877d.
Native `7.1.3-m4rch`, package7.1.3-2, build ID
ce43447e60d7396e06667adb085c234c920ef10d passed the state/signal/ABI tests;
owner confirms peripherals remain normal. WFI stays enabled. Prior actual
4.512GHz and WFI power saving are established; this round's crypto comparison
showed no meaningful performance-governor benefit. Keep schedutil. Native agent
corrected LOAD.SH to fix OpenSSL buffer size: don't rerun the old unbounded kit
script; its source/result is preserved in the returned archive.

## What macOS and source review establish

MACOS.JSN contains the selected current capture. This is G16S, two clusters,
core masks0x3db/0x3db (8+8 enabled cores). Apple's raw num_cores20 describes slots;
reported gpu-core-count16 and mask population agree. Don't report20 enabled.
Both performance tables have16 rows and each groups into11 voltage steps;
CONTRACT.PY preserves cluster-specific voltage/frequency rows and high/low
indices. No relative-power calibration or max-power value is invented.

Pinned public sources in SOURCES.JSN / SOURCE.TGZ:
- GravityLinux/linux 3b85d81f656af14d0fc4bea3eef87fe040c424f9
- GravityLinux/bootloader 950e6b7f268e71cf77889f27a760782bf898b651
- GravityLinux/mesa 87ac51d411f0e58a9433567ec2666f457be89e1d

Critical mismatches: driver matches only apple,agx-t8132; GET_PARAMS reports
0x8132/G/one cluster/ten slots; Platform rejects masks beyond10bits and uses
T8132-specific MCC windows. Loader handles one table and inserts T8132 masks,
37237mW and relative-power calibration. Firmware validation accepts only
mBoot-18000.161.10 and a precise43-bit private VM contract. Current macOS reports
mBoot-20457.1.29, but that is NOT evidence about the Linux boot stub.
Mesa generation16 asserts variant G. Add S explicitly; do not spoof G or
remove firmware checks to make a probe proceed. Shared ISA does not qualify
all queue, tile-buffer, firmware-object, power or address-space layouts.

The Rust platform.rs and drm/mod.rs files are byte-identical to our pinned
kernel source; that is encouraging for porting. The full driver/framework
build still needs checking. Current kernel has CONFIG_RUST unset and no M4 GPU
driver, so the Rust GPU patch cannot be insmod-ed into this existing kernel.

## Capture the actual Linux boot contract now

First verify kit SHA256 and run ordinary capture:

```sh
OUT=/home/alice/Documents/Codex/2026-10-05/he/outputs/gpu-$(date -u +%Y%m%dT%H%M%SZ)
mkdir "$OUT"
(cd /boot/GPU0001 && sha256sum -c SUMS.TXT)
sudo python3 /boot/GPU0001/COLLECT.PY --output "$OUT/baseline"
sudo python3 /boot/GPU0001/LOADADT.PY --output "$OUT/boot-adt"
```

ADT.ko is built against the exact maintained kernel with verified vermagic and
no W=1 warnings. LOADADT.PY checks the exact GNU build ID and kit hashes, refuses
an already-loaded helper, and unloads its module in finally. The helper finds
only the bootloader's phram-compatible reserved-memory node labelled adt,
requires System RAM, maps it as cached RAM and exposes a read-only0400 sysfs
file. It doesn't read GPU MMIO, write registers, start firmware or register DRM.
No /dev/mem, arbitrary physical-address module parameters or MTD write surface.

If it refuses the reservation, preserve the failure and baseline FDT, inspect
why System RAM/resource checks failed, and return a precise fix; don't bypass
checks or substitute macOS addresses. ADT.PY bounds/parses raw metadata and
selects chosen/arm-io/sgx fields. Raw FDT/ADT stay private in the return archive.

Resolve: exact Linux boot firmware identifier; both performance tables and
SRAM rows; private VM base/size; existing GPU firmware/TTB/page-table/handoff
reservations and whether their physical ranges are excluded from the Linux
allocator; GPU node/status/aliases/reg names/power domain/mailbox/AIC resources.
Compare with MACOS.JSN, but take live reservation addresses from this boot.
If firmware is different, keep the exact version barrier and identify the
specific ABI differences before extending it. No blanket allow-any version.

## Begin the actual source port in this session

IDENTIFY.PAT is an identification-only patch against the pinned Gravity
asahi_m4.rs; source/patch/result hashes are in SOURCES.JSN. Application verified;
full Rust module build and native GPU register reads are NOT yet verified.
It adds a distinct T6040 match, defaults probe_only1, maps only the window
through the published ID offsets, and rejects T6040 probe_only0 before normal
registration. T6040 returns before T8132 power/MCC/firmware builders.
No rendering driver is installed or enabled by the ADT capture step.

1. Extract SOURCE.TGZ into a new ext4 working directory and verify SOURCES.JSN
   hashes. It contains selected56 public files, not a complete kernel checkout.
   Use full pinned checkouts when compiling. Review/apply IDENTIFY.PAT in the
   Gravity checkout, not the installed kernel. Record Rust/bindgen/clang and
   required Kconfig/framework differences. Produce actual compilation logs;
   don't label patch application or Rust parsing as a successful module build.
2. Implement a T6040 profile separately from T8132: chip/variant/cluster masks,
   both independent performance ladders, register sizes and discovered MCC
   routing. Keep table decoding generic and test both profiles offline.
   MACOS.JSN already provides derived ladders without copying its live physical
   firmware-memory allocations. Separate physical slots from fused active cores.
3. Audit bootloader memory reservation/handoff against this boot's ADT. Define
   the minimal T6040 metadata handoff patch and exact DT resources needed for
   the identification probe. Review SGX power state/register ID layout before
   actual MMIO: even an ID-only probe can fail on an unpowered window. Do not
   start firmware or change the installed loader as part of this data capture.
4. Audit Mesa's G16G selection and generation16 variant assertion. Prepare an
   explicit G16S model/dispatch change with topology/layout tests, retaining
   G16G behavior. Don't simply map S to G to bypass assertions. Build candidates
   into a separate prefix, never overwrite working system Mesa yet.

Proceed with code and offline builds as far as the captured contract permits;
return concrete patches and build failures rather than only a new checklist.
First hardware milestone: correctly identified G16S and validated memory
contract. Then firmware boot/render node, headless buffer/shader/triangle tests,
then desktop presentation. DCP display support is separate: headless rendering
can be pursued before replacing the working simple framebuffer.

Gravity open PR #5 (https://github.com/GravityLinux/linux/pull/5) adds a
macOS ADT evidence collector for J614s PCIe/SD, not GPU enablement. No open
T6040 GPU implementation was found in the inspected PR lists. Treat this as
a public-work snapshot, not proof nobody is working privately on G16S.

## Return

Create `/boot/m4rch-return-gpu.tar.gz` and SHA256 sidecar, with HANDOVER.md,
complete captures, source pins, patches, offline tests and build logs. Extract
and verify an internal SHA256SUMS manifest. Record what is implemented, compiled,
natively executed and still assumed separately. No CPU retuning, speaker/audio,
suspend, GPU power-limit/voltage changes or desktop package replacement this round.
Keep current GRUB selection and the working matched rollback untouched.
