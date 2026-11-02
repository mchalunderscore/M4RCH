# J614s DAPF handoff

> Historical cache paths below refer to retired trial artifacts; the cache now retains only inputs needed by two current test helpers. For the current boot recovery path, see [recovery](recovery.md).

## DAPF handoff review — 1 November 2026

The installed Aura's `dapf_init_all()` calls `dapf_init_fdt(NULL)`, so the
J614s path whitelist and ready bits in that function are active when booted.
The inspected 1 November boot's `/chosen/m4rch,dapf-ready` had both AOP and ISP bits set, and the
subsequent local U-Boot code uses those bits when admitting its handoffs.
Those bits need a stronger contract before this mechanism can be proposed
upstream: `dapf_init()` also returns success when an ADT instance has no DAPF
bank and preserves firmware state, so the caller can set a ready bit without
having programmed a bank. The J614s-specific validation failure also returns
directly after a possible power enable, bypassing the usual power-down cleanup.
Neither observation establishes that these cases occurred on this Mac. They
are reasons to avoid submitting the existing marker and validation unchanged,
and to compare Aurora's consumer-scoped handoff against actual board data.

## Corrected trial

Read-only inspection of this Mac's ADT found typed DAPF records for both
AOP and ISP. A trial now requires valid instance metadata for those two banks,
rejects a missing DAPF bank, and unwinds a power enable on validation errors.
The J713 regression harness and checks for missing/malformed metadata, cleanup
and ready-bit behavior passed. The trial stage two booted as `10821cf7-da80-4ce5-90f5-ab449c7f5f09`: both
readiness bits were set, AOP reported ready, and the ISP driver bound. The
owner subsequently confirmed a live image from the built-in camera on that
same boot. The kernel reported that sensor tuning file
`apple/isp_2224_01XX.dat` was missing and streamed without it; this confirms
image capture, not fully tuned image quality. The known-good package-managed stage two
was restored and its hash verified for the next boot; the running session
continues to use the trial. The trial also removes
the PMP tree-space allowance tested separately. The corrected source is in
the next local staging recipe while the upstream handoff design is reviewed.

Aurora's [ISP setfile handling PR #668](https://github.com/aurora-silicon/linux/pull/668)
describes the file as model-wide sensor tuning, distinct from per-module
calibration. Its companion [installer PR #71](https://github.com/aurora-silicon/aurora-installer/pull/71)
proposes extracting the J616s IMX958 setfile from the user's macOS, but was
still a draft with hardware qualification pending when checked on 1 November.
The live image here does not establish that its existing board admission also
supports J614s or that a J616s setfile has been qualified on this device.

## Existing Aura producer

The trial bundle's compiled board tree starts its T6041 AOP node enabled;
Aura's existing `dt_set_aop_firmware()` can therefore find it by compatible
and reserve DRAM-backed AOP firmware segments. The local U-Boot helper then
validates those reservations, keeps the code and log references and enables
the corresponding DART. It is not a completely separate firmware producer.
The bundled board DTB describes an enabled AOP whose `iommus` phandle points
to a disabled DART. Therefore removing only the U-Boot AOP helper would also
remove the step that enables that DART; the initial board tree alone is not an
equivalent replacement. The helper's validation and pruning of extra AOP
segment references must also be accounted for when moving this work earlier.
The trial boot's Aura log independently reports that AOP firmware segments
were reserved and that the AOP and ISP0 DAPF banks initialized. A filtered
log check also found two `isp` alias-not-found messages. It printed counts
only and did not retain the log or firmware data.

The same input tree has a disabled T6041 ISP node but no `isp` alias; the
running trial tree likewise has no `isp` alias. Aura's generic
`dt_set_isp()` looks up the ISP by that alias, and its reservation and
firmware-data helpers return without publishing when it is missing. The local
U-Boot path instead finds the node by compatible and creates the two firmware
reservations from the ADT before enabling it. Adding the alias is a possible
route toward Aurora ownership, but is not itself a complete fix: the generic
path also depends on `isp_init()` having established the ISP heap, and its
reservation conventions, failure behavior and DAPF sequencing need to be
compared with the working local contract. Test the combined handoff and camera
capture before removing the U-Boot producer.

At the pinned Aura revision, this is more than an untested heap assumption:
`isp_init()` has no T6040 case in its PMGR-offset switch. If it reaches that
switch on T6040, it follows the unsupported-SoC cleanup path before setting
`isp_initialized`; `isp_get_heap()` consequently fails. `kboot_prepare_dt()`
calls `isp_init()` but does not check its return value. Thus an `isp` alias
alone cannot make this generic producer equivalent to the working J614s
handoff. This conclusion is from the [pinned source](https://github.com/aurora-silicon/aura/blob/a9cad94edb46fd4baf77c6cb1776b3bb5f1a566f/src/isp.c);
it does not establish which earlier checks were reached on the trial boot.
The same switch was present in Aura `main` when checked on 1 November 2026.

This does not mean Aura must allocate a physical ISP heap for the existing
T6040 Linux driver. Aurora Linux [PR #384](https://github.com/aurora-silicon/linux/pull/384)
describes the host backing the firmware's remaining 32 MiB window, and the
retained Aurora kernel source's `apple_isp_init_iommu()` reads the heap IOVA
range and firmware-data end from `iommu-addresses`. Our tested compatibility
tree supplies the heap window without a physical `reg`, while the local
U-Boot producer supplies the two physical firmware reservations. A candidate
Aura producer could therefore preserve that tested representation rather than
force it through `isp_get_heap()`. This is a source-level route to investigate,
not evidence that the generic Aura ISP path or such a replacement has booted.
Linux [PR #531](https://github.com/aurora-silicon/linux/pull/531) moves DAPF
programming and restartable camera power handling into the driver for T8132;
its own description says T6040 is unchanged, so it does not establish that the
J614s ISP DAPF handoff can be removed.

## AOP ownership experiment

[`aura-aop-ownership-experiment.patch`](../experiments/j614s-upstream/aura-aop-ownership-experiment.patch)
is an isolated source experiment against the corrected local Aura overlay.
It moves the existing AOP reservation checks, extra mapping removal and DART
enablement into Aura after the local DAPF result is known. The affected
`kboot.o` compiles; its only warnings are the same two unrelated stack-usage
warnings seen in the baseline build. Nothing was installed or booted.

The experiment now edits a scratch copy and, on a failed AOP check, disables
the AOP and clears the local readiness bit. The affected object compiles with
the same baseline warnings. A host harness ran the real helper on this boot's
final Linux FDT: it accepted the already-pruned AOP reservations and enabled
DART and rejected a missing readiness bit. That is not a test of the earlier
Aura-to-U-Boot tree or of the transactional failure path. The temporary FDT
capture was removed after the check.

The matching [U-Boot experiment](../experiments/j614s-upstream/uboot-aop-ownership-experiment.patch)
removes the AOP producer and relies on Aura's readiness result. It builds
against the exact pinned Aurora source and retained local overlay, with the
installed `.config` and no compiler warnings. The trial binary is
`cache/j614s-aop-ownership-trial/u-boot-nodtb.bin` (SHA-256
`9b16604f1e87a0d942d5690e6a3b8b352211d26fc97e03b6d6cea6b9d317acb5`);
the old AOP helper marker is absent.

A complete experimental Aura image also links with the system AArch64 GCC
toolchain. Its Rust library is reused from the retained staged Aura build after
checking the Rust source trees and generated build configuration match; its
SHA-256 is `7f2d91b019aa6e4f97e021264ad2a725ea8f536b28eea2102b9fe9e5a4870cc6`.
The image is `cache/j614s-aop-ownership-trial/aura-gcc.bin` (SHA-256
`2e4ac5e9c66a3e9ead66ec0b40db1c653964998db9a9ab36f55b101b21000f15`).
The build reports stack-usage warnings in existing code. The prior trial used
Clang, so this full GCC build changes the compiler for all C objects and is not
a controlled single-change boot trial. The local Clang lacks `ld.lld`.

The retained native-kernel build dependencies include Clang and LLD 23.1.4,
matching the earlier Aura trial's toolchain version. A second complete image
was built with those tools and the same retained Rust library and verified
build configuration. It was assembled with the known-good J614s DTB and the
U-Boot experiment; component digests, DTB framing and U-Boot decompression
were verified. The bundle is `cache/j614s-aop-ownership-trial/boot.bin`,
SHA-256 `516bc41784a6b8d30e2036d5ece07dd291fd45ec493f788bca522e08dd7b6e69`.
The failure wrapper was exercised on a copy of the running FDT with an invalid
DART reference: the scratch edits were discarded, AOP was disabled and the ISP
readiness bit was retained. The bundle was selected and Linux subsequently
booted as `e90d941a-2f78-4274-875f-f694eba0157c`; the selected EFI file and
recovery copy matched their expected hashes after boot. The kernel reported
the AOP ready, and the final tree had two AOP firmware references. The owner
confirmed the internal microphone works and was in use on this boot. The
verified previous loader has
now been restored as the default for the next boot; the running session still
uses the trial. Recovery copies remain at
`/boot/efi/m1n1/boot.bin.m4rch-before-sd-gpio` and in
`/var/lib/m4rch/j614s-aop-ownership-trial-20261101/`.

This is not a submission candidate yet: the pair still uses the local
readiness bit, and source-tree and hardware tests must establish the moved
contract and failure behavior. Replace the local interface and verify actual
AOP operation before considering it ready for review.

## AOP marker-free trial

The subsequent [Aura](../experiments/j614s-upstream/aura-aop-no-marker-experiment.patch)
and [U-Boot](../experiments/j614s-upstream/uboot-aop-no-marker-experiment.patch)
experiments remove the AOP readiness bit from the inter-loader tree property.
Aura still uses the validated DAPF result internally to prepare or disable the
AOP; U-Boot leaves Aura's resulting AOP status alone. The ISP's separate bit
is retained for its existing local handoff. Both components build with the
same configuration and toolchain family as the previous trial, and their
combined bundle and recovery copy were hash-verified before selection.
`cache/j614s-aop-no-marker-trial/boot.bin` (SHA-256
`5ba619e037d82854b0d3f47f7ef106ea8afb5b3ad14b13ff56e5c49afb6e057f`)
booted as `b5025572-65d2-4fbd-995a-5c9edbeac1e6`: AOP reported ready,
the final tree published two AOP firmware references and only the ISP
readiness bit. The restoration script verified the trial and recovery hashes
and restored the package-managed loader for the next boot. The known-good EFI
recovery file remains `m1n1/boot.bin.m4rch-before-sd-gpio`. Microphone
operation was confirmed by the owner on this second trial.

## Separated Aura source experiment

[`aura-j614s-aop-upstream-experiment.patch`](../experiments/j614s-upstream/aura-j614s-aop-upstream-experiment.patch)
applies to the pinned Aurora source without the local ISP marker or U-Boot
overlay. It keeps the validated AOP DAPF result inside Aura and uses that
result for the AOP tree handoff. It also retains the tested J614s DAPF path
restriction. The changed objects and a complete Clang 23.1.4 ESP stage-two
image build; the Rust library was reused from the retained staged build after
checking source and build configuration. Two pre-existing unused-variable
warnings remain. The existing J713 DAPF regression fixtures and an adapted
contract harness covering J614s AOP metadata rejection, power cleanup and
readiness passed. The exact image is
`cache/j614s-aop-upstream-experiment/aura.bin` (SHA-256
`f093293569a3e188a62cc7626adb225d464b3a1b06fe8921d9c59bee98d3b6d0`).

This initial source experiment is not equivalent to the booted bundle: it
omits the other local boot handoffs, changes the AOP readiness representation,
and no longer requires the local ISP validation. It was superseded by the
integration trial and review candidate described below.

An integration trial layers the retained display, MCC, SD and other boot
prerequisites plus a separate [local ISP/memory delta](../experiments/j614s-upstream/aura-aop-integration-prerequisites.patch)
onto the separated AOP source. Its adapted AOP DAPF contract and J713 AOP
regression checks pass, and the complete image builds with the retained Clang
23 toolchain and Rust library. The combined bundle
`cache/j614s-aop-upstream-integration-trial/boot.bin`, SHA-256
`c12c9e6c2ce16a5d7f7d1cf53922d8f7f75363da66e6fc6221556afcc0379ab2`,
booted as `4f882cd3-8598-4843-8f19-e9928dd1e0d6`. AOP reported ready, the
tree retained two AOP references and only the ISP readiness bit, and the
owner confirmed both the internal microphone and camera work. The restoration
script verified the trial and recovery hashes and restored the package-managed
default for the next boot. Recovery copies remain at
`m1n1/boot.bin.m4rch-before-sd-gpio` on EFI and under
`/var/lib/m4rch/j614s-aop-upstream-integration-trial-20261101/`. The local ISP
delta extends one shared validation condition, so this is combined-stack
evidence rather than an unmodified standalone upstream image.

The review candidate was rebased onto Aurora Aura main `212e3d1`, built, and
submitted as [Aura PR #47](https://github.com/aurora-silicon/aura/pull/47).
The [review patch](../experiments/j614s-upstream/aura-j614s-aop-review.patch)
adapts the existing test fixtures instead of adding duplicate modules. The PR
records the combined-stack hardware coverage and the fact that its exact
current-main standalone image has not been booted separately.

## Initial ISP ownership prototype

The [ISP ownership experiment](../experiments/j614s-upstream/aura-j614s-isp-ownership-experiment.patch)
is based on the #47 source. It keeps the ISP DAPF result private to Aura,
validates the two ADT segments and existing J614s text/data/heap references,
and uses Aura's existing reservation helpers on a scratch tree before enabling
the ISP and its DARTs. It skips the generic ISP producer on this specific board because
that producer depends on `isp_get_heap()` and can conflict with the separate
T6040 memory-window model. A failed handoff leaves the ISP disabled.

The changed objects and a complete ESP stage-two image built with Clang 23.1.4;
the Rust library was reused from the previous source/configuration-matched
build. The image is `cache/j614s-isp-ownership-experiment/aura-reuse.bin`, SHA-256
`8adc0c68f60aacb9441f75f0c79f7022b221ee841fb59cc0ed8160a67eff1d30`.
Existing J713 DAPF, M4 power and optional-ISP fixtures passed. An additional
host check ran the actual helper against the previously tested J614s board DTB
with public J616s example segment values, verified the resulting reservations
and DART status, and rejected selected invalid segment descriptions. Its
source is `cache/j614s-isp-ownership-experiment/check-real-dtb.py` and refers
to the temporary prototype source; it is not a hardware or actual-ADT test.

The tested AOP integration's Aura source was reconstructed from its recorded
pin and patches; its rebuilt image exactly matched the previously booted image
SHA-256 `ea2e2cc131ece3b3214198c88917ff4ba709545be201a8ea28375611fac52f09`.
The [camera trial delta](../experiments/j614s-upstream/aura-isp-integrated-trial.patch)
adds the ISP ownership change to that baseline while retaining the other local
boot prerequisites. The matching [U-Boot delta](../experiments/j614s-upstream/uboot-isp-aura-ownership-experiment.patch)
removes its separate ISP producer. Both components built; the same ISP helper
passed the real-DTB check described above. The assembled bundle is
`cache/j614s-isp-ownership-experiment/boot.bin`, SHA-256
`8e08e6702d185e31b523cccce266de00b7b19a362fab5d14030e1ea7a09627a3`.

The trial booted as `6e3dd16a-5678-4b1c-9ac4-b87710c13f3e`; the ISP driver
bound, registered `video1`, and the owner confirmed a live camera image. The
verification script restored the package-managed loader for the next boot.
This tests the combined Aura, U-Boot, device-tree and kernel stack, not a
standalone upstream branch. The verified package-managed default is backed up on EFI at
`m1n1/boot.bin.m4rch-before-sd-gpio` and in
`/var/lib/m4rch/isp-ownership-trial-20261101/`. If Linux cannot boot, use
macOS or recoveryOS to copy that EFI backup over `m1n1/boot.bin`.

On 2 November a further combined trial was built and selected to test Aura's
ordinary DAPF initializer in place of the J614s-specific readiness gate and
the `m4rch,dapf-ready` marker. Aura owns both AOP and ISP handoffs, and their
U-Boot producers were removed from the trial. The generic initializer matches
the pinned Aurora implementation; the AOP and ISP handoff code and the #821
board-tree candidate are combined with other previously tested boot fixes.
Both boot components compiled. The owner booted this combination on 2 November
2026 (boot ID `a64d6ac5-bb57-4414-970d-c2ec00a3c601`) and confirmed that
the internal microphone and camera both work. Linux reported AOP ready, and
the interloader readiness marker was absent. This validates this machine and
combined configuration, not all boards or failure paths. The temporary bundle
and cached build receipt have since been removed. See [current recovery](recovery.md)
for the present recovery path.
The package-managed loader was restored for the next boot. Aura PRs
[#47](https://github.com/aurora-silicon/aura/pull/47) and
[#48](https://github.com/aurora-silicon/aura/pull/48) now use Aurora's
generic DAPF discovery instead of the J614s-specific validation and whitelist;
their descriptions distinguish the combined hardware test from standalone PR
testing. Their updated DAPF code and existing AOP/DAPF fixtures were checked
in a reconstructed source tree. The installed package still carries the
earlier local implementation until a package-managed replacement is built and
promoted.

The matching device-tree change is submitted as [Linux PR #821](https://github.com/aurora-silicon/linux/pull/821)
and the Aura handoff as [Aura PR #48](https://github.com/aurora-silicon/aura/pull/48).
The latter is stacked on Aura #47 and includes it in the diff until it is
merged. The device-tree proposal was compiled against #795's device-tree
sources with no new compiler warnings. The tested boot also used #816 and
other local prerequisites; the exact standalone PR branches were not booted.

The board proposal was reorganized after the initial ISP submission. The
[ISP device-tree PR #821](https://github.com/aurora-silicon/linux/pull/821)
was refreshed onto board head `dc054fb02bfb002e41f2dd8f43a3dce2983cf537`;
the new PR head is `4ca62110a994f246c5c97806ab70974b1f0e7e32`. Both the
unmodified board tree and the candidate compiled from exact-revision device
tree includes with identical warnings. The compiled candidate retains
placeholder text and data reservations, the 32 MiB IOVA heap window, and a
disabled ISP pending the loader. This refreshed upstream branch has not itself
been booted; the earlier combined-stack camera test remains the hardware
validation. Build inputs and outputs are in
`cache/j614s-isp-rebased-20261101/`.
