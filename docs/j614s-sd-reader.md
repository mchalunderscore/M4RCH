# J614s SD reader investigation

> This is a chronological investigation. Statements about the installed stack,
> selected trials and recovery files refer to the recorded time unless a later
> update says otherwise. Historical cache artifacts are mostly unavailable.
> For the present boot recovery path, see [recovery](recovery.md).

On 2 November 2026 the owner clarified that during the source-built SD
board-tree trial without the local SD power action and U-Boot rewrite, they
mounted the card and edited files successfully. This adds real read/write
evidence; suspend remains untested.

**Status as of 2 November 2026:** The installed forked kernel includes the
merged J614s board and SD descriptions. In an earlier combined-stack trial,
the source-built board tree detected the reader without the former U-Boot SD
rewrite or Aura SD-specific power action; the owner mounted and edited files.
This does not qualify suspend, sustained writes or every independent upstream
component. See [current status](status.md) and [recovery](recovery.md).

## Upstream device-tree trial — 1 November 2026

[Linux PR #818](https://github.com/aurora-silicon/linux/pull/818) describes the
reader with the existing PCIe and SMC GPIO bindings, based on J614s DT PR
#795. The observed firmware action writes active-high GPIO `gP19`; in Linux,
that is `pwren-gpios = <&smc_gpio 0x19 GPIO_ACTIVE_HIGH>` on the SD port.
Moving both CLKREQ pins to the controller also avoids the duplicate claim.

Two trial boots used a local Aura with the SD power write removed. The first
used U-Boot to add the GPIO and enabled-port properties; inserting the card
created the SDXC block device and its partitions. The second boot used a
source-built DT with those properties, PR #816's board facts and the local
loader compatibility include, and U-Boot with its SD-specific tree rewrite
removed. The GL9755 bound to `sdhci-pci`, the card appeared at SDR104 and its
partition table was read. Wi-Fi and Bluetooth PCI functions enumerated and no
SD pin conflict was logged. Its exact upstream-only PR branch was not booted;
write-protect behavior, sustained writes, suspend, and whether earlier firmware
left power on remain unqualified. The known-good package-managed stage 2 was
restored for the next boot. Trial receipts and exact inputs are in
`cache/j614s-sd-gpio-trial/` and `cache/j614s-sd-static-trial/`.

## Earlier observation — 31 October 2026

On the package-managed `7.3.0-m4rch-touchid` boot, the owner inserted an SD
card into the built-in slot. No new block device or kernel message appeared;
`/sys/class/mmc_host` was empty. PCI enumeration showed the Wi-Fi/Bluetooth
endpoint but no SD controller. The running device tree has
`/pcie@1cb0000000/pci@1,0` and `/iommu@411000000` disabled, and the PCI bus
range ends at 1. The kernel has the `sdhci-pci` module available. The card's
contents, filesystem, capacity and physical health were not tested.

## Previous implementation

The historical [hardware record at bce491f](https://github.com/mchalunderscore/m4rch/blob/bce491f/docs/hardware.md)
reports a complete SD-root boot on J614s and repeated boots and shutdowns.
It also records an SD cache-flush error 84 and block I/O error in one round;
the cause was not determined. This is evidence of prior functionality, not
qualification of the present stack or of reliable writes.

The [old architecture](https://github.com/mchalunderscore/m4rch/blob/bce491f/docs/architecture.md)
describes m1n1 powering the reader and U-Boot training its PCIe link and
providing SD access to GRUB. The historical device-tree contract identifies
the endpoint as Genesys GL9755 (`17a0:9755`). Its
[port-training code](https://github.com/mchalunderscore/m4rch/blob/bce491f/sdboot/sd_pcie.h)
and [PCI bus handoff](https://github.com/mchalunderscore/m4rch/blob/bce491f/sdboot/sd_pci_handoff.h)
are useful references, but were designed for a different boot chain. The SD
workflow became legacy during the 26 October Aurora package migration and
was retired from the active tree on 28 October after the move to internal
storage.

The historical [m1n1 power patch](https://github.com/mchalunderscore/M4RCH/blob/99a6c07/packages/m1n1-m4rch/promoted-source/patches/upstream-integration/06-sd-reader-power.patch)
retains a J614s-guarded SMC action. Its presence in the documented installed
binary does not prove the reader's current power or link state. The current
Linux tree describes port 1 and an IOMMU mapping for bus 2, but explicitly
leaves the port and DART disabled and the bus range narrow. The older U-Boot
handoff cleared temporary SD bridge numbering before Linux enumerated Wi-Fi
on bus 1 and SD on bus 2; those requester IDs must not be swapped.

## Upstream and next experiment

Aurora's [T6040/J616s device-tree series](https://github.com/aurora-silicon/linux/pull/396)
describes the Wi-Fi PCIe path and notes that the SD helper remains disabled;
it does not establish J614s SD operation. [Asahi's M4 support table](https://asahilinux.org/docs/platform/feature-support/m4/)
lists the M4 Pro/Max MacBook SD slot as TBA. At the time of the earlier
investigation no reviewed upstream solution for that handoff had been
identified; the later board-tree trial is above.

## Historical trial preparation — 31 October 2026

The experimental [handoff](https://github.com/mchalunderscore/M4RCH/blob/99a6c07/packages/u-boot-m4rch/promoted-source/patches/sd-handoff/01-j614s-sd-handoff.patch) was built into a
separate U-Boot, using the current U-Boot configuration and the booted
Touch ID source tree. m1n1 still initializes PCIe and applies the existing
guarded SD power action. U-Boot's own PCI scan still sees the port disabled.
When U-Boot prepares the EFI tree, the trial checks the J614s board, port,
reset GPIO, bus range and both DART mappings, then enables the SD port and
DART on the copied live tree. It selects both CLKREQ pin groups on the PCIe
controller, assigns bus 2 to the SD port and supplies the GL9755 card-detect
and write-protect polarity from the older platform's design. The current
kernel and its modules, initramfs, m1n1, embedded board DTB and GRUB are
unchanged. PCIe link and SD DMA behavior are not established until booted.

The production function was run against both the installed board DTB and a
capture of this boot's live tree. It accepted both, rejected a changed bus
range, and the installed-tree diff showed only the intended PCIe, DART,
pinctrl and reader properties. U-Boot built without warnings, with the
installed config; its SD marker appears in the binary. The trial source tree
matches `cache/touchid-candidate/uboot-work` apart from the retained
integration patch, preserved in `cache/jack-promotion/recovery/sd-source/` and the
new handoff header. Image assembly
verified that the current boot image contains the installed m1n1, DTB and
U-Boot, then replaced only the compressed U-Boot component and checked its
decompression. These checks do not prove the candidate boots or the card is
readable. The files and build log are in `cache/sd-reader-trial/`:

- `boot-known-good.bin`: SHA-256 `a3c0a71a8ddebfdc61261a7ef6ff35b0983348387cf25bac00516298448841c4`.
- `boot-sd-trial.bin`: SHA-256 `36756362aaa34339535a11bb1e226f0dd8c884e4ab813dbd5fa21f1c8617b5b9`.
- Trial U-Boot: SHA-256 `34e5e8336c0733c026aeef4895b16d23e6f5d5b804e2cd03ce4581b4ebe034c3`.

The earlier staging and control scripts have been retired after promotion; their
exact copies are preserved in `cache/jack-promotion/recovery/retired-experiments/`.
Use the [boot recovery guide](recovery.md) to restore the previous SD-capable
boot chain if needed.

## Trial boot result — 31 October 2026

The owner booted the armed candidate. Boot ID
`c7c1e03c-890d-4580-8b8b-4ed32af8e1f3` differs from the preceding boot, and
the running device tree has the SD port and DART enabled. The system reached
Linux on `7.3.0-m4rch-touchid`; `/` remains on the internal NVMe. PCIe port 1
linked and enumerated the GL9755 at `02:00.0`, bound to `sdhci-pci`. Wi-Fi
and Bluetooth PCI functions remained at `01:00.0` and `01:00.1`, with their
drivers bound. Linux recognized the inserted card as a 117 GiB UHS-I SDR104
SDXC card, `mmcblk0`, and read its two partition records. Neither partition
was mounted during the initial inspection.

The kernel logged a pinctrl error: both the PCIe controller and its root port
attempted to claim PIN1. Consequently the `pcieport` driver did not bind to
`0000:00:01.0`, although the SD host bound and detected the card. Resolve
ownership was corrected in the later package-managed default. The owner subsequently reported
that hotplug, reads and writes work. The kernel log records card removal at
11:32:59 and reinsertion at 11:33:04, with the SDXC card and both partitions
detected again; no MMC I/O errors appear in the inspected current-boot log.
The precise read/write workload and its integrity checks were not recorded.
Suspend and longer-term reliability remain unqualified. The later
package-managed default fixes the pin conflict. On boot ID
`c7c08627-2c0d-4806-bf4b-3933df129d1b`, `pcieport` bound to `00:01.0`,
`sdhci-pci` bound to `02:00.0`, and the 117 GiB card enumerated at SDR104.
The prior image is retained for recovery.

## Upstream integration update

On 1 November, [PR #818](https://github.com/aurora-silicon/linux/pull/818)
was merged into the J614s board branch for
[PR #795](https://github.com/aurora-silicon/linux/pull/795). The board PR was
subsequently merged into `aurora-wip` on 2 November. This does not establish
that every downstream installation has updated. The board branch also
incorporated [the board identifiers in #816](https://github.com/aurora-silicon/linux/pull/816)
and includes the SEP profile proposed in
[#813](https://github.com/aurora-silicon/linux/pull/813). The board maintainer
retained a 189 mm panel `adj-height-mm` rather than the deletion proposed in
#816; that difference needs to be accounted for in later board validation.
