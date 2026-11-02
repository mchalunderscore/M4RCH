# J614s boot keyboard

> Historical cache paths below describe past trials and are not current recovery instructions; most of those artifacts are no longer in the checkout. For the current boot recovery path, see [recovery](recovery.md).

On 31 October 2026 the owner confirmed the internal J614s keyboard worked in
U-Boot and GRUB, and that keyboard and trackpad worked in Linux after an MTP
handoff trial. The running trial log showed retained MTP DART bypass, adoption
of three RTKit buffers, and keyboard and multi-touch readiness. The later package-managed `7.3.0-m4rch-touchid` default has since booted;
the keyboard handoff observation above is from the earlier trial.

m1n1 passes a device tree to U-Boot, which initializes input and presents the
UEFI console to GRUB. M1 MacBooks use U-Boot's SPI keyboard driver; M2 and
later machines use an MTP coprocessor over DockChannel. The previous T6040
U-Boot deliberately left MTP to Linux, as in [Aurora U-Boot #16](https://github.com/aurora-silicon/u-boot/pull/16).
The J614s trial demonstrated that key reports work through U-Boot's FIFO path
before Linux registers its receive ring.

The installed U-Boot adapts Aurora's [J713 retained-session work](https://github.com/aurora-silicon/u-boot/pull/7)
to J614s: it preserves the live helper, its RTKit buffer inventory, DART bypass,
and discovery/READY messages for Linux. The Linux DART and RTKit helper changes
are scoped to J614s. The existing T6041 HID driver registers the M4 DMA receive
ring and configures the trackpad AFE; see [Aurora Linux #409](https://github.com/aurora-silicon/linux/pull/409).
Stopping and restarting newer MTP helpers is not assumed safe; related failures
are documented in [Aurora U-Boot #4](https://github.com/aurora-silicon/u-boot/pull/4)
and [#1](https://github.com/aurora-silicon/u-boot/pull/1).

The historical [Linux source record](https://github.com/mchalunderscore/M4RCH/blob/99a6c07/packages/linux-m4rch/promoted-source/source-stack.md)
and [U-Boot source record](https://github.com/mchalunderscore/M4RCH/blob/99a6c07/packages/u-boot-m4rch/promoted-source/source-stack.md)
identify the earlier patches and binaries. The old cached experiment was removed.
The temporary tested fallback and instructions are in [recovery](recovery.md).
