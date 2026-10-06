// SPDX-License-Identifier: GPL-2.0-only
/* Temporary resource metadata only: no mappings, power domains or GPU reads. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/init.h>
#include "resource-blob.h"
static int overlay_id;
static int __init resource_init(void)
{
    struct device_node *existing;
    int ret;
    if (!of_machine_is_compatible("apple,t6040") ||
        !of_machine_is_compatible("apple,j614s"))
        return -ENODEV;
    existing = of_find_node_by_path("/m4rch-gpu-tests");
    if (existing) { of_node_put(existing); return -EEXIST; }
    ret = of_overlay_fdt_apply(resource_dtb, resource_dtb_len, &overlay_id, NULL);
    if (ret) return ret;
    existing = of_find_node_by_path("/m4rch-gpu-tests");
    if (!existing) { of_overlay_remove(&overlay_id); return -ENODEV; }
    ret = of_platform_populate(existing, NULL, NULL, NULL);
    of_node_put(existing);
    if (ret) { of_overlay_remove(&overlay_id); return ret; }
    if (!ret)
        pr_info("m4rch GPU resource overlay installed; no power/reset/clock or ID-access properties\n");
    return ret;
}
static void __exit resource_exit(void)
{
    int ret = of_overlay_remove(&overlay_id);
    if (ret) pr_err("m4rch GPU resource overlay removal failed: %d\n", ret);
    else pr_info("m4rch GPU resource overlay removed\n");
}
module_init(resource_init);
module_exit(resource_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary J614s GPU resource metadata; no GPU access");
