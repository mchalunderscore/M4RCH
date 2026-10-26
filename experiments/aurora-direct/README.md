# Direct Aurora J614s candidate

Separate AURD001 test for Mac16,8/J614s/T6040: 12 CPU cores, 16 GPU cores,
24 GB RAM. AURT002 and the original native-validated loader are preserved.
Internal speakers stay excluded; external audio is allowed.

profile.json pins kernel, Mesa, ALSA UCM and loader inputs. The kernel base is
exact Aurora tree d6b171e95516b1683968d220800acee244c01869. No unmerged kernel
or Mesa PR patches are applied. Linux's EFI stub stays stock. The local kernel
change is the generated J614s board template/DTB Makefile entry.

The boot bridge retains its working NVMe control tree while generating a
separate Linux tree from live FDT/ADT data: CPU fuse state/release addresses,
RAM, both forms of memory reservation, radio calibration, USB tunables, PMP,
GPU regions/OPPs and AOP/ISP firmware regions. GPU power-domain and PMP report
dependencies are enabled together only after admission. The fallback removes
the GPU dependency set completely.

AOP reservations follow aurora-silicon/m1n1 PR 41, merged into aurora-wip as
6ebbc2db19edfa53e643c6f3a229e44241614ae2: DRAM segments become apple,asc-mem
nodes with memory-region and iommu-addresses. The proven Gravity-based m1n1
component is rebuilt with bounded T8110-format AOP/ISP0 DAPF setup. Its live
chosen receipt gates the corresponding Linux devices. The fallback uses the
unchanged original m1n1 component and admits neither device. This adaptation
remains local; the kernel and Mesa base directly on Aurora. Never supply the
donor J616s DTB and its physical memory addresses to Linux.

rebuild.sh records the kernel configuration/build commands for native ARM64
Debian trixie. Sources must live on the case-sensitive Linux filesystem.
Tool versions, source archives, logs and receipts are in out/aurora-direct/.
The source was reconstructed from the pinned base archive and Aurora's
aggregate diff, then checked against GitHub's Git tree. Fresh archive indexing
requires git add -f: several tracked dotfiles are ignored upstream.

Build m1n1 from the pinned Gravity loader profile, its existing checked patch
and prepare_m1n1.py. Artwork is e613a87e526f8fec439c4129e69dd2821b38d258.
Build U-Boot from the same profile plus prepare_loader.py; pack the primary
and original-m1n1 fallback. Mesa uses Gallium asahi/zink/softpipe, Vulkan
asahi, EGL/GBM, X11/Wayland and LLVM 19; prefix /opt/m4rch-aurora-direct1.

The first native AURD001 attempt stopped at ANS endpoint discovery (-62).
The inherited Gravity U-Boot stopped RTKit, but Aurora's M4 Pro driver
requires its live session. prepare_loader.py now also applies
prepare_live_nvme.py, adapting Aurora U-Boot 7680260272f3's exit protocol:
retire I/O queues, retain enabled/ready admin queues, RTKit and SART; no ANS
power transition or PMGR reset. Failed retirement or unhealthy registers
halt the loader. The FDT reserves U-Boot's entire allocation arena
inside verified live RAM, retaining firmware DMA buffers and old queues
through Linux's takeover. Kernel driver sources remain unchanged.

Revision 2's size guard incorrectly compared the actual arena with
SYS_MALLOC_LEN (64 MiB), omitting ENV_SIZE (124 KiB). The native boot stopped
at the handoff with -15 before starting Linux. Revision 3 uses the same
TOTAL_MALLOC_LEN expression as U-Boot's mem_malloc_init; fixtures cover the
real 0x401f000 span and reject the earlier truncated expected size. Bounds
checking and the live-session contract remain enforced. Native diagnostics
now identify failed checks and show CPU handoff and allocator ranges.

Revision 3 rejected CPU 0x10100 with release=0. The CPU guard had wrongly
assumed that MPIDR zero was always the boot CPU. m1n1's dt_set_cpus explicitly
skips assigning a release address to the CPU currently executing. Revision 4
passes read_mpidr() from the U-Boot wrapper into the data-only adapter, exempts
only that actual boot CPU from the nonzero-address rule, requires it to exist
in the admitted topology, and sets the FDT boot CPU header accordingly.
Fixtures now cover both a P-core boot CPU (0x10100) and an E-core boot CPU (0),
including rejection of a zero E-core address when it is a secondary and an
unknown boot MPIDR. This does not yet establish Linux SMP bring-up.

Revision 4 booted Arch from NVMe. Saved native dmesg is under native-r4;
keyboard/trackpad and Bluetooth initialized. Wi-Fi detected BCM4388 but its
firmware failed to start. CPU OPP setup attempted nonexistent fused CPUs 8/13.
The runtime GPU check used find on /proc/device-tree, a symlink it never
followed, so asahi was not loaded. Revision 5 removes fused CPU nodes (as
m1n1 does) after pruning cooling, cpu-map and interrupt-affinity references;
copies apple,antenna-sku for Broadcom's per-board firmware filename selection;
and explicitly loads asahi with DT admission still controlling probe.
log_buf_len=4M retains early SMP messages. Revision 5 booted natively: all
12 CPUs are online with frequency scaling, and Wi-Fi firmware now initializes.
The owner reports working webcam and USB3 on all ports. Exact payload and return
bundle are preserved under out/aurora-direct/native-r5. See NATIVE-RESULTS.md
for the GPU layout rejection and remaining qualification gaps.

Revision 6 retains the same kernel and loader binaries. It explicitly loads
snd_soc_apple_mca for the headphone CPU DAI and improves symlink-aware camera/IIO,
USB sysfs, driver-binding and deferred-probe collection. Built-in speaker
amplifiers remain excluded. Revision 6 requires a native boot test.

The revised initramfs loads input before waiting for NVMe and displays
online/present CPUs. A tactile trackpad click alone does not establish Linux
input ownership, and one boot logo does not establish an online CPU count.
CPU handoff rejects zero secondary release addresses and unexpected boot
methods. Original failed binaries and evidence are under
out/aurora-direct/failed-native-20261024. These changes need native validation.

Macaudio selects amp drivers even for a headphone-only card. Packaging omits
TAS2764/TAS2770 and regenerates depmod metadata, retaining macaudio for the
separate jack. Kernel driver sources remain unchanged and internal amplifiers
cannot bind in this package.

Validation: stock EFI source comparison; ASan/UBSan handoff fixtures including
malformed/missing firmware/DMA data; FDT header reservations; speaker exclusion;
module/initramfs readback; loader framing; GRUB syntax; and matched-pair selector
round trips. Mesa's Asahi suite has 55 passes and one existing failure,
NativeForms.ImageStoreUsesDataTypeAcrossChipsAndFormats. Synthetic 25G83
fixtures establish data handling, not hardware operation.

BOOT.md documents native checks and rollback. Native DCP, brightness/external
display takeover and hardware qualification remain open.
