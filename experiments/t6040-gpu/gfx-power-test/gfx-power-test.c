// SPDX-License-Identifier: GPL-2.0-only
/* Exercise the existing GFX genpd provider only. No SGX/reset/clock/firmware API. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
static struct platform_device *consumer;
static int __init gfx_test_init(void)
{
    struct of_phandle_args spec = {};
    u32 reg[2], cells;
    const char *label;
    int ret;
    if (!of_machine_is_compatible("apple,t6040") || !of_machine_is_compatible("apple,j614s")) return -ENODEV;
    spec.np = of_find_node_by_path("/soc/power-management@288e80000/power-controller@110");
    if (!spec.np) return -ENODEV;
    ret = of_property_read_u32_array(spec.np, "reg", reg, 2);
    if (ret || reg[0] != 0x110 || reg[1] != 4 ||
        of_property_read_u32(spec.np, "#power-domain-cells", &cells) || cells ||
        of_property_read_string(spec.np, "label", &label) || strcmp(label, "gfx")) {
        of_node_put(spec.np); return -EINVAL;
    }
    consumer = platform_device_register_simple("m4rch-gfx-power-test", -1, NULL, 0);
    if (IS_ERR(consumer)) { ret = PTR_ERR(consumer); of_node_put(spec.np); return ret; }
    ret = of_genpd_add_device(&spec, &consumer->dev);
    of_node_put(spec.np);
    if (ret) goto unregister;
    ret = pm_runtime_set_suspended(&consumer->dev);
    if (ret) goto detach;
    pm_runtime_enable(&consumer->dev);
    ret = pm_runtime_resume_and_get(&consumer->dev);
    if (ret < 0) { pm_runtime_disable(&consumer->dev); goto detach; }
    pr_info("m4rch GFX test: existing genpd runtime resume succeeded; no SGX access\n");
    return 0;
detach:
    pm_genpd_remove_device(&consumer->dev);
unregister:
    platform_device_unregister(consumer);
    return ret;
}
static void __exit gfx_test_exit(void)
{
    int ret = pm_runtime_put_sync_suspend(&consumer->dev);
    pr_info("m4rch GFX test: runtime suspend result=%d\n", ret);
    pm_runtime_disable(&consumer->dev);
    ret = pm_genpd_remove_device(&consumer->dev);
    if (ret) pr_err("m4rch GFX test: domain detach error=%d\n", ret);
    platform_device_unregister(consumer);
}
module_init(gfx_test_init);
module_exit(gfx_test_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Existing J614s GFX genpd runtime power test without GPU access");
