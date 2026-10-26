# Gravity M4 Pro/Max hypervisor review — 2026-10-17

The open [Gravity bootloader PR #9](https://github.com/GravityLinux/bootloader/pull/9)
is a promising instrument for observing working macOS GPU behavior on our
T6040/G16S machine. It does not implement our Linux platform contract, power
calibration, command producers or completion/readback path.

## Reviewed source and dependency

Reviewed PR #9 head `5c79bcbc6a68aa3577fcecc73e00bed247c56e30` from
`janmarek98/bootloader:m4-pro-max-support`, including its complete source tree.
It targets `PR_sptm_hv`, rather than `main`, and depends on the larger
[SPTM hypervisor PR #8](https://github.com/GravityLinux/bootloader/pull/8)
(head `8da6b14ba4672b93ad93917770a7516ec5889238` at review time).
Both PRs are open. The PR #8 description reports firmware 26.6.2 and testing on
Neo; PR #9 describes T6041 XNU bring-up. Neither establishes a successful
hypervisor boot or accelerated guest rendering on this J614s/T6040 machine.

PR #9 increases DART capacity to 64, sizes boot memory/page-table bookkeeping
from managed RAM, backs all supported TXM bootstrap channel slots and initializes
VMPIDR_EL2 on guest entry. It separates the NVMMU's 64 hardware tags from queue
depth, preserves certain unused firmware-locked DART streams, and fixes host
mapping invalidation with ALLE2IS. Frequent PPM reads and CLPC HVCs gain local
handling to reduce exits and global-lock contention. These are guest/hypervisor
changes; the NVMMU and cache fixes should not be transplanted into Linux or the
normal stage-2 path without checking their distinct ownership and context.

## How it could help the GPU work

A bootable macOS guest would provide a reference for the private native-derived
GPU work restored from ARCHROOT: compare GPU power sequencing and MMIO accesses,
UAT mapping publication/invalidation, mailbox ordering, queue/descriptor
publication and completion events against a small known draw. Observing these
transitions could distinguish a wrong hardware/firmware assumption from a
Linux integration mistake. Timing under traps can change behavior; traces alone
do not prove the uninstrumented path works.

The source already has generic MMIO hooks, `proxyclient/hv/trace_agx.py`, and an
AGX tracer with UAT table/page tracing. However, `constructutils.Ver.MATRIX`
only lists firmware through V13_5 and GPU generations G13/G14/G14X. The sample
AGX script also contains hardcoded register ranges from other platforms.
Therefore the bundled decoded tracer is not ready for G16S/26.6.2. Do not spoof
an older version or run the sample's broad register tracing unchanged. Start
with narrowly scoped raw tracing using the actual guest ADT; add decoded
structures only after qualifying the exact G16S firmware ABI.

## Recommended isolated experiment

1. Build the pinned PR #9 tree independently, with its inherited PR #8 code.
   Audit local J614s boot/debug transport requirements and retain the working
   enrolled stage 1 and normal stage-2 bundle. Qualify the installed firmware,
   guest payload and RAM topology against the reviewed sources.
2. Establish a host debug connection and a reproducible guest boot before
   enabling GPU tracing. The launcher adds guest boot arguments and explicitly
   clears the PMU panic counter; review that behavior rather than treating it
   as a read-only collector.
3. Capture narrowly scoped raw GPU initialization and one small macOS draw,
   with timestamps, guest/firmware identities and mapping lifetimes. Derive
   addresses from that boot's ADT. Keep proprietary payloads and resulting
   private research local, consistent with existing project provenance.
4. Compare the capture to the retained Linux GPU path and identify one concrete
   mismatch before changing it. The restored latest trial stopped at OF overlay
   PRE_APPLY, with no GPU firmware start or submissions; that metadata failure
   remains a separate local issue. The unexplained host resets have no proven
   connection to either the framebuffer mapping or the hypervisor changes.

No hypervisor code was merged into the normal loader and no guest or hardware
trial was run in this review. Next useful milestone: qualified J614s guest boot
with a working host debug transport, followed by raw GPU initialization traces.
