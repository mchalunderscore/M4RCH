// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Fixed-key diagnostic; no key enumeration or SMC write API. */
#include <linux/debugfs.h>
#include <linux/ktime.h>
#include <linux/mfd/macsmc.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/seq_file.h>

static struct device *smc_dev;
static struct apple_smc *smc;
static struct dentry *directory;
static const char keys[][5] = {
	"Te05", "Te0S", "Tp01", "Tp0Y", "Tp0b", "Tp0e",
	"F0Ac", "F1Ac", "F0Tg", "F1Tg", "F0Md", "F1Md",
};

static int keys_show(struct seq_file *seq, void *unused)
{
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(keys); i++) {
		const char *name = keys[i];
		smc_key key = (u32)(u8)name[0] << 24 | (u32)(u8)name[1] << 16 |
			      (u32)(u8)name[2] << 8 | (u8)name[3];
		struct apple_smc_key_info info = {};
		u8 data[4] = {};
		int status, read_status = -ENODATA;

		status = apple_smc_get_key_info(smc, key, &info);
		if (status >= 0 && info.size > 0 && info.size <= sizeof(data))
			read_status = apple_smc_read(smc, key, data, info.size);
		seq_printf(seq, "%llu %s info=%d size=%u type=%08x flags=%02x read=%d raw=",
			   ktime_get_boottime_ns(), name, status, info.size,
			   info.type_code, info.flags, read_status);
		if (read_status >= 0 && read_status == info.size)
			seq_printf(seq, "%*phN", info.size, data);
		seq_putc(seq, '\n');
	}
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(keys);

static int __init diagnostic_init(void)
{
	if (!of_machine_is_compatible("apple,j614s"))
		return -ENODEV;
	smc_dev = bus_find_device_by_name(&platform_bus_type, NULL, "50c600000.smc");
	if (!smc_dev)
		return -ENODEV;
	if (!smc_dev->driver || strcmp(smc_dev->driver->name, "macsmc")) {
		put_device(smc_dev);
		return -ENODEV;
	}
	smc = dev_get_drvdata(smc_dev);
	if (!smc) {
		put_device(smc_dev);
		return -ENODEV;
	}
	directory = debugfs_create_dir("m4rch-smc-readonly", NULL);
	if (IS_ERR(directory)) {
		put_device(smc_dev);
		return PTR_ERR(directory);
	}
	debugfs_create_file("keys", 0400, directory, NULL, &keys_fops);
	return 0;
}

static void __exit diagnostic_exit(void)
{
	debugfs_remove_recursive(directory);
	put_device(smc_dev);
}
module_init(diagnostic_init);
module_exit(diagnostic_exit);
MODULE_LICENSE("Dual MIT/GPL");
MODULE_DESCRIPTION("J614s fixed-key read-only SMC diagnostic");
