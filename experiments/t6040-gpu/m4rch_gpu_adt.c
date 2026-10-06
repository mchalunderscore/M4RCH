// SPDX-License-Identifier: GPL-2.0-only
/* Read only the loader's reserved ADT RAM; no GPU register or firmware access. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/mm.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>

static void *adt;
static size_t adt_size;
static struct kobject *directory;

static ssize_t read_adt(struct file *file, struct kobject *kobj,
                       const struct bin_attribute *attr, char *buf,
                       loff_t offset, size_t count)
{
    if (offset < 0)
        return -EINVAL;
    if (offset >= adt_size)
        return 0;
    count = min_t(size_t, count, adt_size - offset);
    memcpy(buf, (const char *)adt + offset, count);
    return count;
}

static struct bin_attribute raw = {
    .attr = { .name = "adt", .mode = 0400 },
    .read = read_adt,
};

static int __init gpu_adt_init(void)
{
    struct device_node *node, *parent;
    struct resource resource;
    const char *label;
    int ret = -ENODEV;

    if (!of_machine_is_compatible("apple,j614s") ||
        !of_machine_is_compatible("apple,t6040"))
        return -ENODEV;
    for_each_compatible_node(node, NULL, "phram") {
        if (of_property_read_string(node, "label", &label) ||
            strcmp(label, "adt"))
            continue;
        parent = of_get_parent(node);
        if (!parent || strcmp(parent->name, "reserved-memory")) {
            of_node_put(parent);
            continue;
        }
        of_node_put(parent);
        ret = of_address_to_resource(node, 0, &resource);
        of_node_put(node);
        if (ret)
            return ret;
        adt_size = resource_size(&resource);
        if (!(resource.flags & IORESOURCE_MEM) || !resource.start ||
            adt_size < 8 || adt_size > 16 * 1024 * 1024)
            return -EINVAL;
        if (region_intersects(resource.start, adt_size,
                              IORESOURCE_SYSTEM_RAM, IORES_DESC_NONE)
            != REGION_INTERSECTS)
            return -ENODEV;
        adt = memremap(resource.start, adt_size, MEMREMAP_WB);
        if (!adt)
            return -ENOMEM;
        directory = kobject_create_and_add("m4rch_gpu_adt", kernel_kobj);
        if (!directory) {
            memunmap(adt);
            return -ENOMEM;
        }
        raw.size = adt_size;
        ret = sysfs_create_bin_file(directory, &raw);
        if (ret) {
            kobject_put(directory);
            memunmap(adt);
        }
        return ret;
    }
    return -ENODEV;
}

static void __exit gpu_adt_exit(void)
{
    sysfs_remove_bin_file(directory, &raw);
    kobject_put(directory);
    memunmap(adt);
}
module_init(gpu_adt_init);
module_exit(gpu_adt_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("m4rch loader-reserved ADT read-only capture");
