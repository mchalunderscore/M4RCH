/* SPDX-License-Identifier: GPL-2.0+ */
/* J614s GL9755 setup from Linux gl9755_hw_setting(). The caller must have
 * validated the board and PCI ID. Program CD/WP polarity in hardware so the
 * controller and software agree about card presence; do not invert it again
 * in the MMC host capabilities. No ASPM, MSI or power-state changes here.
 */
#define GL9755_PCI_WT 0x800
#define GL9755_PCI_PECONF 0x44
#define GL9755_PCI_WT_EN BIT(0)
#define GL9755_PCI_INVERT (BIT(30) | BIT(31))
#define GL9755_PCI_CLOCKS (GENMASK(14, 12) | BIT(29))
#define GL9755_PCI_MASK (GL9755_PCI_INVERT | GL9755_PCI_CLOCKS)

/* Linux opens WT even for read-only vendor-register queries. Verification
 * must use that window too; a gate-closed zero is not a configuration value.
 */
static int gl9755_pci_transaction(struct udevice *dev, int configure)
{
	u32 wt, gate, before = 0, after = 0, expected;
	int ret, close_ret = 0, have_value = 0;

	ret = dm_pci_read_config32(dev, GL9755_PCI_WT, &wt);
	if (ret)
		goto report;
	if (wt == 0xffffffff) {
		ret = -EIO;
		goto report;
	}

	/* Once opening the gate is attempted, every exit attempts to close it.
	 * A failed config write can still have reached the device.
	 */
	if (!(wt & GL9755_PCI_WT_EN)) {
		ret = dm_pci_write_config32(dev, GL9755_PCI_WT,
					  wt | GL9755_PCI_WT_EN);
		if (ret)
			goto close;
	}
	ret = dm_pci_read_config32(dev, GL9755_PCI_WT, &gate);
	if (ret)
		goto close;
	if (gate == 0xffffffff || !(gate & GL9755_PCI_WT_EN)) {
		ret = -EIO;
		goto close;
	}
	ret = dm_pci_read_config32(dev, GL9755_PCI_PECONF, &before);
	if (ret)
		goto close;
	if (before == 0xffffffff) {
		ret = -EIO;
		goto close;
	}
	after = before;
	have_value = 1;
	if (configure) {
		expected = (before | GL9755_PCI_INVERT) & ~GL9755_PCI_CLOCKS;
		ret = dm_pci_write_config32(dev, GL9755_PCI_PECONF, expected);
		if (ret)
			goto close;
		have_value = 0;
		ret = dm_pci_read_config32(dev, GL9755_PCI_PECONF, &after);
		if (ret)
			goto close;
		have_value = after != 0xffffffff;
	}
	if (!have_value || (after & GL9755_PCI_MASK) != GL9755_PCI_INVERT)
		ret = -EIO;
close:
	/* This helper changes only WT_EN; restore its other entry-time bits.
	 * Like Linux, leave write access disabled even if it was initially on.
	 */
	close_ret = dm_pci_write_config32(dev, GL9755_PCI_WT,
					wt & ~GL9755_PCI_WT_EN);
	if (!close_ret) {
		close_ret = dm_pci_read_config32(dev, GL9755_PCI_WT, &gate);
		if (!close_ret && (gate == 0xffffffff ||
				  (gate & GL9755_PCI_WT_EN)))
			close_ret = -EIO;
	}
	if (!ret)
		ret = close_ret;
report:
	if (!configure) {
		if (have_value)
			printf("ARCHM4: GL9755 gated post-reset PECONF=%08x "
			       "status=%d, gate cleanup=%d\n", after, ret, close_ret);
		else
			printf("ARCHM4: GL9755 gated post-reset PECONF unavailable "
			       "status=%d, gate cleanup=%d\n", ret, close_ret);
		return ret;
	}
	if (ret) {
		printf("ARCHM4: GL9755 PCI setup failed (%d), gate cleanup=%d\n",
		       ret, close_ret);
		return ret;
	}
	printf("ARCHM4: GL9755 PECONF=%08x -> %08x; hardware CD/WP polarity set\n",
	       before, after);
	return 0;
}

static int gl9755_pci_init(struct udevice *dev)
{
	return gl9755_pci_transaction(dev, 1);
}

static int gl9755_pci_verify(struct udevice *dev)
{
	return gl9755_pci_transaction(dev, 0);
}
