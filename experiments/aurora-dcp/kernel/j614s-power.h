/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Included in iomfb_m4.c. Initial J614s takeover retains the firmware's live
 * display power state. DISPINT is not J713's logical device 8; do not send
 * that command, or truncate native table ID 17 into its four-bit field.
 * No DPMS, power-cycle or suspend boundary is qualified by this candidate.
 */
#include <linux/soc/apple/pmp.h>
#include <linux/soc/apple/pmp-report.h>
#include <linux/unaligned.h>

static struct device *j614s_display_pmp;
static DEFINE_MUTEX(j614s_display_power_lock);

static bool j614s_display_board(void)
{
	return of_machine_is_compatible("apple,j614s") &&
	       of_machine_is_compatible("apple,t6040");
}

static int j614s_display_power_check(struct device *consumer)
{
	struct device *supplier = READ_ONCE(j614s_display_pmp);

	if (!supplier || !device_is_bound(supplier))
		return -ENODEV;
	return apple_pmp_report_wait_supplier_ready(supplier, 0);
}

static int j614s_display_power_prepare(struct device *consumer)
{
	struct platform_device *pdev;
	struct device_node *np;
	const u8 *table;
	int ret, size;

	guard(mutex)(&j614s_display_power_lock);
	if (j614s_display_pmp)
		return j614s_display_power_check(consumer);
	if (!j614s_display_board() ||
	    !of_property_read_bool(consumer->of_node, "apple,j614s-inherited-mappings"))
		return -ENODEV;
	np = of_parse_phandle(consumer->of_node, "apple,pmp", 0);
	if (!np)
		return -ENODEV;
	table = of_get_property(np, "apple,tunable-soc-device", &size);
	ret = -ENODEV;
	/* Identity check against the owner's saved native 25G83 table. These
	 * bytes identify the supplier; they are not a new power-command ABI.
	 */
	if (!of_device_is_compatible(np, "apple,t6041-pmp-v2") || !table ||
	    size != 34 * 0x7c || get_unaligned_le32(table + 16 * 0x7c) != 17 ||
	    memcmp(table + 16 * 0x7c + 0x74, "DISPINT\0", 8))
		goto put_node;
	pdev = of_find_device_by_node(np);
	if (!pdev) { ret = -EPROBE_DEFER; goto put_node; }
	ret = apple_pmp_link_device(consumer);
	if (ret)
		goto put_device;
	device_lock(&pdev->dev);
	if (!pdev->dev.driver || strcmp(pdev->dev.driver->name, "apple_pmp") ||
	    !dev_get_drvdata(&pdev->dev)) {
		ret = -EPROBE_DEFER;
		goto unlock;
	}
	pm_runtime_get_noresume(&pdev->dev);
	ret = apple_pmp_report_wait_supplier_ready(&pdev->dev, 5000);
	if (ret) {
		pm_runtime_put_noidle(&pdev->dev);
		goto unlock;
	}
	/* Retained backing and supplier references live until reboot, just as
	 * the adopted DCP/PIODMA session does. No second PMP mailbox owner.
	 */
	__module_get(pdev->dev.driver->owner);
	WRITE_ONCE(j614s_display_pmp, get_device(&pdev->dev));
	dev_info(consumer, "J614s boot display power retained; no J713 PMP command sent\n");
unlock:
	device_unlock(&pdev->dev);
put_device:
	put_device(&pdev->dev);
put_node:
	of_node_put(np);
	return ret;
}
