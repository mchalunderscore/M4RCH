# ANS memory handoff review

> Historical cache paths below refer to retired trial artifacts; the cache now retains only inputs needed by two current test helpers. For the current boot recovery path, see [recovery](recovery.md).

Aurora Aura's [PR #8](https://github.com/aurora-silicon/aura/pull/8)
reserves the retained stage-two heap and ANS SART ranges for selected chips.
Its heap reservation is created while Aura prepares the tree; the local J614s
path reserves the later high-water mark after DAPF initialization. The two
points are not necessarily equivalent: later allocations must be accounted for
before removing the local reservation. Aurora's existing chip predicates do
not include T6040 in those two ANS-related paths.

The separate U-Boot reservation covers its whole malloc arena. It also covers
memory allocated by U-Boot itself, so Aura's earlier heap reservation alone
cannot establish that it is redundant. In the Aurora U-Boot source used by
our package, the generic NVMe driver allocates submission and completion
queues in the heap, and the Apple driver allocates NVMMU TCBs there too. For
post-M4 handoff it retires I/O queues and leaves the controller enabled for
Linux to adopt; the admin queue and controller state still need analysis. The
wake path separately allocates RTKit shared buffers using LMB and publishes
them as `no-map` nodes. This is distinct from the older cold-boot path, which
uses heap-backed RTKit buffers.

Relevant source: [Aura tree preparation](https://github.com/aurora-silicon/aura/blob/a9cad94/src/kboot.c),
[Aurora U-Boot Apple NVMe](https://github.com/aurora-silicon/u-boot/blob/d30213eadcaa886f4206d7661b61bc6cf7837828/drivers/nvme/nvme_apple.c),
and [generic NVMe queues](https://github.com/aurora-silicon/u-boot/blob/d30213eadcaa886f4206d7661b61bc6cf7837828/drivers/nvme/nvme.c).
The running trial's tree has no `ans-rtkit@` reserved-memory nodes; that
observation alone does not identify which ANS path ran or prove that its
buffers are safe.

The Linux-visible `/sys/firmware/fdt` has an empty memory reservation map on
the 2 November trial boot. This is expected for this EFI boot path: the
[kernel EFI stub](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/drivers/firmware/efi/libstub/fdt.c)
deletes the FDT's reservation entries and relies on the EFI memory map instead.
Before installing the FDT, the pinned U-Boot source's
[`efi_carve_out_dt_rsv()`](https://github.com/aurora-silicon/u-boot/blob/d30213eadcaa886f4206d7661b61bc6cf7837828/lib/efi_loader/efi_dt_fixup.c)
attempts to add each reservation to that map as reserved memory. Thus an empty
Linux-visible FDT map is not evidence that the loader omitted the reservations;
nor does it establish that every EFI reservation succeeded. U-Boot logs a
failure to add an entry but continues, so the actual EFI map or boot log must
be inspected to establish coverage.

The running Linux tree describes an enabled `apple,t6041-sart` and an enabled
`apple,t6041-nvme-ans2` whose `apple,sart` phandle points to it. A read-only
inspection of this Mac's firmware ADT on 2 November found exactly one
`/arm-io/sart-ans`, with `compatible = "sart,coastguard"` and SART version 3,
which Aura's `sart_init()` supports. This does not establish the live SART
entries or prove that later U-Boot allocations lie in the ranges Aura observes.

The small [J614s ANS SART experiment](../experiments/j614s-upstream/aura-j614s-ans-sart-experiment.patch)
extends the existing Aura SART reservation branch to the J614s root compatible.
The changed `kboot.o` compiled against Aura's 2 November source; the candidate
has not been booted and does not replace either the late Aura heap reservation or
the U-Boot allocator reservation. A complete candidate was built from the
previously booted corrected SEP trial's Aura source, using its release,
chainloading and ESP stage-two configuration and the same compiler version.
The candidate preserves that trial's board DTB and U-Boot byte-for-byte. Its
SHA-256 is `c6ebe7c70105f51589ad02b74dc0730883d8cfafad06609e2b6cc50248a09b40`;
the component checksums are in the machine-local receipt at
`cache/j614s-ans-live-trial/receipt.json`.
The trial was selected on 2 November after verifying the package-managed
default and the EFI recovery copy. The helper restores the default with
`cache/j614s-ans-live-trial/trial-stage2.sh restore`. If a future trial does
not boot, copy `m1n1/boot.bin.m4rch-before-sd-gpio` over `m1n1/boot.bin`
from macOS or recoveryOS, keeping the recovery copy.

On boot `f616c770-5f9c-4054-8927-4f8f293099fc`, Linux started from NVMe;
Aura logged three ANS buffer reservations (32, 16 and 16 KiB) and no SART
initialization or reservation errors. All three ranges had zero overlap with
Linux's top-level System RAM resources. The boot kernel checksum matched the
previous boot and the kernel log reported no NVMe or block I/O errors. The
verified package-managed default was restored for the next boot. This was a
combined locally patched boot stack: the observation does not isolate which
pre-existing reservation may already cover those ranges, and the EFI memory
map was not inspected directly.

The narrowly scoped change is submitted as [Aura PR #51](https://github.com/aurora-silicon/aura/pull/51),
ready for review. An upstream-main-based build also succeeded with the release,
chainloading and ESP stage-two configuration; that build was not separately
booted. The PR does not replace the separate late Aura or U-Boot heap work.

## Reduced-reservation hardware trial

At the owner's request, a trial selected on 2 November removes both the late
J614s Aura high-water reservation and the U-Boot malloc-arena reservation.
It retains the J614s SART reservations from PR #51 and the other handoffs
from the preceding successful trial. The board DTB is unchanged. The rebuilt
U-Boot publishes its allocator range in `/chosen/m4rch,trial-uboot-arena`
for this experiment; that property does not reserve memory. The temporary
candidate and its cached receipt have since been removed.

That trial has ended. See [current recovery](recovery.md) for the present boot
stack and recovery path. A working boot alone cannot
prove outstanding DMA cannot corrupt data later; a loader backup cannot undo
filesystem corruption. Inspect the SART log, allocator range, Linux memory
resources and storage errors on the trial boot before drawing conclusions.

The trial booted Linux on `b64aad35-e949-4463-b844-a8deb1e7df44`; the NVMe
root filesystem mounted and the kernel log showed no NVMe or block I/O
errors. The kernel image checksum matched the preceding boot. The temporary
marker described a 65,660 KiB U-Boot allocator, of which 65,596 KiB
overlapped Linux's top-level System RAM resources. This confirms the range is
mostly available to Linux, but does not establish whether ANS can still DMA
to it. The package-managed default was restored for the next boot. The
initial attempt to read the Aura log used a fixed MTD number, which referred
to NVRAM on this boot; its zero ANS count is invalid and no contents were
saved. After identifying the Aura log by its MTD name, the check found three
ANS reservations, no SART or reservation errors, and no overlap between the
three ranges and Linux's top-level System RAM resources. These observations
do not directly inspect the EFI map or establish that ANS has stopped using
other U-Boot allocations.

The trial's `drivers/nvme/nvme_apple.c` and `drivers/nvme/nvme.c` Git blob
hashes matched current Aurora `aurora-wip` on 2 November (`d5a0db035ef49338e91bf0a683cc8b7038d645df`
and `a96a348e5caad255dbf76790b78084f1921ea68e`, respectively). This is
the same T6040 U-Boot storage handoff used for J616s; the complete trial
still includes other J614s changes. Aura main does not apply its retained
heap or SART-allowed-range paths to T6040. PR #51 adds the latter for J614s,
so that SART reservation is an intentional difference from current J616s
Aura behavior. The PR description records the reduced-reservation boot and
scrub rather than implying the downstream reservations were still present.

On the same reduced-reservation boot, a read-only Btrfs scrub completed in
33 seconds, checking 87.40 GiB and reporting no errors. The kernel log showed
no Btrfs checksum, NVMe timeout or block I/O errors after the scan. Btrfs
reported that block groups with swapfile extents are excluded; files without
checksums are not validated as ordinary checksummed data. This is useful
evidence about data read during the trial, not a test of all filesystem data
or proof that old bootloader DMA cannot occur. The owner also clarified on
2 November that they used the writable root filesystem for normal work for a
considerable period during this trial. That is additional real-world
read/write evidence; it does not cover every failure path.

For a stronger next test, instrument the actual U-Boot-to-Linux transition:
record the admin and I/O queue and TCB addresses and live SART ranges at
handoff, then capture controller state and pointer replacement in the Linux
adoption path before and after the controller is disabled. Compare those
addresses with memory Linux can allocate, including any firmware buffers
retained after adoption. Check that the observation covers both the normal
retirement path and errors; neither a successful scrub nor a post-adoption
register snapshot establishes safety during the earlier interval. SART alone
does not filter every DMA transaction from a device. Any instrumentation is
for a trial, not part of the upstream patch.

## Remaining wrapper ownership

The current package must keep its existing wrapper until the replacement
producers and the device tree are selected together. The following upstream
work provides a path to remove pieces, not proof that the installed package
already contains equivalent behavior:

| Local U-Boot handoff | Upstream work | Remaining constraint |
| --- | --- | --- |
| AOP firmware and ownership | [Aura #47](https://github.com/aurora-silicon/aura/pull/47) | Adopt the matching Aura and board-tree changes together and check the resulting live tree. |
| ISP firmware and ownership | [Aura #48](https://github.com/aurora-silicon/aura/pull/48) | Stacked on #47; preserve camera behavior until both producers are present. |
| Three USB controller/PHY tunings | [Aura #49](https://github.com/aurora-silicon/aura/pull/49) | USB 2 was tested on all three ports; USB 3 data remains untested. |
| SEP/display reservations | [Aura #50](https://github.com/aurora-silicon/aura/pull/50) | Use a matching tree and Aura build; the newer upstream-based variant has not had its own hardware boot. |
| SD board-tree rewrite | [Linux #795](https://github.com/aurora-silicon/linux/pull/795) | The updated board tree supplies the needed topology; the installed older tree still depends on the local rewrite. |
| HDMI PHY handoff | No equivalent established yet | An HDMI display test remains outstanding. |
| U-Boot allocator reservation | No equivalent established yet | Resolve allocations through EFI and Linux adoption, including late GRUB reads. |

The wrapper starts from Aura's live tree, applies these fixups, then reserves
the U-Boot allocator in the outgoing EFI tree. Removing the wrapper as a whole
before all of those responsibilities have replacements would discard behavior.

Upstream comparison: [U-Boot #16](https://github.com/aurora-silicon/u-boot/pull/16)
describes the T6040 wake and adoption paths in the `aurora-wip` production
chain. The repository's current `main` driver differs from the pinned
`aurora-wip` source and lacks that wake path, so its behavior must not be
treated as interchangeable. [U-Boot #8](https://github.com/aurora-silicon/u-boot/pull/8)
describes reaping a timed-out command and resetting the controller before
handoff, including a failed-reset state. Neither PR's description establishes
that an outstanding command is safely contained when reset fails. As checked
on 1 November 2026, neither PR had conversation comments or inline review
threads clarifying that failure path.

Before replacing the broad reservation, establish which buffers remain
controller- or firmware-accessible on each wake/adoption path, including the
failure path when retiring I/O queues fails, and verify coverage through Linux
adoption. A targeted reservation can then be compared on real hardware with
the known-working boot chain. Until then retain the existing protection.

There is an additional failure-path concern in that source revision:
`nvme_retire_io_queues()` reports an error if a timed-out I/O cannot be
reaped or reset, but `apple_nvme_remove()` logs the error and continues the
handoff. A read or write command can refer to a caller-supplied buffer outside
the malloc arena. Consequently the broad heap reservation is not, by itself,
a guarantee that an outstanding failed I/O cannot reach memory Linux reuses.
This is a source-level risk, not evidence that a timeout occurred on this
Mac. The concern begins before handoff: the synchronous submission function
marks a timed-out command outstanding and returns, and the block read/write
path then returns its caller's data buffer without first proving DMA stopped.
The subsequent reap or reset protects the next queue submission, but happens
after that return. Whether a particular controller can still DMA after the
timeout, and whether the caller reuses the buffer, are not established by
this source inspection.

The next block request also prepares its PRP list *before* entering the
submission function that reaps the previous timed-out command. For a transfer
large enough to use a PRP list, `nvme_setup_prps()` can overwrite or even
free and replace `dev->prp_pool` at that point. If the earlier outstanding
command still reads that pool, waiting at submission is too late to protect
it. This is a source-level ordering issue in both the pinned source and the
Aurora `main` version checked; it has not been reproduced on hardware. Moving
the reap ahead of PRP preparation could address that ordering, but would not
by itself protect the first request's data buffer after a timeout. A complete
fix needs to cover both lifetimes, including a controller that cannot be
quiesced.

In the same source revision EFI `ExitBootServices` calls
`dm_remove_devices_active()`, whose return type is void and which does not
propagate the result of device removal. Simply returning an error from the
NVMe remove callback therefore would not establish an EFI boot failure. The
controller behavior and an effective failure response need to be established
before proposing a change. See [EFI shutdown](https://github.com/aurora-silicon/u-boot/blob/d30213eadcaa886f4206d7661b61bc6cf7837828/lib/efi_loader/efi_boottime.c)
and [device removal](https://github.com/aurora-silicon/u-boot/blob/d30213eadcaa886f4206d7661b61bc6cf7837828/drivers/core/root.c).

The same lifetime problem is not limited to block I/O. In the pinned U-Boot
source, `nvme_identify()` submits an admin command using a caller-provided DMA
buffer. If polling fails or times out, `nvme_submit_sync_cmd()` marks the
admin queue outstanding and returns an error; both the controller identify
path (`nvme_get_info_from_identify()`) and namespace probing
(`nvme_probe_namespace()`) immediately free their identify buffers on that
error. A later reap or reset cannot retroactively protect those buffers from a
controller that continues DMA. This is a source-level failure-path concern,
not a reproduced timeout, and it means an eventual fix must address admin as
well as I/O command buffer lifetimes.

A retired PRP-lifetime experiment refactored the existing queue preparation
into a helper and called it before
`nvme_setup_prps()` can overwrite or free the previous command's list. The
upstream `aurora-wip` NVMe source blob matched the pinned build source when
checked on 1 November; the modified `drivers/nvme/nvme.o` compiled with the
existing Apple configuration. The command's own data buffer can still be
returned or freed before the timed-out command is quiesced, and admin identify
buffers have the same issue. This partial experiment was not booted or tested
against a real timeout; it was not a complete storage handoff fix and was not
submitted as one. Its patch is no longer carried in the active tree.

The current reset callback is not a complete answer to that lifetime problem.
The Apple driver considers DMA stopped only after clearing `CC.EN` and
observing `CSTS.RDY` clear; its wait can itself fail. Also, when controller
polling fails, `nvme_poll_ctrl()` marks the device failed, and the existing
recovery condition short-circuits without calling the reset callback. A
complete proposal therefore needs a defined containment action even when
polling or disable fails, before returning arbitrary caller-owned buffers.
Simply calling the current reset routine earlier does not cover that case.
This remains a code analysis, not evidence that this Mac encountered the
failure.
