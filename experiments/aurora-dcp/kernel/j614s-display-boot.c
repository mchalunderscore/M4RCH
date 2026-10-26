// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Keep the shared loader's display devices inert for ordinary boot entries.
 * Only this kernel and an explicit command line admit the live DCP handoff.
 */
#include <linux/init.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <linux/string.h>

static bool j614s_dcp_requested;

static int __init j614s_dcp_option(char *value)
{
	return value ? kstrtobool(value, &j614s_dcp_requested) : -EINVAL;
}
early_param("m4rch.dcp", j614s_dcp_option);

static int j614s_display_power_topology(struct device_node *dcp,
		struct of_changeset *changes, struct property **allocated)
{
	struct device_node *pmp = of_parse_phandle(dcp, "apple,pmp", 0);
	struct device_node *report = of_find_node_by_path("/pmp-report@5003c0000");
	struct device_node *existing;
	struct property *property;
	__be32 phandle;
	int ret = -ENODEV;

	if (!pmp || !report || !of_device_is_available(pmp) ||
	    !of_device_is_available(report) || !report->phandle ||
	    !of_device_is_compatible(pmp, "apple,t6041-pmp-v2") ||
	    !of_device_is_compatible(report, "apple,t6041-pmp-v2-report"))
		goto out;
	if (of_find_property(pmp, "apple,pmp-report", NULL)) {
		existing = of_parse_phandle(pmp, "apple,pmp-report", 0);
		ret = existing == report ? 0 : -ENODEV;
		of_node_put(existing);
		goto out;
	}
	/* Complete the native supplier topology in the same transaction that
	 * admits display devices, before platform devices are populated.
	 * Do not replace an existing link or create another report/PMP owner.
	 */
	property = kzalloc(sizeof(*property), GFP_KERNEL);
	*allocated = property;
	if (!property) { ret = -ENOMEM; goto out; }
	phandle = cpu_to_be32(report->phandle);
	property->name = kstrdup("apple,pmp-report", GFP_KERNEL);
	property->value = kmemdup(&phandle, sizeof(phandle), GFP_KERNEL);
	property->length = sizeof(phandle);
	if (!property->name || !property->value) { ret = -ENOMEM; goto out; }
	ret = of_changeset_add_property(changes, pmp, property);
out:
	of_node_put(pmp);
	of_node_put(report);
	return ret;
}

static int __init j614s_display_boot(void)
{
	static const struct { const char *path, *compatible; } devices[] = {
		{ "/iommu@402300000", "apple,t6041-dart" },
		{ "/iommu@402340000", "apple,t6041-dart" },
		{ "/mailbox@402e08000", "apple,asc-mailbox-v4" },
		{ "/dcp@402e00000", "apple,t6041-dcp" },
		{ "/display-subsystem", "apple,t6041-display-subsystem" },
	};
	struct device_node *nodes[ARRAY_SIZE(devices)] = {}, *dcp, *chosen;
	struct property *properties[ARRAY_SIZE(devices) + 1] = {};
	struct of_changeset changes;
	const char *marker, *uuid;
	int ret = -ENODEV;

	if (!j614s_dcp_requested)
		return 0;
	if (!of_machine_is_compatible("apple,j614s") ||
	    !of_machine_is_compatible("apple,t6040"))
		goto failed;
	chosen = of_find_node_by_path("/chosen");
	ret = of_property_read_string(chosen, "m4rch,dcp-handoff", &marker);
	if (!ret && strcmp(marker, "DCP001-v1"))
		ret = -ENODEV;
	of_node_put(chosen);
	if (ret)
		goto failed;
	ret = -ENODEV;
	for (unsigned int i = 0; i < ARRAY_SIZE(devices); i++) {
		nodes[i] = of_find_node_by_path(devices[i].path);
		if (!nodes[i] || !of_device_is_compatible(nodes[i], devices[i].compatible) ||
		    of_device_is_available(nodes[i]))
			goto failed;
	}
	dcp = nodes[3];
	if (of_property_read_string(dcp, "apple,firmware-uuid", &uuid) ||
	    strcmp(uuid, "6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3") ||
	    of_property_count_u32_elems(dcp, "memory-region") != 8 ||
	    !of_property_read_bool(dcp, "apple,j614s-inherited-mappings"))
		goto failed;
	/* Allocate the complete change set first. No partially admitted hardware
	 * graph is left behind on an allocation/property-update failure.
	 */
	of_changeset_init(&changes);
	ret = j614s_display_power_topology(dcp, &changes,
					 &properties[ARRAY_SIZE(devices)]);
	if (ret)
		goto destroy;
	for (unsigned int i = 0; i < ARRAY_SIZE(devices); i++) {
		struct property *property = kzalloc(sizeof(*property), GFP_KERNEL);

		properties[i] = property;
		if (!property) { ret = -ENOMEM; goto destroy; }
		property->name = kstrdup("status", GFP_KERNEL);
		property->value = kstrdup("okay", GFP_KERNEL);
		property->length = 5;
		if (!property->name || !property->value) { ret = -ENOMEM; goto destroy; }
		ret = of_changeset_update_property(&changes, nodes[i], property);
		if (ret)
			goto destroy;
	}
	ret = of_changeset_apply(&changes);
destroy:
	of_changeset_destroy(&changes);
	if (!ret) {
		pr_info("DCP001: J614s live display handoff admitted; retained power, manual native trial\n");
		for (unsigned int i = 0; i < ARRAY_SIZE(devices); i++)
			of_node_put(nodes[i]);
		return 0;
	}
failed:
	for (unsigned int i = 0; i < ARRAY_SIZE(devices); i++)
		of_node_put(nodes[i]);
	for (unsigned int i = 0; i < ARRAY_SIZE(properties); i++) {
		if (properties[i]) {
			kfree(properties[i]->name);
			kfree(properties[i]->value);
			kfree(properties[i]);
		}
	}
	pr_err("DCP001: refusing incomplete/unqualified J614s display handoff (%d)\n", ret);
	return ret ?: -ENODEV;
}
/* Before of_platform_default_populate_init(), after the flat DT is unflattened. */
core_initcall(j614s_display_boot);
