/* SPDX-License-Identifier: GPL-2.0+ */
/* GL9755 subword reads must use an aligned DWORD transaction. Match Linux's
 * sdhci_gli_readb/readw; writes retain their native width (no register RMW).
 */
static u16 gl9755_readw(struct sdhci_host *host, int reg)
{
	u32 value = readl(host->ioaddr + (reg & ~3));

	return (value >> ((reg & 3) * 8)) & 0xffff;
}

static u8 gl9755_readb(struct sdhci_host *host, int reg)
{
	u32 value = readl(host->ioaddr + (reg & ~3));

	return (value >> ((reg & 3) * 8)) & 0xff;
}

static const struct sdhci_ops gl9755_ops = {
	.read_w = gl9755_readw,
	.read_b = gl9755_readb,
};
