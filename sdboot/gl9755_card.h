/* SPDX-License-Identifier: GPL-2.0+ */
/* J614s GL9755 native card detection. PCI setup establishes polarity in
 * hardware; do not apply GPIO or software inversion here. The two-second
 * window is a local bring-up bound, not a documented GL9755 timing rule.
 */
#define GL9755_CARD_WAIT_MS 2000
#define GL9755_CARD_READY (SDHCI_CARD_STATE_STABLE | SDHCI_CARD_PRESENT)

static int gl9755_wait_card(struct sdhci_host *host)
{
	u32 first, state;
	unsigned int elapsed = 0;
	int ret;

	first = state = sdhci_readl(host, SDHCI_PRESENT_STATE);
	for (;;) {
		/* Unreadable MMIO must not masquerade as every status bit set. */
		if (state == 0xffffffff) {
			ret = -EIO;
			break;
		}
		if ((state & GL9755_CARD_READY) == GL9755_CARD_READY) {
			ret = 0;
			break;
		}
		if (elapsed == GL9755_CARD_WAIT_MS) {
			ret = state & SDHCI_CARD_STATE_STABLE ?
				-ENOMEDIUM : -ETIMEDOUT;
			break;
		}
		/* A stable absent sample can still change after endpoint reset or
		 * hardware polarity setup. Give it the same bounded settle window.
		 */
		mdelay(1);
		elapsed++;
		state = sdhci_readl(host, SDHCI_PRESENT_STATE);
	}
	printf("ARCHM4: GL9755 card state first=%08x last=%08x "
	       "present=%u stable=%u pin=%u elapsed=%ums result=%d "
	       "clock=%04x power=%02x\n",
	       first, state, !!(state & SDHCI_CARD_PRESENT),
	       !!(state & SDHCI_CARD_STATE_STABLE),
	       !!(state & SDHCI_CARD_DETECT_PIN_LEVEL), elapsed, ret,
	       sdhci_readw(host, SDHCI_CLOCK_CONTROL),
	       sdhci_readb(host, SDHCI_POWER_CONTROL));
	return ret;
}

static int gl9755_get_cd(struct sdhci_host *host)
{
	u32 state = sdhci_readl(host, SDHCI_PRESENT_STATE);

	if (state != 0xffffffff &&
	    (state & GL9755_CARD_READY) == GL9755_CARD_READY)
		return 1;
	printf("ARCHM4: GL9755 card detect rejected state=%08x "
	       "present=%u stable=%u pin=%u\n",
	       state, !!(state & SDHCI_CARD_PRESENT),
	       !!(state & SDHCI_CARD_STATE_STABLE),
	       !!(state & SDHCI_CARD_DETECT_PIN_LEVEL));
	return 0;
}
