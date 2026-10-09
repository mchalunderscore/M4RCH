// SPDX-License-Identifier: GPL-2.0-only
/* Acquire/release a GFX reset reference only; never operate the reset line. */
#include <linux/atomic.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/kobject.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/reset.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/utsname.h>

#if !defined(CONFIG_OF_KOBJ) || !defined(CONFIG_OF_DYNAMIC) || \
    !defined(CONFIG_RESET_CONTROLLER)
#error This capability probe requires OF_KOBJ, OF_DYNAMIC and RESET_CONTROLLER
#endif

#define EXPECTED_RELEASE "7.1.13-m4rch-gpu-contract"
#define GFX_PATH "/soc/power-management@288e80000/power-controller@110"
#define GFX_PROVIDER "288e80000.power-management:power-controller@110"
#define PRIVATE_NAME "/m4rch-private-gfx-reset-capability"

static unsigned int run_gate;
module_param(run_gate, uint, 0400);
MODULE_PARM_DESC(run_gate, "0 refuses; 1 metadata and exclusive reference lookup only");

static atomic_t private_releases = ATOMIC_INIT(0);

/* This private, detached node never enters the live tree or sysfs. */
static void private_node_release(struct kobject *kobj)
{
	struct device_node *node = container_of(kobj, struct device_node, kobj);
	struct property *prop = node->properties;

	WARN_ON(node->parent || node->child || node->sibling || node->deadprops ||
		node->data || !of_node_check_flag(node, OF_DETACHED));
	while (prop) {
		struct property *next = prop->next;

		kfree(prop->name);
		kfree(prop->value);
		kfree(prop);
		prop = next;
	}
	kfree(node->full_name);
	kfree(node);
	atomic_inc(&private_releases);
}

static const struct kobj_type private_node_type = {
	.release = private_node_release,
};

static struct device_node *private_consumer_create(phandle actual_phandle)
{
	struct device_node *node;
	struct property *prop;
	__be32 reference = cpu_to_be32(actual_phandle);

	node = kzalloc(sizeof(*node), GFP_KERNEL);
	if (!node)
		return ERR_PTR(-ENOMEM);
	of_node_set_flag(node, OF_DYNAMIC);
	of_node_set_flag(node, OF_DETACHED);
	/* of_node_init uses unexported of_node_ktype; this node has its own owner. */
	kobject_init(&node->kobj, &private_node_type);
	fwnode_init(&node->fwnode, &of_fwnode_ops);
	node->full_name = kstrdup(PRIVATE_NAME, GFP_KERNEL);
	if (!node->full_name)
		goto fail;
	node->name = node->full_name + 1;
	prop = kzalloc(sizeof(*prop), GFP_KERNEL);
	if (!prop)
		goto fail;
	node->properties = prop;
	prop->name = kstrdup("resets", GFP_KERNEL);
	prop->value = kmemdup(&reference, sizeof(reference), GFP_KERNEL);
	prop->length = sizeof(reference);
	if (!prop->name || !prop->value)
		goto fail;
	return node;

fail:
	of_node_put(node);
	return ERR_PTR(-ENOMEM);
}

static int verify_provider(struct device_node *provider)
{
	struct platform_device *pdev;
	const char *label, *compatible;
	u32 reg[2], reset_cells, power_cells;
	int ret;

	if (of_property_count_u32_elems(provider, "reg") != 2 ||
	    of_property_read_u32_array(provider, "reg", reg, 2) ||
	    reg[0] != 0x110 || reg[1] != 4 ||
	    of_property_count_u32_elems(provider, "#reset-cells") != 1 ||
	    of_property_read_u32(provider, "#reset-cells", &reset_cells) ||
	    reset_cells != 0 ||
	    of_property_count_u32_elems(provider, "#power-domain-cells") != 1 ||
	    of_property_read_u32(provider, "#power-domain-cells", &power_cells) ||
	    power_cells != 0 ||
	    of_property_count_strings(provider, "label") != 1 ||
	    of_property_read_string(provider, "label", &label) || strcmp(label, "gfx") ||
	    of_property_count_strings(provider, "compatible") != 2 ||
	    of_property_read_string_index(provider, "compatible", 0, &compatible) ||
	    strcmp(compatible, "apple,t6041-pmgr-pwrstate") ||
	    of_property_read_string_index(provider, "compatible", 1, &compatible) ||
	    strcmp(compatible, "apple,t8103-pmgr-pwrstate"))
		return -EINVAL;

	pdev = of_find_device_by_node(provider);
	if (!pdev)
		return -ENODEV;
	device_lock(&pdev->dev);
	ret = !strcmp(dev_name(&pdev->dev), GFX_PROVIDER) &&
	      pdev->dev.driver &&
	      !strcmp(pdev->dev.driver->name, "apple-pmgr-pwrstate") ? 0 : -ENODEV;
	device_unlock(&pdev->dev);
	put_device(&pdev->dev);
	return ret;
}

static int __init gfx_reset_capability_init(void)
{
	struct device_node *provider = NULL, *resolved = NULL, *consumer = NULL;
	struct reset_control *reset;
	unsigned int released;
	int ret;

	if (run_gate != 1)
		return -EPERM;
	if (strcmp(utsname()->release, EXPECTED_RELEASE) ||
	    !of_machine_is_compatible("apple,t6040") ||
	    !of_machine_is_compatible("apple,j614s"))
		return -ENODEV;
	provider = of_find_node_by_path(GFX_PATH);
	if (!provider)
		return -ENODEV;
	ret = verify_provider(provider);
	if (ret)
		goto out;
	if (!provider->phandle || provider->phandle == U32_MAX) {
		pr_info("m4rch GFX reset capability: registered provider lacks a usable phandle; no lookup or reset operation\n");
		ret = -ENODATA;
		goto out;
	}
	resolved = of_find_node_by_phandle(provider->phandle);
	if (resolved != provider) {
		ret = -EUCLEAN;
		goto out;
	}
	consumer = private_consumer_create(provider->phandle);
	if (IS_ERR(consumer)) {
		ret = PTR_ERR(consumer);
		consumer = NULL;
		goto out;
	}
	/* EXCLUSIVE has no DEASSERTED flag: get/put invoke no line operations. */
	reset = __fwnode_reset_control_get(of_fwnode_handle(consumer), NULL, 0,
					 RESET_CONTROL_EXCLUSIVE);
	if (IS_ERR_OR_NULL(reset)) {
		ret = reset ? PTR_ERR(reset) : -ENODEV;
		pr_info("m4rch GFX reset capability: exclusive reference lookup failed=%d; no reset operation\n", ret);
		goto out;
	}
	reset_control_put(reset);
	ret = 0;
	pr_info("m4rch GFX reset capability: exclusive reference acquired and released for actual phandle=%u; no reset operation\n",
		provider->phandle);

out:
	of_node_put(consumer);
	of_node_put(resolved);
	of_node_put(provider);
	released = atomic_read(&private_releases);
	if (consumer && released != 1) {
		/* Preserve our callback text if a private node unexpectedly survived. */
		__module_get(THIS_MODULE);
		pr_err("m4rch GFX reset capability: private consumer retained unexpectedly; helper pinned; no reset operation\n");
		return 0;
	}
	if (consumer)
		pr_info("m4rch GFX reset capability: private consumer released=%u\n", released);
	return ret;
}

static void __exit gfx_reset_capability_exit(void)
{
	/* All successful lookups are released in init; there is no reset operation. */
}

module_init(gfx_reset_capability_init);
module_exit(gfx_reset_capability_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J614s GFX reset reference capability only; no reset operation");
