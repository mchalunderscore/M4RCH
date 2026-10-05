/* SPDX-License-Identifier: GPL-2.0+ */
/* Finish J614s port1 setup after m1n1 has initialized the shared PHY.
 * Register layout/order follows the pinned Linux pcie-apple driver and
 * Apple pinctrl driver. No common PHY reset, DART or other port access.
 * Call only after validating the live DT's port/PHY/GPIO addresses.
 */
#define SD_PHY_REQ_ACK (BIT(0) | BIT(1) | BIT(2) | BIT(3))
#define SD_PHY_REFCLK_EN (BIT(9) | BIT(10))
#define SD_PHY_REFCLK_CGEN (BIT(30) | BIT(31))
#define SD_GPIO_MODE GENMASK(3, 1)
#define SD_GPIO_PERIPH GENMASK(6, 5)
#define SD_GPIO_OUTPUT BIT(1)
#define SD_GPIO_DATA BIT(0)

static int apple_sd_pcie_train(void __iomem *port, void __iomem *phy,
			       void __iomem *gpio)
{
	u32 link = readl(port + PORT_LINKSTS);
	u32 clock = readl(phy);
	u32 appclk = readl(port + PORT_APPCLK);
	u32 ready = readl(port + PORT_STATUS);
	u32 perst = readl(port + PORT_T602X_PERST);
	u32 ltssm = readl(port + PORT_LTSSMCTL);
	u32 reset = readl(gpio + 4 * 5);
	u32 clkreq = readl(gpio + 4 * 1);
	int ret;

	printf("ARCHM4: SD port1 link=%08x ltssm=%08x phy=%08x appclk=%08x\n",
	       link, ltssm, clock, appclk);
	printf("ARCHM4: SD port1 ready=%08x perst=%08x gpio5=%08x clkreq1=%08x\n",
	       ready, perst, reset, clkreq);
	if (link & PORT_LINKSTS_UP) {
		puts("ARCHM4: SD PCIe link already up\n");
		return 0;
	}
	/* A link attempt is only valid on the controller state m1n1 prepares.
	 * Unknown or partially initialized hardware needs investigation, not a
	 * shared PHY reset or a retry loop here. CLKREQ1 must retain function1.
	 */
	if ((clock & (SD_PHY_REQ_ACK | SD_PHY_REFCLK_EN)) !=
			(SD_PHY_REQ_ACK | SD_PHY_REFCLK_EN) ||
	    (clock & BIT(4)) ||
	    !(appclk & PORT_APPCLK_EN) || !(ready & PORT_STATUS_READY) ||
	    !(perst & PORT_PERST_OFF) || (ltssm & PORT_LTSSMCTL_START) ||
	    (link & PORT_LINKSTS_BUSY) ||
	    (clkreq & (SD_GPIO_MODE | SD_GPIO_PERIPH)) != BIT(5)) {
		puts("ARCHM4: SD PCIe handoff state is unexpected; no reset attempted\n");
		return -ENODEV;
	}
	puts("ARCHM4: releasing SD endpoint reset and starting PCIe link training\n");
	/* Active-low GPIO5 PERST#: set GPIO output low, with clocks stable.
	 * Preserve unrelated pin fields, as the Apple pinctrl driver does.
	 */
	reset = (reset & ~(SD_GPIO_MODE | SD_GPIO_PERIPH | SD_GPIO_DATA)) |
		SD_GPIO_OUTPUT;
	writel(reset, gpio + 4 * 5);
	udelay(100);
	writel(reset | SD_GPIO_DATA, gpio + 4 * 5);
	mdelay(100);
	/* Match Linux's final per-port clock-gating setup before training. */
	writel(clock | SD_PHY_REFCLK_CGEN, phy);
	writel(appclk & ~PORT_APPCLK_CGDIS, port + PORT_APPCLK);
	writel(PORT_LTSSMCTL_START, port + PORT_LTSSMCTL);
	ret = readl_poll_sleep_timeout(port + PORT_LINKSTS, link,
				       link & PORT_LINKSTS_UP, 100, 500000);
	if (ret) {
		printf("ARCHM4: SD PCIe training timed out: link=%08x ready=%08x ltssm=%08x\n",
		       link, readl(port + PORT_STATUS), readl(port + PORT_LTSSMCTL));
		return ret;
	}
	puts("ARCHM4: SD PCIe link trained\n");
	return 0;
}
