// SPDX-License-Identifier: GPL-2.0-only
/* A reviewed bounded boot-data RAM sample, read only; no GPU register/power/firmware calls. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/mm.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include "sample-contract.h"
static void *sample;
static struct kobject *directory;
static ssize_t sample_read(struct file *file, struct kobject *kobj,
 const struct bin_attribute *attr, char *buf, loff_t off, size_t count)
{
 if (off < 0) return -EINVAL;
 if (off >= SAMPLE_BYTES) return 0;
 count = min_t(size_t, count, SAMPLE_BYTES - off);
 memcpy(buf, (char *)sample + off, count);
 return count;
}
static struct bin_attribute raw = {
 .attr = { .name = "data", .mode = 0400 }, .read = sample_read, .size = SAMPLE_BYTES,
};
static int __init sample_init(void)
{
 void *mapping;
 int ret;
 if (!of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 /* Exact ranges from the qualified current boot; harness must match boot ID. */
 if (!((SAMPLE_BASE == 0x10001d44000ULL && (SAMPLE_BYTES == 0x4000 || SAMPLE_BYTES == 0x138000)) ||
       (SAMPLE_BASE == 0x105fffb8000ULL && SAMPLE_BYTES == 0x4000) ||
       (SAMPLE_BASE == 0x105fff78000ULL && SAMPLE_BYTES == 0x40000) ||
       (SAMPLE_BASE == 0x105fff74000ULL && SAMPLE_BYTES == 0x4000) ||
       (SAMPLE_BASE == 0x105fff70000ULL && SAMPLE_BYTES == 0x4000) ||
       (SAMPLE_BASE == 0x10000be4000ULL && SAMPLE_BYTES == 0x60000)))
  return -EINVAL;
 /* Never sample allocatable Linux RAM or a mixed System RAM range. */
 if (region_intersects(SAMPLE_BASE, SAMPLE_BYTES,
                      IORESOURCE_SYSTEM_RAM, IORES_DESC_NONE) != REGION_DISJOINT)
  return -ENODEV;
 sample = kvmalloc(SAMPLE_BYTES, GFP_KERNEL);
 if (!sample) return -ENOMEM;
 mapping = memremap(SAMPLE_BASE, SAMPLE_BYTES, MEMREMAP_WB);
 if (!mapping) { kvfree(sample); return -ENOMEM; }
 /* Firmware DATA is not assumed CPU coherent. This sampler never writes it;
  * no CPU writes to this reservation are performed by the sampler.
  * Discard cached CPU lines before observing firmware-written contents.
  * Keep table/TEXT sampler behavior unchanged in this isolated correction.
  */
 if (SAMPLE_BASE == 0x10001d44000ULL) {
  unsigned long address;
  for (address=(unsigned long)mapping;
       address<(unsigned long)mapping+SAMPLE_BYTES;address+=16)
   asm volatile("dc ivac, %0" :: "r"(address) : "memory");
  asm volatile("dsb sy" ::: "memory");
 }
 memcpy(sample, mapping, SAMPLE_BYTES);
 memunmap(mapping);
 directory = kobject_create_and_add("m4rch_gpu_data_sample", kernel_kobj);
 if (!directory) { kvfree(sample); return -ENOMEM; }
 ret = sysfs_create_bin_file(directory, &raw);
 if (ret) { kobject_put(directory); kvfree(sample); }
 return ret;
}
static void __exit sample_exit(void)
{
 sysfs_remove_bin_file(directory, &raw);
 kobject_put(directory);
 kvfree(sample);
}
module_init(sample_init);
module_exit(sample_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded read-only J614s boot GPU data RAM sample");
