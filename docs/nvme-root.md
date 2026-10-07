# NVMe installation

Target layout:

| Partition | Purpose |
| --- | --- |
| Existing 4 GiB APFS stub | Apple-authorized m1n1 and U-Boot |
| New 1 GiB FAT32 ESP | UEFI/GRUB, kernels and initramfs |
| New ext4 partition | Persistent Linux root; remaining reserved space |

Keep the SD installation intact as rollback. The ESP does not replace the Apple
stub: Apple starts the authorized APFS installation, which bridges into UEFI.

## Allocated space

Read-only macOS inspection on 2026-10-06 verified the owner's new allocation:

- Current identifier: `disk0s7`, label `M4RCH_ROOT`, filesystem exFAT.
- GPT partition UUID: `5FDB35C6-3A66-416D-8358-6555FD99FCC5`.
- Offset: 362,525,229,056 bytes; length: 127,954,583,552 bytes.
- Logical sector size: 4,096 bytes. Do not use 512-byte sector arithmetic.

Replace only this allocation with the ESP and ext4 partitions. A 1 GiB ESP leaves
126,880,841,728 bytes (about 118.17 GiB) for ext4, before filesystem overhead.
Preserve the main macOS APFS, existing Linux stub, ISC and system-Recovery
partitions. Device numbers can change; identify the reservation by UUID, bounds,
size and parent disk before any write. Back up the complete GPT before splitting.
The exFAT partition has not been replaced by this preparation.

## Boot support required

The current bridge explicitly disables `CONFIG_NVME` and boots through `archsd`.
Linux NVMe working does not establish that U-Boot can read Apple ANS storage.
An NVMe ESP alone therefore does not yet make this installation boot without SD.
A full internal boot needs Apple ANS-aware storage discovery in the bridge and
UEFI block access, followed by GRUB loading from the new ESP.

The first migration can keep loading the kernel and a separate NVMe-capable
initramfs from the SD ESP, then mount the NVMe ext4 root. This gives the root
filesystem's speed benefit while preserving the known boot path. Leave the new NVMe ESP empty for the eventual internal boot. Keep `/boot`
mounted from SD during this phase.

The existing `sdboot/init` is deliberately SD-specific: it searches MMC devices,
validates the SD partition geometry and expands that card. Merely changing a
GRUB `root=UUID=` parameter will not work. Provide a separate NVMe early-userspace
path with an explicit new root UUID and **no automatic GPT resizing**.

## Migration gates

1. Reconcile the internal-stub partition receipt with the owner's authorized
   macOS shrink and new allocation, preserving its original creation receipt.
   The old strict receipt otherwise rejects the changed main APFS size/layout.
2. Capture Linux ANS health, sector geometry and all partition UUIDs. Qualify
   storage again after the Apple-stub upgrade; never run write tests on APFS.
3. Prepare a checked split confined to the reserved span, with new ESP/root
   partition UUIDs and a new ext4 filesystem UUID. Do not duplicate the SD UUID.
4. Copy Linux preserving numeric ownership, ACLs, xattrs, hardlinks and sparse
   files. Quiesce writers for the final synchronization. Update the copied
   `fstab` and create the separate NVMe initramfs and GRUB entry.
5. Keep the existing SD entry and root. GRUB keyboard input is unavailable;
   select the trial default explicitly in the macOS-editable SD configuration.
6. Verify native writes, package transactions, repeated boots/shutdowns and
   ANS errors before making NVMe root the normal selection. Qualify the bridge
   separately before removing the SD dependency.

## Preferred macOS preparation

Linux is not required to prepare the filesystems. An offline block copy of the
unmounted SD ext4 partition preserves its complete filesystem metadata and
avoids the live-copy consistency problem. The planned NVMe root is larger than
the SD root. After copying, change the destination ext4 UUID, check the filesystem,
grow it to the new partition bounds and update only the copied `fstab`.
Keep the SD source unchanged and the NVMe ESP empty.

The project-local Darwin e2fsprogs 1.47.4 tools now include `e2fsck`, `tune2fs`
and `resize2fs`. A disposable image test passed offline cloning, changing UUID,
metadata checksums, growth from64 to96 MiB, a final filesystem check and file
preservation. Receipt: `out/nvme-macos-tools-check.json`. No real disk was written.
This verifies the tool path, not the real SD filesystem or the complete migration.

`diskutil splitPartition` supports replacing an existing exFAT allocation, but
its FAT32 filesystem personality must not be confused with the GPT ESP type.
The guarded macOS writer now implements these transactions; see the command
section below. The native
kit below remains an alternative; do not run both migration paths.

## Native migration kit

`make nvme-kit` reads the allocated macOS partition and prepares
`out/nvme-migration`. Stage that directory as `/boot/NVME0001`, then follow its
`HANDOVER.md` in Linux. The kit provides guarded inspect/split/format commands,
a seed copy and a quiescent final copy, plus an isolated SD-loaded NVMe trial.
It leaves the NVMe ESP empty. No automatic reboot or Apple-policy change occurs.

The copied installation's SD-only boot updater deliberately remains blocked by
its old root-UUID check. Kernel/config/firmware update integration is still
required; do not bypass that check. The trial is usable for native qualification,
not yet a maintained NVMe boot installation.

Partition splitting, filesystem creation, root copying and NVMe boot selection
have not been performed by macOS preparation.

## macOS migration command

The guarded macOS writer is now implemented. Review before migrating:

```sh
sudo make nvme-review PREFLIGHT=/absolute/path/to/passing/preflight
sudo make nvme-migrate PREFLIGHT=/absolute/path/to/passing/preflight
```

Review is read-only and requires the SD ESP mounted. Migration confirms the
reservation UUID, repeats the read-only SD filesystem check, backs up both GPT
regions and splits only the reservation. macOS denied raw GPT retyping on the
active internal disk, so this path keeps the two Basic Data types temporarily.
The FAT32 allocation is an empty ESP placeholder; the new ext4 root boots by
UUID regardless of that partition type. After a successful NVMe boot, run
`sudo python3 /boot/NVME0002/finalize-types.py` in Linux. It verifies the root,
all protected GPT entries and both reserved ranges, changes only the two type
fields to EFI/Linux, and verifies all UUIDs, attributes and bounds afterward.
No macOS security changes are required.
If macOS cannot recognize the new partition identities, it stops before cloning.
The copy verifies every destination chunk, changes the destination ext4 UUID,
grows ext4 and updates the copied root fstab. Copying125 GB over SD may take
roughly half an hour; keep AC connected and leave the card inserted.

The SD-loaded trial lives under `/boot/NVME0002` and becomes the explicit GRUB
default. Its appended initramfs overrides `/init` and adds fixed NVMe root
configuration. The old SD kernel, initramfs and menu entries remain intact.
The NVMe ESP has no boot files. No Apple enrollment change or automatic reboot
occurs. Follow `/boot/NVME0002/HANDOVER.md` after booting successfully.

This writer has source tests and disposable-image ext4 tests. Real partitioning,
cloning and native boot remain untested. Failure leaves a phase receipt in
`out/nvme-macos-migration.json`; do not delete it to rerun destructive stages.
GPT backups cannot recover overwritten exFAT contents. Preserve all receipts
and inspect the actual phase/layout before recovery.

Restore SD selection from macOS using the actual mounted ESP path:

```sh
sudo cp /Volumes/ARCHBOOT/NVME0002/grub-before.cfg /Volumes/ARCHBOOT/grub/grub.cfg
sync
```

The maintained7.1.3 kernel builds Apple NVMe, NVMe core and SART as modules;
ext4 is built in. The macOS writer resolves the exact dependency closure from
the SD root's modules.dep, copies those uncompressed module files, verifies
their release strings, and appends them to the initramfs. A small static
AArch64 finit_module helper loads them in dependency order before root discovery.
No host module or different kernel build is substituted. Source tests validate
the dependency ordering and archive composition; the new early-loader path
still requires the first native boot to qualify it.

If `diskutil` completed the split but the original guard stopped because it
reordered GPT slots, continue with `sudo make nvme-resume PREFLIGHT=...`.
The checked resume accepts only `splitting` or `partitioned` receipts. It keeps
UUID, type, attributes, offset and length checks on every protected partition,
while allowing entry-number changes. It verifies the exact new allocation and
saved SD GRUB before continuing; it never calls `splitPartition` again.
Type `RESUME NVME` at its prompt. Other interrupted phases require investigation.

Darwin's raw NVMe node requires4 KiB-aligned I/O; ext4 superblock accesses can
be smaller. Filesystem tools therefore use `/dev/diskNsM`, while the aligned
clone uses `/dev/rdiskNsM`. An `Invalid argument` on the raw node alone is not
proof of corruption. A `cloning` receipt with a completed copy digest can now
resume post-copy checks without repeating the copy, after verifying target GPT
identities and the copied ext4 superblock/UUID. An incomplete copy cannot use
that automatic continuation.

## Fully internal boot

The `loader-internal` profile is an isolated candidate: m1n1 initializes ANS,
U-Boot reads the internal NVMe ESP, and its ARM64 GRUB application loads the
kernel and tested NVMe initramfs. U-Boot's namespace writes are disabled; PCI,
MMC and USB are disabled, with **no SD fallback**. The fixed profile currently
binds to this Mac's reserved ESP UUID and bounds.

```sh
make loader-internal
sudo make internal-esp-review
sudo make internal-esp
sudo make boot-internal
```

The ESP command verifies all protected GPT entries, copies the tested boot
artifacts, changes the NVMe root's `/boot` to the internal ESP (readable by all),
and installs NVMe-aware initramfs/update hooks. It does not change GPT or Apple's
boot policy. Its backups are in `out/internal-esp-backup/` on the Mac. It also
adds a validated layout extension, preserving the original stub creation receipt.
The next config package carries the same NVMe hook support.

The boot command stages the new bridge using the existing Recovery enrollment
flow. Complete the credentials/enrollment step it prints. No Apple firmware
upgrade is involved: the dedicated stub remains **26.5.2 / 25F84**.

**Copying the ESP is not enough to remove the SD.** After enrollment, shut down,
remove the SD, and boot M4RCH. Confirm `/` is the NVMe ext4 filesystem and `/boot`
is the internal ESP. A successful boot with the card absent releases it for
camera use. Preserve the Mac-local backup until that test passes.

Upstream NVMe firmware fixes are retained verbatim with commit IDs and SHA256
in `sdboot/uboot-nvme-sources.json`; the local T8132 I/O-queue registration follows
our already working Linux driver. Compilation and offline checks do not establish
native U-Boot ANS initialization or its handoff to Linux.

### First card-removed trial

The first internal-only trial stopped in m1n1 after `nvme: initialized`, before
its checked ANS shutdown/handoff completion. This is not evidence of an absent
ESP or a U-Boot storage error. The revised candidate restores the proven J614s
SMC reader-supply setup, which does not probe or require an inserted card, and
adds a visible checkpoint before each checked ANS shutdown operation. U-Boot
still has MMC/PCI disabled and no SD fallback. The supply change is a hypothesis,
not yet a confirmed fix. Restage with `sudo make boot-internal` and re-enroll;
there is no need to rerun the ESP copy or root migration.

The second card-removed trial (IMG_0866) completed both I/O queue deletions and
stopped at controller shutdown. The next candidate keeps the normal SHN request
and mandatory SHST_DONE check but polls CSTS directly under the original
five-second deadline, without processing RTKit messages inside that wait. It
prints the initial CC/CSTS, the request-write checkpoint and first/final CSTS.
This tests mailbox-dispatch interference; it does not establish that interference
is the cause. Timeout still refuses handoff and retains firmware-owned buffers.
