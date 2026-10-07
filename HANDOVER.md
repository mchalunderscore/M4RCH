# Application START and shutdown passed; table audit captured — 2026-10-07

Current GPU-contract boot 9a7d7e28-5156-4a4b-aeb5-c24bbcd50c5a; WFI Y.
Fresh metadata validated. Crashlog1, IOP/AP ON, START32/33, AP QUIESCED,
IOP SLEEP, stop readback and normal unload passed. No retained probe resources.
START transmission is verified; app readiness/work completion not established.
No init graph, work submissions or new DMA addresses were supplied.

Read-only snapshots captured ttbs/pagetables/l2/handoff and helpers unloaded.
Offline 16 KiB, shifts36/25/14 traversal matches TEXT and DATA physical addresses.
Candidate root/bundle share an absent top-level entry: real mapped backing is
needed before publication. ttbs/l2/handoff snapshots zero. This is a limited
snapshot audit, not allocation permission or complete collision/coherency proof.
Neither interface identifier was found as contiguous bytes in older sampled
TEXT/DATA; split instruction constants remain possible, so no ABI conclusion.

NEXT: a normal reboot is needed for the next fresh-cold firmware experiment,
NOT to clear pinned resources this time. Warm restart is unresolved; avoid
replaying START from sleeping status6e. Prepared asc-app-observe starts32/33,
observes up to250ms/32 messages without replies or init graph, then attempts
acknowledged shutdown and conditional unload. Recapture/revalidate boot firmware
DATA and matching kernel/module hashes. No kernel build or macOS handoff.
Continue explicit G16S init-graph planning; do not enable donor T8132 bootstrap.
Normal GPU startup stays gated. Owner "r" means rebooted and ready.

Evidence docs/evidence/2026-10-07-gravity-gpu-app-start.json,
2026-10-07-gravity-gpu-graph-samples.json and 2026-10-07-gravity-gpu-boot-table-audit.json.
Offline walker experiments/t6040-gpu/audit-boot-tables.py. Next source
experiments/t6040-gpu/asc-app-observe, built helper out/gpu-gravity-contract counterpart.
Earlier checkpoints follow. Same default1 GPU-contract kernel retained.

# Managed wake unresolved; application endpoint trial prepared — 2026-10-07

Current GPU-contract boot df0ffd12-a6a3-4973-a4fe-f6923f80cf71; WFI Y.
Cold HELLO/map/crashlog, IOP ON/AP ON, AP QUIESCED/IOP SLEEP passed again.
INIT220 with ASC START unchanged and continuous GFX power reference still
produced no messages in four seconds. Final control0/status48 failed stop.
asc_managed_wake is pinned; REBOOT REQUIRED. Never force removal or retry here.
This rules out START toggling or power release as the sole explanation, but
does not establish why wake fails. No further blind wake variations queued.

NEXT: normal reboot, same default1 kernel. Revalidate fresh ADT/build/module
hashes. Prepared asc-app-start starts crashlog1, validates/echoes reserved DATA
offer, establishes IOP/AP ON, then sends START to advertised application32/33.
No root/init graph, command submissions or new DMA buffer. Then request AP
QUIESCED/IOP SLEEP and attempt stop/conditional retirement. Capture all messages;
pin on failure. This advances the GPU path without requiring warm wake first.
Application readiness is not demonstrated by sending START alone: distinguish
message transmission, firmware responses and future initialization acceptance.
Full T6040 driver startup remains gated. Warm restart still requires investigation.

Receipt docs/evidence/2026-10-07-gravity-gpu-managed-wake.json; raw logs
out/gpu-gravity-contract/managed-wake-boot. Next source experiments/t6040-gpu/asc-app-start;
matching helper out/gpu-gravity-contract/asc-app-start. No kernel rebuild/macOS
handoff needed. Owner "r" means rebooted and ready. Earlier notes follow.

# Cold retirement reproduced; managed wake next — 2026-10-07

Current boot 666c136e-bee9-45f0-80a7-e30e6b4fe34a, GPU-contract kernel; WFI Y.
Fresh ADT revalidated DATA bounds. Cold endpoint1/crashlog boot, IOP ON, AP ON,
AP QUIESCED, IOP SLEEP and normal unload succeeded again. Explicit INIT220 after
manually stopping ASC and dropping/reacquiring power produced no messages.
Final control0/status48 did NOT satisfy stop readback. asc_crashlog_wake retains
resources; REBOOT REQUIRED; never force removal or retry in this boot.

NEXT: normal Linux reboot, same default1. Prepared asc-managed-wake keeps ASC
START and the same GFX power reference across three bounded protocol cycles:
cold HELLO/map/crashlog/ON/shutdown, then INIT220 warm wake without manually
stopping the controller. Only finally attempts core stop and conditional unload.
This follows the donor distinction: RTKit shutdown changes AP/IOP protocol states,
not the ASC start bit. Candidate explanation only, not native qualification.
Revalidate fresh boot ADT, build ID and module hash before loading. No application
endpoints, graph construction or new DMA buffers. Keep normal GPU startup gated.

Receipt docs/evidence/2026-10-07-gravity-gpu-explicit-wake.json; logs
out/gpu-gravity-contract/wake-boot. Next source experiments/t6040-gpu/asc-managed-wake,
matching helper built in out/gpu-gravity-contract/asc-managed-wake. No kernel rebuild
or macOS handoff required. Owner "r" means rebooted and ready. Earlier notes follow.

# Crashlog boot and shutdown passed; explicit wake next — 2026-10-07

Owner shorthand: a message consisting of "r" means rebooted and ready to continue.
Current GPU-contract boot 518f3863-eb8c-4593-9378-b7686c41706d; fresh ADT
captured with matching-kernel read-only helper, then helper unloaded; WFI Y.

Cold bounded HELLO12/map exchange + system endpoint1 start succeeded. Firmware
requested crashlog buffer 0x10001de4000+0x8000. Checked wholly within this boot's
reserved DATA range 0x10001d44000+0x138000, page aligned and disjoint from Linux
System RAM; echoed firmware's own offer. No new DMA allocation or RAM write.
IOP ON20, AP ON20, AP QUIESCED10 and IOP SLEEP1 ACKs all observed. Core stop
control0/status6e and empty RX FIFO allowed normal module unload. One successful
crashlog-only retirement, no application endpoints/initialization graph/rendering.

Repeat with ASC START alone from status6e produced no HELLO in four seconds.
Resources retained by asc_crashlog; REBOOT REQUIRED. Never force removal.
The low status bits alone do not distinguish fresh status6a from stopped/sleeping
status6e. Do not label status6e a fresh cold boot. Driver C apple_rtkit_wake uses
IOP INIT220; next prepared probe adds that explicit wake sequence, gated separately.
It accepts cold status6a, or warm6e only with wake_gate=1. Not yet run natively.

NEXT: normal Linux reboot, same default1 kernel. Recapture/revalidate firmware
DATA bounds and bind helper to new boot/build/module hashes. First qualify cold
boot/shutdown with asc-crashlog-wake; after successful unload try explicit warm
wake_gate=1. Retain on failure. No kernel build or macOS handoff required. Keep
normal T6040 startup gated. Successful shutdown does not yet prove repeatable
restart, full driver teardown or acceleration.

Receipt: docs/evidence/2026-10-07-gravity-gpu-crashlog-shutdown.json.
Sources experiments/t6040-gpu/asc-crashlog and asc-crashlog-wake. Logs/artifacts
out/gpu-gravity-contract counterparts. Earlier checkpoints follow; rollback
remains /boot/GPUC001/grub-before.cfg -> /boot/grub/grub.cfg, sync.

# Guarded GPU binding passed; shutdown trial needs reboot — 2026-10-07

Current boot 7.1.13-m4rch-gpu-contract, build ID
1c0b2b5b48a59316f75940aa4049a5f671eca95c. Owner reports peripherals normal;
WFI Y. T6040 normal-start guard refused before MMIO/firmware builders. Three
powered Rust identification cycles bound successfully, returned ID 0x0a031100,
counts 0011020a/00040404, clusters 400c0c02. Each released device, driver,
resource overlay and GFX power normally; suspend result 0. No firmware startup
in those three cycles. Captured masks remain metadata, not new native fuse reads.

Then a bounded buffer-free shutdown probe negotiated HELLO12 and both endpoint
maps. AP QUIESCED request received no response within two seconds; IOP SLEEP
was not attempted. Core stop readback control0/status6e passed. asc_shutdown is
intentionally pinned with power/mappings retained. REBOOT REQUIRED. Never force
module removal or attempt a second start in this boot. No endpoint starts, buffer
addresses, initialization graph or rendering commands were supplied.

NEXT: normal Linux reboot into the same default1 GPU-contract kernel. No new
kernel build or macOS handoff required. Qualify advertised endpoint1/crashlog
lifecycle and IOP ON acknowledgement before retrying AP shutdown. Donor RTKit
starts system endpoints explicitly to complete boot; our minimal exchange omitted
that step. This is a candidate explanation for absent AP ACK, not proven causality.
Keep normal startup gated and validate firmware-requested buffer bounds against
fresh reserved-memory metadata before acknowledging any buffer. Avoid new DMA
addresses until that contract is established. Verified teardown remains priority.

Receipts: docs/evidence/2026-10-07-gravity-gpu-binding.json and
2026-10-07-gravity-gpu-shutdown.json. Experimental source:
experiments/t6040-gpu/asc-shutdown; logs out/gpu-gravity-contract/native-boot
and asc-shutdown. Earlier staged checkpoint remains below for rollback details.

# Guarded Gravity GPU framework — staged reboot checkpoint, 2026-10-07

NEXT BOOT: 7.1.13-m4rch-gpu-contract, isolated linux-m4rch-gpu-contract package.
GRUB default 1 selects /GPUC001/vmlinuz and matching initramfs.img. Normal
maintained 7.1.13-m4rch-gravity remains entry 0. No GPU node added and no GPU
firmware/application startup allowed on T6040. Probe-only defaults to 1 and
normal startup is explicitly refused before donor board-specific builders.

Full LLVM/Rust Image/modules build and modpost passed. One upstream unused
Rust RTKit import warning. All 39 files in the maintained baseline patch are
byte-identical, including USB, WFI, framebuffer, NVMe and CPU changes. Native
package installation generated the separate NVMe initramfs. Its root UUID,
partition/bounds, release, package identity and NVMe dependencies were inspected.
Package hooks also regenerated the normal initramfs; normal kernel is unchanged.
No native trial boot or stability claim yet.

After the previous handshake reboot: retained probe resources cleared; WFI Y.
Read-only reserved TEXT/DATA samples captured and helpers unloaded normally.
Loaded TEXT contains RTKit-3255.160.4.release, matching recorded 25G83 candidate.
This is version-string evidence, not full-container byte identity or ABI proof.
Seven candidate byte-codec tests and six existing topology/voltage tests pass.
Candidate codec is independent of the live driver; unknown main fields preserved,
queue prefetch/completion separated, cluster voltage columns distinct. Reference
machine has 20 cores; retain our native 16-core masks 3db/3db.

NEXT: reboot Linux normally; check maintained peripherals and WFI/SME on this
Rust-enabled trial. Then load the guarded framework and qualify dynamic resource
metadata/identification before planning RTKit crashlog/application startup and
initialization graph. Do not jump to donor bootstrap or advertise acceleration.
Verified teardown is a priority: completed donor Bootstrap Drop calls shutdown;
raw Rust RtKit Drop only frees. Audit post-start constructor errors and test AP
QUIESCED / IOP SLEEP shutdown before relying on reload without reboot. Old bounded
ASC experiment intentionally retains resources after startup; never force unload.

Rollback: copy /boot/GPUC001/grub-before.cfg to /boot/grub/grub.cfg and sync;
normal maintained entry 0 remains present. No automatic reboot performed.
Source recipe: experiments/t6040-gpu/gravity-contract; candidate codecs g16s_abi.rs.
Receipts: docs/evidence/2026-10-07-gravity-gpu-contract-trial.json and
2026-10-07-gravity-gpu-loaded-firmware.json. Build/logs out/gpu-gravity-contract.
Earlier checkpoints below are historical.

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
