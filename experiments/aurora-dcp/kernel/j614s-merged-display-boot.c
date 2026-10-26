// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Admit Aurora's standard T6041 handoff before platform-device population.
 * The common loader keeps display devices disabled for older fallback kernels.
 */
#include <linux/init.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <linux/string.h>

static bool requested;
static int __init display_option(char *value)
{
	return value ? kstrtobool(value, &requested) : -EINVAL;
}
early_param("m4rch.dcp", display_option);

static int __init j614s_display_boot(void)
{
	static const char * const paths[] = {
		"/iommu@402300000", "/iommu@402340000", "/mailbox@402e08000",
		"/dcp@402e00000", "/dcp@402e00000/piodma", "/display-subsystem",
	};
	struct device_node *nodes[ARRAY_SIZE(paths)] = {};
	struct property *properties[ARRAY_SIZE(paths)] = {};
	struct of_changeset changes;
	int ret = -ENODEV;

	if (!requested)
		return 0;
	if (!of_machine_is_compatible("apple,j614s") ||
	    !of_machine_is_compatible("apple,t6040"))
		return -ENODEV;
	of_changeset_init(&changes);
	for (unsigned int i = 0; i < ARRAY_SIZE(paths); i++) {
		nodes[i] = of_find_node_by_path(paths[i]);
		if (!nodes[i])
			goto out;
	}
	/* The standard marker is written only after m1n1 completes its validated
	 * same-boot handoff and the U-Boot bridge remaps all references and names.
	 */
	for (unsigned int i = 3; i < ARRAY_SIZE(paths); i++)
		if (!of_property_read_bool(nodes[i], "apple,t6041-handoff") ||
		    !of_find_property(nodes[i], "memory-region-names", NULL))
			goto out;
	for (unsigned int i = 0; i < ARRAY_SIZE(paths); i++) {
		struct property *p;

		if (of_device_is_available(nodes[i]))
			continue;
		p = kzalloc(sizeof(*p), GFP_KERNEL);
		properties[i] = p;
		ret = -ENOMEM;
		if (!p)
			goto out;
		p->name = kstrdup("status", GFP_KERNEL);
		p->value = kstrdup("okay", GFP_KERNEL);
		p->length = 5;
		if (!p->name || !p->value)
			goto out;
		ret = of_changeset_update_property(&changes, nodes[i], p);
		if (ret)
			goto out;
	}
	ret = of_changeset_apply(&changes);
out:
	of_changeset_destroy(&changes);
	for (unsigned int i = 0; i < ARRAY_SIZE(paths); i++) {
		of_node_put(nodes[i]);
		if (ret && properties[i]) {
			kfree(properties[i]->name);
			kfree(properties[i]->value);
			kfree(properties[i]);
		}
	}
	if (ret)
		pr_err("AUDP010: standard T6041 display handoff unavailable (%d)\n", ret);
	else
		pr_info("AUDP010: J614s standard T6041 handoff admitted; normal DMA and locked-DART mirror\n");
	return ret;
}
core_initcall(j614s_display_boot);
