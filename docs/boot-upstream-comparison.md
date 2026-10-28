# J614s standard-boot comparison

Reviewed 2026-10-27 against Aurora [U-Boot #16](https://github.com/aurora-silicon/u-boot/pull/16), draft head `d032fb2afd2d611c4554d28b2298e5a3063fa820`. This is an offline assessment; no candidate was installed or booted.

## Verdict

At the time of this review, Aurora's work was promising but not yet a replacement for this J614s boot chain. Its author reported four production-equivalent J616s boots through a tethered stage 1 and one separately tethered fresh-ANS path. The PR was draft, had not reported untethered J616s or any J614s boots, and listed a Neo regression boot as pending. GRUB has no working keyboard on our machine, and failure before Linux starts can require external recovery; the old boot backup has since been retired.

## Boot and NVMe

- The installed chain is `m1n1-m4rch 20261025-2`, `u-boot-m4rch 2026.07-3`, `linux-m4rch 7.3.0-9`; the normal `Arch Linux` entry booted successfully after promotion.
- The installed [U-Boot patch](../packages/u-boot-m4rch/promoted-source/uboot.patch) implements `archnvme`: it verifies the J614s board, locates the uniquely identified internal ESP by GPT UUID, type, start and size, validates the EFI executable, creates an EFI disk device path and calls `bootefi`. The live `/chosen/asahi,efi-system-partition` names the same ESP and `/boot/EFI/BOOT/BOOTAA64.EFI` is present.
- #16's generic EFI path searches NVMe partitions for the stage-1-named ESP and a loader, may fall back to another ESP with the EFI loader, and can try direct kernel or generic bootflow. Its selection policy is broader than our hard-coded GPT identity and extent checks. Existence of our EFI file alone does not establish that all upstream discovery and EFI-device-path details work on this installation.
- Both use the T6041-specific NVMMU linear queue location. #16 also allocates aligned TCBs and writes both queue bases before controller enable. For a fresh iBoot ANS it creates one RTKit session and publishes up to eight LMB buffers as `no-map` `ans-rtkit@...` nodes; when a previous stage already started the session, it adopts instead. The hardware state that this machine's enrolled stage 1 produces must be established before choosing either path. The draft's stage-1 observations are from J616s, not this installed J614s stage 1.
- Our current U-Boot bridge instead retains its full live allocation arena in the Linux FDT, including memory possibly allocated while GRUB reads storage. The running FDT has `/chosen/m4rch,ans-live-handoff = "v1"` and no `apple,rtkit-handoff` property on the NVMe node. The installed Linux source accepts a running, enabled-and-ready controller without that property; it requires `apple,rtkit-handoff = "nvme-disabled-v1"` when adopting a disabled controller. This is a code-path comparison, not evidence that #16's handoff is already safe with our exact stage 1, SART reservations, live FDT and kernel.

## FDT handoffs and recovery

The installed `archnvme` also constructs a separate Linux FDT using a J614s template, and transfers and validates current-boot reservations, phandles and data for GPU, internal and external DCP, AOP, ISP, PMP and USB. In particular the promoted external-display stack depends on remapping DCP reserved memory and consumers. The #16 head's normal EFI path passes its m1n1-prepared control FDT and calls `apple_nvme_fdt_fixup`; it does not contain our `aurora_j614s_handoff` bridge. This does **not** prove upstream m1n1 could never construct an equivalent tree, but it has not been demonstrated for this installed J614s combination. Swapping U-Boot alone would omit the bridge without establishing an equivalent replacement.

Aurora [U-Boot #8](https://github.com/aurora-silicon/u-boot/pull/8) added a generic post-M4 timeout reset path and was merged; its author reports its reset testing was in QEMU, not Apple hardware. The reconstructed current U-Boot source contains `nvme_reap_timed_out()`, a call to `nvme_reset_ctrl()`, and the Apple `reset_ctrl` callback; its built binary matches the installed U-Boot byte for byte and contains the reset diagnostic strings. Earlier `packages/README.md` text said the withdrawn local timeout-recovery candidate was not retained; that text has been corrected. The old withdrawn candidate and upstream generic reset are not established to be the same change, and the binary does not establish that a reset occurred or would succeed on J614s. Do not test failure recovery on the live NVMe by forcing timeouts.

## Offline checks

- Downloaded the exact #16 head and built `u-boot-nodtb.bin` successfully on this AArch64 machine using `apple_m1_defconfig`; this is a build-only result, not an installation or a boot test. SHA-256: `a7a0d50cbffdc9bac7359d10f05a23d0386874c60aab214d44aa9c0a26324a9b`.
- A dry-run of the PR's multi-commit patch series against our already-modified reconstructed source reported conflicts in board and NVMe code. Because the commits were not applied sequentially in that dry run, the result indicates integration work but is not a precise conflict count.
- Existing offline external-display bridge and restore tests passed. The captured-ADT audit accepted the saved J614s ADT and rejected two deliberately altered fixtures. These validate current bridge behavior, not the upstream boot candidate.
- The existing boot artifacts and configuration were not modified. The previous boot bundle remains under `/boot/*before-external-promotion*`.

## Path to an informed trial

1. Trace the enrolled stage-1 ANS and SART ownership contract from existing evidence, with no live NVMe register manipulation. Compare its inherited memory and queue state with both #16 handoff paths and the exact running Linux driver. Separate the previously withdrawn local recovery change from the generic upstream reset code that is present.
2. Build a combined **offline** candidate that preserves the J614s FDT translation and every tested DCP, GPU, AOP, ISP, PMP and USB handoff while replacing the boot-selection path incrementally. Verify a generated FDT against the actual live tree and reserved-memory/IOMMU constraints, including buffers allocated after GRUB starts. Compare ESP choice and EFI loaded-image path with this disk's actual layout.
3. Run existing bridge tests, negative/malformed FDT fixtures, queue and timeout tests, and reproducible build checks. Obtain upstream J616s untethered/Neo regression results if they become available; neither substitutes for J614s tests.
4. Before a physical trial, prepare and verify recovery for a failure before GRUB and before Linux's rollback service can run. The internal keyboard cannot select an alternate GRUB entry. Preserve all currently working boot, GRUB and module artifacts; no enrolled stage-1 change is implied. A successful build or mock test is not proof that storage handoff or peripherals work on hardware.
