# T6040 GPU reclaim investigation

> Historical trial commands and diagnostic paths in this record may have been retired.
> See the [documentation index](README.md) for preserved source archives and
> the current setup; do not treat trial boot paths as current recovery instructions.

The running 7.3.0-m4rch kernel uses the G17 backend for the J614s T6040 GPU. Its
VM shrinker counts eligible objects under the reservation lock and will reclaim
private objects under memory pressure only when the relevant safety conditions
hold. The ordinary path requires a quiet GPU address space; objects advised
DONTNEED have a separate purge path. Kernel or exportable objects, kernel-mapped
objects, objects with other backing leases and contended or unsafe states are
not necessarily reclaimable. A zero count cannot by itself identify which of
these conditions caused it.

During the preceding Shinri load, host GPU user residency rose to roughly
8.6–9.2 GB with less than 1 GiB of host memory available and severe memory
pressure. After the VM exited, user residency fell to around 3.3 GB. The
ledger measures driver-held GPU allocations within shared system RAM; it is not
additional dedicated VRAM, and it does not say which allocations are idle or
reclaimable. The driver counters and guest process PSS must not be added as
independent memory totals. No per-shrinker measurements were captured in that
run, so these figures do not establish why pressure persisted.

The current kernel has CONFIG_SHRINKER_DEBUG disabled. A separate diagnostic
kernel is being built from the same source and configuration with that option
on and a distinct kernel release. The diagnostic reports **instantaneous
eligibility**, not actual reclaim, via debugfs. `tools/gpu-reclaim-monitor.py`
collects these counts alongside GPU residency, per-client fdinfo, host memory,
swap and pressure. Shrinker IDs do not themselves identify the client. Counts
are best-effort snapshots subject to nonblocking locks and activity and do not
include all allocated memory. Repeat samples across load and idle are needed.

Upstream review: Aurora's [T6040 G17 bring-up #408](https://github.com/aurora-silicon/linux/pull/408)
and [G17 submission changes #423](https://github.com/aurora-silicon/linux/pull/423)
are part of the basis already used locally. The open [J616s 20-core enablement
#463](https://github.com/aurora-silicon/linux/pull/463) is for a different
board/core configuration and is not an established reclaim fix for this
J614s. Asahi documents [its gaming stack](https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/)
on M1/M2; that does not establish how this newer T6040 backend behaves.

The diagnostic build also adds three monotonic, aggregate counters to
`gpu_memory`: shrinker scan calls, pages requested, and pages for which the
driver reported releasing backing. Releasing GPU backing does not necessarily
mean Linux immediately evicted that memory from RAM. The instrumentation only
updates atomic counters after a normal scan; it does not alter candidate
selection or trigger a scan. Monitor reads of shrinker `count` do not change
these scan counters. Counts and release totals can race with snapshots.

The owner's suggestion to adapt newer T6040 work is sound. The current local
`g17/fw/initdata/v25g83.rs` contains static leakage coefficients, whereas PR
#463 introduces a reader for per-chip power/calibration values. Its companion
[m1n1 #52](https://github.com/aurora-silicon/m1n1/pull/52) supplies that handoff.
Both are currently scoped/tested to J616s 20-core hardware. Adapting the reader
and bootloader handoff for J614s 16-core is a plausible separate GPU correctness
and performance improvement, but the PR description and listed commits do not
claim a reclaim fix. The full diff could not be retrieved through the web
interface; the assessment is based on the PR and commit descriptions, not a
complete code-diff review. The firmware-image admission from #453 is already
present in the local `hw/t6040.rs`. Establish the memory baseline before
changing calibration so results remain attributable.

The diagnostic kernel is installed as `7.3.0-m4rch-gpureclaim` and the
`m4rch-gpureclaim` GRUB entry is currently the default. Its Image, separate
module tree and initramfs were verified after installation; both GRUB files
passed `grub-script-check` and the initramfs includes Apple NVMe and SART.
The ordinary kernel and initramfs hashes were unchanged. Original GRUB files
are `/boot/grub/grub-before-gpureclaim.cfg` and
`/boot/grub/custom-before-gpureclaim.cfg`; restore them from a working system
or external recovery media if necessary. The config, diagnostic patch, build
logs and staged artifacts are under `out/gpu-reclaim-diag`. The disposable
2.8 GiB source copy was removed after installation. The test kernel has not
yet been booted, and no Shinri reclaim measurement has yet been captured.

## Live Shinri load, 27 October

The diagnostic kernel booted successfully. A read-only monitor sampled the
per-shrinker count, GPU ledger, scan outcome counters and host pressure into
`out/gpu-reclaim-diag/shinri-monitor.jsonl`. At the desktop baseline, GPU user
residency was about 1.3 GiB and sampled eligibility about 25 MiB. With Steam
open, one sample showed 2.1 GiB resident and 226 MiB eligible, without memory
pressure or scans. During the reported server-cache stall, one later sample
showed 6.26 GiB user GPU resident, 3.2 MiB eligible, 341 shrinker scans and
1.81 GiB cumulative backing releases; available memory was 0.52 GiB and
logical swap use 8.83 GiB, with 10-second full memory PSI 4.91%. These are
sample values and move over time. Repeated releases may concern the same
objects; cumulative release is not a unique allocation total and releasing
backing does not prove the kernel immediately freed the physical pages.

Earlier in the stall, the largest two DRM clients were held by the libkrun VM
and reported approximately 2.32 and 0.45 GiB resident; guest GPU clients
cannot be assigned to an individual guest process from those host holders
alone. The findings establish that scanning and releases occur, and that the
instantaneously eligible quantity can be tiny despite substantial residency.
They do not distinguish a busy VM, exportable buffers, other leases, contention
or another candidate exclusion, and do not prove the loading stall's sole cause.

## Root cause and transport prototype

The pinned Mesa `agx_virtio_bo_alloc` sets `USE_MAPPABLE | USE_SHAREABLE`
for every new virtio buffer and does not set `DRM_ASAHI_GEM_VM_PRIVATE`.
The pinned virglrenderer forwards those flags to the host GEM create and
exports a DMA-BUF for the shareable blob. The host `idle_reclaim_candidate`
excludes exportable objects, and shmem's idle-release helper independently
rejects an object with `obj->dma_buf`. In a live snapshot the VM process held
5,148 distinct DRM DMA-BUF inodes with a total reported size of 5.58 GiB;
these are nominal buffer sizes, overlap the GPU ledger, and the exporter name
alone does not distinguish individual DRM devices. The source establishes why
ordinary buffers created through this virtio allocation path are excluded.

A bounded experiment minimizing the game showed sampled eligible memory between
0.4 and 111.4 MiB while user GPU residency stayed around 7.0–7.2 GiB. This
does not isolate every exclusion or prove what the game itself was doing, but
it did not reveal a multi-GiB idle-VM reclaim opportunity.

An isolated prototype separates Mesa BOs that are explicitly nonshareable from
shared BOs, keeps the latter on DMA-BUF, and uses the virglrenderer opaque
resource direct-map callback for private BOs. Wire version 4 gates the new
path. Mesa and virglrenderer compiled, but a standalone muvm Vulkan probe
failed at guest mmap: stock libkrun only handles exportable file-backed blobs
in its installed configuration. It never called the direct-map callback.
The current prototype also modifies an isolated libkrun build to call
`virgl_renderer_resource_map_fixed` for opaque renderer-owned blobs. This is
not installed, and the safety of guest mappings under GPU backing eviction,
KVM invalidation, resource teardown and buffer sharing has not been proven.
Do not use the private path with unmodified libkrun or assume a successful
compile demonstrates safe reclaim.

The isolated three-component candidate passed Vulkan device enumeration and
120-frame `vkcube` presentation. A separate guest probe created and kept a
64 MiB coherent buffer mapped, signalled readiness, and waited. Its dedicated
host shrinker counted 4,226 pages, including the test BO. A debugfs scan
requested 4,096 host pages; the driver reported releasing exactly 4,096 pages
(64 MiB), and the count fell to 130 pages. The guest then verified its mapped
CPU contents, submitted a GPU fill and verified the result. The process exited
successfully and no associated GPU/KVM fault appeared in the checked kernel
log. This is a limited correctness test, not proof of sustained safety or that
Linux physically evicted the data to swap.

At the owner's request a Steam VM was started with the three candidate
libraries loaded from the workspace, not installed system-wide. The monitor
for the candidate is `out/gpu-reclaim-diag/candidate-monitor.jsonl`. The
candidate Steam Vulkan loader has opened the staged library. Steam reported
shader processing before the Shinri comparison; the game has not yet been
qualified on the candidate at this point.

Space cleanup while the candidate was active: obsolete paru download archives
were removed while retaining the latest built packages. `make clean` removed
rebuildable intermediates from the old HDR candidate; its Image, vmlinux,
config and symbol files were copied to `out/hdr-candidate/preserved-build`.
The cleaned source tree was archived as
`out/hdr-candidate/source-preserved.tar.zst`, validated with `zstd -t`, a full
archive listing and SHA-256, then its expanded copy was removed. Restore it
with `mkdir -p out/hdr-candidate/source && tar --zstd -xf
out/hdr-candidate/source-preserved.tar.zst -C out/hdr-candidate/source`.
Installed boot kernels and their recovery GRUB files were not removed.

## Candidate Shinri run

The candidate Steam VM reached the Shinri lobby; the owner reported it felt
better overall but opening the player list and character menu the first time
still took longer than desired. At one loading-stage sample 2.62 GiB of GPU
backing was counted eligible, and a later sample reached 4.98 GiB. Those are
instantaneous counts; during other samples the gate returned near zero. By one
lobby snapshot the VM held 57 distinct `drm` DMA-BUF inodes totalling 0.11 GiB
nominal, against 5,148 and 5.58 GiB in the earlier live sample. The workloads
and timing were not identical, and the counts do not prove all corresponding
buffers were resident. The candidate was loaded from isolated workspace paths;
installed graphics libraries were not replaced.

The candidate did not eliminate memory pressure: after loading, sampled host
available memory was roughly 0.4–0.7 GiB and logical swap use around 12 GiB,
versus roughly 10–11 GiB in the earlier run, which started with less swap
already used. High cumulative release totals are not unique bytes; re-eviction
and restoration may contribute to churn, but the current counters cannot
attribute repeated bytes. Host-wide major-fault and swap-in counters continue
to rise during the lobby; they are not process-specific and do not establish
the reason for a particular menu's delay. No matching GPU fault was observed
in the checked log. Further safety and gameplay testing is required before
promoting this candidate to the default Steam or system graphics stack.

The owner reports the candidate session looks and feels substantially better
than macOS, while memory use remains too high. Reopening the player list was
quicker; character selection remained somewhat slow, consistent with additional
first-use work but not sufficient to attribute the delay to a specific cause.
The user prefers general stack correctness fixes, not game-specific changes.

A one-time guest snapshot at 19:02 reported GMod PSS about 2.83 GiB and five
Chromium renderer processes together about 3.61 GiB PSS; a GPU Chromium process
was about 0.58 GiB and utility processes about 0.59 GiB combined. Guest PSS,
GPU accounting, and the host VM footprint overlap and must not be summed.
Host swap was about 12–13 GiB logically used, mostly zram; e.g. zram reported
about 4.4 GiB compressed storage and the disk swapfile 0 B. The frequent
host-wide swap-ins and major faults are consistent with memory pressure but do
not identify the cause of a particular menu delay.

A separate general path to investigate is Aurora's mixed user-page-size work:
[Linux #170](https://github.com/aurora-silicon/linux/pull/170) was superseded
by the 7.3 integration, and [aurora-steam-native #8](https://github.com/aurora-silicon/aurora-steam-native/pull/8)
reports ARM64 Steam/Proton testing on Neo. The current kernel source includes
pieces, but its configuration has 52-bit VA/PA and LPA2 enabled; the
`ARM64_USER4K_EXPERIMENTAL` Kconfig requires 48-bit VA and PA and disables
LPA2. Whether a 48-bit kernel supports this T6040 board and its devices must
be investigated and qualified on a separate recoverable kernel. Do not infer
hardware compatibility or a memory saving from the upstream report.

After the candidate comparison, high-frequency monitoring was stopped to
avoid overhead. Build output directories were removed while retaining patched
source, experiment patches, logs and the staged libraries used by the live VM.
`tools/steam-gpu-reclaim-test.sh` provides an explicit experimental relaunch;
it refuses to start if another muvm VM is already running. The default Steam
launcher and installed graphics packages remain unchanged. The staged stack is
experimental and its continued use is not a long-term qualification.
## Native 4 KiB userspace Shinri test

The separately installed `7.3.0-m4rch-user4k` kernel booted on the T6040;
native 16 KiB and opt-in 4 KiB page/protection/fork smoke tests passed.
The Aurora native ARM64 Steam launcher ran directly on the host, without
muvm. The Steam idle process-tree sample was 1,165,037 KiB PSS; the earlier
VM guest-process sample was 1,294,760 KiB PSS, but these scopes and startup
states differ and do not measure the VM's complete host overhead.

Official ARM64 Proton 11 and Experimental initially exited immediately. A
separate Proton 11 smoke prefix showed Wine startup failing at its restored
stack pointer followed by FEX failing to read its CPU registry; this matches
the SME-without-SVE signal-frame issue documented in Aurora's upstream
`wine-arm64-sve-payload-guard.patch`. A candidate built from Valve wine
`proton_11.0` commit `e60892cc2398b0a83c332a2078c7b85e47bdb42b` with that
patch passed a 4 KiB x86-64 Windows cmd smoke test where the original exited
29. Valve's `proton-11.0-2e` tag was subsequently verified to pin that exact
Wine commit. The locally built component remains experimental; it is not a
full Valve build. It is installed separately as `Proton 11.0-2e ARM64 (SME
fix)`. Its source and build details are in `packages/proton-arm64-sme/` and
logs are under `out/user4k-test/`. The native Steam launcher is installed as
the default through steam-m4rch 1.0.0.81-11; VM Steam fallback launchers were
removed at the owner's request. A 4 KiB-capable kernel with user4k=on is
required.

The owner reported that Shinri's server cache and entry to the lobby were
much faster. A few native lobby samples showed 1.29–1.58 GiB available,
7.63–7.65 GiB logical swap used and 6.53–6.58 GiB GPU user residency; the
earlier VM candidate lobby samples showed 0.40–0.66 GiB available, 12.75–13.19
GiB logical swap used and 7.32–7.41 GiB GPU user residency. These are
observational samples, not a controlled benchmark, and workload/cache/uptime
differences remain. The native session still incurred measurable memory
pressure. At one nearby observation all swap was zram and disk swap use was
zero. Logical swap and compressed physical RAM are distinct quantities.
The guest-to-host GPU reclaim transport candidate was not used by this direct
host test. Monitor samples are in `out/user4k-test/native-monitor.jsonl`.

After the owner closed other applications, leaving Steam, Garry's Mod and
Codex, the lobby showed about 2.4–2.7 GiB available and 5.7 GiB logical
swap, entirely on zram; zram consumed about 2.1 GiB physical RAM and disk swap
was unused. Recent 10-second full-memory PSI approached zero. The reduced
desktop monitor is `out/user4k-test/native-reduced-desktop-monitor.jsonl`.
The owner reported the player list and character-selection menu were both
much quicker than in the VM. The character-selection click repeated about
three times, versus once on macOS. The before and after observations were
not synchronized, so the change cannot be attributed solely to closing apps.

Upstream sources: https://github.com/aurora-silicon/aurora-steam-native ;
https://github.com/aurora-silicon/aurora-steam-native/blob/main/proton/wine-arm64-sve-payload-guard.patch ;
https://github.com/ValveSoftware/wine/tree/proton_11.0 .

The working user4k kernel was promoted without rebuilding to main package
`linux-m4rch 7.3.0-6`. Its release remains `7.3.0-m4rch-user4k`; the main boot
image matches the tested image by SHA-256. GRUB defaults to the standard
`Arch Linux` entry with `user4k=on`; `GRUB_TOP_LEVEL` selects the main packaged
image after regeneration. Previous
kernel images, initramfs files, modules and GRUB configuration were retained;
see `out/user4k-test/README.md` for recovery. A subsequent reboot confirmed the
standard main boot image, 4 KiB process checks and graphics devices. The old GPU experiment's source and build tree
is preserved in `out/gpu-reclaim-diag/build-src-preserved.tar.zst`.

## Owner verification

The owner reports that Steam and Shinri are now about as good as on macOS.
The remaining performance investigation is therefore no longer an active
project priority. The earlier measurements and experimental Proton details
above remain as historical evidence.
