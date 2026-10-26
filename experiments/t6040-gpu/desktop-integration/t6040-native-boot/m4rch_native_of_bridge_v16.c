// SPDX-License-Identifier: GPL-2.0-only
/* Metadata bridge only. No MMIO, firmware boot, or reservation allocation. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/ioport.h>
#include <linux/mm.h>
#include <linux/firmware.h>
#include <linux/mutex.h>
#include <linux/sizes.h>

static uint provider_phandle;
module_param(provider_phandle, uint, 0444);
static int overlay_id;
static bool attempted;
static DEFINE_MUTEX(apply_lock);

static int validate_overlay(struct notifier_block *nb, unsigned long action, void *arg)
{
	struct of_overlay_notify_data *data = arg;
	struct device_node *child;
	const __be32 *reg;
	u64 base, bytes;
	u32 pd;
	int len, count = 0;
	if (action != OF_OVERLAY_PRE_APPLY)
		return NOTIFY_OK;
	if (of_node_name_eq(data->target, "reserved-memory") && data->target->parent == of_root) {
		for_each_child_of_node(data->overlay, child) {
			reg = of_get_property(child, "reg", &len);
			if (strncmp(child->name, "native-gpu-", 11) || !reg || len != 16 ||
			    !of_property_present(child, "no-map"))
				goto invalid;
			base = of_read_number(reg, 2); bytes = of_read_number(reg + 2, 2);
			if (!base || bytes < SZ_16K || ((base | bytes) & (SZ_16K - 1)) ||
			    base + bytes < base ||
			    region_intersects(base, bytes, IORESOURCE_SYSTEM_RAM,
					IORES_DESC_NONE) != REGION_DISJOINT)
				goto invalid;
			count++;
		}
		return count == 5 ? NOTIFY_OK : notifier_from_errno(-EINVAL);
	}
	if (of_node_name_eq(data->target, "soc") && data->target->parent == of_root) {
		for_each_child_of_node(data->overlay, child) {
			if (!(of_device_is_compatible(child, "apple,agx-t6040") ||
			      of_device_is_compatible(child, "apple,t8140-asc-mailbox")) ||
			    of_property_read_u32(child, "power-domains", &pd) ||
			    pd != provider_phandle)
				goto invalid;
			count++;
		}
		return count == 2 ? NOTIFY_OK : notifier_from_errno(-EINVAL);
	}
	return notifier_from_errno(-EINVAL);
invalid:
	of_node_put(child);
	return notifier_from_errno(-EINVAL);
}
static struct notifier_block overlay_guard = { .notifier_call = validate_overlay };

static int set_apply(const char *value, const struct kernel_param *kp)
{
	const struct firmware *fw;
	int ret;
	/* A fixed name forces the launcher to publish its current-boot result. */
	if (!provider_phandle || !sysfs_streq(value, "m4rch/native-current.dtbo"))
		return -EINVAL;
	mutex_lock(&apply_lock);
	if (attempted) { ret = -EBUSY; goto done; }
	ret = request_firmware(&fw, "m4rch/native-current.dtbo", NULL);
	if (ret) goto done;
	if (fw->size > SZ_1M) { ret = -E2BIG; goto release; }
	ret = of_overlay_notifier_register(&overlay_guard);
	if (ret) goto release;
	attempted = true;
	/* Retain even a partly applied overlay, provider and module until reboot.
	 * GPU/RTKit DMA ownership belongs to the integrated driver's quarantine.
	 */
	__module_get(THIS_MODULE);
	ret = of_overlay_fdt_apply(fw->data, fw->size, &overlay_id, NULL);
	of_overlay_notifier_unregister(&overlay_guard);
release:
	release_firmware(fw);
done:
	mutex_unlock(&apply_lock);
	return ret;
}
static const struct kernel_param_ops apply_ops = { .set = set_apply };
module_param_cb(apply, &apply_ops, NULL, 0200);

static int __init native_bridge_init(void)
{
	struct device_node *provider, *gpu;
	int ret;
	if (!of_machine_is_compatible("apple,j614s") ||
	    !of_machine_is_compatible("apple,t6040")) return -ENODEV;
	gpu = of_find_compatible_node(NULL, NULL, "apple,agx-t6040");
	if (gpu) { of_node_put(gpu); return -EEXIST; }
	provider = of_find_node_by_path("/soc/power-management@288e80000/power-controller@110");
	if (!provider) return -ENODEV;
	ret = of_m4rch_ensure_phandle(provider, &provider_phandle);
	of_node_put(provider);
	return ret;
}
static void __exit native_bridge_exit(void) { }
module_init(native_bridge_init);
module_exit(native_bridge_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Current-loader T6040 OF metadata bridge; explicit one-shot activation");
